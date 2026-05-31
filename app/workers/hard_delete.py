import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.workers.celery_app import celery

LOG = logging.getLogger(__name__)

DATABASE_URL = os.getenv("SYNC_DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


@celery.task
def hard_delete_users():
    """
    CCPA compliance — anonymizes users deactivated more than 30 days ago.
    Preserves the row with scrambled PII for abuse investigation audit trail.
    Also cleans up expired token blacklist entries.
    Runs nightly at 3am UTC via Celery beat (after retention at 2am).
    """
    db = SessionLocal()
    try:
        # 1. Find users where is_active = false AND deactivated_at < NOW() - INTERVAL '30 days'
        #    Hint: use text() with a raw SQL SELECT — returns list of UUIDs

        # 2. For each user_id, anonymize PII fields in a single UPDATE:
        #    username = 'deleted_' || id::text
        #    email    = 'deleted_' || id::text || '@deleted.findr'
        #    bio      = NULL
        #    hashed_password = ''
        #    email_verification_token = NULL
        #    password_reset_token     = NULL

        # 3. Clean up expired token blacklist rows:
        #    DELETE FROM token_blacklist WHERE expires_at < NOW()

        # 4. Commit and log how many users were anonymized

        result = db.execute(text("""
            SELECT 
                id 
            FROM users
            WHERE is_active = false
            AND deactivated_at < NOW() - INTERVAL '30 days'
        """))
        user_ids = [str(row[0]) for row in result.fetchall()]

        for id in user_ids:
            db.execute(text("""
                UPDATE users
                SET 
                    username = 'deleted_' || id::text,
                    email = 'deleted_' || id::text || '@deleted.findr',
                    bio = NULL,
                    hashed_password = '',
                    email_verification_token = NULL,
                    password_reset_token = NULL
                WHERE id = :user_id::uuid
            """), {"user_id": id})
            
        result = db.execute(text("""
            DELETE FROM token_blacklist WHERE expires_at < NOW()
        """))

        db.commit()
        LOG.info(f"{len(user_ids)} users anonymized.")

    except Exception as e:
        db.rollback()
        LOG.error(f"Hard delete failed: {e}")
        raise

    finally:
        db.close()
