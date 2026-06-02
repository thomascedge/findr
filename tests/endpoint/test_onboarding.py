"""
Tests for onboarding and offboarding endpoints.
Covers: email verification, password reset, logout, reactivation,
terms acceptance, location consent, and onboarding status.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User

# ── Email verification ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_email_success(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """A valid verification token marks the email as verified."""
    # Seed a verification token directly on test_user
    # POST /api/v1/auth/verify-email with that token
    # Assert 200
    # Refresh test_user from DB — assert email_verified_at is set
    # Assert email_verification_token is now None (single-use)
    pass


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient):
    """An invalid verification token returns 400."""
    # POST /api/v1/auth/verify-email with a random string as token
    # Assert 400
    pass


@pytest.mark.asyncio
async def test_resend_verification_generates_new_token(
    client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession
):
    """Resending verification generates a new token."""
    # Clear email_verification_token and email_verified_at on test_user
    # POST /api/v1/auth/resend-verification with auth_headers
    # Assert 200
    # Refresh test_user — assert email_verification_token is not None
    pass


@pytest.mark.asyncio
async def test_resend_verification_already_verified(
    client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession
):
    """Resending when already verified returns a no-op response."""
    # Set email_verified_at on test_user
    # POST /api/v1/auth/resend-verification
    # Assert 200 and status == "already verified"
    pass


# ── Password reset ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_forgot_password_always_200(client: AsyncClient):
    """forgot-password always returns 200 regardless of email existence."""
    # POST /api/v1/auth/forgot-password with a non-existent email
    # Assert 200 (not 404 — prevents user enumeration)
    pass


@pytest.mark.asyncio
async def test_forgot_password_sets_token(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """forgot-password sets a reset token on an existing user."""
    # POST /api/v1/auth/forgot-password with test_user.email
    # Refresh test_user — assert password_reset_token is not None
    # Assert password_reset_expires_at is in the future
    pass


@pytest.mark.asyncio
async def test_reset_password_success(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """A valid reset token allows setting a new password."""
    # Seed password_reset_token and a future password_reset_expires_at on test_user
    # POST /api/v1/auth/reset-password with the token and new_password
    # Assert 200
    # Refresh test_user — assert password_reset_token is None (cleared)
    pass


@pytest.mark.asyncio
async def test_reset_password_expired_token(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """An expired reset token returns 400."""
    # Seed password_reset_token and a past password_reset_expires_at on test_user
    # POST /api/v1/auth/reset-password
    # Assert 400
    pass


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient):
    """An invalid reset token returns 400."""
    # POST /api/v1/auth/reset-password with a made-up token
    # Assert 400
    pass


# ── Logout ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_success(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
):
    """Logging out blacklists the current token."""
    # POST /api/v1/auth/logout with auth_headers
    # Assert 204
    # Query TokenBlacklist — assert a row exists for the token
    pass


@pytest.mark.asyncio
async def test_logout_requires_auth(client: AsyncClient):
    """Logging out without a token returns 401."""
    # POST /api/v1/auth/logout with no headers
    # Assert 401
    pass


# ── Reactivation ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reactivate_within_30_days(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """A user can reactivate their account within 30 days of deactivation."""
    # Set test_user.is_active = False and deactivated_at = 10 days ago
    # Generate a token for test_user using create_token()
    # POST /api/v1/auth/reactivate-by-token?token=...
    # Assert 200
    # Refresh test_user — assert is_active is True and deactivated_at is None
    pass


@pytest.mark.asyncio
async def test_reactivate_after_30_days_blocked(
    client: AsyncClient, test_user: User, db: AsyncSession
):
    """Reactivation after 30 days is rejected."""
    # Set test_user.is_active = False and deactivated_at = 35 days ago
    # POST /api/v1/auth/reactivate-by-token?token=...
    # Assert 400
    pass


# ── Terms & consent ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accept_terms(
    client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession
):
    """Accepting terms sets terms_accepted_at and terms_version."""
    # POST /api/v1/legal/accept-terms with {"terms_version": "1.0"}
    # Assert 200
    # Refresh test_user — assert terms_accepted_at is set and terms_version == "1.0"
    pass


@pytest.mark.asyncio
async def test_consent_location(
    client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession
):
    """Consenting to location tracking sets location_consent_at."""
    # POST /api/v1/legal/consent-location
    # Assert 200
    # Refresh test_user — assert location_consent_at is set
    pass


# ── Onboarding status ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_onboarding_status_all_incomplete(
    client: AsyncClient, auth_headers: dict
):
    """A freshly registered user has all onboarding steps incomplete."""
    # GET /api/v1/auth/onboarding-status
    # Assert 200
    # Assert email_verified is False, terms_accepted is False, onboarding_complete is False
    pass


@pytest.mark.asyncio
async def test_onboarding_status_complete(
    client: AsyncClient, auth_headers: dict, test_user: User, db: AsyncSession
):
    """A user who completes all steps has onboarding_complete=True."""
    # Seed: email_verified_at, terms_accepted_at, location_consent_at on test_user
    # Seed: a UserLocation row for test_user
    # Seed: a UserPhoto row with status=COMPLETE for test_user
    # GET /api/v1/auth/onboarding-status
    # Assert onboarding_complete is True
    pass
