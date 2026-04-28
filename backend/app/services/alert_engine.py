"""
Alert engine — runs periodic threshold checks and records alerts.

Uses APScheduler AsyncIOScheduler so jobs execute on the uvicorn event loop
without blocking request handling.
"""
import json
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import Alert, AlertType
from app.redis_client import (
    get_relay_state,
    get_sensor_latest,
    is_device_online,
    set_relay_state,
)
from app.services.event_queues import alert_event_queue

logger = logging.getLogger(__name__)


class AlertEngine:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        self._scheduler.add_job(
            self.check_thresholds,
            trigger="interval",
            seconds=30,
            id="check_thresholds",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self.retry_moodle_sync,
            trigger="interval",
            minutes=10,
            id="retry_moodle_sync",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("Alert engine started")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Alert engine stopped")

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _alert_exists(self, room_id: str, alert_type: AlertType) -> bool:
        """Return True if an unacknowledged alert of this type already exists."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Alert.id).where(
                    Alert.room_id == room_id,
                    Alert.type == alert_type,
                    Alert.acknowledged == False,  # noqa: E712
                ).limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def _create_alert(
        self,
        room_id: str,
        alert_type: AlertType,
        message: str,
        value: float | None = None,
    ) -> None:
        async with AsyncSessionLocal() as db:
            alert = Alert(
                room_id=room_id,
                type=alert_type,
                value=value,
                message=message,
            )
            db.add(alert)
            await db.commit()
            await db.refresh(alert)

        event = {
            "type": "alert",
            "alert_type": alert_type.value,
            "room_id": room_id,
            "message": message,
            "value": value,
        }
        try:
            alert_event_queue.put_nowait(event)
        except Exception:
            pass

    async def _auto_relay(self, room_id: str, device: str, action: str) -> None:
        """Publish MQTT + update Redis for auto-mode relay change."""
        from app.services.mqtt_bridge import publish_mqtt
        await set_relay_state(room_id, device, action)
        topic = f"classroom/{room_id}/relay/{device}"
        await publish_mqtt(topic, json.dumps({"action": action}))
        logger.info("Auto-control: room=%s device=%s → %s", room_id, device, action)

    # ── Scheduled job ─────────────────────────────────────────────────────

    async def check_thresholds(self) -> None:
        room_id = settings.room_id
        try:
            await self._check_room(room_id)
        except Exception as exc:
            logger.error("Alert engine check failed for %s: %s", room_id, exc)

    async def _check_room(self, room_id: str) -> None:
        sensors = await get_sensor_latest(room_id)

        # ── Temperature → auto AC control ─────────────────────────────────
        temp_entry = sensors.get("temperature")
        if temp_entry:
            temp = temp_entry["value"]
            ac_mode = await get_relay_state(room_id, "ac")

            if ac_mode == "auto":
                if temp > settings.temp_ac_on_threshold:
                    await self._auto_relay(room_id, "ac", "on")
                    if not await self._alert_exists(room_id, AlertType.temp_high):
                        await self._create_alert(
                            room_id,
                            AlertType.temp_high,
                            f"Temperature {temp:.1f}°C exceeds threshold "
                            f"({settings.temp_ac_on_threshold}°C) — AC turned on automatically",
                            value=temp,
                        )
                elif temp < settings.temp_ac_off_threshold:
                    await self._auto_relay(room_id, "ac", "off")
                    if not await self._alert_exists(room_id, AlertType.temp_low):
                        await self._create_alert(
                            room_id,
                            AlertType.temp_low,
                            f"Temperature {temp:.1f}°C below threshold "
                            f"({settings.temp_ac_off_threshold}°C) — AC turned off automatically",
                            value=temp,
                        )

        # ── Air quality alert ──────────────────────────────────────────────
        aq_entry = sensors.get("air_quality")
        if aq_entry:
            aq = aq_entry["value"]
            if aq > settings.air_quality_alert_threshold:
                if not await self._alert_exists(room_id, AlertType.air_quality_high):
                    await self._create_alert(
                        room_id,
                        AlertType.air_quality_high,
                        f"Air quality {aq:.0f} ppm exceeds threshold "
                        f"({settings.air_quality_alert_threshold} ppm)",
                        value=aq,
                    )

        # ── Device offline ─────────────────────────────────────────────────
        online = await is_device_online(room_id)
        if not online:
            if not await self._alert_exists(room_id, AlertType.device_offline):
                await self._create_alert(
                    room_id,
                    AlertType.device_offline,
                    f"ESP32 in {room_id} has not sent a heartbeat — device may be offline",
                )

    # ── Moodle retry job ──────────────────────────────────────────────────

    async def retry_moodle_sync(self) -> None:
        """Pop failed session IDs from the Redis retry queue and re-sync."""
        from app.services.moodle_client import moodle_client, pop_retry_queue

        session_ids = await pop_retry_queue(max_items=10)
        if not session_ids:
            return

        logger.info("Moodle retry job: processing %d queued sessions", len(session_ids))
        for session_id in session_ids:
            try:
                result = await moodle_client.sync_attendance(session_id)
                logger.info("Moodle retry result for %s: %s", session_id, result)
            except Exception as exc:
                logger.error("Moodle retry failed for session %s: %s", session_id, exc)

    # ── Called externally from recognition_loop ────────────────────────────

    async def record_attendance_anomaly(
        self, session_id: str, room_id: str, message: str
    ) -> None:
        await self._create_alert(
            room_id,
            AlertType.attendance_anomaly,
            message,
        )


alert_engine = AlertEngine()
