import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from starlette.testclient import TestClient
from app.main import app

# Default date of birth — 25 years old, passes 18+ check
DEFAULT_DOB = (datetime.now(timezone.utc) - timedelta(days=25 * 365)).isoformat()


@pytest.fixture(scope="module", autouse=True)
def mock_ses():
    """Mock SES globally for all integration tests — no real emails sent."""
    with patch("app.core.email.ses_client"):
        yield


@pytest.fixture(scope="module")
def client():
    """
    Integration test client — uses the live stack (Postgres + Redis).
    Requires docker compose up before running.
    Uses Starlette's TestClient for WebSocket support.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Register and log in a fresh user for each test module."""
    client.post("/api/v1/auth/register", json={
        "username": "integration_user",
        "email": "integration@test.com",
        "password": "password123",
        "date_of_birth": DEFAULT_DOB,
    })
    response = client.post("/api/v1/auth/token", data={
        "username": "integration_user",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def auth_headers_2(client):
    """A second user for multi-user WebSocket tests."""
    client.post("/api/v1/auth/register", json={
        "username": "integration_user_2",
        "email": "integration2@test.com",
        "password": "password123",
        "date_of_birth": DEFAULT_DOB,
    })
    response = client.post("/api/v1/auth/token", data={
        "username": "integration_user_2",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
