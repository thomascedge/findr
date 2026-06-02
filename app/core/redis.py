import redis.asyncio as aioredis
import os

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
    return _redis


async def close_redis():
    if _redis:
        await _redis.aclose()
