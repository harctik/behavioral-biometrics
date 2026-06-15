import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

def make_celery(app_name=__name__):
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    celery = Celery(
        app_name,
        backend=redis_url,
        broker=redis_url
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return celery

celery_app = make_celery()

@celery_app.task(name="process_telemetry_batch")
def process_telemetry_batch(session_id, payload_data):
    """
    Background task to process behavioral telemetry asynchronously.
    """
    pass

@celery_app.task(name="send_email_async")
def send_email_async(to_email, template_name, context):
    """
    Background task to send emails without blocking HTTP requests.
    """
    logger.info(f"[Celery] Sending {template_name} email to {to_email}")
    try:
        from app.mail import MailService
        mail_service = MailService()
        if template_name == "verification":
            mail_service.send_email_verification(to_email, context.get("username"), context.get("verify_token"))
        elif template_name == "password_reset":
            mail_service.send_password_reset(to_email, context.get("username"), context.get("reset_token"))
    except Exception as e:
        logger.error(f"[Celery] Failed to send email to {to_email}: {e}")

@celery_app.task(name="log_audit_evidence_async")
def log_audit_evidence_async(action, status, user_id, session_id, resource, metadata, rationale, retention_tag):
    """
    Background task to log audit evidence asynchronously to prevent database write locks on the critical path.
    """
    try:
        from app.database import DatabaseManager
        from app.config import Settings
        
        settings = Settings()
        db = DatabaseManager(settings.SQLALCHEMY_DATABASE_URI)
        db.log_audit_evidence(
            action=action,
            status=status,
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            metadata=metadata,
            rationale=rationale,
            retention_tag=retention_tag
        )
    except Exception as e:
        logger.error(f"[Celery] Failed to log audit evidence: {e}")


@celery_app.task(
    name="train_user_models_async",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=600,   # 10-minute soft limit
    time_limit=660,        # 11-minute hard limit
)
def train_user_models_async(self, user_id, force_phase=None):
    """
    Background task: Full ML training pipeline for a user.

    Runs the TrainingOrchestrator which coordinates all 15+ models:
      - Phase 1: Data loading & feature extraction
      - Phase 2: Synthetic impostor generation (Gaussian + permutation)
      - Phase 3: Per-model training (OC-SVM, IF, k-NN, PA, AE, Transformer, GRU, Siamese, SimCLR, GAN, Duress)
      - Phase 4: Bayesian fusion calibration
      - Phase 5: Model persistence & versioning
      - Phase 6: Audit trail logging

    Args:
        user_id: The user whose models to train.
        force_phase: Override auto-detected enrollment phase (bootstrap/building/mature).

    Returns:
        TrainingReport dict with per-model metrics.
    """
    logger.info("[Celery] Starting ML training for user %d (phase=%s)", user_id, force_phase or "auto")
    try:
        from app.database import DatabaseManager
        from app.config import Settings
        from app.training_orchestrator import TrainingOrchestrator

        settings = Settings()
        db = DatabaseManager(settings.SQLALCHEMY_DATABASE_URI)
        orchestrator = TrainingOrchestrator(db=db, models_dir=settings.MODELS_BASE_PATH)
        report = orchestrator.train_all(user_id=user_id, force_phase=force_phase)

        logger.info(
            "[Celery] Training complete for user %d: %d models trained, %d failed, %.1fs",
            user_id, len(report.models_trained), len(report.models_failed),
            report.duration_seconds,
        )
        return report.to_dict()

    except Exception as exc:
        logger.error("[Celery] Training failed for user %d: %s", user_id, exc)
        # Retry on transient failures (DB lock, resource exhaustion)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("[Celery] Max retries exceeded for user %d training", user_id)
            return {"error": str(exc), "user_id": user_id, "retries_exhausted": True}


@celery_app.task(name="retrain_all_users_async", soft_time_limit=3600)
def retrain_all_users_async():
    """
    Scheduled task: Retrain models for ALL active users.

    Run this nightly or weekly via Celery Beat to keep models fresh
    as user behavior evolves (concept drift mitigation).
    """
    logger.info("[Celery] Starting batch retraining for all active users...")
    try:
        from app.database import DatabaseManager
        from app.config import Settings

        settings = Settings()
        db = DatabaseManager(settings.SQLALCHEMY_DATABASE_URI)
        # Get all users who have completed calibration
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT user_id FROM users WHERE calibration_complete = TRUE AND is_active = TRUE"
            ).fetchall()

        user_ids = [row["user_id"] for row in rows]
        logger.info("[Celery] Batch retraining %d users", len(user_ids))

        results = {}
        for uid in user_ids:
            # Dispatch individual training tasks (fan-out)
            task = train_user_models_async.delay(uid)
            results[uid] = task.id

        return {"dispatched": len(results), "task_ids": results}

    except Exception as e:
        logger.error("[Celery] Batch retraining failed: %s", e)
        return {"error": str(e)}

