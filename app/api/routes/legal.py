from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.core.security import get_current_user
from app.models.models import User, UserReport, Message, UserPhoto, UserLocation, utcnow
from app.schemas.schemas import UserReportCreate, UserReportOut, AcceptTermsRequest

router = APIRouter(prefix="/legal", tags=["legal"])

CURRENT_TERMS_VERSION = "1.0"


@router.post("/accept-terms", status_code=200)
async def accept_terms(
    payload: AcceptTermsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record the user's acceptance of the Terms of Service.
    """
    current_user.terms_accepted_at = utcnow()
    current_user.terms_version = payload.terms_version
    await db.commit()
    return {"status": "terms accepted", "version": payload.terms_version}


@router.post("/consent-location", status_code=200)
async def consent_location(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record explicit consent for precise location tracking.
    """
    current_user.location_consent_at = utcnow()
    await db.commit()
    return {"status": "location consent recorded"}


@router.post("/report", response_model=UserReportOut, status_code=201)
async def report_user(
    payload: UserReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Report a user for inappropriate behavior.
    Required for FOSTA-SESTA compliance. Reports feed the admin review queue.
    """
    user = await db.get(User, current_user.id)

    if not user:
        raise HTTPException(status_code=400, detail="User not found.")
    
    if payload.reported_id == current_user.id:
        raise HTTPException(status_code=400, detail="User cannot report themself.")

    reported_user = await db.get(User, payload.reported_id)
    if not reported_user:
        raise HTTPException(status_code=404, detail="Reported user not found.")

    user_report = UserReport(
        reporter_id = current_user.id,
        reported_id = payload.reported_id,
        reason=payload.reason,
        details=payload.details
    )

    db.add(user_report)
    await db.commit()
    await db.refresh(user_report)
    return user_report


@router.get("/export-data")
async def export_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CCPA right to know — returns all data Findr holds on the current user.
    """
    user = await db.get(User, current_user.id)

    result = await db.execute(select(Message).where(Message.sender_id == current_user.id))
    messages_list = result.all()

    result = await db.execute(select(UserPhoto).where(UserPhoto.user_id == current_user.id))
    photos_list = result.all()

    result = await db.execute(select(UserLocation).where(UserLocation.user_id == current_user.id))
    location = result.all()

    user_export_data = {
        "profile": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "bio": user.bio,
            "date_of_birth": user.date_of_birth,
            "created_at": user.created_at,
            "terms_accepted_at": user.terms_accepted_at,
            "terms_version": user.terms_version,
            "location_consent_at": user.location_consent_at
        },
        "location": location,
        "messages": messages_list,
        "photos": photos_list
    }

    return user_export_data


@router.delete("/delete-account", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    CCPA right to deletion — soft deactivates the account.
    """
    current_user.is_active = False
    current_user.deactivated_at = utcnow()
    await db.commit()
