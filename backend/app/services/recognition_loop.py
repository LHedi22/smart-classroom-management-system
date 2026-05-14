"""
Background recognition loop — snapshot-per-cycle model.

Every CYCLE_DURATION seconds the camera scans the room at RECOGNITION_FPS,
accumulating the set of recognised student IDs. At the end of each cycle a
single transaction evaluates every enrolled student:

  detected this cycle  →  absent  → present  (if not manually adjusted)
  not detected         →  present → absent   (if not manually adjusted)

Manual professor adjustments (adjusted_by IS NOT NULL) are never overwritten.

Stub mode (FACE_RECOGNITION_ENABLED=false): every cycle randomly picks ~70 %
of enrolled students as "seen" so the bidirectional logic is fully exercised.
"""
import asyncio
import logging
import random
import time

from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    Session as SessionModel,
    SessionStatus,
    Student,
    course_students,
)
from app.services.event_queues import attendance_event_queue
from app.services.face_recognition_service import _FR_AVAILABLE, face_recognition_service

logger = logging.getLogger(__name__)

FRAME_INTERVAL = 1.0 / settings.recognition_fps
ANOMALY_THRESHOLD = 2

_loop_task: asyncio.Task | None = None
_stop_event = asyncio.Event()
_current_session_id: str | None = None
_current_room_id: str | None = None
_seen_this_cycle: set[str] = set()


# ─────────────────────────────────────────────────────────────────────────
# Public getter — exposes partial-cycle state for final evaluation on end
# ─────────────────────────────────────────────────────────────────────────

def get_current_seen_ids() -> set[str]:
    """Snapshot of faces seen in the current (possibly partial) scan cycle."""
    return set(_seen_this_cycle)


# ─────────────────────────────────────────────────────────────────────────
# Core evaluation — one transaction per cycle
# ─────────────────────────────────────────────────────────────────────────

async def _run_cycle_evaluation(session_id: str, seen_ids: set[str]) -> None:
    """
    Batch-update attendance for every enrolled student based on seen_ids.

    - absent → present: students in seen_ids whose record is 'absent'
    - present → absent: students not in seen_ids whose record is 'present'
    - Records where adjusted_by IS NOT NULL are never touched.
    """
    async with AsyncSessionLocal() as db:
        session = await db.get(SessionModel, session_id)
        if session is None or session.status != SessionStatus.active:
            return

        enrolled_rows = (
            await db.execute(
                select(course_students.c.student_id)
                .where(course_students.c.course_id == session.course_id)
            )
        ).scalars().all()

        if not enrolled_rows:
            return

        enrolled_set = {str(sid) for sid in enrolled_rows}
        present_ids = [sid for sid in enrolled_set if sid in seen_ids]
        absent_ids  = [sid for sid in enrolled_set if sid not in seen_ids]

        if present_ids:
            await db.execute(
                update(AttendanceRecord)
                .where(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.student_id.in_(present_ids),
                    AttendanceRecord.status == AttendanceStatus.absent,
                    AttendanceRecord.adjusted_by.is_(None),
                )
                .values(status=AttendanceStatus.present, detected_at=func.now())
            )

        if absent_ids:
            await db.execute(
                update(AttendanceRecord)
                .where(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.student_id.in_(absent_ids),
                    AttendanceRecord.status == AttendanceStatus.present,
                    AttendanceRecord.adjusted_by.is_(None),
                )
                .values(status=AttendanceStatus.absent)
            )

        await db.commit()
        logger.info(
            "[CYCLE] session=%s  seen=%d  present_flipped=%d  absent_flipped=%d",
            session_id, len(seen_ids), len(present_ids), len(absent_ids),
        )


# ─────────────────────────────────────────────────────────────────────────
# WS event helper
# ─────────────────────────────────────────────────────────────────────────

def _emit_ws_event(
    room_id: str,
    session_id: str,
    student_id: str,
    student_name: str,
    confidence: float,
) -> None:
    try:
        attendance_event_queue.put_nowait({
            "type": "attendance",
            "room_id": room_id,
            "session_id": session_id,
            "student_id": student_id,
            "student_name": student_name,
            "confidence": confidence,
            "status": "present",
        })
    except asyncio.QueueFull:
        pass


# ─────────────────────────────────────────────────────────────────────────
# Stub loop (FACE_RECOGNITION_ENABLED=false)
# ─────────────────────────────────────────────────────────────────────────

async def _stub_recognition_loop(session_id: str, room_id: str) -> None:
    """Simulate attendance fluctuation — ~70 % present per cycle, ±2 variance."""
    global _seen_this_cycle
    logger.info("[FACE_STUB] Stub loop started for session %s", session_id)

    while not _stop_event.is_set():
        _seen_this_cycle = set()

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

            if students:
                n = max(0, round(len(students) * 0.7) + random.randint(-2, 2))
                chosen = random.sample(students, min(n, len(students)))
                _seen_this_cycle = {str(s.id) for s in chosen}

                await _run_cycle_evaluation(session_id, _seen_this_cycle)

                for student in chosen:
                    _emit_ws_event(room_id, session_id, str(student.id), student.name, 0.99)

        except Exception as exc:
            logger.warning("[FACE_STUB] Error in stub cycle: %s", exc)

        # Wait for next cycle; exit immediately if stop is signalled
        try:
            await asyncio.wait_for(
                _stop_event.wait(), timeout=settings.attendance_cycle_duration
            )
            break
        except asyncio.TimeoutError:
            pass

    _seen_this_cycle = set()
    logger.info("[FACE_STUB] Stub loop stopped for session %s", session_id)


# ─────────────────────────────────────────────────────────────────────────
# Real recognition loop
# ─────────────────────────────────────────────────────────────────────────

async def _recognition_loop(session_id: str, room_id: str) -> None:
    global _seen_this_cycle

    try:
        import cv2  # type: ignore[import]
    except ImportError:
        logger.warning("OpenCV not available — recognition loop cannot run")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.warning("Camera not available — recognition loop skipped")
        return

    logger.info("Recognition loop started for session %s", session_id)
    name_cache: dict[str, str] = {}

    try:
        while not _stop_event.is_set():
            _seen_this_cycle = set()
            cycle_deadline = time.monotonic() + settings.attendance_cycle_duration

            # ── SCAN phase ────────────────────────────────────────────────
            while time.monotonic() < cycle_deadline and not _stop_event.is_set():
                frame_start = time.monotonic()

                ret, frame = cap.read()
                if not ret:
                    logger.warning("Camera read failed — skipping frame")
                    await asyncio.sleep(FRAME_INTERVAL)
                    continue

                matches = face_recognition_service.recognize_faces(frame)
                recognized_count = sum(1 for m in matches if m["student_id"] != "UNKNOWN")

                for match in matches:
                    sid = match["student_id"]
                    if sid == "UNKNOWN":
                        continue
                    if sid not in _seen_this_cycle:
                        _seen_this_cycle.add(sid)
                        if sid not in name_cache:
                            try:
                                async with AsyncSessionLocal() as _db:
                                    student = await _db.get(Student, sid)
                                    name_cache[sid] = student.name if student else sid
                            except Exception:
                                name_cache[sid] = sid
                        _emit_ws_event(
                            room_id, session_id, sid, name_cache[sid], match["confidence"]
                        )

                # Occupancy anomaly check
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

                await asyncio.sleep(max(0.0, FRAME_INTERVAL - (time.monotonic() - frame_start)))

            # ── EVALUATE phase ─────────────────────────────────────────────
            if not _stop_event.is_set():
                await _run_cycle_evaluation(session_id, _seen_this_cycle)

    finally:
        _seen_this_cycle = set()
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
