import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_redis_pool: aioredis.Redis | None = None


def get_redis_pool() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    yield get_redis_pool()


async def set_sensor_latest(
    room_id: str,
    sensor_type: str,
    value: float,
    unit: str,
) -> None:
    r = get_redis_pool()
    key = f"classroom:{room_id}:sensors:{sensor_type}"
    payload = json.dumps({"value": value, "unit": unit})
    await r.set(key, payload, ex=300)  # 5-minute TTL


async def get_sensor_latest(room_id: str) -> dict[str, Any]:
    r = get_redis_pool()
    sensor_types = ["temperature", "humidity", "air_quality", "sound"]
    result: dict[str, Any] = {}

    keys = [f"classroom:{room_id}:sensors:{t}" for t in sensor_types]
    values = await r.mget(keys)

    for sensor_type, raw in zip(sensor_types, values):
        if raw is not None:
            result[sensor_type] = json.loads(raw)

    return result


async def set_device_online(room_id: str, ttl_seconds: int = 60) -> None:
    r = get_redis_pool()
    await r.set(f"classroom:{room_id}:online", "1", ex=ttl_seconds)


async def is_device_online(room_id: str) -> bool:
    r = get_redis_pool()
    return await r.exists(f"classroom:{room_id}:online") == 1


async def set_relay_state(room_id: str, device: str, action: str) -> None:
    r = get_redis_pool()
    await r.set(f"classroom:{room_id}:relay:{device}", action)


async def get_relay_state(room_id: str, device: str) -> str:
    r = get_redis_pool()
    val = await r.get(f"classroom:{room_id}:relay:{device}")
    return val if val is not None else "auto"


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
