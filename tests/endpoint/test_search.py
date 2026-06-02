"""Tests for user search endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User


@pytest.mark.asyncio
async def test_search_by_username(
    client: AsyncClient, auth_headers: dict, test_user_2: User
):
    response = await client.get(
        f"/api/v1/search/users?q={test_user_2.username}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    usernames = [u["username"] for u in response.json()]
    assert test_user_2.username in usernames


@pytest.mark.asyncio
async def test_search_by_bio(
    client: AsyncClient, auth_headers: dict, test_user_2: User, db: AsyncSession
):
    test_user_2.bio = "I love hiking and coffee"
    await db.commit()
    await db.refresh(test_user_2)

    response = await client.get(
        "/api/v1/search/users?q=hiking",
        headers=auth_headers,
    )
    assert response.status_code == 200
    usernames = [user["username"] for user in response.json()]
    assert test_user_2.username in usernames


@pytest.mark.asyncio
async def test_search_excludes_current_user(
    client: AsyncClient, auth_headers: dict, test_user: User
):
    """Current user never appears in their own search results."""
    response = await client.get(
        f"/api/v1/search/users?q={test_user.username}", headers=auth_headers
    )
    assert response.status_code == 200
    ids = [user["id"] for user in response.json()]
    assert test_user.id not in ids


@pytest.mark.asyncio
async def test_search_excludes_inactive_users(
    client: AsyncClient, auth_headers: dict, test_user_2: User, db: AsyncSession
):
    """Deactivated users do not appear in search results."""
    test_user_2.is_active = False
    await db.commit()
    await db.refresh(test_user_2)

    response = await client.get(
        "/api/v1/search/users?q={test_user_2.username}", headers=auth_headers
    )
    assert response.status_code == 200
    usernames = [user["username"] for user in response.json()]
    assert test_user_2.username not in usernames


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(client: AsyncClient, auth_headers: dict):
    """A query with no matching users returns an empty list."""
    response = await client.get(
        "/api/v1/search/users?q=zzznomatch999", headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    """Search without a token returns 401."""
    response = await client.get(
        "/api/v1/search/users",
    )
    assert response.status_code == 401
