"""
API monitoring and metrics collection for Behavior-Based Authentication API.

This module provides comprehensive metrics collection, monitoring, and analytics
for API performance, usage, and error tracking.
"""

import time
import threading
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

from flask import request, g, current_app


class MetricType(Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"  # Incremental counter (requests, errors)
    GAUGE = "gauge"  # Current value (active connections, memory)
    HISTOGRAM = "histogram"  # Distribution (response times, payload sizes)
    TIMER = "timer"  # Timing measurements
    RATE = "rate"  # Rate per second/minute


@dataclass
class Metric:
    """Base metric class."""

    name: str
    type: MetricType
    value: Any
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIMetric:
    """API-specific metric data."""

    endpoint: str
    method: str
    status_code: int
    response_time: float  # in milliseconds
    request_size: int  # in bytes
    response_size: int  # in bytes
    user_id: Optional[int] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    additional_tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self, retention_period: int = 3600):  # 1 hour retention
        self.metrics: List[Metric] = []
        self.api_metrics: List[APIMetric] = []
        self.lock = threading.Lock()
        self.retention_period = retention_period
        self._last_cleanup = datetime.utcnow()

        # Aggregated counters
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.timers = defaultdict(list)

        # Rate limiting metrics
        self.rate_limits = defaultdict(lambda: defaultdict(int))

        # Error tracking
        self.errors_by_endpoint = defaultdict(lambda: defaultdict(int))
        self.errors_by_type = defaultdict(int)

    def record_metric(self, metric: Metric):
        """Record a metric."""
        with self.lock:
            metric.timestamp = datetime.utcnow()
            self.metrics.append(metric)

            # Update aggregated metrics based on type
            if metric.type == MetricType.COUNTER:
                key = self._get_metric_key(metric.name, metric.tags)
                self.counters[key] += metric.value
            elif metric.type == MetricType.GAUGE:
                key = self._get_metric_key(metric.name, metric.tags)
                self.gauges[key] = metric.value
            elif metric.type == MetricType.HISTOGRAM or metric.type == MetricType.TIMER:
                key = self._get_metric_key(metric.name, metric.tags)
                self.timers[key].append(metric.value)

            # Auto-cleanup old metrics
            self._cleanup_old_metrics()

    def record_api_call(self, metric: APIMetric):
        """Record an API call metric."""
        with self.lock:
            self.api_metrics.append(metric)

            # Track errors
            if metric.status_code >= 400:
                endpoint_key = f"{metric.method} {metric.endpoint}"
                self.errors_by_endpoint[endpoint_key][metric.status_code] += 1

                if metric.error_message:
                    error_type = (
                        metric.error_message.split(":")[0]
                        if ":" in metric.error_message
                        else "unknown"
                    )
                    self.errors_by_type[error_type] += 1

            # Auto-cleanup old metrics
            self._cleanup_old_metrics()

    def _get_metric_key(self, name: str, tags: Dict[str, str]) -> str:
        """Create a unique key for a metric with tags."""
        if not tags:
            return name

        sorted_tags = sorted(tags.items())
        tag_string = ":".join(f"{k}={v}" for k, v in sorted_tags)
        return f"{name}:{tag_string}"

    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        now = datetime.utcnow()
        if (now - self._last_cleanup).seconds < 300:  # Cleanup every 5 minutes
            return

        cutoff = now - timedelta(seconds=self.retention_period)

        with self.lock:
            # Cleanup metrics
            self.metrics = [m for m in self.metrics if m.timestamp > cutoff]
            self.api_metrics = [m for m in self.api_metrics if m.timestamp > cutoff]

            # Cleanup aggregated data (keep all for now, could implement sliding window)
            self._last_cleanup = now

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        with self.lock:
            now = datetime.utcnow()
            one_minute_ago = now - timedelta(minutes=1)
            five_minutes_ago = now - timedelta(minutes=5)
            one_hour_ago = now - timedelta(hours=1)

            # Filter recent metrics
            recent_metrics = [
                m for m in self.api_metrics if m.timestamp > one_minute_ago
            ]
            recent_5min = [
                m for m in self.api_metrics if m.timestamp > five_minutes_ago
            ]

            # Calculate request rates
            requests_1min = len(recent_metrics)
            requests_5min = len(recent_5min)
            requests_1min_rate = requests_1min / 60  # per second
            requests_5min_rate = requests_5min / 300  # per second

            # Calculate error rates
            errors_1min = sum(1 for m in recent_metrics if m.status_code >= 400)
            errors_5min = sum(1 for m in recent_5min if m.status_code >= 400)
            error_rate_1min = (
                (errors_1min / requests_1min * 100) if requests_1min > 0 else 0
            )
            error_rate_5min = (
                (errors_5min / requests_5min * 100) if requests_5min > 0 else 0
            )

            # Calculate response time percentiles
            response_times = [m.response_time for m in recent_5min]
            if response_times:
                avg_response_time = statistics.mean(response_times)
                p95_response_time = statistics.quantiles(response_times, n=20)[
                    18
                ]  # 95th percentile
                p99_response_time = statistics.quantiles(response_times, n=100)[
                    98
                ]  # 99th percentile
            else:
                avg_response_time = p95_response_time = p99_response_time = 0

            # Get top endpoints
            endpoint_counts = defaultdict(int)
            for metric in recent_5min:
                endpoint_counts[f"{metric.method} {metric.endpoint}"] += 1

            top_endpoints = sorted(
                endpoint_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # Get error breakdown
            error_breakdown = {}
            for endpoint, error_counts in self.errors_by_endpoint.items():
                total_errors = sum(error_counts.values())
                if total_errors > 0:
                    error_breakdown[endpoint] = dict(error_counts)

            return {
                "timestamp": now.isoformat(),
                "requests": {
                    "total_last_hour": len(
                        [m for m in self.api_metrics if m.timestamp > one_hour_ago]
                    ),
                    "rate_1min": round(requests_1min_rate, 2),
                    "rate_5min": round(requests_5min_rate, 2),
                    "count_1min": requests_1min,
                    "count_5min": requests_5min,
                },
                "errors": {
                    "count_1min": errors_1min,
                    "count_5min": errors_5min,
                    "rate_1min": round(error_rate_1min, 2),
                    "rate_5min": round(error_rate_5min, 2),
                    "by_endpoint": dict(error_breakdown),
                    "by_type": dict(self.errors_by_type),
                },
                "performance": {
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "p95_response_time_ms": round(p95_response_time, 2)
                    if response_times
                    else 0,
                    "p99_response_time_ms": round(p99_response_time, 2)
                    if response_times
                    else 0,
                    "min_response_time_ms": min(response_times)
                    if response_times
                    else 0,
                    "max_response_time_ms": max(response_times)
                    if response_times
                    else 0,
                },
                "top_endpoints": [
                    {"endpoint": endpoint, "count": count}
                    for endpoint, count in top_endpoints
                ],
                "aggregated_metrics": {
                    "counters": dict(self.counters),
                    "gauges": dict(self.gauges),
                    "timer_counts": {k: len(v) for k, v in self.timers.items()},
                },
            }

    def get_endpoint_stats(self, endpoint: str, method: str = None) -> Dict[str, Any]:
        """Get statistics for a specific endpoint."""
        with self.lock:
            filtered = [
                m
                for m in self.api_metrics
                if m.endpoint == endpoint and (method is None or m.method == method)
            ]

            if not filtered:
                return {"endpoint": endpoint, "method": method, "total_calls": 0}

            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)
            recent = [m for m in filtered if m.timestamp > one_hour_ago]

            response_times = [m.response_time for m in recent]
            status_codes = defaultdict(int)
            for m in recent:
                status_codes[m.status_code] += 1

            return {
                "endpoint": endpoint,
                "method": method or "ALL",
                "total_calls": len(filtered),
                "calls_last_hour": len(recent),
                "response_time_ms": {
                    "avg": round(statistics.mean(response_times), 2)
                    if response_times
                    else 0,
                    "min": min(response_times) if response_times else 0,
                    "max": max(response_times) if response_times else 0,
                    "p95": round(statistics.quantiles(response_times, n=20)[18], 2)
                    if len(response_times) >= 20
                    else 0,
                    "p99": round(statistics.quantiles(response_times, n=100)[98], 2)
                    if len(response_times) >= 100
                    else 0,
                },
                "status_codes": dict(status_codes),
                "error_rate": (
                    sum(1 for m in recent if m.status_code >= 400) / len(recent) * 100
                    if recent
                    else 0
                ),
                "throughput_bytes_per_sec": (
                    sum(m.request_size + m.response_size for m in recent) / 3600
                    if recent
                    else 0
                ),
            }

    def reset(self):
        """Reset all metrics (for testing)."""
        with self.lock:
            self.metrics.clear()
            self.api_metrics.clear()
            self.counters.clear()
            self.gauges.clear()
            self.timers.clear()
            self.errors_by_endpoint.clear()
            self.errors_by_type.clear()


