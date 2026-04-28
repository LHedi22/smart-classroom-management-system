"""
Moodle integration client.

All requests use the Moodle REST API:
  POST {MOODLE_URL}/webservice/rest/server.php
  params: wstoken, moodlewsrestformat=json, wsfunction=<function>

If Moodle is unreachable, the session_id is pushed to the Redis retry queue
"moodle:retry_queue" so the alert engine can retry later.
"""
import logging
from typing import Any

import httpx

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import AttendanceRecord, AttendanceStatus

logger = logging.getLogger(__name__)

# Moodle status codes for the attendance plugin
_STATUS_MAP: dict[AttendanceStatus, int] = {
    AttendanceStatus.present: 1,
    AttendanceStatus.absent:  2,
    AttendanceStatus.late:    3,
    AttendanceStatus.excused: 4,
}

_MOODLE_ENDPOINT = "/webservice/rest/server.php"


class MoodleClient:
    def __init__(self) -> None:
        self._base_url = settings.moodle_url.rstrip("/")
        self._token = settings.moodle_token
        # Single shared async client; created lazily
        self._client: httpx.AsyncClient | None = None

    # ── Internal helpers ──────────────────────────────────────────────────

    def _client_instance(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=10.0,
            )
        return self._client

    def _base_params(self, wsfunction: str) -> dict[str, str]:
        return {
            "wstoken": self._token,
            "moodlewsrestformat": "json",
            "wsfunction": wsfunction,
        }

    async def _call(self, wsfunction: str, **extra_params: Any) -> Any:
        """Make a Moodle REST API call and return the parsed JSON response."""
        params = {**self._base_params(wsfunction), **extra_params}
        client = self._client_instance()
        resp = await client.post(_MOODLE_ENDPOINT, params=params)
        resp.raise_for_status()
        data = resp.json()
        # Moodle embeds errors as {"exception": ..., "message": ...} with HTTP 200
        if isinstance(data, dict) and "exception" in data:
            raise RuntimeError(
                f"Moodle API error [{wsfunction}]: {data.get('message', data)}"
            )
        return data

    # ── Public API ────────────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        """Return True if Moodle is reachable and the token is valid."""
        try:
            await self._call("core_webservice_get_site_info")
            return True
        except Exception as exc:
            logger.warning("Moodle connection test failed: %s", exc)
            return False

    async def get_courses(self) -> list[dict]:
        """Return list of all courses from Moodle."""
        try:
            result = await self._call("core_course_get_courses")
            return result if isinstance(result, list) else []
        except Exception as exc:
            logger.error("get_courses failed: %s", exc)
            return []

    async def get_enrolled_users(self, course_id: int) -> list[dict]:
        """Return list of users enrolled in a Moodle course."""
        try:
            result = await self._call("core_enrol_get_enrolled_users", courseid=course_id)
            return result if isinstance(result, list) else []
        except Exception as exc:
            logger.error("get_enrolled_users failed for course %s: %s", course_id, exc)
            return []

    async def sync_attendance(self, session_id: str) -> dict:
        """
        Sync all attendance records for a session to Moodle.

        Maps our AttendanceStatus → Moodle status codes (1=present, 2=absent,
        3=late, 4=excused), calls mod_attendance_add_attendance, then marks
        all successfully-synced records with moodle_synced=True.

        On Moodle connection failure the session_id is pushed to the Redis
        retry queue "moodle:retry_queue" for later retry.
        """
        from sqlalchemy import select

        synced = 0
        failed = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.moodle_synced == False,  # noqa: E712
                )
            )
            records = list(result.scalars().all())

        if not records:
            logger.info("sync_attendance: no unsynced records for session %s", session_id)
            return {"synced": 0, "failed": 0, "session_id": session_id}

        # Build attendance payload for Moodle attendance plugin
        attendance_data: list[dict] = [
            {
                "studentid": r.student_id,
                "statusid": _STATUS_MAP.get(r.status, 2),
                "remarks": f"Synced from Smart Classroom — status: {r.status.value}",
            }
            for r in records
        ]

        try:
            # Moodle attendance plugin: mod_attendance_add_attendance
            # Parameters follow the plugin's external function signature.
            # We pass the session identifier and a flat list of student statuses.
            flat_params: dict[str, Any] = {
                "attendances[0][sessionid]": session_id,
            }
            for idx, entry in enumerate(attendance_data):
                flat_params[f"attendances[0][userdata][{idx}][studentid]"] = entry["studentid"]
                flat_params[f"attendances[0][userdata][{idx}][statusid]"] = entry["statusid"]
                flat_params[f"attendances[0][userdata][{idx}][remarks]"] = entry["remarks"]

            await self._call("mod_attendance_add_attendance", **flat_params)

            # Mark records synced
            record_ids = [r.id for r in records]
            async with AsyncSessionLocal() as db:
                from sqlalchemy import update
                await db.execute(
                    update(AttendanceRecord)
                    .where(AttendanceRecord.id.in_(record_ids))
                    .values(moodle_synced=True)
                )
                await db.commit()

            synced = len(records)
            logger.info("Moodle sync success: %d records for session %s", synced, session_id)

        except httpx.ConnectError as exc:
            logger.warning(
                "Moodle unreachable — queuing session %s for retry: %s", session_id, exc
            )
            await _push_retry_queue(session_id)
            failed = len(records)

        except Exception as exc:
            logger.error(
                "Moodle sync failed for session %s: %s", session_id, exc
            )
            await _push_retry_queue(session_id)
            failed = len(records)

        return {"synced": synced, "failed": failed, "session_id": session_id}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ── Redis retry queue helpers ──────────────────────────────────────────────

async def _push_retry_queue(session_id: str) -> None:
    try:
        from app.redis_client import get_redis_pool
        r = get_redis_pool()
        await r.rpush("moodle:retry_queue", session_id)
        logger.info("Pushed session %s to moodle:retry_queue", session_id)
    except Exception as exc:
        logger.error("Failed to push to retry queue: %s", exc)


async def pop_retry_queue(max_items: int = 10) -> list[str]:
    """Pop up to max_items session IDs from the retry queue."""
    try:
        from app.redis_client import get_redis_pool
        r = get_redis_pool()
        items = []
        for _ in range(max_items):
            val = await r.lpop("moodle:retry_queue")
            if val is None:
                break
            items.append(val)
        return items
    except Exception as exc:
        logger.error("Failed to read retry queue: %s", exc)
        return []


# ── Singleton ─────────────────────────────────────────────────────────────

moodle_client = MoodleClient()
