import os
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.workers.celery_app import celery

LOG = logging.getLogger(__name__)

@celery.task
def purge_old_messages():
    """Hard deletes messages where deleted_at is older than 90 days."""
    DATABASE_URL = os.getenv('SYNC_DATABASE_URL')
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        result = db.execute(
            text("""
                    DELETE FROM messages
                    WHERE deleted_at IS NOT NULL
                    AND deleted_at < NOW() - INTERVAL '90 days'
                """))
        db.commit()
        LOG.info(f'{result.rowcount} records deleted from messages table.')

    except Exception as e:
        db.rollback()
        LOG.error(f'Hard delete failed with exception: {e}')
        raise  # re-raise so Celery marks the task as failed

    finally:
        db.close()
