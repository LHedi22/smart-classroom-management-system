from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    Course,
    Session,
    SessionStatus,
    Student,
    course_students,
)
from app.models.schemas import (
    AttendanceAdjust,
    AttendanceRecordResponse,
    AttendanceWithStudent,
    StudentHistoryEntry,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# GET /api/sessions/{session_id}/attendance
# ─────────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/attendance", response_model=list[AttendanceWithStudent])
async def get_session_attendance(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceWithStudent]:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .options(selectinload(AttendanceRecord.student))
        .order_by(AttendanceRecord.detected_at)
    )
    records = result.scalars().all()

    return [
        AttendanceWithStudent(
            id=r.id,
            session_id=r.session_id,
            student_id=r.student_id,
            status=r.status,
            detected_at=r.detected_at,
            adjusted_by=r.adjusted_by,
            adjusted_at=r.adjusted_at,
            moodle_synced=r.moodle_synced,
            student_name=r.student.name,
            student_number=r.student.student_id,
        )
        for r in records
    ]


# ─────────────────────────────────────────────────────────────────────────
# PATCH /api/attendance/{record_id}
# ─────────────────────────────────────────────────────────────────────────

@router.patch("/attendance/{record_id}", response_model=AttendanceRecordResponse)
async def adjust_attendance(
    record_id: str,
    body: AttendanceAdjust,
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecord:
    record = await db.get(AttendanceRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    record.status = body.status
    record.adjusted_by = "professor"
    record.adjusted_at = datetime.now(timezone.utc)
    record.moodle_synced = False  # needs re-sync after adjustment
    await db.commit()
    await db.refresh(record)
    return record


# ─────────────────────────────────────────────────────────────────────────
# POST /api/sessions/{session_id}/mark-absent
# ─────────────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/mark-absent", response_model=list[AttendanceRecordResponse])
async def mark_absent(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceRecord]:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Students enrolled in this course
    enrolled_q = await db.execute(
        select(Student.id).join(
            course_students, Student.id == course_students.c.student_id
        ).where(course_students.c.course_id == session.course_id)
    )
    enrolled_ids = {row[0] for row in enrolled_q.all()}

    # Students who already have a record for this session
    recorded_q = await db.execute(
        select(AttendanceRecord.student_id).where(AttendanceRecord.session_id == session_id)
    )
    recorded_ids = {row[0] for row in recorded_q.all()}

    missing_ids = enrolled_ids - recorded_ids
    new_records: list[AttendanceRecord] = []

    for sid in missing_ids:
        record = AttendanceRecord(
            session_id=session_id,
            student_id=sid,
            status=AttendanceStatus.absent,
        )
        db.add(record)
        new_records.append(record)

    await db.commit()
    for r in new_records:
        await db.refresh(r)
    return new_records


# ─────────────────────────────────────────────────────────────────────────
# GET /api/students/{student_id}/attendance-history
# ─────────────────────────────────────────────────────────────────────────

@router.get("/students/{student_id}/attendance-history", response_model=list[StudentHistoryEntry])
async def get_student_history(
    student_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[StudentHistoryEntry]:
    student = await db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    result = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.student_id == student_id)
        .options(
            selectinload(AttendanceRecord.session).selectinload(Session.course)
        )
        .order_by(AttendanceRecord.detected_at.desc())
    )
    records = result.scalars().all()

    return [
        StudentHistoryEntry(
            record_id=r.id,
            session_id=r.session_id,
            course_code=r.session.course.code,
            course_name=r.session.course.name,
            session_date=r.session.started_at,
            status=r.status,
            detected_at=r.detected_at,
            adjusted_by=r.adjusted_by,
        )
        for r in records
    ]
