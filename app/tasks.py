import os
from celery import Celery

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
    # In a real implementation, this would call ml_ensemble.evaluate_session
    # and update the redis cache or database for the given session.
    pass
