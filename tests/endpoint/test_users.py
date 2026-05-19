import pytest
from httpx import AsyncClient


# ── Get profile ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers, test_user):
    """An authenticated user can fetch their own profile."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


# ── Update profile ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_username(client: AsyncClient, auth_headers):
    """A user can update their username to an available one."""
    response = await client.patch("/api/v1/users/me", json={
        "username": "newusername",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "newusername"


@pytest.mark.asyncio
async def test_update_username_taken(client: AsyncClient, auth_headers, test_user_2):
    """Updating to a username already taken by another user returns 409."""
    response = await client.patch("/api/v1/users/me", json={
        "username": "testuser2",
    }, headers=auth_headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_username_same_as_current(client: AsyncClient, auth_headers):
    """Updating to the same username as current should not return 409."""
    response = await client.patch("/api/v1/users/me", json={
        "username": "testuser",
    }, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_bio(client: AsyncClient, auth_headers):
    """A user can update their bio."""
    response = await client.patch("/api/v1/users/me", json={
        "bio": "Hello, I'm a test user.",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["bio"] == "Hello, I'm a test user."


@pytest.mark.asyncio
async def test_update_bio_clear(client: AsyncClient, auth_headers):
    """A user can clear their bio by sending an empty string."""
    response = await client.patch("/api/v1/users/me", json={
        "bio": "",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["bio"] == ""


@pytest.mark.asyncio
async def test_update_no_fields(client: AsyncClient, auth_headers):
    """Sending no fields is a no-op and returns the unchanged profile."""
    response = await client.patch("/api/v1/users/me", json={}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


# ── Delete account ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_me(client: AsyncClient, auth_headers, test_user, db):
    """Deleting account sets is_active to False and returns 204."""
    response = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 204

    await db.refresh(test_user)
    assert test_user.is_active is False


@pytest.mark.asyncio
async def test_deleted_user_cannot_access_routes(client: AsyncClient, auth_headers, test_user, db):
    """A deleted user's token is rejected on protected routes."""
    await client.delete("/api/v1/users/me", headers=auth_headers)

    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 401
