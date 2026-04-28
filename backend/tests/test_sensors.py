"""
Tests for the sensors API.

Redis is mocked — these tests run without a live Redis instance.
Sensor history is written directly to the in-memory SQLite test DB.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.db_models import SensorReading, SensorType

pytestmark = pytest.mark.asyncio


# ── /api/sensors/latest ───────────────────────────────────────────────────

async def test_latest_returns_correct_structure(client: AsyncClient) -> None:
    mock_sensors = {
        "temperature": {"value": 24.5, "unit": "C"},
        "humidity": {"value": 62.0, "unit": "%"},
    }
    with patch("app.api.sensors.get_sensor_latest", new_callable=AsyncMock, return_value=mock_sensors):
        resp = await client.get("/api/sensors/latest?room_id=room1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["room_id"] == "room1"
    assert "sensors" in data
    assert data["sensors"]["temperature"]["value"] == 24.5
    assert data["sensors"]["humidity"]["unit"] == "%"


async def test_latest_empty_when_redis_has_no_data(client: AsyncClient) -> None:
    with patch("app.api.sensors.get_sensor_latest", new_callable=AsyncMock, return_value={}):
        resp = await client.get("/api/sensors/latest?room_id=room_empty")
    assert resp.status_code == 200
    assert resp.json()["sensors"] == {}


async def test_latest_defaults_to_room1(client: AsyncClient) -> None:
    with patch("app.api.sensors.get_sensor_latest", new_callable=AsyncMock, return_value={}) as mock_fn:
        resp = await client.get("/api/sensors/latest")
    assert resp.status_code == 200
    assert resp.json()["room_id"] == "room1"


async def test_latest_graceful_on_redis_error(client: AsyncClient) -> None:
    async def _raise(*_a, **_kw):
        raise ConnectionError("Redis down")

    with patch("app.api.sensors.get_sensor_latest", side_effect=_raise):
        resp = await client.get("/api/sensors/latest?room_id=room1")
    # Endpoint catches the exception and returns empty sensors dict
    assert resp.status_code == 200
    assert resp.json()["sensors"] == {}


# ── /api/sensors/history ─────────────────────────────────────────────────

async def _insert_reading(
    test_engine,
    room_id: str,
    sensor_type: SensorType,
    value: float,
    unit: str,
    recorded_at: datetime | None = None,
) -> SensorReading:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as db:
        reading = SensorReading(
            room_id=room_id,
            sensor_type=sensor_type,
            value=value,
            unit=unit,
        )
        if recorded_at is not None:
            reading.recorded_at = recorded_at
        db.add(reading)
        await db.commit()
        await db.refresh(reading)
        return reading


async def test_history_returns_correct_records(client: AsyncClient, test_engine) -> None:
    await _insert_reading(test_engine, "room_hist", SensorType.temperature, 25.0, "C")
    await _insert_reading(test_engine, "room_hist", SensorType.humidity, 55.0, "%")

    resp = await client.get("/api/sensors/history?room_id=room_hist")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) >= 2
    types = {r["sensor_type"] for r in records}
    assert "temperature" in types
    assert "humidity" in types


async def test_history_filters_by_sensor_type(client: AsyncClient, test_engine) -> None:
    await _insert_reading(test_engine, "room_type_filter", SensorType.temperature, 30.0, "C")
    await _insert_reading(test_engine, "room_type_filter", SensorType.air_quality, 420.0, "ppm")

    resp = await client.get("/api/sensors/history?room_id=room_type_filter&sensor_type=temperature")
    assert resp.status_code == 200
    records = resp.json()
    assert all(r["sensor_type"] == "temperature" for r in records)


async def test_history_respects_date_filters(client: AsyncClient, test_engine) -> None:
    early = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    late = datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

    await _insert_reading(test_engine, "room_dates", SensorType.temperature, 20.0, "C", recorded_at=early)
    await _insert_reading(test_engine, "room_dates", SensorType.temperature, 35.0, "C", recorded_at=late)

    # Ask only for readings after May 2024
    resp = await client.get(
        "/api/sensors/history?room_id=room_dates&from_ts=2024-05-01T00:00:00Z"
    )
    assert resp.status_code == 200
    values = [r["value"] for r in resp.json()]
    assert 35.0 in values
    assert 20.0 not in values


async def test_history_empty_for_unknown_room(client: AsyncClient) -> None:
    resp = await client.get("/api/sensors/history?room_id=no_such_room_xyz")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Redis round-trip (unit test for redis_client helpers) ─────────────────

async def test_redis_set_and_get_sensor() -> None:
    """Verify the JSON serialization round-trip for set/get_sensor_latest."""
    import json
    from unittest.mock import AsyncMock, MagicMock, patch

    fake_redis = MagicMock()
    fake_redis.set = AsyncMock()
    fake_redis.mget = AsyncMock(
        return_value=[
            json.dumps({"value": 24.5, "unit": "C"}),
            None,
            None,
            None,
        ]
    )

    with patch("app.redis_client.get_redis_pool", return_value=fake_redis):
        from app.redis_client import get_sensor_latest, set_sensor_latest

        await set_sensor_latest("room1", "temperature", 24.5, "C")
        fake_redis.set.assert_called_once()

        result = await get_sensor_latest("room1")
        assert result["temperature"]["value"] == 24.5
        assert result["temperature"]["unit"] == "C"
        assert "humidity" not in result
