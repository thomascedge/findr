import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from sqlalchemy import select

from app.core.security import decode_token
from app.core.redis import get_redis
from app.core.presence import (
    set_presence, remove_presence, refresh_ttl,
    get_nearby_from_redis, get_pubsub_channel
)
from app.core.location import compute_geohash, fuzz_coordinates
from app.db import AsyncSessionLocal
from app.models.models import User

router = APIRouter(tags=["ws"])


@router.websocket("/ws/map")
async def map_websocket(websocket: WebSocket, token: str = Query(...)):
    """Real-time map presence WebSocket endpoint."""

    try:
        user_id = decode_token(token)
    except HTTPException:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await websocket.close(code=4004)
            return
        username = user.username

    await websocket.accept()

    redis = await get_redis()
    pubsub = redis.pubsub()

    current_channel = None
    listener_task = None

    async def _listen_pubsub(channel: str):
        """Subscribes to a Redis pub/sub channel and forwards messages to the WebSocket."""
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    try:
        async for data in websocket.iter_text():
            msg = json.loads(data)
            event = msg.get("event")
            payload = msg.get("payload", {})

            if event == "location_update":
                lat, lng = fuzz_coordinates(payload["lat"], payload["lng"])
                geohash = compute_geohash(lat, lng)
                visible = payload.get("visible", True)
                await set_presence(user_id, username, lat, lng, geohash, visible)

                new_channel = get_pubsub_channel(geohash)
                if new_channel != current_channel:
                    if current_channel:
                        await pubsub.unsubscribe(current_channel)
                    current_channel = new_channel
                    if listener_task:
                        listener_task.cancel()
                    listener_task = asyncio.create_task(_listen_pubsub(new_channel))

                nearby = await get_nearby_from_redis(lat, lng, geohash, user_id)
                await websocket.send_text(json.dumps({"event": "map_snapshot", "payload": {"users": nearby}}))

            elif event == "heartbeat":
                await refresh_ttl(user_id)

    except WebSocketDisconnect:
        await remove_presence(user_id)
        if listener_task:
            listener_task.cancel()
        if current_channel:
            await pubsub.unsubscribe(current_channel)
        await pubsub.aclose()