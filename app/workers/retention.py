import os
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.workers.celery_app import celery

LOG = logging.getLogger(__name__)

DATABASE_URL = os.getenv("SYNC_DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


@celery.task
def purge_old_messages():
    """Hard deletes messages where deleted_at is older than 90 days."""
    db = SessionLocal()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        result = db.execute(
            text("""
                    DELETE FROM messages
                    WHERE deleted_at IS NOT NULL
                    AND deleted_at < :cutoff
                """),
            {"cutoff": cutoff},
        )
        db.commit()
        LOG.info(f"{result.rowcount} records deleted from messages table.")

    except Exception as e:
        db.rollback()
        LOG.error(f"Hard delete failed with exception: {e}")
        raise

    finally:
        db.close()
