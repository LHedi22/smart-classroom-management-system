from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
    AttendanceRosterEntry,
    AttendanceWithStudent,
    StudentHistoryEntry,
)

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────
# GET /api/sessions/{session_id}/attendance
# ─────────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/attendance", response_model=list[AttendanceRosterEntry])
async def get_session_attendance(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceRosterEntry]:
    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # All students enrolled in this course, alphabetically
    enrolled_q = await db.execute(
        select(Student)
        .join(course_students, Student.id == course_students.c.student_id)
        .where(course_students.c.course_id == session.course_id)
        .order_by(Student.name)
    )
    enrolled = enrolled_q.scalars().all()

    # Existing attendance records keyed by student_id
    records_q = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id == session_id)
        .options(selectinload(AttendanceRecord.student))
    )
    record_by_student = {r.student_id: r for r in records_q.scalars().all()}

    roster: list[AttendanceRosterEntry] = []
    for student in enrolled:
        r = record_by_student.get(student.id)
        if r:
            roster.append(AttendanceRosterEntry(
                id=r.id,
                session_id=r.session_id,
                student_id=r.student_id,
                status=r.status,
                detected_at=r.detected_at,
                adjusted_by=r.adjusted_by,
                adjusted_at=r.adjusted_at,
                moodle_synced=r.moodle_synced,
                student_name=student.name,
                student_number=student.student_id,
            ))
        else:
            # Virtual absent entry — student enrolled but not yet detected
            roster.append(AttendanceRosterEntry(
                session_id=session_id,
                student_id=student.id,
                status=AttendanceStatus.absent,
                student_name=student.name,
                student_number=student.student_id,
            ))

    # Sort: present/late first, then absent with real records, then virtual absent (id=None)
    status_order = {AttendanceStatus.present: 0, AttendanceStatus.late: 1,
                    AttendanceStatus.excused: 2, AttendanceStatus.absent: 3}
    roster.sort(key=lambda e: (
        status_order.get(e.status, 9),
        e.id is None,
        e.student_name,
    ))
    return roster


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

    enrolled_q = await db.execute(
        select(Student.id).join(
            course_students, Student.id == course_students.c.student_id
        ).where(course_students.c.course_id == session.course_id)
    )
    enrolled_ids = [row[0] for row in enrolled_q.all()]

    if not enrolled_ids:
        return []

    # Single atomic statement — no race window between two queries.
    # ON CONFLICT DO NOTHING skips students already recorded (present/late/etc).
    # RETURNING gives us only the rows that were actually inserted.
    stmt = (
        pg_insert(AttendanceRecord)
        .values([
            {"session_id": session_id, "student_id": sid, "status": AttendanceStatus.absent}
            for sid in enrolled_ids
        ])
        .on_conflict_do_nothing(index_elements=["session_id", "student_id"])
        .returning(AttendanceRecord.id)
    )
    result = await db.execute(stmt)
    new_ids = [row[0] for row in result.all()]
    await db.commit()

    if not new_ids:
        return []

    new_records_q = await db.execute(
        select(AttendanceRecord).where(AttendanceRecord.id.in_(new_ids))
    )
    return list(new_records_q.scalars().all())


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
