"""
Background recognition loop.

Runs at 2 fps while a session is active. Detects faces, records attendance,
and flags occupancy anomalies.
"""
import asyncio
import logging
import time

from app.database import AsyncSessionLocal
from app.models.db_models import AttendanceRecord, AttendanceStatus
from app.services.event_queues import attendance_event_queue
from app.services.face_recognition_service import face_recognition_service

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 30
FRAME_INTERVAL = 0.5  # 2 fps
ANOMALY_THRESHOLD = 2  # alert if HOG count > face count + this value

_loop_task: asyncio.Task | None = None
_stop_event = asyncio.Event()
_current_session_id: str | None = None
_current_room_id: str | None = None


# ─────────────────────────────────────────────────────────────────────────
# Attendance DB write
# ─────────────────────────────────────────────────────────────────────────

async def _record_attendance(session_id: str, student_id: str) -> None:
    from app.models.db_models import Student
    async with AsyncSessionLocal() as db:
        record = AttendanceRecord(
            session_id=session_id,
            student_id=student_id,
            status=AttendanceStatus.present,
        )
        db.add(record)
        await db.commit()


def _log_task_exc(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        logger.error("Attendance DB write failed: %s", task.exception())


# ─────────────────────────────────────────────────────────────────────────
# Core loop
# ─────────────────────────────────────────────────────────────────────────

async def _recognition_loop(session_id: str, room_id: str) -> None:
    # Import cv2 lazily — may not be available on all platforms
    try:
        import cv2  # type: ignore[import]
    except ImportError:
        logger.warning("OpenCV not available — recognition loop cannot run")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.warning("Camera not available (VideoCapture(0) failed) — recognition loop skipped")
        return

    logger.info("Recognition loop started for session %s", session_id)

    # cooldown tracker: {student_id: last_marked_ts}
    last_marked: dict[str, float] = {}
    # name cache to avoid repeated DB lookups per frame
    name_cache: dict[str, str] = {}

    try:
        while not _stop_event.is_set():
            frame_start = time.monotonic()

            ret, frame = cap.read()
            if not ret:
                logger.warning("Camera read failed — skipping frame")
                await asyncio.sleep(FRAME_INTERVAL)
                continue

            # ── Face recognition ──────────────────────────────────────
            matches = face_recognition_service.recognize_faces(frame)
            recognized_count = sum(1 for m in matches if m["student_id"] != "UNKNOWN")

            now = time.time()
            for match in matches:
                sid = match["student_id"]
                if sid == "UNKNOWN":
                    continue

                last_ts = last_marked.get(sid, 0.0)
                if now - last_ts < COOLDOWN_SECONDS:
                    continue  # still in cooldown

                last_marked[sid] = now

                # Fire-and-forget DB write
                task = asyncio.create_task(_record_attendance(session_id, sid))
                task.add_done_callback(_log_task_exc)

                # Resolve student name (cached after first lookup)
                if sid not in name_cache:
                    try:
                        from app.models.db_models import Student
                        async with AsyncSessionLocal() as _db:
                            student = await _db.get(Student, sid)
                            name_cache[sid] = student.name if student else sid
                    except Exception:
                        name_cache[sid] = sid

                # Push event to WebSocket queue
                event = {
                    "type": "attendance",
                    "room_id": room_id,
                    "session_id": session_id,
                    "student_id": sid,
                    "student_name": name_cache[sid],
                    "confidence": match["confidence"],
                    "status": "present",
                }
                try:
                    attendance_event_queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

            # ── Occupancy anomaly check ───────────────────────────────
            hog_count = face_recognition_service.count_heads(frame)
            if hog_count > recognized_count + ANOMALY_THRESHOLD:
                msg = (
                    f"Occupancy mismatch: ~{hog_count} people detected, "
                    f"{recognized_count} recognized"
                )
                try:
                    from app.services.alert_engine import alert_engine
                    asyncio.create_task(
                        alert_engine.record_attendance_anomaly(session_id, room_id, msg)
                    )
                except Exception:
                    pass

            # ── Pace to ~2 fps ────────────────────────────────────────
            elapsed = time.monotonic() - frame_start
            sleep_time = max(0.0, FRAME_INTERVAL - elapsed)
            await asyncio.sleep(sleep_time)

    finally:
        cap.release()
        logger.info("Recognition loop stopped for session %s", session_id)


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

async def start_recognition(session_id: str, room_id: str = "room1") -> None:
    global _loop_task, _current_session_id, _current_room_id

    if _loop_task is not None and not _loop_task.done():
        logger.warning("Recognition loop already running — stopping previous session first")
        await stop_recognition()

    _stop_event.clear()
    _current_session_id = session_id
    _current_room_id = room_id
    _loop_task = asyncio.create_task(
        _recognition_loop(session_id, room_id), name=f"recognition_loop_{session_id}"
    )
    logger.info("Recognition loop task created for session %s room %s", session_id, room_id)


async def stop_recognition() -> None:
    global _loop_task, _current_session_id, _current_room_id

    _stop_event.set()
    if _loop_task is not None and not _loop_task.done():
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    _loop_task = None
    _current_session_id = None
    _current_room_id = None
    logger.info("Recognition loop stopped")
