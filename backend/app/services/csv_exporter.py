from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import (
    AttendanceRecord,
    Course,
    Session,
    SessionStatus,
)


async def export_course_csv(course_id: str, db: AsyncSession) -> str:
    course = await db.get(Course, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")

    sessions_q = await db.execute(
        select(Session)
        .where(Session.course_id == course_id, Session.status == SessionStatus.ended)
        .order_by(Session.started_at)
    )
    sessions = list(sessions_q.scalars().all())
    session_ids = [s.id for s in sessions]
    date_map = {
        s.id: s.started_at.strftime("%Y-%m-%d") if s.started_at else ""
        for s in sessions
    }

    fieldnames = [
        "session_date", "session_id", "student_name", "student_id",
        "status", "detected_at", "adjusted_by", "adjusted_at",
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()

    if not session_ids:
        return output.getvalue()

    recs_q = await db.execute(
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id.in_(session_ids))
        .options(selectinload(AttendanceRecord.student))
    )
    recs = list(recs_q.scalars().all())

    recs_sorted = sorted(
        recs,
        key=lambda r: (
            date_map.get(r.session_id, ""),
            r.student.name if r.student else "",
        ),
    )

    for r in recs_sorted:
        status_str = r.status.value if hasattr(r.status, "value") else str(r.status)
        writer.writerow({
            "session_date": date_map.get(r.session_id, ""),
            "session_id":   r.session_id,
            "student_name": r.student.name if r.student else "",
            "student_id":   r.student.student_id if r.student else "",
            "status":       status_str,
            "detected_at":  r.detected_at.isoformat() if r.detected_at else "",
            "adjusted_by":  r.adjusted_by or "",
            "adjusted_at":  r.adjusted_at.isoformat() if r.adjusted_at else "",
        })

    return output.getvalue()