# Global metrics collector instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


class MetricsMiddleware:
    """Flask middleware for collecting API metrics."""

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize metrics middleware with Flask app."""
        self.collector = get_metrics_collector()

        @app.before_request
        def start_timer():
            g.start_time = time.time()
            g.request_id = hashlib.md5(
                f"{time.time()}{request.remote_addr}{request.path}".encode()
            ).hexdigest()[:16]

        @app.after_request
        def record_metrics(response):
            # Skip metrics for certain paths
            if request.path in ["/metrics", "/healthz", "/ready"]:
                return response

            # Calculate response time
            response_time = 0
            if hasattr(g, "start_time"):
                response_time = (time.time() - g.start_time) * 1000  # Convert to ms

            # Get request size
            request_size = 0
            if request.content_length:
                request_size = request.content_length
            elif request.data:
                request_size = len(request.data)

            # Get response size
            response_size = 0
            if response.content_length:
                response_size = response.content_length
            elif response.get_data():
                response_size = len(response.get_data())

            # Record API metric
            metric = APIMetric(
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                request_size=request_size,
                response_size=response_size,
                user_id=getattr(g, "user_id", None),
                client_ip=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                error_message=None,
            )

            self.collector.record_api_call(metric)

            # Add metrics headers
            response.headers["X-Request-ID"] = getattr(g, "request_id", "")
            response.headers["X-Response-Time"] = f"{response_time:.2f}ms"

            return response

        @app.errorhandler(Exception)
        def record_error_metrics(error):
            """Record error metrics for unhandled exceptions."""
            if hasattr(g, "start_time"):
                response_time = (time.time() - g.start_time) * 1000

                metric = APIMetric(
                    endpoint=request.path,
                    method=request.method,
                    status_code=500,
                    response_time=response_time,
                    request_size=request.content_length or 0,
                    response_size=0,
                    user_id=getattr(g, "user_id", None),
                    client_ip=request.remote_addr,
                    user_agent=request.user_agent.string
                    if request.user_agent
                    else None,
                    error_message=str(error),
                )

                self.collector.record_api_call(metric)

            # Re-raise the error for Flask's default error handling
            raise error


def record_counter(name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
    """Record a counter metric."""
    collector = get_metrics_collector()
    metric = Metric(
        name=name,
        type=MetricType.COUNTER,
        value=value,
        timestamp=datetime.utcnow(),
        tags=tags or {},
    )
    collector.record_metric(metric)


def record_gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Record a gauge metric."""
    collector = get_metrics_collector()
    metric = Metric(
        name=name,
        type=MetricType.GAUGE,
        value=value,
        timestamp=datetime.utcnow(),
        tags=tags or {},
    )
    collector.record_metric(metric)


