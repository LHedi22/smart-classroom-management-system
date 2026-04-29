"""
Background recognition loop.

Runs at 2 fps while a session is active. Detects faces, records attendance,
and flags occupancy anomalies.

When FACE_RECOGNITION_ENABLED=false (stub mode), a lightweight async loop
emits a synthetic attendance event every 45 seconds for a randomly chosen
enrolled student so the WebSocket and frontend need no changes.
"""
import asyncio
import logging
import random
import time

from app.database import AsyncSessionLocal
from app.models.db_models import AttendanceRecord, AttendanceStatus
from app.services.event_queues import attendance_event_queue
from app.services.face_recognition_service import _FR_AVAILABLE, face_recognition_service

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 30
FRAME_INTERVAL = 0.5  # 2 fps
ANOMALY_THRESHOLD = 2  # alert if HOG count > face count + this value
STUB_INTERVAL = 45  # seconds between synthetic attendance events in stub mode

_loop_task: asyncio.Task | None = None
_stop_event = asyncio.Event()
_current_session_id: str | None = None
_current_room_id: str | None = None


# ─────────────────────────────────────────────────────────────────────────
# Attendance DB write
# ─────────────────────────────────────────────────────────────────────────

async def _record_attendance(session_id: str, student_id: str) -> None:
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
# Stub loop (FACE_RECOGNITION_ENABLED=false)
# ─────────────────────────────────────────────────────────────────────────

async def _stub_recognition_loop(session_id: str, room_id: str) -> None:
    """Emit a synthetic attendance event every STUB_INTERVAL seconds."""
    from sqlalchemy import select

    from app.models.db_models import Session as SessionModel, Student, course_students

    logger.info("[FACE_STUB] Stub recognition loop started for session %s", session_id)

    while not _stop_event.is_set():
        await asyncio.sleep(STUB_INTERVAL)
        if _stop_event.is_set():
            break

        try:
            async with AsyncSessionLocal() as db:
                session = await db.get(SessionModel, session_id)
                if session is None:
                    break

                students = (
                    await db.execute(
                        select(Student)
                        .join(course_students, Student.id == course_students.c.student_id)
                        .where(course_students.c.course_id == session.course_id)
                    )
                ).scalars().all()

            if not students:
                continue

            student = random.choice(students)
            event = {
                "type": "attendance",
                "room_id": room_id,
                "session_id": session_id,
                "student_id": str(student.id),
                "student_name": student.name,
                "confidence": 0.99,
                "status": "present",
            }
            try:
                attendance_event_queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        except Exception as exc:
            logger.warning("[FACE_STUB] Error in stub loop: %s", exc)

    logger.info("[FACE_STUB] Stub recognition loop stopped for session %s", session_id)


# ─────────────────────────────────────────────────────────────────────────
# Real recognition loop
# ─────────────────────────────────────────────────────────────────────────

async def _recognition_loop(session_id: str, room_id: str) -> None:
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

    last_marked: dict[str, float] = {}
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
                    continue

                last_marked[sid] = now

                task = asyncio.create_task(_record_attendance(session_id, sid))
                task.add_done_callback(_log_task_exc)

                if sid not in name_cache:
                    try:
                        from app.models.db_models import Student
                        async with AsyncSessionLocal() as _db:
                            student = await _db.get(Student, sid)
                            name_cache[sid] = student.name if student else sid
                    except Exception:
                        name_cache[sid] = sid

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

    if _FR_AVAILABLE:
        coro = _recognition_loop(session_id, room_id)
        name = f"recognition_loop_{session_id}"
    else:
        coro = _stub_recognition_loop(session_id, room_id)
        name = f"recognition_stub_{session_id}"

    _loop_task = asyncio.create_task(coro, name=name)
    logger.info(
        "%s task created for session %s room %s",
        "Recognition" if _FR_AVAILABLE else "Stub recognition",
        session_id,
        room_id,
    )


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
