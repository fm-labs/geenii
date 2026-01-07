import redis
from redis import asyncio as aioredis

from geenii import settings

aio_redis_global = aioredis.Redis | None
redis_global = redis.Redis | None

def get_global_aioredis_client() -> aioredis.Redis:
    global aio_redis_global
    if aio_redis_global is None:
        aio_redis_global = get_aioredis_client()
    return aio_redis_global


def get_aioredis_client(redis_url=settings.REDIS_URI) -> aioredis.Redis:
    if not redis_url:
        raise ValueError("REDIS_URI must be set in environment variables.")
    return aioredis.from_url(redis_url, decode_responses=True)


def get_global_redis_client() -> redis.Redis:
    global redis_global
    if redis_global is None:
        redis_global = get_redis_client()
    return redis_global


def get_redis_client(redis_url=settings.REDIS_URI) -> redis.Redis:
    if not redis_url:
        raise ValueError("REDIS_URI must be set in environment variables.")

    return redis.from_url(redis_url, decode_responses=True)