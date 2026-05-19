from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):    
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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
    lat: float # fuzzed coord
    lng: float # fuzzed coord
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
