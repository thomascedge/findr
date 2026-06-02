import math
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional

from app.db import get_db
from app.core.security import get_current_user
from app.models.models import User, UserLocation
from app.schemas.schemas import UserSearchResult

router = APIRouter(prefix="/search", tags=["search"])


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Returns the distance in miles between two lat/lng coordinates."""
    R = 3958.8  # Earth radius in miles
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


@router.get("/users", response_model=list[UserSearchResult])
async def search_users(
    q: Optional[str] = Query(
        default=None, description="Username or bio keyword search"
    ),
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_miles: float = 5.0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for active users by username/bio keyword and/or proximity.
    TODO: Architected to swap to Elasticsearch later — keep all query logic here.

    Filters applied in order:
    - is_active = True, excludes current user
    - If q provided: case-insensitive ilike match on username OR bio
    - If lat/lng provided: Haversine distance filter in Python
    """
    # Base query — active users excluding current user
    stmt = select(User).where(
        User.is_active == True,
        User.id != current_user.id,
    )

    # Keyword filter on username OR bio
    if q:
        stmt = stmt.where(
            or_(
                User.username.ilike(f"%{q}%"),
                User.bio.ilike(f"%{q}%"),
            )
        )

    result = await db.execute(stmt)
    users = result.scalars().all()

    # Location filter — apply in Python for now, move to DB subquery at scale
    if lat is not None and lng is not None:
        # Fetch all user locations in one query
        user_ids = [u.id for u in users]
        loc_result = await db.execute(
            select(UserLocation).where(UserLocation.user_id.in_(user_ids))
        )
        locations = {loc.user_id: loc for loc in loc_result.scalars().all()}

        filtered = []
        for user in users:
            loc = locations.get(user.id)
            if not loc:
                continue
            distance = _haversine_miles(lat, lng, loc.lat, loc.lng)
            if distance <= radius_miles:
                filtered.append((user, distance))

        return [
            UserSearchResult(
                id=user.id,
                username=user.username,
                bio=user.bio,
                distance_miles=round(distance, 2),
            )
            for user, distance in sorted(filtered, key=lambda x: x[1])
        ]

    # No location filter — return all keyword matches without distance
    return [
        UserSearchResult(
            id=user.id,
            username=user.username,
            bio=user.bio,
            distance_miles=None,
        )
        for user in users
    ]
