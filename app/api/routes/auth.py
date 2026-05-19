from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.schemas import UserRegister, UserPublic, TokenResponse, PasswordChange
from app.models.models import User
from app.core.security import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserPublic, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where((User.username==payload.username) | (User.email==payload.email)))
    user = result.scalar_one_or_none()

    if user:
        raise HTTPException(status_code=409, detail="User already exists.")
    
    new_user = User(
        username= payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
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

@router.patch("/password")
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):  
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password.")

    current_user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return {"status": "password updated"}
    