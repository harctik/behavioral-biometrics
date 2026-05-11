"""Flask application factory.

Thin orchestrator that configures extensions, registers API namespaces from
the ``app.api`` package, and mounts template-driven UI routes.

Production middleware stack:
  1. Request correlation (``X-Request-ID``)
  2. Structured request/response logging
  3. CSRF enforcement
  4. Security headers (HSTS, CSP, X-Frame-Options …)
  5. CORS (configurable via ``CORS_ORIGINS``)
"""

import time
import uuid
from datetime import timedelta
from flask import Flask, request, g, session
from flask_jwt_extended import JWTManager
from flask_restx import Api
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import logging
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Settings
from .config import Settings
_settings = Settings()

if _settings.SQLALCHEMY_DATABASE_URI and _settings.SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
    from .database_pg import get_engine
else:
    from .database import get_engine
from .logging_config import setup_logging, get_logger
from .redis_store import get_redis_client
from .error_handling import make_error_response, ErrorHandler

logger = get_logger(__name__)

DEFAULT_RATE_LIMIT = "5 per minute"


def create_app(env: str = "development"):
    """Application factory.

    Args:
        env: ``development``, ``production`` or ``testing``.
    """
    settings = Settings()
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    setup_logging(app=app)

    app.config.update(
        {
            "SECRET_KEY": settings.SECRET_KEY,
            "DEBUG": settings.DEBUG,
            "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
            # Flask-JWT-Extended requires a timedelta, not raw seconds.
            "JWT_ACCESS_TOKEN_EXPIRES": timedelta(
                minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES
            ),
            "JWT_TOKEN_LOCATION": ["headers", "cookies"],
            "JWT_COOKIE_SECURE": not settings.DEBUG,
            "JWT_COOKIE_CSRF_PROTECT": True,
            "JWT_COOKIE_SAMESITE": "Strict",
            "DATABASE_PATH": settings.DATABASE_PATH,
            "SQLALCHEMY_DATABASE_URI": settings.SQLALCHEMY_DATABASE_URI or f"sqlite:///{settings.DATABASE_PATH}",
            "CSRF_ENABLED": settings.CSRF_ENABLED,
            "CSRF_HEADER_NAME": settings.CSRF_HEADER_NAME,
            "RISK_HIGH_THRESHOLD": settings.RISK_HIGH_THRESHOLD,
            "RISK_MEDIUM_THRESHOLD": settings.RISK_MEDIUM_THRESHOLD,
            "STEP_UP_RISK_SCORE_THRESHOLD": settings.STEP_UP_RISK_SCORE_THRESHOLD,
            "HSTS_MAX_AGE": settings.HSTS_MAX_AGE,
            "REFERRER_POLICY": settings.REFERRER_POLICY,
            "CSP_POLICY": settings.CSP_POLICY,
            "TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES": settings.TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES,
            "TRUST_TIMELINE_MAX_WINDOW_MINUTES": settings.TRUST_TIMELINE_MAX_WINDOW_MINUTES,
            "TRANSACTION_SIGNING_REQUIRED": settings.TRANSACTION_SIGNING_REQUIRED,
            "TXN_SIGNING_KEY": settings.TXN_SIGNING_KEY,
            "TXN_SIGNING_PREVIOUS_KEY": settings.TXN_SIGNING_PREVIOUS_KEY,
            "JWT_PREVIOUS_SECRET_KEY": settings.JWT_PREVIOUS_SECRET_KEY,
            "ADMIN_USERNAMES": settings.ADMIN_USERNAMES,
            "ANALYST_USERNAMES": settings.ANALYST_USERNAMES,
            "REDIS_URL": settings.REDIS_URL,
            "SESSION_CACHE_TTL_SECONDS": settings.SESSION_CACHE_TTL_SECONDS,
            "CORS_ORIGINS": settings.CORS_ORIGINS,
            "SESSION_CONTEXT_STRICT": settings.SESSION_CONTEXT_STRICT,
            "BACKUP_FERNET": settings.BACKUP_FERNET,
            # Mail settings
            "MAIL_SERVER": settings.MAIL_SERVER,
            "MAIL_PORT": settings.MAIL_PORT,
            "MAIL_USE_TLS": settings.MAIL_USE_TLS,
            "MAIL_USERNAME": settings.MAIL_USERNAME,
            "MAIL_PASSWORD": settings.MAIL_PASSWORD,
            "MAIL_DEFAULT_SENDER": settings.MAIL_DEFAULT_SENDER,
            "MAIL_BACKEND": settings.MAIL_BACKEND,
            "AWS_REGION": settings.AWS_REGION,
            "RESEND_API_KEY": settings.RESEND_API_KEY,
            "RESET_URL_BASE": settings.RESET_URL_BASE,
        }
    )

    if env == "testing":
        app.config["CSRF_ENABLED"] = False
        app.config["DATABASE_PATH"] = ":memory:"
        app.config["TESTING"] = True

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt = JWTManager(app)

    @jwt.decode_key_loader
    def load_signing_key(jwt_header, jwt_payload):
        kid = (jwt_header or {}).get("kid", "current")
        if kid == "previous" and app.config.get("JWT_PREVIOUS_SECRET_KEY"):
            return app.config["JWT_PREVIOUS_SECRET_KEY"]
        return app.config["JWT_SECRET_KEY"]

    # JWT blocklist — check Redis for revoked tokens on every request
    @jwt.token_in_blocklist_loader
    def _check_jwt_blocklist(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        if not jti:
            return False
        rc = app.extensions.get("redis_client")
        if rc:
            try:
                return rc.exists(f"jwt_blocklist:{jti}") > 0
            except Exception:
                logger.warning("Redis unavailable for JWT blocklist check")
        return False

    # ── Rate Limiter ────────────────────────────────────────────────────────
    from app.extensions import limiter

    limiter._default_limits = [DEFAULT_RATE_LIMIT]
    # Prefer Redis for rate limiting when available
    if settings.RATELIMIT_STORAGE_URI and settings.RATELIMIT_STORAGE_URI != "memory://":
        storage_uri = settings.RATELIMIT_STORAGE_URI
    elif settings.REDIS_URL:
        storage_uri = settings.REDIS_URL
    else:
        storage_uri = "memory://"
        if not settings.DEBUG:
            logger.warning(
                "Rate limiter using in-memory storage in non-DEBUG mode. "
                "In multi-worker deployments, rate limits are per-process. "
                "Set REDIS_URL or RATELIMIT_STORAGE_URI for shared counters."
            )
    limiter._storage_uri = storage_uri
    limiter.init_app(app)

    # ── Flask-RESTX API (OpenAPI) ───────────────────────────────────────────
    api = Api(
        app,
        version="1.0",
        title="Behavior-Based Authentication API",
        description="API for continuous authentication and behavioral biometrics",
        doc="/api/v1/",
        prefix="/api/v1",
        default="Authentication",
        default_label="Authentication endpoints",
    )

    from app.api import (
        auth_ns,
        session_ns,
        behavioral_ns,
        transaction_ns,
        admin_ns,
        compliance_ns,
        banking_ns,
    )

    api.add_namespace(auth_ns, path="")
    api.add_namespace(session_ns, path="/session")
    api.add_namespace(transaction_ns, path="/transaction")
    api.add_namespace(behavioral_ns, path="/behavioral")
    api.add_namespace(admin_ns, path="/admin")
    api.add_namespace(compliance_ns, path="/compliance")
    api.add_namespace(banking_ns, path="/banking")

    # ── ErrorHandler middleware (correlation IDs, structured exceptions) ─────
    ErrorHandler(app, debug=app.debug)

    # ── IP Allowlist / Denylist Enforcement ────────────────────────────────
    _ip_allowlist = {
        ip.strip() for ip in (settings.IP_ALLOWLIST or "").split(",") if ip.strip()
    }
    _ip_denylist = {
        ip.strip() for ip in (settings.IP_DENYLIST or "").split(",") if ip.strip()
    }

    @app.before_request
    def _enforce_ip_acl():
        """Block denied IPs; restrict to allowlisted IPs when configured."""
        client_ip = request.remote_addr or ""
        if _ip_denylist and client_ip in _ip_denylist:
            logger.warning("Blocked denied IP: %s on %s", client_ip, request.path)
            return make_error_response("IP_DENIED", "Access denied", status=403)
        if _ip_allowlist and client_ip not in _ip_allowlist:
            logger.warning(
                "Blocked non-allowlisted IP: %s on %s", client_ip, request.path
            )
            return make_error_response("IP_NOT_ALLOWED", "Access denied", status=403)

    # ── HTTPS Enforcement ───────────────────────────────────────────────────
    @app.before_request
    def _enforce_https():
        """Force HTTPS in production environments."""
        if not app.debug and not app.testing and not request.is_secure:
            if request.headers.get('X-Forwarded-Proto', 'http') == 'http':
                from flask import redirect
                url = request.url.replace('http://', 'https://', 1)
                return redirect(url, code=301)

    # ── Request correlation & structured logging ────────────────────────────
    @app.before_request
    def _start_request_timer():
        g.request_start = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def _log_request(response):
        duration_ms = (
            time.perf_counter() - getattr(g, "request_start", time.perf_counter())
        ) * 1000
        request_id = getattr(g, "request_id", "-")
        if not request.path.startswith("/static"):
            logger.info(
                "request_id=%s method=%s path=%s status=%d duration_ms=%.1f ip=%s ua=%s",
                request_id,
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                request.remote_addr,
                request.headers.get("User-Agent", "-")[:80],
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
        return response

    # ── CORS ────────────────────────────────────────────────────────────────
    @app.after_request
    def _add_cors_headers(response):
        origin = request.headers.get("Origin", "")
        allowed = app.config.get("CORS_ORIGINS", "")

        # Prevent wildcard CORS in production
        if allowed == "*" and not app.debug:
            logger.warning(
                "CORS_ORIGINS=* is insecure in production. "
                "Set explicit origins in CORS_ORIGINS."
            )
            # In production, do NOT reflect wildcard — require explicit config
            return response

        if allowed == "*":
            # Debug/development only
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
        else:
            # Parse comma-separated allowlist
            allowed_set = {
                o.strip()
                for o in (
                    allowed if isinstance(allowed, str) else ",".join(allowed)
                ).split(",")
                if o.strip()
            }
            if origin in allowed_set:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers.add("Vary", "Origin")
            else:
                # Origin not allowed — don't set ACAO header
                return response

        response.headers[
            "Access-Control-Allow-Methods"
        ] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers[
            "Access-Control-Allow-Headers"
        ] = "Content-Type, Authorization, X-CSRF-Token, X-Request-ID, X-Device-Id"
        response.headers[
            "Access-Control-Expose-Headers"
        ] = "X-Request-ID, X-Response-Time"
        response.headers["Access-Control-Max-Age"] = "600"
        return response

    # ── Security Headers ────────────────────────────────────────────────────
    @app.after_request
    def _add_security_headers(response):
        csp_policy = app.config.get("CSP_POLICY", "default-src 'self'")
        response.headers["Content-Security-Policy"] = csp_policy
        if not app.debug:
            response.headers[
                "Strict-Transport-Security"
            ] = f"max-age={app.config.get('HSTS_MAX_AGE', 31536000)}; includeSubDomains; preload"
        response.headers["Referrer-Policy"] = app.config.get(
            "REFERRER_POLICY", "no-referrer"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=(self)"
        )
        return response

    # ── CSRF Enforcement (per-session tokens) ───────────────────────────────
    csrf_serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="csrf-token")

    @app.before_request
    def _enforce_csrf():
        if not app.config.get("CSRF_ENABLED", True):
            return None
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return None
        if not request.path.startswith("/api/"):
            return None

        # Exempt auth routes from CSRF (login/register/reset don't have a token yet)
        # Also exempt JWT-protected transaction/session endpoints that are called
        # from the SPA (they already require valid JWT bearer tokens for auth)
        exempt_routes = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/password-reset/confirm",
            "/api/v1/auth/csrf-token",
            "/api/v1/auth/mfa/verify",
            "/api/v1/auth/send-otp-email",
        }
        exempt_prefixes = (
            "/api/v1/transaction/",
            "/api/v1/session/",
            "/api/v1/behavioral/",
        )
        logger.debug("CSRF check: path=%s, exempt=%s", request.path, request.path in exempt_routes)
        if request.path in exempt_routes:
            return None
        if any(request.path.startswith(p) for p in exempt_prefixes):
            return None

        header_name = app.config.get("CSRF_HEADER_NAME", "X-CSRF-Token")
        provided = request.headers.get(header_name)
        if not provided:
            logger.warning("CSRF check failed: Missing token for path %s", request.path)
            return make_error_response(
                "CSRF_TOKEN_INVALID", "Missing CSRF token", status=403
            )

        try:
            # Validate token signature + timestamp (max_age=8h)
            csrf_serializer.loads(provided, max_age=28800)
        except (BadSignature, SignatureExpired):
            return make_error_response(
                "CSRF_TOKEN_INVALID", "Invalid or expired CSRF token", status=403
            )
        return None

    # ── Database & Redis ────────────────────────────────────────────────────
    if _settings.SQLALCHEMY_DATABASE_URI and _settings.SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        try:
            db = get_engine(app.config["SQLALCHEMY_DATABASE_URI"])
        except Exception as pg_err:
            logger.error(
                "PostgreSQL connection failed (%s). Falling back to SQLite at %s",
                pg_err, app.config["DATABASE_PATH"]
            )
            from app.database import get_engine as get_sqlite_engine
            db = get_sqlite_engine(app.config["DATABASE_PATH"])
    else:
        db = get_engine(app.config["DATABASE_PATH"])
    redis_client = (
        get_redis_client(app.config.get("REDIS_URL") or "")
        if app.config.get("REDIS_URL")
        else None
    )

    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.extensions["db"] = db
    app.extensions["redis_client"] = redis_client

    # ── Mail Service ───────────────────────────────────────────────────────
    from .mail import MailService

    mail = MailService()
    mail.init_app(app)

    # ── Error Handlers ──────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(error):
        return make_error_response("NOT_FOUND", "Resource not found", status=404)

    @app.errorhandler(500)
    def internal_server_error(error):
        logger.exception("Internal server error")
        return make_error_response(
            "INTERNAL_ERROR", "Internal server error", status=500
        )

    @app.context_processor
    def inject_csrf():
        """Inject a per-request, signed CSRF token into templates."""
        token = csrf_serializer.dumps({"rid": getattr(g, "request_id", "")})
        return dict(csrf_token=token)

    # ── Note: All UI is served by the Next.js frontend. ──────────────────
    # No Flask template routes are registered.
    # The Next.js proxy rewrites /api/* → Flask backend.

    # ── Health / Readiness ──────────────────────────────────────────────────
    @app.route("/healthz")
    @limiter.limit("30 per minute")
    def healthz():
        return "OK", 200

    @app.route("/ready")
    @limiter.limit("30 per minute")
    def ready():
        checks = {}
        try:
            with db.get_connection() as conn:
                conn.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        if redis_client:
            try:
                redis_client.ping()
                checks["redis"] = "ok"
            except Exception:
                checks["redis"] = "error"
        else:
            checks["redis"] = "not_configured"

        all_ok = all(v == "ok" for v in checks.values() if v != "not_configured")
        status = 200 if all_ok else 500
        return {"status": "ready" if all_ok else "degraded", "checks": checks}, status

    # ── Production Readiness Audit (runs once at startup) ──────────────────
    if env != "testing":
        _production_readiness_check(app, settings, redis_client)

    return app


