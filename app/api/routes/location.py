from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import get_db
from app.schemas.schemas import LocationUpdate, NearbyUser
from app.models.models import User, UserLocation, utcnow
from app.core.security import get_current_user
from app.core.location import fuzz_coordinates, compute_geohash, haversine_query

router = APIRouter(prefix="/location", tags=["location"])


@router.put("/me")
async def update_my_location(payload: LocationUpdate,
                             current_user: User = Depends(get_current_user), 
                             db: AsyncSession = Depends(get_db)):

    new_lat, new_lng = fuzz_coordinates(payload.lat, payload.lng)
    location_data = {
        "user_id": current_user.id, 
        "lat": new_lat, 
        "lng": new_lng,
        "geohash": compute_geohash(new_lat, new_lng),
        "is_visible": payload.visible,
        "last_seen": utcnow()
    }

    stmt = insert(UserLocation).values(location_data)
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=['user_id'],
        set_={k: v for k, v in location_data.items() if k != "user_id"}
    )

    await db.execute(upsert_stmt)
    await db.commit()
    return {'status': 'ok'}
    


@router.get("/nearby", response_model=list[NearbyUser])
async def get_nearby(current_user: User = Depends(get_current_user), 
                     radius_miles: float = 5, 
                     db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserLocation).where(UserLocation.user_id == current_user.id))
    user_location = result.scalar_one_or_none()

    if not user_location:
        raise HTTPException(status_code=404, detail="Location not set.")
    current_lat = user_location.lat
    current_lng = user_location.lng
    
    location_data = {"user_id": str(current_user.id), 
                     "lat": current_lat, 
                     "lng": current_lng, 
                     "radius_miles": radius_miles,
                     "visible": True}
    
    result = await db.execute(
        haversine_query(current_lat, current_lng, radius_miles),
        location_data
    )
    
    nearby_users = [NearbyUser(**row._mapping) for row in result]
    nearby_users = [user for user in nearby_users if user.user_id != current_user.id]
    return nearby_users


@router.delete("/me")
async def go_offline(current_user: User = Depends(get_current_user), 
                     db: AsyncSession = Depends(get_db)):    
    result = await db.execute(select(UserLocation).where(UserLocation.user_id == current_user.id))
    location = result.scalar_one_or_none()

    if not location:
        return {"status": "offline"}

    location.is_visible = False
    await db.commit()
    return {"status": "offline"}