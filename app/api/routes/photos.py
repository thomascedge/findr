import io
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from PIL import Image

from app.db import get_db
from app.core.security import get_current_user
from app.core.s3 import upload_photo, get_photo_url
from app.models.models import User, UserPhoto, ModerationStatus, utcnow
from app.workers.moderation import moderate_photo


router = APIRouter(prefix="/photos", tags=["photos"])


@router.post("/", status_code=201)
async def upload_user_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a photo. Max 3 photos per user. Converts to WebP before storing."""
    response = await db.execute(select(func.count()).select_from(UserPhoto).where(UserPhoto.user_id == current_user.id, UserPhoto.deleted_at == None))
    count = response.scalar_one()
    if count >= 3:
        raise HTTPException(status_code=400, detail="Max photos already uploaded")

    content = await file.read()
    if len(content) > 10 * (1024 ** 2):
        raise HTTPException(status_code=413, detail='File size too big.')

    img = Image.open(io.BytesIO(content))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    webp_bytes = buf.getvalue()

    photo_id = uuid.uuid4()
    s3_key = f'photos/{current_user.id}/{photo_id}.webp'

    upload_photo(webp_bytes, s3_key)

    photo_data = {
        "id": photo_id,
        "user_id": current_user.id,
        "s3_key": s3_key,
        "display_order": count + 1,
        "moderation_status": ModerationStatus.PENDING,
        "uploaded_at": utcnow(),
        "deleted_at": None
    }
    new_photo = UserPhoto(**photo_data)
    db.add(new_photo)
    await db.commit()
    await db.refresh(new_photo)

    # queue task in Redis while Celery picks up task asynchronously
    # upload returns while moderation works in background 
    moderate_photo.delay(str(photo_id), s3_key)

    return {'status': 'ok', 'photo_id': photo_id}


@router.delete("/{photo_id}")
async def delete_user_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a photo. If it was the primary, clears primary_photo_id."""
    response = await db.execute(select(UserPhoto).where(UserPhoto.id == photo_id))
    photo = response.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo does not exist.")

    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Photo does not belong to this user.")

    photo.deleted_at = utcnow()

    if current_user.primary_photo_id == photo_id:
        current_user.primary_photo_id = None

    await db.commit()
    return {"status": "deleted"}


@router.patch("/{photo_id}/primary")
async def set_primary_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a photo as the user's primary photo."""
    response = await db.execute(select(UserPhoto).where(UserPhoto.id == photo_id))
    photo = response.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo does not exist.")
    
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Photo does not belong to this user.")
    
    if photo.moderation_status != ModerationStatus.COMPLETE:
        raise HTTPException(status_code=400, detail="Photo not yet moderated.")

    current_user.primary_photo_id = photo_id
    await db.commit()

    return {"status": "updated"}


@router.patch("/{photo_id}/order")
async def update_photo_order(
    photo_id: uuid.UUID,
    display_order: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the display order of a photo."""
    response = await db.execute(select(UserPhoto).where(UserPhoto.id == photo_id))
    photo = response.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo does not exist.")
    
    if photo.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Photo does not belong to this user.")
    
    photo.display_order = display_order
    await db.commit()

    return {"status": "updated"}

@router.get("/")
async def get_user_photos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active photos for the current user with presigned URLs."""
    response = await db.execute(select(UserPhoto).where(UserPhoto.user_id == current_user.id, UserPhoto.deleted_at == None).order_by(UserPhoto.display_order))
    photos = response.scalars().all()
    
    photo_list = []
    for photo in photos:
        photo_list.append({
            "id": photo.id,
            "s3_key": photo.s3_key,
            "url": get_photo_url(photo.s3_key),
            "display_order": photo.display_order,
            "moderation_status": photo.moderation_status
        })

    return photo_list 
