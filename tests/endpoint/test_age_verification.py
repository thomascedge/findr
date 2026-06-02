"""
Tests for age verification on registration (COPPA compliance).
All tests use the register endpoint — add date_of_birth to UserRegister
and implement the age check in auth.py before running these.
"""

import pytest
from datetime import timedelta
from httpx import AsyncClient
from app.models.models import utcnow


def _dob(years_ago: int) -> str:
    """Returns an ISO datetime string for a date N years ago."""
    return (utcnow() - timedelta(days=years_ago * 365)).isoformat()


def _reg_payload(username: str, years_ago: int) -> dict:
    """Returns a valid registration payload with the given age."""
    return {
        "username": username,
        "email": "username@test.com",
        "password": "password123",
        "date_of_birth": _dob(years_ago),
    }


@pytest.mark.asyncio
async def test_register_18_succeeds(client: AsyncClient):
    """A user who is exactly 18 can register."""
    response = await client.post(
        "/api/v1/auth/register", json=_reg_payload("user18", 18)
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_register_over_18_succeeds(client: AsyncClient):
    """A user who is 25 can register."""
    response = await client.post(
        "/api/v1/auth/register", json=_reg_payload("user31", 31)
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_register_17_blocked(client: AsyncClient):
    """A user who is 17 cannot register."""
    response = await client.post(
        "/api/v1/auth/register", json=_reg_payload("user17", 17)
    )
    assert response.status_code == 400
    assert "18" in response.text


@pytest.mark.asyncio
async def test_register_under_13_blocked(client: AsyncClient):
    """A user who is 12 is hard blocked."""
    # POST /api/v1/auth/register with date_of_birth = 12 years ago
    # Assert 400
    response = await client.post(
        "/api/v1/auth/register", json=_reg_payload("user12", 12)
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_missing_dob(client: AsyncClient):
    """Registration without date_of_birth returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "userNone",
            "email": "userNone@test.com",
            "password": "password123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_future_dob(client: AsyncClient):
    """Registration with a future date of birth returns 400."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "userNone",
            "email": "userTomorrow@test.com",
            "password": "password123",
            "date_of_birth": (utcnow() + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 400
