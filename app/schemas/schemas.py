from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

# ── Auth ──────────────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    date_of_birth: datetime  # must be 18+ — validated in auth.py register endpoint


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    # accepts the user's email address
    # always returns 200 regardless of whether the email exists — prevents user enumeration
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    # token from the reset email link
    # new_password replaces the current hashed_password on the user row
    token: str
    new_password: str = Field(min_length=8, max_length=72)


class VerifyEmailRequest(BaseModel):
    # single-use token from the verification email
    # clears email_verification_token and sets email_verified_at on success
    token: str


class OnboardingStatus(BaseModel):
    # each field maps to a step in the onboarding flow
    # all must be True for onboarding_complete to be True
    email_verified: bool
    terms_accepted: bool
    location_consent: bool
    has_photo: bool
    has_location: bool
    onboarding_complete: bool


# ── User ──────────────────────────────────────────────────────────────────────


class UserPublic(BaseModel):
    id: UUID
    username: str
    bio: Optional[str]
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=32)
    bio: Optional[str] = Field(default=None)


# ── Location ──────────────────────────────────────────────────────────────────


class LocationUpdate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    visible: bool = Field(default=True)


class NearbyUser(BaseModel):
    user_id: UUID
    username: str
    lat: float  # fuzzed coord
    lng: float  # fuzzed coord
    distance_miles: float


# ── Chat ──────────────────────────────────────────────────────────────────────


class ChatOut(BaseModel):
    id: UUID
    is_group: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Messages ──────────────────────────────────────────────────────────────────


class MessageSend(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: UUID
    chat_id: UUID
    sender_id: UUID
    body: str
    sent_at: datetime
    edited_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class MessageReadOut(BaseModel):
    message_id: UUID
    user_id: UUID
    read_at: datetime
    model_config = {"from_attributes": True}


class MessageEdit(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


# ── Password ──────────────────────────────────────────────────────────────────


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)


# ── Legal ─────────────────────────────────────────────────────────────────────


class UserReportCreate(BaseModel):
    reported_id: UUID
    reason: str = Field(min_length=3, max_length=255)
    details: Optional[str] = Field(default=None, max_length=2000)


class UserReportOut(BaseModel):
    id: UUID
    reporter_id: UUID
    reported_id: UUID
    reason: str
    details: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


class AcceptTermsRequest(BaseModel):
    # version should match the current ToS version string e.g. "1.0"
    # stored on user row so re-prompting is possible when ToS changes
    terms_version: str = Field(min_length=1, max_length=16)


# ── Search ────────────────────────────────────────────────────────────────────


class UserSearchResult(BaseModel):
    id: UUID
    username: str
    bio: Optional[str]
    distance_miles: Optional[float]  # None when no location filter applied
    model_config = {"from_attributes": True}
