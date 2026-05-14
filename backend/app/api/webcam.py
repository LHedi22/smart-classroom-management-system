"""
Laptop-mode webcam endpoints.

GET  /api/webcam/encodings            — face encodings for all enrolled students
POST /api/webcam/enroll               — store a pre-computed embedding (laptop-side DeepFace)
POST /api/webcam/attendance           — report an attendance event (present | absent)
POST /api/webcam/start-recognition    — spawn laptop_recognition.py as a subprocess (demo)
POST /api/webcam/stop-recognition     — terminate the running subprocess
GET  /api/webcam/recognition-status   — check if the subprocess is alive

These endpoints are called exclusively by laptop_recognition.py and
laptop_enroll.py running on the host. No auth required.
"""
import asyncio
import base64
import logging
import subprocess
import sys
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    FaceEncoding,
    Session as SessionModel,
    SessionStatus,
    Student,
)
from app.models.schemas import (
    WebcamAttendanceRequest,
    WebcamAttendanceResponse,
    WebcamEncodingEntry,
    WebcamEnrollRequest,
)
from app.services.event_queues import attendance_event_queue

logger = logging.getLogger(__name__)
router = APIRouter()


# ── GET /api/webcam/encodings ──────────────────────────────────────────────────

@router.get("/encodings", response_model=list[WebcamEncodingEntry])
async def get_encodings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WebcamEncodingEntry]:
    """Return base64 face encodings for all enrolled students."""
    rows = (
        await db.execute(
            select(FaceEncoding, Student).join(Student, FaceEncoding.student_id == Student.id)
        )
    ).all()

    return [
        WebcamEncodingEntry(
            student_id=str(enc.student_id),
            name=student.name,
            encoding_b64=base64.b64encode(enc.encoding).decode(),
        )
        for enc, student in rows
        if enc.encoding and len(enc.encoding) > 0
    ]


# ── POST /api/webcam/enroll ───────────────────────────────────────────────────

@router.post("/enroll")
async def store_laptop_encoding(
    body: WebcamEnrollRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Store a pre-computed FaceNet embedding from the host-side laptop_enroll.py.
    Replaces any existing encoding rows for this student so there's always one
    clean, non-zero vector after laptop enrollment.
    """
    encoding_bytes = base64.b64decode(body.encoding_b64)
    if len(encoding_bytes) != 512:
        raise HTTPException(status_code=422, detail="encoding must be 128-d float32 (512 bytes)")

    student = await db.get(Student, body.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student_not_found")

    # Replace any existing rows (stub zeros or prior enrollment)
    await db.execute(delete(FaceEncoding).where(FaceEncoding.student_id == body.student_id))
    db.add(FaceEncoding(
        id=str(uuid_lib.uuid4()),
        student_id=body.student_id,
        encoding=encoding_bytes,
    ))
    await db.commit()

    logger.info("[LAPTOP] Stored encoding for %s", student.name)
    return {"stored": True}


# ── POST /api/webcam/attendance ────────────────────────────────────────────────

@router.post("/attendance", response_model=WebcamAttendanceResponse)
async def record_webcam_attendance(
    body: WebcamAttendanceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebcamAttendanceResponse:
    if body.status not in ("present", "absent"):
        raise HTTPException(status_code=422, detail="status must be 'present' or 'absent'")

    session = (
        await db.execute(
            select(SessionModel).where(
                SessionModel.room_id == settings.room_id,
                SessionModel.status == SessionStatus.active,
                SessionModel.ended_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="no_active_session")

    student = await db.get(Student, body.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="student_not_found")

    existing = (
        await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == session.id,
                AttendanceRecord.student_id == body.student_id,
            )
        )
    ).scalar_one_or_none()

    # Never overwrite a professor's manual adjustment
    if existing is not None and existing.adjusted_by is not None:
        return WebcamAttendanceResponse(recorded=False)

    recorded = False

    if body.status == "present":
        if existing is None:
            db.add(AttendanceRecord(
                session_id=session.id,
                student_id=body.student_id,
                status=AttendanceStatus.present,
            ))
        else:
            existing.status = AttendanceStatus.present
            existing.detected_at = datetime.now(timezone.utc)
        await db.commit()
        recorded = True

    elif body.status == "absent":
        if existing is None:
            return WebcamAttendanceResponse(recorded=False)
        existing.status = AttendanceStatus.absent
        await db.commit()
        recorded = True

    if recorded:
        try:
            attendance_event_queue.put_nowait({
                "type": "attendance",
                "room_id": settings.room_id,
                "session_id": session.id,
                "student_id": body.student_id,
                "student_name": student.name,
                "confidence": body.confidence,
                "status": body.status,
                "source": "laptop_webcam",
            })
        except Exception:
            pass

        logger.info("[LAPTOP] %-7s %s (conf=%.2f)", body.status.upper(), student.name, body.confidence)

    return WebcamAttendanceResponse(recorded=recorded)


# ── Subprocess management (demo mode) ─────────────────────────────────────────

_proc_store: dict = {}  # {"proc": Popen}


def _find_recognition_script() -> Path | None:
    """Search for laptop_recognition.py starting from the project root."""
    candidates = [
        Path(__file__).parents[3] / "laptop_recognition.py",  # backend/app/api → project root
        Path.cwd() / "laptop_recognition.py",
        Path.cwd().parent / "laptop_recognition.py",
    ]
    return next((p for p in candidates if p.exists()), None)


@router.post("/start-recognition")
async def start_recognition() -> dict:
    """Spawn laptop_recognition.py as a host subprocess (demo only)."""
    proc = _proc_store.get("proc")
    if proc is not None and proc.poll() is None:
        return {"running": True, "pid": proc.pid, "message": "Already running"}

    script = _find_recognition_script()
    if script is None:
        raise HTTPException(
            status_code=503,
            detail="laptop_recognition.py not found. Start it manually: python laptop_recognition.py",
        )

    # Stop the backend stub/recognition loop so laptop_recognition.py is the sole
    # attendance source. Without this, the stub loop randomly overrides absent marks.
    try:
        from app.services.recognition_loop import stop_recognition as _stop_loop
        asyncio.create_task(_stop_loop())
    except Exception as exc:
        logger.warning("Could not stop backend recognition loop: %s", exc)

    new_proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _proc_store["proc"] = new_proc
    logger.info("[DEMO] Started laptop_recognition.py (pid=%d)", new_proc.pid)
    return {"running": True, "pid": new_proc.pid}


@router.post("/stop-recognition")
async def stop_recognition() -> dict:
    """Terminate the running laptop_recognition.py subprocess."""
    proc = _proc_store.get("proc")
    if proc is None or proc.poll() is not None:
        return {"running": False, "message": "Not running"}

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    logger.info("[DEMO] Stopped laptop_recognition.py (pid=%d)", proc.pid)
    _proc_store.pop("proc", None)
    return {"running": False}


@router.get("/recognition-status")
async def recognition_status() -> dict:
    """Return whether laptop_recognition.py subprocess is currently alive."""
    proc = _proc_store.get("proc")
    running = proc is not None and proc.poll() is None
    return {"running": running, "pid": proc.pid if running else None}
