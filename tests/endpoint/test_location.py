import pytest
from httpx import AsyncClient


# ── Update location ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_location_success(client: AsyncClient, auth_headers):
    """A user can update their location with valid lat/lng."""
    response = await client.put("/api/v1/location/me", json={
        "lat": 30.2672,
        "lng": -97.7431,
        "visible": True,
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_update_location_twice_upserts(client: AsyncClient, auth_headers, db, test_user):
    """Updating location twice results in only one row in user_locations."""
    from app.models.models import UserLocation
    from sqlalchemy import select

    await client.put("/api/v1/location/me", json={"lat": 30.2, "lng": -97.7, "visible": True}, headers=auth_headers)
    await client.put("/api/v1/location/me", json={"lat": 30.3, "lng": -97.8, "visible": True}, headers=auth_headers)

    result = await db.execute(select(UserLocation).where(UserLocation.user_id == test_user.id))
    locations = result.scalars().all()
    assert len(locations) == 1


@pytest.mark.asyncio
async def test_update_location_invalid_lat(client: AsyncClient, auth_headers):
    """Lat out of range (-90 to 90) returns 422."""
    response = await client.put("/api/v1/location/me", json={
        "lat": 999,
        "lng": -97.7431,
        "visible": True,
    }, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_location_invalid_lng(client: AsyncClient, auth_headers):
    """Lng out of range (-180 to 180) returns 422."""
    response = await client.put("/api/v1/location/me", json={
        "lat": 30.2672,
        "lng": 999,
        "visible": True,
    }, headers=auth_headers)
    assert response.status_code == 422


# ── Nearby ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_nearby_no_location(client: AsyncClient, auth_headers):
    """Getting nearby users when current user has no location returns 404."""
    response = await client.get("/api/v1/location/nearby", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_nearby_invisible_user_excluded(client: AsyncClient, auth_headers, auth_headers_2):
    """An invisible user does not appear in nearby results."""
    # Set user 2 location but invisible
    await client.put("/api/v1/location/me", json={"lat": 30.2672, "lng": -97.7431, "visible": False}, headers=auth_headers_2)
    # Set user 1 location
    await client.put("/api/v1/location/me", json={"lat": 30.2672, "lng": -97.7431, "visible": True}, headers=auth_headers)

    response = await client.get("/api/v1/location/nearby", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0


# ── Go offline ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_go_offline(client: AsyncClient, auth_headers, test_user, db):
    """Going offline sets is_visible to False."""
    from app.models.models import UserLocation
    from sqlalchemy import select

    await client.put("/api/v1/location/me", json={"lat": 30.2672, "lng": -97.7431, "visible": True}, headers=auth_headers)
    response = await client.delete("/api/v1/location/me", headers=auth_headers)
    assert response.status_code == 200

    result = await db.execute(select(UserLocation).where(UserLocation.user_id == test_user.id))
    loc = result.scalar_one_or_none()
    assert loc.is_visible is False
