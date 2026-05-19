import os
from celery import Celery
from celery.schedules import crontab

REDIS = os.getenv("REDIS_URL")
celery = Celery('findr', broker=REDIS, backend=REDIS)
celery.autodiscover_tasks(['app.workers'])
celery.conf.update(
    worker_hijack_root_logger=False,
    broker_connection_retry_on_startup=True,
    include=["app.workers.retention"],
    timezone="UTC",
    beat_schedule={
        "retention.purge_old_messages": {
            "task": "app.workers.retention.purge_old_messages",
            "schedule": crontab(hour=2, minute=0),
        },

        # v2 — US scale
        # "presence.cleanup_stale_presence": { ... },
        # "analytics.aggregate_daily_stats": { ... },
        # "moderation.retry_failed_photo_reviews": { ... },
    },
)