def record_timer(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Record a timer metric."""
    collector = get_metrics_collector()
    metric = Metric(
        name=name,
        type=MetricType.TIMER,
        value=value,
        timestamp=datetime.utcnow(),
        tags=tags or {},
    )
    collector.record_metric(metric)


def record_histogram(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Record a histogram metric."""
    collector = get_metrics_collector()
    metric = Metric(
        name=name,
        type=MetricType.HISTOGRAM,
        value=value,
        timestamp=datetime.utcnow(),
        tags=tags or {},
    )
    collector.record_metric(metric)


# Flask route for metrics endpoint
def setup_metrics_endpoint(app):
    """Setup metrics endpoint for Prometheus or JSON output."""

    @app.route("/metrics")
    def metrics_endpoint():
        """Endpoint to expose metrics in JSON format."""
        collector = get_metrics_collector()
        summary = collector.get_summary()
        return json.dumps(summary, indent=2), 200, {"Content-Type": "application/json"}

    @app.route("/metrics/endpoint/<path:endpoint>")
    def endpoint_metrics(endpoint):
        """Get metrics for a specific endpoint."""
        method = request.args.get("method")
        collector = get_metrics_collector()
        stats = collector.get_endpoint_stats(endpoint, method)
        return json.dumps(stats, indent=2), 200, {"Content-Type": "application/json"}

    @app.route("/metrics/reset", methods=["POST"])
    def reset_metrics():
        """Reset all metrics (requires authentication in production)."""
        # In production, this should be protected
        if app.config.get("ENV") == "production":
            return json.dumps({"error": "Not allowed in production"}), 403
