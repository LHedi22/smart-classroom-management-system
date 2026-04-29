import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_professor
from app.database import get_db
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    Course,
    Professor,
    ProfessorRole,
    SensorReading,
    SensorType,
    Session,
    SessionStatus,
    Student,
    course_students,
)
from app.models.schemas import (
    AttendanceDetailItem,
    MoodleSyncResult,
    SessionDetailResponse,
    SessionResponse,
    SessionSensorsLatestResponse,
    SessionSensorsSummaryResponse,
    SessionStart,
    SessionWithSummary,
    SensorLatestItem,
    SensorStats,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _compute_display_status(session: Session) -> str:
    """Derive the UI status from DB status + time. Never stored in DB."""
    if session.status == SessionStatus.ended:
        return "done"
    if session.status == SessionStatus.upcoming:
        return "upcoming"
    # active: live only if start time has passed
    now = datetime.now(timezone.utc)
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return "live" if started <= now else "upcoming"


def _display_sort_key(item: SessionWithSummary) -> tuple:
    ORDER = {"live": 0, "upcoming": 1, "done": 2}
    rank = ORDER.get(item.display_status, 2)
    started = item.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    # upcoming: soonest first (+timestamp); done: most recent first (-timestamp)
    if item.display_status == "upcoming":
        return (rank, started.timestamp())
    return (rank, -started.timestamp())


async def _build_summary(session: Session, db: AsyncSession) -> SessionWithSummary:
    present_q = await db.execute(
        select(func.count()).where(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.status == AttendanceStatus.present,
        )
    )
    total_q = await db.execute(
        select(func.count()).where(AttendanceRecord.session_id == session.id)
    )
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
        present_count=present_q.scalar_one(),
        total_students=total_q.scalar_one(),
        course=course_schema,
        display_status=_compute_display_status(session),
        course_name=course_obj.name if course_obj else "",
        course_code=course_obj.code if course_obj else "",
    )


async def _build_detail(session: Session, db: AsyncSession) -> SessionDetailResponse:
    summary = await _build_summary(session, db)

    # Enrolled count
    enrolled_q = await db.execute(
        select(func.count())
        .select_from(course_students)
        .where(course_students.c.course_id == session.course_id)
    )
    total_enrolled = enrolled_q.scalar_one()

    # Attendance with student info
    recs_q = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session.id)
        .options(selectinload(AttendanceRecord.student))
        .order_by(AttendanceRecord.detected_at)
    )
    records = recs_q.scalars().all()

    attendance = [
        AttendanceDetailItem(
            student_id=r.student_id,
            name=r.student.name,
            student_number=r.student.student_id,
            status=r.status,
            detected_at=r.detected_at,
        )
        for r in records
    ]

    return SessionDetailResponse(
        **summary.model_dump(),
        total_enrolled=total_enrolled,
        attendance=attendance,
    )


# ─────────────────────────────────────────────────────────────────────────
# Standard session endpoints
# ─────────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    body: SessionStart,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
) -> Session:
    course = await db.get(Course, body.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if current.role == ProfessorRole.professor and course.professor_id != current.id:
        raise HTTPException(status_code=403, detail="Not authorized to start sessions for this course")

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
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
) -> list[SessionWithSummary]:
    q = select(Session)
    if current.role == ProfessorRole.professor:
        q = q.join(Course, Session.course_id == Course.id).where(
            Course.professor_id == current.id
        )
    if course_id:
        q = q.where(Session.course_id == course_id)
    if room_id:
        q = q.where(Session.room_id == room_id)

    result = await db.execute(q)
    sessions = result.scalars().all()
    summaries = [await _build_summary(s, db) for s in sessions]

    # Sort: live → upcoming (soonest first) → done (most recent first)
    summaries.sort(key=_display_sort_key)
    return summaries


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
) -> SessionDetailResponse:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return await _build_detail(session, db)


# ─────────────────────────────────────────────────────────────────────────
# Session-scoped sensor endpoints
# Mounted at /api/sessions so paths become /api/sessions/{id}/sensors/...
# ─────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}/sensors/latest", response_model=SessionSensorsLatestResponse)
async def get_session_sensors_latest(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
) -> SessionSensorsLatestResponse:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    sensors: dict[str, SensorLatestItem] = {}
    for stype in SensorType:
        stmt = (
            select(SensorReading)
            .where(
                SensorReading.room_id == session.room_id,
                SensorReading.sensor_type == stype,
                SensorReading.recorded_at >= session.started_at,
            )
            .order_by(SensorReading.recorded_at.desc())
            .limit(1)
        )
        if session.ended_at is not None:
            stmt = stmt.where(SensorReading.recorded_at <= session.ended_at)

        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is not None:
            sensors[stype.value] = SensorLatestItem(
                value=row.value,
                unit=row.unit,
                recorded_at=row.recorded_at,
            )

    return SessionSensorsLatestResponse(session_id=session_id, sensors=sensors)


@router.get("/{session_id}/sensors/summary", response_model=SessionSensorsSummaryResponse)
async def get_session_sensors_summary(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
) -> SessionSensorsSummaryResponse:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != SessionStatus.ended:
        raise HTTPException(
            status_code=400,
            detail="Sensor summary is only available for ended sessions",
        )

    stats: dict[str, SensorStats] = {}
    for stype in SensorType:
        row = (
            await db.execute(
                select(
                    func.avg(SensorReading.value),
                    func.min(SensorReading.value),
                    func.max(SensorReading.value),
                ).where(
                    SensorReading.room_id == session.room_id,
                    SensorReading.sensor_type == stype,
                    SensorReading.recorded_at >= session.started_at,
                    SensorReading.recorded_at <= session.ended_at,
                )
            )
        ).one()
        if row[0] is not None:
            stats[stype.value] = SensorStats(
                avg=round(row[0], 1),
                min=round(row[1], 1),
                max=round(row[2], 1),
            )

    return SessionSensorsSummaryResponse(
        session_id=session_id,
        temperature=stats.get("temperature"),
        humidity=stats.get("humidity"),
        air_quality=stats.get("air_quality"),
        sound=stats.get("sound"),
    )
