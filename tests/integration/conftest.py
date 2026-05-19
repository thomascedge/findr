# tests/integration/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest_asyncio.fixture
async def client():
    """
    Integration test client — uses the live stack (Postgres + Redis).
    Requires docker compose up before running.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Register and log in a fresh user for each test."""
    # 1. Register a new user via POST /api/v1/auth/register
    # 2. Log in via POST /api/v1/auth/token
    # 3. Return {"Authorization": f"Bearer {token}"}
    await client.post("/api/v1/auth/register", json={
        "username": "integration_user",
        "email": "integration@test.com",
        "password": "password123",
    })
    response = await client.post("/api/v1/auth/token", data={
        "username": "integration_user",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_headers_2(client: AsyncClient):
    """A second user for multi-user WebSocket tests."""
    await client.post("/api/v1/auth/register", json={
        "username": "integration_user_2",
        "email": "integration2@test.com",
        "password": "password123",
    })
    response = await client.post("/api/v1/auth/token", data={
        "username": "integration_user_2",
        "password": "password123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}