def _production_readiness_check(app, settings, redis_client):
    """Emit startup warnings for common production misconfigurations."""
    warnings_list = []

    if settings.SECRET_KEY == "dev-secret-key-change-in-production":
        warnings_list.append(
            "SECRET_KEY is set to the default dev value. "
            "Generate a secure random key for production."
        )

    if settings.JWT_SECRET_KEY == "dev-jwt-secret-key-change-in-production":
        warnings_list.append(
            "JWT_SECRET_KEY is set to the default dev value. "
            "Generate a secure random key for production."
        )

    if not settings.REDIS_URL:
        warnings_list.append(
            "REDIS_URL is not set. Rate limiting, JWT blocklist, and session "
            "caching will use in-memory storage — NOT safe for multi-worker "
            "deployments. Set REDIS_URL to a Redis instance."
        )

    if not settings.BACKUP_FERNET or settings.BACKUP_FERNET == "":
        warnings_list.append(
            "BACKUP_FERNET is not set. An ephemeral key will be generated, "
            "making encrypted backup codes unreadable after restart."
        )

    db_uri = settings.SQLALCHEMY_DATABASE_URI or ""
    db_path = settings.DATABASE_PATH
    if "postgresql" not in db_uri.lower() and db_path != ":memory:" and "postgresql" not in db_path.lower():
        warnings_list.append(
            f"Using SQLite at '{db_path}'. For high-concurrency production "
            "deployments, migrate to PostgreSQL to avoid write-lock contention."
        )

    if (not settings.MAIL_SERVER or settings.MAIL_SERVER == "localhost") and settings.MAIL_BACKEND not in ("resend", "ses"):
        warnings_list.append(
            "MAIL_SERVER (or MAIL_BACKEND='resend'/'ses') is not configured. "
            "Password reset and OTP emails will use the console fallback."
        )

    if settings.CORS_ORIGINS == "*":
        warnings_list.append(
            "CORS_ORIGINS=* allows all origins. Set explicit frontend "
            "origin(s) for production."
        )

    if redis_client:
        try:
            redis_client.ping()
        except Exception:
            warnings_list.append(
                "REDIS_URL is configured but Redis is unreachable. "
                "Rate limiting and JWT blocklist will NOT function."
            )

    if warnings_list:
        logger.warning("=" * 60)
        logger.warning("PRODUCTION READINESS CHECK — %d issue(s):", len(warnings_list))
        for i, w in enumerate(warnings_list, 1):
            logger.warning("  [%d] %s", i, w)
        logger.warning("=" * 60)
    else:
        logger.info("Production readiness check: all clear ✓")
