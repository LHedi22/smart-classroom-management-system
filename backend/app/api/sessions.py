import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import AttendanceRecord, AttendanceStatus, Course, Session, SessionStatus
from app.models.schemas import MoodleSyncResult, SessionResponse, SessionStart, SessionWithSummary

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

async def _build_summary(session: Session, db: AsyncSession) -> SessionWithSummary:
    present_q = await db.execute(
        select(func.count()).where(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.status == AttendanceStatus.present,
        )
    )
    present_count = present_q.scalar_one()

    total_q = await db.execute(
        select(func.count()).where(AttendanceRecord.session_id == session.id)
    )
    total_students = total_q.scalar_one()

    course_obj = await db.get(Course, session.course_id)

    from app.models.schemas import CourseResponse
    course_schema = CourseResponse.model_validate(course_obj) if course_obj else None

    return SessionWithSummary(
        id=session.id,
        course_id=session.course_id,
        room_id=session.room_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        present_count=present_count,
        total_students=total_students,
        course=course_schema,
    )


# ─────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(body: SessionStart, db: AsyncSession = Depends(get_db)) -> Session:
    course = await db.get(Course, body.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # Only one active session per room at a time
    existing = await db.execute(
        select(Session).where(
            Session.room_id == body.room_id,
            Session.status == SessionStatus.active,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A session is already active in this room")

    session = Session(course_id=body.course_id, room_id=body.room_id, status=SessionStatus.active)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Launch recognition loop without blocking the response
    try:
        from app.services.recognition_loop import start_recognition
        asyncio.create_task(start_recognition(session.id, session.room_id))
    except Exception as exc:
        logger.warning("Could not start recognition loop: %s", exc)

    return session


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)) -> Session:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == SessionStatus.ended:
        raise HTTPException(status_code=409, detail="Session already ended")

    session.status = SessionStatus.ended
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    try:
        from app.services.recognition_loop import stop_recognition
        asyncio.create_task(stop_recognition())
    except Exception as exc:
        logger.warning("Could not stop recognition loop: %s", exc)

    # Trigger Moodle sync in background — failure must not affect the response
    _sid = session.id
    async def _bg_sync() -> None:
        try:
            from app.services.moodle_client import moodle_client
            result = await moodle_client.sync_attendance(_sid)
            logger.info("Auto Moodle sync on session end: %s", result)
        except Exception as exc:
            logger.warning("Auto Moodle sync failed for session %s: %s", _sid, exc)

    asyncio.create_task(_bg_sync())

    return session


@router.post("/{session_id}/sync-moodle", response_model=MoodleSyncResult)
async def sync_session_moodle(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> MoodleSyncResult:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.services.moodle_client import moodle_client
    result = await moodle_client.sync_attendance(session_id)
    return MoodleSyncResult(**result)


@router.get("", response_model=list[SessionWithSummary])
async def list_sessions(
    course_id: str | None = Query(None),
    room_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> list[SessionWithSummary]:
    q = select(Session).order_by(Session.started_at.desc())
    if course_id:
        q = q.where(Session.course_id == course_id)
    if room_id:
        q = q.where(Session.room_id == room_id)
    if status_filter:
        try:
            q = q.where(Session.status == SessionStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status_filter}")

    result = await db.execute(q)
    sessions = result.scalars().all()
    return [await _build_summary(s, db) for s in sessions]


@router.get("/{session_id}", response_model=SessionWithSummary)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> SessionWithSummary:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _build_summary(session, db)
