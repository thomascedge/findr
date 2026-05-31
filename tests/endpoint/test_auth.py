import pytest
from httpx import AsyncClient


# ── Register ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """A new user can register with valid username, email, and password."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@test.com",
        "password": "password123",
        "date_of_birth": "1990-01-01T00:00:00Z",
    })
    assert response.status_code == 201
    assert response.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user):
    """Registering with an already taken username returns 409."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "different@test.com",
        "password": "password123",
        "date_of_birth": "1990-01-01T00:00:00Z",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    """Registering with an already taken email returns 409."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "differentuser",
        "email": "test@test.com",
        "password": "password123",
        "date_of_birth": "1990-01-01T00:00:00Z",
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Registering with a malformed email returns 422."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "not-an-email",
        "password": "password123",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_username(client: AsyncClient):
    """Registering with a username under 3 chars returns 422."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "ab",
        "email": "new@test.com",
        "password": "password123",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Registering with a password under 8 chars returns 422."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@test.com",
        "password": "short",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_password_too_long(client: AsyncClient):
    """Registering with a password over 72 chars returns 422."""
    response = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@test.com",
        "password": "a" * 73,
    })
    assert response.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """A registered user can log in and receive a JWT token."""
    response = await client.post("/api/v1/auth/token", data={
        "username": "testuser",
        "password": "password123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """Logging in with the wrong password returns 401."""
    response = await client.post("/api/v1/auth/token", data={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Logging in with a username that doesn't exist returns 401."""
    response = await client.post("/api/v1/auth/token", data={
        "username": "ghost",
        "password": "password123",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user(client: AsyncClient, test_user, db):
    """A deactivated user cannot log in."""
    test_user.is_active = False
    await db.commit()

    response = await client.post("/api/v1/auth/token", data={
        "username": "testuser",
        "password": "password123",
    })
    assert response.status_code == 401


# ── Protected routes ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_protected_route_no_token(client: AsyncClient):
    """Accessing a protected route without a token returns 401."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_malformed_token(client: AsyncClient):
    """Accessing a protected route with a malformed token returns 401."""
    response = await client.get("/api/v1/users/me", headers={
        "Authorization": "Bearer not-a-real-token"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_token_rejected(client: AsyncClient, test_user, auth_headers, db):
    """A token belonging to a deactivated user is rejected on protected routes."""
    test_user.is_active = False
    await db.commit()

    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 401


# ── Change password ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, auth_headers):
    """A user can change their password with the correct current password."""
    response = await client.patch("/api/v1/auth/password", json={
        "current_password": "password123",
        "new_password": "newpassword123",
    }, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, auth_headers):
    """Providing the wrong current password returns 401."""
    response = await client.patch("/api/v1/auth/password", json={
        "current_password": "wrongpassword",
        "new_password": "newpassword123",
    }, headers=auth_headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient, auth_headers):
    """New password under 8 chars returns 422."""
    response = await client.patch("/api/v1/auth/password", json={
        "current_password": "password123",
        "new_password": "short",
    }, headers=auth_headers)
    assert response.status_code == 422
