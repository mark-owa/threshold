"""Celery application instance.

The worker is used for queued event processing. Demo/API paths can still run
the reference workflow synchronously when immediate inspection is useful.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "threshold",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

celery_app.autodiscover_tasks(["app.workers"])


celery_app.conf.beat_schedule = {
    "retry-due-actions-every-minute": {
        "task": "threshold.retry_due_actions",
        "schedule": 60.0,
    },
}
