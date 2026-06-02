"""Tests for legal endpoints: user reporting, data export, and account deletion."""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import UserReportCreate
from app.models.models import User, UserReport


# ── User reporting ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_user_success(client: AsyncClient, auth_headers: dict, test_user_2: User):
    """A user can report another user with a valid reason."""
    # POST /api/v1/legal/report with reported_id=test_user_2.id and a reason
    # Assert 201
    # Assert response contains reason and reported_id
    payload = UserReportCreate(
            reported_id=test_user_2.id,
            reason="Innapropriate behavior",
            details="Some details"
        )
    
    response = await client.post(
        '/api/v1/legal/report',
        json=payload.model_dump(mode='json'),
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert 'reason' in data
    assert 'reported_id' in data


@pytest.mark.asyncio
async def test_report_user_not_found(client: AsyncClient, auth_headers: dict):
    """Reporting a non-existent user returns 404."""
    # POST /api/v1/legal/report with a random UUID as reported_id
    # Assert 404
    payload = UserReportCreate(
            reported_id=uuid.uuid4(),
            reason="Innapropriate behavior",
            details="Some details"
        )
    
    response = await client.post(
        '/api/v1/legal/report',
        json=payload.model_dump(mode='json'),
        headers=auth_headers
    )
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_report_self_blocked(client: AsyncClient, auth_headers: dict, test_user: User):
    """A user cannot report themselves."""
    # POST /api/v1/legal/report with reported_id = current user's id
    # Assert 400
    payload = UserReportCreate(
            reported_id=test_user.id,
            reason="Innapropriate behavior",
            details="Some details"
        )
    
    response = await client.post(
        '/api/v1/legal/report',
        json=payload.model_dump(mode='json'),
        headers=auth_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_report_requires_auth(client: AsyncClient, test_user_2: User):
    """Reporting without a token returns 401."""
    # POST /api/v1/legal/report with no auth headers
    # Assert 401
    payload = UserReportCreate(
            reported_id=test_user_2.id,
            reason="Innapropriate behavior",
            details="Some details"
        )
    
    response = await client.post(
        '/api/v1/legal/report',
        json=payload.model_dump(mode='json'),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_report_reason_too_short(client: AsyncClient, auth_headers: dict, test_user_2: User):
    """Report reason under 3 chars returns 422."""
    # POST with reason = "ab" (below min_length=3)
    # Assert 422
    response = await client.post(
        '/api/v1/legal/report',
        json={
            "reported_id": str(test_user_2.id),
            "reason": "ab",
            "details": "Some details",
        },
        headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_creates_db_row(client: AsyncClient, auth_headers: dict, test_user: User, test_user_2: User, db: AsyncSession):
    """Submitting a report creates a UserReport row in the database."""
    # POST /api/v1/legal/report
    # Query UserReport table directly using db
    # Assert one row exists with correct reporter_id and reported_id
    payload = UserReportCreate(
            reported_id=test_user_2.id,
            reason="Innapropriate activity",
            details="Some details"
        )
    
    response = await client.post(
        '/api/v1/legal/report',
        json=payload.model_dump(mode='json'),
        headers=auth_headers
    )
    assert response.status_code == 201
    report_id = response.json()['id']

    report = await db.get(UserReport, uuid.UUID(report_id))
    assert str(report.reporter_id) == str(test_user.id)
    assert str(report.reported_id) == str(test_user_2.id)


# ── Data export ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_data_returns_all_sections(client: AsyncClient, auth_headers: dict, test_user: User):
    """Data export returns profile, location, messages, and photos sections."""
    # GET /api/v1/legal/export-data
    # Assert 200
    # Assert response has keys: profile, location, messages, photos
    # Assert profile.username matches test_user.username
    response = await client.get(
        '/api/v1/legal/export-data',
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {'profile', 'location', 'messages', 'photos'}
    assert data['profile']['username'] == test_user.username

@pytest.mark.asyncio
async def test_export_data_requires_auth(client: AsyncClient):
    """Data export without a token returns 401."""
    # GET /api/v1/legal/export-data with no headers
    # Assert 401
    response = await client.get(
        '/api/v1/legal/export-data',
    )
    assert response.status_code == 401


# ── Account deletion ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_account_deactivates_user(client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession):
    """Deleting account sets is_active=False and deactivated_at."""
    # DELETE /api/v1/legal/delete-account
    # Assert 204
    # Refresh test_user from DB
    # Assert is_active == False and deactivated_at is not None
    response = await client.delete(
        '/api/v1/legal/delete-account',
        headers=auth_headers
    )
    assert response.status_code == 204
    await db.refresh(test_user)
    assert test_user.is_active == False
    assert test_user.deactivated_at is not None


@pytest.mark.asyncio
async def test_delete_account_token_rejected_after(client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession):
    """After deletion, the user's token is rejected on protected routes."""
    # DELETE /api/v1/legal/delete-account
    # GET /api/v1/users/me with same auth_headers
    # Assert 401
    response = await client.delete(
        '/api/v1/legal/delete-account',
        headers=auth_headers
    )
    assert response.status_code == 204

    response = await client.get(
        '/api/v1/users/me',
        headers=auth_headers
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_account_requires_auth(client: AsyncClient):
    """Deleting account without a token returns 401."""
    # DELETE /api/v1/legal/delete-account with no headers
    # Assert 401
    response = await client.delete(
        '/api/v1/legal/delete-account',
    )
    assert response.status_code == 401
