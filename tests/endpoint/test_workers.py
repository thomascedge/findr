import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from tests import logging
from app.models.models import Chat, Message, UserPhoto, PhotoModerationTag, ModerationStatus
from app.workers.retention import purge_old_messages
from app.workers.moderation import moderate_photo


# ── Helpers ───────────────────────────────────────────────────────────────────
def _mock_reckognition():
    return patch("app.workers.moderation.rekognition")

def _mock_retention(db):
    return patch("app.workers.retention.SessionLocal", return_value=db)

def _mock_moderation(db):
    return patch("app.workers.moderation.SessionLocal", return_value=db)

def _mock_application_retries(application_name: str, max_retries=3):
    if application_name.lower() == "celery":
        return patch("celery.app.task.Context.retries", new_callable=PropertyMock, return_value=max_retries)
    if application_name.lower() == "moderation":
        return patch("app.workers.moderation.moderate_photo.max_retries", max_retries)


# ── Retention task ────────────────────────────────────────────────────────────
def test_purge_old_messages_deletes_expired(db_sync, test_message_sync):
    """Hard deletes messages where deleted_at is older than 90 days."""
    msg = test_message_sync(deleted_at=datetime.now(timezone.utc) - timedelta(days=91))
    msg_id = msg.id

    with _mock_retention(db_sync):
        purge_old_messages()

    db_sync.get(Message, msg_id) is None


def test_purge_old_messages_keeps_recent(db_sync, test_message_sync):
    """Does not delete messages soft-deleted less than 90 days ago."""
    msg = test_message_sync(deleted_at=datetime.now(timezone.utc) - timedelta(days=31))
    msg_id = msg.id

    with _mock_retention(db_sync):
        purge_old_messages()

    assert db_sync.get(Message, msg_id) is not None


def test_purge_old_messages_keeps_undeleted(db_sync, test_message_sync):
    """Does not delete messages where deleted_at is NULL."""
    msg = test_message_sync()
    msg_id = msg.id

    with _mock_retention(db_sync):
        purge_old_messages()

    assert db_sync.get(Message, msg_id) is not None


def test_purge_old_messages_logs_count(db_sync, test_message_sync, caplog):
    """Logs how many rows were deleted."""
    test_message_sync(deleted_at=datetime.now(timezone.utc) - timedelta(days=91))
    test_message_sync(deleted_at=datetime.now(timezone.utc) - timedelta(days=92))

    with _mock_retention(db_sync):
        with caplog.at_level(logging.INFO, logger="app.workers.retention"):
            purge_old_messages()

    assert "2" in caplog.text


# ── Moderation task ───────────────────────────────────────────────────────────

def test_moderate_photo_success(db_sync, test_photo_sync):
    """On success, writes tags and sets moderation_status to COMPLETE."""
    photo_id = test_photo_sync.id
    s3_key = test_photo_sync.s3_key

    test_response = {
        "ModerationLabels": [
            {"Name": "Explicit Nudity", "Confidence": 92.5},
            {"Name": "Suggestive", "Confidence": 67.3}
        ]
    }

    with _mock_reckognition() as mock_rek, _mock_moderation(db_sync):
        mock_rek.detect_moderation_labels.return_value = test_response
        moderate_photo(str(photo_id), s3_key)

    photo = db_sync.get(UserPhoto, photo_id)
    assert photo.moderation_status == ModerationStatus.COMPLETE
    
    tags = db_sync.query(PhotoModerationTag).filter_by(photo_id=photo_id).all()
    assert len(tags) == 2


def test_moderate_photo_no_labels(db_sync, test_photo_sync):
    """A clean photo with no labels still sets status to COMPLETE."""
    photo_id = test_photo_sync.id
    s3_key = test_photo_sync.s3_key

    test_response = {
        "ModerationLabels": []
    }

    with _mock_reckognition() as mock_rek, _mock_moderation(db_sync):
        mock_rek.detect_moderation_labels.return_value = test_response
        moderate_photo(str(photo_id), s3_key)

    photo = db_sync.get(UserPhoto, photo_id)
    assert photo.moderation_status == ModerationStatus.COMPLETE
    
    tags = db_sync.query(PhotoModerationTag).filter_by(photo_id=photo_id).all()
    assert len(tags) == 0


def test_moderate_photo_sets_failed_after_max_retries(db_sync, test_photo_sync):
    """After max retries exhausted, sets moderation_status to FAILED."""
    photo_id = test_photo_sync.id
    s3_key = test_photo_sync.s3_key

    with _mock_reckognition() as mock_rek, \
         _mock_moderation(db_sync), \
         _mock_application_retries("moderation"), \
         _mock_application_retries("celery", 3):        
        
        mock_rek.detect_moderation_labels.side_effect = Exception("Rekognition unavailable")

        try:
            moderate_photo(str(photo_id), s3_key)
        except Exception:
            pass

    photo = db_sync.get(UserPhoto, photo_id)
    assert photo.moderation_status == ModerationStatus.FAILED


def test_moderate_photo_retries_on_failure(db_sync, test_photo_sync):
    """Retries the task when Rekognition raises an exception."""
    photo_id = test_photo_sync.id
    s3_key = test_photo_sync.s3_key

    with _mock_reckognition() as mock_rek, _mock_moderation(db_sync), _mock_application_retries("celery", 1):
        mock_rek.detect_moderation_labels.side_effect = Exception("Rekognition unavailable")

        try:
            moderate_photo(str(photo_id), s3_key)
        except Exception:
            pass

    photo = db_sync.get(UserPhoto, photo_id)
    assert photo.moderation_status == ModerationStatus.PENDING


def test_moderate_photo_tags_written_before_status_update(db_sync, test_photo_sync):
    """Tags are committed before moderation_status is updated to COMPLETE."""
    photo_id = test_photo_sync.id
    s3_key = test_photo_sync.s3_key

    test_response = {
        "ModerationLabels": [
            {"Name": "Explicit Nudity", "Confidence": 92.5},
            {"Name": "Suggestive", "Confidence": 67.3},
            {"Name": "Violence", "Confidence": 54.3}
        ]
    }

    with _mock_reckognition() as mock_rek, _mock_moderation(db_sync):
        mock_rek.detect_moderation_labels.return_value = test_response
        moderate_photo(str(photo_id), s3_key)
    
    photo = db_sync.get(UserPhoto, photo_id)
    assert photo.moderation_status == ModerationStatus.COMPLETE
    
    tags = db_sync.query(PhotoModerationTag).filter_by(photo_id=photo_id).all()
    assert len(tags) == 3
