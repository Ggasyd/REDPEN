"""Celery app configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "redpen",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
)

# Celery Beat schedule (daily retention enforcement)
celery_app.conf.beat_schedule = {
    "retention-enforcement-daily": {
        "task": "app.workers.tasks.retention_enforcement_daily",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2 AM
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])
