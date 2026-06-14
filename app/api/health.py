"""Health check endpoint for monitoring, load balancers, and uptime probes."""
import logging
from flask_restx import Namespace, Resource

logger = logging.getLogger(__name__)

health_ns = Namespace("health", description="System health checks")


@health_ns.route("")
class HealthCheck(Resource):
    def get(self):
        """
        Returns system health status.

        Checks:
          - Database connectivity
          - Redis availability
          - ML model readiness
        """
        status = {"status": "healthy", "checks": {}}

        # 1. Database check
        try:
            from app.extensions import get_db
            db = get_db()
            with db.get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            status["checks"]["database"] = {"status": "up"}
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

        # 3. ML model check
        try:
            from app.models.ml_models import EnsembleBehavioralClassifier
            status["checks"]["ml_models"] = {"status": "available"}
        except ImportError:
            status["checks"]["ml_models"] = {"status": "unavailable"}
        except Exception as e:
            status["checks"]["ml_models"] = {"status": "error", "error": str(e)}

        http_code = 200 if status["status"] == "healthy" else 503
        return status, http_code
