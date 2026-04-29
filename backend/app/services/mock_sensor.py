"""
Mock sensor publisher — activated when MOCK_MODE=true.

Registers two APScheduler jobs on the shared AlertEngine scheduler:
  - Every 5s: publish drifting sensor values to the four sensor MQTT topics
  - Every 30s: publish a heartbeat to classroom/{room_id}/status

Uses a single ephemeral aiomqtt client per job invocation (same pattern as
publish_mqtt in mqtt_bridge.py) so it never interferes with the subscriber loop.
"""
import json
import logging
import math
import random
import time

import aiomqtt as mqtt

from app.config import settings

logger = logging.getLogger(__name__)


async def _publish_sensors(room_id: str) -> None:
    t = time.time()
    ts = int(t)

    readings = [
        (
            f"classroom/{room_id}/sensors/temperature",
            {
                "value": round(22 + 5 * abs(math.sin(t / 60)) + random.uniform(-0.3, 0.3), 1),
                "unit": "C",
                "ts": ts,
            },
        ),
        (
            f"classroom/{room_id}/sensors/humidity",
            {
                "value": round(50 + 10 * abs(math.sin(t / 90)) + random.uniform(-1, 1), 1),
                "unit": "%",
                "ts": ts,
            },
        ),
        (
            f"classroom/{room_id}/sensors/air_quality",
            {
                "value": round(250 + 150 * abs(math.sin(t / 120)) + random.uniform(-10, 10), 0),
                "unit": "ppm",
                "ts": ts,
            },
        ),
        (
            f"classroom/{room_id}/sensors/sound",
            {
                "value": 1 if random.random() < 0.7 else 0,
                "unit": "bool",
                "ts": ts,
            },
        ),
    ]

    try:
        async with mqtt.Client(
            hostname=settings.mqtt_broker_host,
            port=settings.mqtt_broker_port,
            keepalive=10,
        ) as client:
            for topic, payload in readings:
                await client.publish(topic, json.dumps(payload))
    except Exception as exc:
        logger.warning("[MOCK] Sensor publish failed: %s", exc)


async def _publish_heartbeat(room_id: str) -> None:
    ts = int(time.time())
    try:
        async with mqtt.Client(
            hostname=settings.mqtt_broker_host,
            port=settings.mqtt_broker_port,
            keepalive=10,
        ) as client:
            await client.publish(
                f"classroom/{room_id}/status",
                json.dumps({"online": True, "ts": ts}),
            )
    except Exception as exc:
        logger.warning("[MOCK] Heartbeat publish failed: %s", exc)


def start_mock_publisher(scheduler, room_id: str) -> None:
    """Register mock sensor and heartbeat jobs on an already-started scheduler."""
    scheduler.add_job(
        _publish_sensors,
        trigger="interval",
        seconds=5,
        args=[room_id],
        id="mock_sensor_publish",
        replace_existing=True,
    )
    scheduler.add_job(
        _publish_heartbeat,
        trigger="interval",
        seconds=30,
        args=[room_id],
        id="mock_heartbeat_publish",
        replace_existing=True,
    )
    logger.info("[MOCK] Mock sensor publisher started for room %s", room_id)
