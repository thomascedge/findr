import uuid
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.schemas import (
    UserRegister,
    UserPublic,
    TokenResponse,
    PasswordChange,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    OnboardingStatus,
)
from app.models.models import User, TokenBlacklist, UserPhoto, UserLocation, utcnow
from app.core.security import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    decode_token,
    oauth2_scheme,
)
from app.core.email import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

CURRENT_TERMS_VERSION = "1.0"
TOKEN_EXPIRY_HOURS = 24


def _calculate_age(date_of_birth: datetime) -> int:
    """Returns age in whole years from a timezone-aware date of birth."""
    return (datetime.now(timezone.utc) - date_of_birth).days // 365


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.
    Enforces 18+ age requirement (COPPA compliance).
    Generates an email verification token — email_verified_at starts as null.
    """
    if payload.date_of_birth >= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400, detail="Date of birth cannot be in the future."
        )

    if _calculate_age(payload.date_of_birth) < 18:
        raise HTTPException(status_code=400, detail="Must be 18 or older to register.")

    result = await db.execute(
        select(User).where(
            (User.username == payload.username) | (User.email == payload.email)
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists.")

    verification_token = secrets.token_urlsafe(32)

    new_user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        date_of_birth=payload.date_of_birth,
        email_verification_token=verification_token,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    send_verification_email(payload.email, verification_token, payload.username)

    return new_user


@router.post("/token", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """Login and return a JWT. Inactive users are rejected."""
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user.")

    token = create_token(user.id)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204)
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke the current JWT by adding it to the token blacklist.
    """
    token_blacklist = TokenBlacklist(
        jti=token,
        blacklisted_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
    )
    db.add(token_blacklist)
    await db.commit()


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """
    Consume an email verification token and mark the email as verified.
    Token is single-use — cleared after successful verification.
    """
    result = await db.execute(
        select(User).where(User.email_verification_token == payload.token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token."
        )

    user.email_verified_at = utcnow()
    user.email_verification_token = None
    await db.commit()
    return {"status": "email verified"}


@router.post("/resend-verification")
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resend the email verification token. No-ops if already verified."""
    if current_user.email_verified_at:
        return {"status": "already verified"}

    token = secrets.token_urlsafe(32)
    current_user.email_verification_token = token
    await db.commit()

    send_verification_email(current_user.email, token, current_user.username)
    return {"status": "verification email sent"}


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
):
    """
    Generate a password reset token and queue a reset email.
    Always returns 200 regardless of whether the email exists — prevents user enumeration.
    Token expires in 1 hour.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = utcnow() + timedelta(hours=1)
        await db.commit()
        send_password_reset_email(payload.email, token)

    return {"status": "if that email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
):
    """Consume a password reset token and set a new password."""
    result = await db.execute(
        select(User).where(User.password_reset_token == payload.token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token.")

    if user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    await db.commit()
    return {"status": "password reset successful"}


@router.post("/reactivate-by-token")
async def reactivate_by_token(token: str, db: AsyncSession = Depends(get_db)):
    """
    Reactivate a deactivated account using a valid JWT.
    """
    user_id = decode_token(token)
    user = await db.get(User, uuid.UUID(user_id))

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.is_active:
        return {"status": "account already active"}

    days_since_deactivation = (datetime.utcnow() - user.deactivated_at).days
    if days_since_deactivation > 30:
        raise HTTPException(status_code=400, detail="Reactivation window expired.")

    user.is_active = True
    user.deactivated_at = None
    await db.commit()
    return {"status": "account reactivated"}


@router.patch("/password")
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password.")
    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"status": "password updated"}


@router.get("/onboarding-status", response_model=OnboardingStatus)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns which onboarding steps the user has completed.
    Marks onboarding_completed_at on the user row when all steps are done.
    """
    result = await db.execute(
        select(UserPhoto).where(
            UserPhoto.user_id == current_user.id,
            UserPhoto.deleted_at == None,
        )
    )
    user_photo = result.scalar_one_or_none()

    result = await db.execute(
        select(UserLocation).where(UserLocation.user_id == current_user.id)
    )
    user_location = result.scalar_one_or_none()

    user = await db.get(User, current_user.id)

    email_verified = user.email_verified_at is not None
    terms_accepted = user.terms_accepted_at is not None
    location_consent = user.location_consent_at is not None
    has_photo = user_photo is not None
    has_location = user_location is not None
    onboarding_complete = all(
        [email_verified, terms_accepted, location_consent, has_photo, has_location]
    )

    if onboarding_complete and not user.onboarding_completed_at:
        user.onboarding_completed_at = utcnow()
        await db.commit()

    onboarding_status = OnboardingStatus(
        email_verified=email_verified,
        terms_accepted=terms_accepted,
        location_consent=location_consent,
        has_photo=has_photo,
        has_location=has_location,
        onboarding_complete=onboarding_complete,
    )

    return onboarding_status
