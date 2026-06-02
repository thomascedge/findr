import pytest
from starlette.testclient import TestClient

from app.main import app

# ── Helpers ───────────────────────────────────────────────────────────────────


def _fake_image_bytes() -> bytes:
    """Returns minimal valid JPEG bytes for upload testing."""
    # Create a small image in memory using Pillow and return as bytes


def _token(headers: dict) -> str:
    return headers["Authorization"].replace("Bearer ", "")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    """
    Integration test client — uses the live stack including LocalStack.
    Requires docker compose up before running.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Register and log in a fresh user for photo pipeline tests."""
    # Register a new user
    # Log in and return auth headers


# ── Upload pipeline ───────────────────────────────────────────────────────────


def test_photo_upload_stored_in_s3(client, auth_headers):
    """Uploaded photo is stored in LocalStack S3 as a WebP file."""
    # Upload a fake image
    # Assert 201 response with photo_id
    # Use boto3 pointed at LocalStack to verify the object exists in S3
    # Assert the key ends in .webp


def test_photo_upload_queues_moderation_task(client, auth_headers):
    """Uploading a photo queues a moderate_photo Celery task."""
    # Upload a fake image
    # Assert 201
    # Check Celery task is queued
    # Hint: inspect active/reserved tasks via celery.control.inspect()


def test_photo_upload_creates_pending_db_row(client, auth_headers):
    """Uploaded photo creates a UserPhoto row with moderation_status=PENDING."""
    # Upload a fake image
    # Query the DB for the UserPhoto row
    # Assert moderation_status == PENDING


def test_photo_not_visible_until_moderation_complete(client, auth_headers):
    """A photo with status=PENDING does not appear as primary-eligible."""
    # Upload a fake image
    # Attempt to set it as primary photo
    # Assert 400 — pending photos cannot be set as primary


def test_full_moderation_pipeline(client, auth_headers):
    """
    Full pipeline: upload → moderation task runs → status becomes COMPLETE.
    This test requires Celery worker to be running and LocalStack Rekognition
    to be available. It may take a few seconds for the task to complete.
    """
    # Upload a fake image — this queues the moderation task
    # Wait briefly for the Celery worker to process it
    # Hint: use time.sleep(2) or poll with retries
    # Query the DB for the UserPhoto row
    # Assert moderation_status == COMPLETE
    # Assert at least one PhotoModerationTag row exists


def test_s3_photo_served_via_presigned_url(client, auth_headers):
    """GET /photos/ returns presigned URLs that are accessible."""
    # Upload a photo (moderation can be mocked or waited on)
    # GET /api/v1/photos/
    # Assert each photo in the response has a url field
    # Assert the URL contains the s3_key
