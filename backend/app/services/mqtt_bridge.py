import asyncio
import json
import logging

import aiomqtt as mqtt

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import SensorReading, SensorType
from app.redis_client import set_device_online, set_sensor_latest
from app.services.event_queues import sensor_event_queue  # noqa: F401 – re-exported for compat

logger = logging.getLogger(__name__)

_bridge_task: asyncio.Task | None = None
_stop_event: asyncio.Event = asyncio.Event()


# ─────────────────────────────────────────────────────────────────────────
# DB write — fire-and-forget helper
# ─────────────────────────────────────────────────────────────────────────

async def _persist_sensor(room_id: str, sensor_type: str, value: float, unit: str) -> None:
    try:
        sensor_enum = SensorType(sensor_type)
    except ValueError:
        logger.warning("Unknown sensor type: %s", sensor_type)
        return

    async with AsyncSessionLocal() as session:
        record = SensorReading(
            room_id=room_id,
            sensor_type=sensor_enum,
            value=value,
            unit=unit,
        )
        session.add(record)
        await session.commit()


def _log_task_exception(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.error("DB persist task failed: %s", task.exception())


# ─────────────────────────────────────────────────────────────────────────
# Message handlers
# ─────────────────────────────────────────────────────────────────────────

async def _handle_sensor(topic: str, payload: str) -> None:
    """classroom/<room_id>/sensors/<type>"""
    parts = topic.split("/")
    if len(parts) < 4:
        return

    room_id = parts[1]
    sensor_type = parts[3]

    try:
        data = json.loads(payload)
        value = float(data["value"])
        unit = str(data.get("unit", ""))
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Bad sensor payload on %s: %s — %s", topic, payload, exc)
        return

    # 1. Redis cache
    await set_sensor_latest(room_id, sensor_type, value, unit)

    # 2. PostgreSQL — fire and forget
    task = asyncio.create_task(_persist_sensor(room_id, sensor_type, value, unit))
    task.add_done_callback(_log_task_exception)

    # 3. WebSocket event queue (non-blocking put)
    event = {"type": "sensor", "room_id": room_id, "sensor_type": sensor_type, "value": value, "unit": unit}
    try:
        sensor_event_queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.debug("sensor_event_queue full — dropping event")


async def _handle_status(topic: str, payload: str) -> None:
    """classroom/<room_id>/status"""
    parts = topic.split("/")
    if len(parts) < 3:
        return

    room_id = parts[1]
    try:
        data = json.loads(payload)
        online = bool(data.get("online", False))
    except json.JSONDecodeError:
        return

    if online:
        await set_device_online(room_id, ttl_seconds=60)
        logger.debug("Device %s heartbeat", room_id)


# ─────────────────────────────────────────────────────────────────────────
# Main bridge loop with exponential backoff
# ─────────────────────────────────────────────────────────────────────────

async def _bridge_loop() -> None:
    backoff = 1.0
    max_backoff = 60.0

    while not _stop_event.is_set():
        try:
            logger.info(
                "MQTT bridge connecting to %s:%s",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
            )
            async with mqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
                keepalive=30,
            ) as client:
                backoff = 1.0  # reset on successful connect
                logger.info("MQTT bridge connected")

                await client.subscribe("classroom/+/sensors/#")
                await client.subscribe("classroom/+/status")

                async for message in client.messages:
                    if _stop_event.is_set():
                        break

                    topic = str(message.topic)
                    payload = message.payload.decode("utf-8", errors="replace")

                    if "/sensors/" in topic:
                        await _handle_sensor(topic, payload)
                    elif topic.endswith("/status"):
                        await _handle_status(topic, payload)

        except mqtt.MqttError as exc:
            if _stop_event.is_set():
                break
            logger.warning("MQTT connection lost: %s — retry in %.0fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except Exception as exc:
            if _stop_event.is_set():
                break
            logger.error("Unexpected MQTT bridge error: %s — retry in %.0fs", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    logger.info("MQTT bridge stopped")


# ─────────────────────────────────────────────────────────────────────────
# Public lifecycle API
# ─────────────────────────────────────────────────────────────────────────

async def start_mqtt_bridge() -> None:
    global _bridge_task
    _stop_event.clear()
    _bridge_task = asyncio.create_task(_bridge_loop(), name="mqtt_bridge")
    logger.info("MQTT bridge task started")


async def stop_mqtt_bridge() -> None:
    _stop_event.set()
    if _bridge_task is not None and not _bridge_task.done():
        _bridge_task.cancel()
        try:
            await _bridge_task
        except asyncio.CancelledError:
            pass
    logger.info("MQTT bridge task stopped")


async def publish_mqtt(topic: str, payload: str) -> None:
    """Publish a single MQTT message using a short-lived client connection."""
    try:
        async with mqtt.Client(
            hostname=settings.mqtt_broker_host,
            port=settings.mqtt_broker_port,
            keepalive=10,
        ) as client:
            await client.publish(topic, payload)
            logger.debug("MQTT published %s → %s", topic, payload)
    except Exception as exc:
        logger.warning("MQTT publish failed for %s: %s", topic, exc)
