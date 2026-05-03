import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_professor
from app.config import settings
from app.database import get_db
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    AtRiskExplanation,
    Course,
    Professor,
    ProfessorRole,
    Session,
    SessionStatus,
    Student,
    course_students,
)
from app.models.schemas import AtRiskStudentResponse, PerCourseRisk

router = APIRouter()

_PIPELINE_LOCK_KEY = "at_risk:pipeline:lock"
# TTL doubles as both a concurrency guard and a cooldown window after the run finishes.
# Deleting the key on completion would allow immediate re-runs; leaving TTL to expire
# naturally gives ~10 minutes of breathing room between pipeline invocations.
_PIPELINE_LOCK_TTL = 600  # 10 minutes


async def _maybe_run_pipeline() -> None:
    from app.redis_client import get_redis_pool
    from app.services.at_risk_engine import run_at_risk_pipeline
    import logging as _logging
    _log = _logging.getLogger(__name__)
    redis = get_redis_pool()
    acquired = await redis.set(_PIPELINE_LOCK_KEY, "1", nx=True, ex=_PIPELINE_LOCK_TTL)
    if not acquired:
        return
    try:
        await run_at_risk_pipeline()
    except Exception as exc:
        # Delete the lock so the next page load can retry rather than waiting 10 minutes
        _log.error("At-risk pipeline crashed — releasing lock for retry: %s", exc, exc_info=True)
        await redis.delete(_PIPELINE_LOCK_KEY)


async def _overall_rates(db: AsyncSession, student_ids: list[str]) -> dict[str, float]:
    """Compute overall attendance rate across all ended sessions for a batch of students."""
    if not student_ids:
        return {}
    rows = (await db.execute(
        select(
            AttendanceRecord.student_id,
            func.sum(case((AttendanceRecord.status == AttendanceStatus.present, 1), else_=0)).label("present"),
            func.count().label("total"),
        )
        .join(Session, Session.id == AttendanceRecord.session_id)
        .where(
            AttendanceRecord.student_id.in_(student_ids),
            Session.status == SessionStatus.ended,
        )
        .group_by(AttendanceRecord.student_id)
    )).all()
    return {
        r.student_id: round((r.present / r.total) if r.total > 0 else 0.0, 4)
        for r in rows
    }


def _make_response(
    flagged: dict,
    student_obj: Student,
    overall_rate: float,
    expl: AtRiskExplanation | None,
) -> AtRiskStudentResponse:
    if expl:
        per_course = [PerCourseRisk(**c) for c in (expl.per_course_data or [])]
        return AtRiskStudentResponse(
            student_id=flagged["student_id"],
            student_name=student_obj.name,
            student_number=student_obj.student_id,
            overall_attendance_rate=expl.overall_attendance_rate,
            summary_explanation=expl.summary_explanation,
            per_course_data=per_course,
            generated_at=expl.generated_at,
            ollama_reachable=expl.ollama_reachable,
        )
    return AtRiskStudentResponse(
        student_id=flagged["student_id"],
        student_name=student_obj.name,
        student_number=student_obj.student_id,
        overall_attendance_rate=overall_rate,
        summary_explanation=None,
        per_course_data=[],
        generated_at=None,
        ollama_reachable=True,  # pipeline hasn't run yet — "Generating…" in the UI
    )


@router.get("/at-risk", response_model=list[AtRiskStudentResponse])
async def list_at_risk(
    course_id: str | None = Query(None),
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    from app.services.insights_engine import insights_engine

    prof_id = None if current.role == ProfessorRole.admin else current.id
    flagged = await insights_engine.get_at_risk_students(
        db, prof_id, threshold=settings.at_risk_threshold
    )

    if not flagged:
        return []

    # Optional course_id filter — keep only students enrolled in that course
    if course_id:
        enrolled_ids = set(
            (await db.execute(
                select(course_students.c.student_id)
                .where(course_students.c.course_id == course_id)
            )).scalars().all()
        )
        flagged = [f for f in flagged if f["student_id"] in enrolled_ids]

    if not flagged:
        return []

    student_ids = [f["student_id"] for f in flagged]

    # Load student objects
    students = {
        s.id: s for s in (await db.execute(
            select(Student).where(Student.id.in_(student_ids))
        )).scalars().all()
    }

    # Load any existing explanation rows
    explanations = {
        e.student_id: e for e in (await db.execute(
            select(AtRiskExplanation).where(AtRiskExplanation.student_id.in_(student_ids))
        )).scalars().all()
    }

    # Compute overall rates for students who don't have an explanation row yet
    missing_ids = [sid for sid in student_ids if sid not in explanations]
    rates = await _overall_rates(db, missing_ids)

    results = []
    for f in flagged:
        sid = f["student_id"]
        student_obj = students.get(sid)
        if not student_obj:
            continue
        expl = explanations.get(sid)
        overall_rate = expl.overall_attendance_rate if expl else rates.get(sid, f["attendance_rate"])
        results.append(_make_response(f, student_obj, overall_rate, expl))

    results.sort(key=lambda r: r.overall_attendance_rate)

    # Fire-and-forget: regenerate explanations in the background (Redis lock prevents pile-ups)
    asyncio.create_task(_maybe_run_pipeline())

    return results


@router.get("/at-risk/{student_id}", response_model=AtRiskStudentResponse)
async def get_at_risk_student(
    student_id: str,
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    from app.services.insights_engine import insights_engine

    # Professor role: verify student is in at least one of their courses
    if current.role != ProfessorRole.admin:
        enrolled = (await db.execute(
            select(course_students.c.student_id)
            .join(Course, Course.id == course_students.c.course_id)
            .where(
                course_students.c.student_id == student_id,
                Course.professor_id == current.id,
            )
            .limit(1)
        )).first()
        if enrolled is None:
            raise HTTPException(status_code=403, detail="Access denied")

    prof_id = None if current.role == ProfessorRole.admin else current.id
    flagged_list = await insights_engine.get_at_risk_students(
        db, prof_id, threshold=settings.at_risk_threshold
    )
    flagged_map = {f["student_id"]: f for f in flagged_list}

    if student_id not in flagged_map:
        raise HTTPException(status_code=404, detail="Student is not currently at risk")

    student_obj = await db.get(Student, student_id)
    if not student_obj:
        raise HTTPException(status_code=404, detail="Student not found")

    expl = (await db.execute(
        select(AtRiskExplanation).where(AtRiskExplanation.student_id == student_id)
    )).scalar_one_or_none()

    overall_rate = expl.overall_attendance_rate if expl else (
        await _overall_rates(db, [student_id])
    ).get(student_id, flagged_map[student_id]["attendance_rate"])

    return _make_response(flagged_map[student_id], student_obj, overall_rate, expl)


@router.post("/at-risk/recompute", status_code=status.HTTP_202_ACCEPTED)
async def recompute_at_risk(
    current: Professor = Depends(get_current_professor),
):
    if current.role != ProfessorRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    from app.services.at_risk_engine import run_at_risk_pipeline
    asyncio.create_task(run_at_risk_pipeline())
    return {"message": "Recompute started"}
