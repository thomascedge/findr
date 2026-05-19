import json
from app.core.redis import get_redis

PRESENCE_TTL = 180          # 3 min
HEARTBEAT_INTERVAL = 60     # 60 sec



def _geohash_channel(geohash: str) -> str:
    """Returns the pub/sub channel name for a given geohash prefix"""
    return f"map:{geohash[:5]}"


async def set_presence(user_id: str, username: str, lat: float, lng: float, geohash: str, visible: bool = True):
    """Writes or updates a user's presence in Redis"""
    redis = await get_redis()
    channel = _geohash_channel(geohash)
    key = f"presence:{user_id}"

    # delete key as user is offline
    if not visible:
        await redis.publish(channel, json.dumps({"event": "user_left", "user_id": user_id}))
        await redis.delete(key)

    # write to redis
    else:
        await redis.hset(key, mapping={"lat": lat, "lng": lng, "geohash": geohash, "username": username})
        await redis.expire(key, PRESENCE_TTL)
        await redis.publish(channel, json.dumps({'event': 'user_joined', 'user_id': user_id, "username": username, "lat": lat, "lng": lng}))


async def remove_presence(user_id: str):
    """Removes a user from Redis presence and notifies their channel."""
    redis = await get_redis()
    key = f"presence:{user_id}"

    hash = await redis.hgetall(key)
    if "geohash" not in hash.keys():
        return
    
    geohash = hash['geohash']
    channel = _geohash_channel(geohash)

    await redis.publish(channel, json.dumps({"event": "user_left", "user_id": user_id}))
    await redis.delete(key)


async def refresh_ttl(user_id: str):
    """Resets the TTL on a user's presence key without a full write"""
    redis = await get_redis()
    await redis.expire(f'presence:{user_id}', PRESENCE_TTL)


async def get_nearby_from_redis(lat: float, lng: float, geohash: str, exclude_user_id: str) -> list[dict]:
    """Returns nearby active users from Redis"""
    redis = await get_redis()
    keys = await redis.keys("presence:*")
    nearby_users = []
    excluded_user = f"presence:{exclude_user_id}"

    for key in keys:
        user = await redis.hgetall(key)

        if not user or key == excluded_user or user["geohash"][:4] != geohash[:4]:
            continue
        else:
            nearby_users.append({
                "user_id": key.replace("presence:", ""),
                "username": user["username"],
                "lat": float(user["lat"]),
                "lng": float(user["lng"]),
            })

    return nearby_users


async def get_pubsub_channel(geohash: str) -> str:
    """Returns the pub/sub channel for a given geohash"""
    return _geohash_channel(geohash)
