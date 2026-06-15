"""Health check endpoint for monitoring, load balancers, and uptime probes."""
import logging
import os
import datetime
from flask_restx import Namespace, Resource

logger = logging.getLogger(__name__)

health_ns = Namespace("health", description="System health checks")

_start_time = datetime.datetime.now(datetime.timezone.utc)


@health_ns.route("")
class HealthCheck(Resource):
    def get(self):
        """
        Returns system health status.

        Checks:
          - Database connectivity
          - Redis availability
          - ML model readiness
          - Version, uptime, environment
        """
        uptime_delta = datetime.datetime.now(datetime.timezone.utc) - _start_time
        status = {
            "status": "healthy",
            "version": os.environ.get("APP_VERSION", "2.0.0"),
            "environment": os.environ.get("FLASK_ENV", "development"),
            "uptime_seconds": round(uptime_delta.total_seconds(), 1),
            "checks": {},
        }

        # 1. Database check
        try:
            from app.extensions import get_db
            db = get_db()
            with db.get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            status["checks"]["database"] = {
                "status": "up",
                "type": "postgresql" if getattr(db, 'is_pg', False) else "sqlite",
            }
        except Exception as e:
            logger.error("Health check — database failed: %s", e)
            status["checks"]["database"] = {"status": "down", "error": str(e)}
            status["status"] = "degraded"

        # 2. Redis check
        try:
            from flask import current_app
            rc = current_app.extensions.get("redis_client")
            if rc:
                rc.ping()
                status["checks"]["redis"] = {"status": "up"}
            else:
                status["checks"]["redis"] = {"status": "not_configured"}
        except Exception as e:
            logger.error("Health check — redis failed: %s", e)
            status["checks"]["redis"] = {"status": "down", "error": str(e)}
            status["status"] = "degraded"

        # 3. ML engines check
        ml_engines_loaded = 0
        ml_engines_total = 11
        engine_modules = [
            ("cognitive_engine", "app.models.cognitive_engine"),
            ("duress_detector", "app.models.duress_detector"),
            ("liveness_detector", "app.models.liveness_detector"),
            ("invisible_challenge", "app.models.invisible_challenge_engine"),
            ("device_intelligence", "app.models.device_intelligence"),
            ("composite_signal", "app.models.composite_signal_engine"),
            ("gan_adversarial", "app.models.gan_adversarial"),
            ("passive_enrollment", "app.models.passive_enrollment"),
            ("adwin_drift", "app.models.adwin_drift"),
            ("transaction_baseline", "app.models.transaction_baseline"),
            ("feature_selector", "app.models.per_user_feature_selector"),
            ("bayesian_fusion", "app.models.bayesian_fusion"),
            ("transformer_encoder", "app.models.transformer_model"),
            ("siamese_network", "app.models.siamese_network"),
            ("simclr", "app.models.simclr"),
        ]
        ml_engines_total = len(engine_modules)
        for name, module in engine_modules:
            try:
                __import__(module)
                ml_engines_loaded += 1
            except ImportError:
                pass

        status["checks"]["ml_models"] = {
            "status": "available" if ml_engines_loaded > 0 else "unavailable",
            "engines_loaded": ml_engines_loaded,
            "engines_total": ml_engines_total,
            "fusion_mode": "bayesian" if ml_engines_loaded >= 12 else "weighted_average",
        }

        # 4. Celery worker availability
        try:
            from app.tasks import celery_app
            insp = celery_app.control.inspect(timeout=0.5)
            ping = insp.ping()
            if ping:
                status["checks"]["celery"] = {"status": "up", "workers": len(ping)}
            else:
                status["checks"]["celery"] = {"status": "degraded", "note": "No workers responding"}
        except Exception:
            status["checks"]["celery"] = {"status": "unavailable", "note": "Broker not reachable"}

        http_code = 200 if status["status"] == "healthy" else 503
        return status, http_code


@health_ns.route("/ready")
class ReadinessCheck(Resource):
    def get(self):
        """Kubernetes-style readiness probe. Returns 200 only when DB is connected."""
        try:
            from app.extensions import get_db
            db = get_db()
            with db.get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"ready": True}, 200
        except Exception as e:
            return {"ready": False, "error": str(e)}, 503


@health_ns.route("/info")
class SystemInfo(Resource):
    def get(self):
        """System metadata for monitoring dashboards and CI/CD pipelines."""
        import sys
        import platform
        uptime_delta = datetime.datetime.now(datetime.timezone.utc) - _start_time
        return {
            "service": "behavioral-auth-api",
            "version": os.environ.get("APP_VERSION", "3.0.0"),
            "python": sys.version,
            "platform": platform.platform(),
            "uptime_seconds": round(uptime_delta.total_seconds(), 1),
            "architecture": {
                "pattern": "Service-Repository",
                "fusion": "Bayesian Belief Update",
                "async": "Celery + Redis",
                "ml_engines": 15,
                "transformer": "4-head Self-Attention (d=64, L=2)",
                "enrollment": "Progressive 3-phase (bootstrap→building→mature)",
            },
            "features": {
                "bayesian_fusion": True,
                "celery_async": True,
                "repository_pattern": True,
                "transformer_encoder": True,
                "duress_detection": True,
                "gan_adversarial": True,
                "adwin_drift": True,
                "simclr_contrastive": True,
                "siamese_verification": True,
                "hmac_transaction_signing": True,
                "hash_chain_audit": True,
            },
        }, 200


