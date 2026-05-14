import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_professor
from app.database import get_db
from app.models.db_models import (
    AttendanceForecast,
    Course,
    Professor,
    ProfessorRole,
)
from app.models.schemas import CourseForecastResponse, TrendDataPoint

router = APIRouter()

_PIPELINE_LOCK_KEY = "forecast:pipeline:lock"
_PIPELINE_LOCK_TTL = 1800  # 30 minutes — matches _FRESH_SKIP_SECONDS in forecast_engine


async def _maybe_run_pipeline() -> None:
    from app.redis_client import get_redis_pool
    from app.services.forecast_engine import run_forecast_pipeline
    import logging as _logging

    _log = _logging.getLogger(__name__)
    redis = get_redis_pool()
    acquired = await redis.set(_PIPELINE_LOCK_KEY, "1", nx=True, ex=_PIPELINE_LOCK_TTL)
    if not acquired:
        return
    try:
        await run_forecast_pipeline()
    except Exception as exc:
        _log.error("Forecast pipeline crashed — releasing lock for retry: %s", exc, exc_info=True)
        await redis.delete(_PIPELINE_LOCK_KEY)


# Severity order for sorting the course list: worst first
_SEVERITY_ORDER: dict[str | None, int] = {
    "accelerating_decline": 0,
    "steady_decline": 1,
    "stable": 2,
    "recovering": 3,
    None: 4,
}


def _make_response(course: Course, fc: AttendanceForecast | None) -> CourseForecastResponse:
    if fc is None:
        # Pipeline hasn't run yet for this course — show "Generating…" state
        return CourseForecastResponse(
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            trend_data=[],
            sessions_analyzed=0,
            expected_next_rate=None,
            trend_classification=None,
            confidence_level=None,
            interpretation=None,
            suggested_action=None,
            # ollama_reachable is unknown here; True is the optimistic default.
            # The frontend uses generated_at=None to show "Generating…", not this field.
            ollama_reachable=True,
            generated_at=None,
        )
    return CourseForecastResponse(
        course_id=fc.course_id,
        course_code=course.code,
        course_name=course.name,
        trend_data=[TrendDataPoint(**p) for p in (fc.trend_data or [])],
        sessions_analyzed=len(fc.trend_data or []),
        expected_next_rate=fc.expected_next_rate,
        trend_classification=fc.trend_classification,
        confidence_level=fc.confidence_level,
        interpretation=fc.interpretation,
        suggested_action=fc.suggested_action,
        ollama_reachable=fc.ollama_reachable,
        generated_at=fc.generated_at,
    )


@router.get("/forecasting", response_model=list[CourseForecastResponse])
async def list_forecasts(
    course_id: str | None = Query(None),
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    course_q = select(Course)
    if current.role != ProfessorRole.admin:
        course_q = course_q.where(Course.professor_id == current.id)
    if course_id:
        course_q = course_q.where(Course.id == course_id)

    courses = (await db.execute(course_q)).scalars().all()
    if not courses:
        return []

    course_ids = [c.id for c in courses]
    forecasts = {
        f.course_id: f for f in (await db.execute(
            select(AttendanceForecast).where(AttendanceForecast.course_id.in_(course_ids))
        )).scalars().all()
    }

    results = [_make_response(c, forecasts.get(c.id)) for c in courses]
    results.sort(key=lambda r: _SEVERITY_ORDER.get(r.trend_classification, 4))

    # Fire pipeline in background — Redis lock prevents pile-ups
    asyncio.create_task(_maybe_run_pipeline())

    return results


@router.get("/forecasting/{course_id}", response_model=CourseForecastResponse)
async def get_course_forecast(
    course_id: str,
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if current.role != ProfessorRole.admin and course.professor_id != current.id:
        raise HTTPException(status_code=403, detail="Access denied")

    fc = (await db.execute(
        select(AttendanceForecast).where(AttendanceForecast.course_id == course_id)
    )).scalar_one_or_none()

    return _make_response(course, fc)


@router.post("/forecasting/recompute", status_code=status.HTTP_202_ACCEPTED)
async def recompute_forecasts(
    current: Professor = Depends(get_current_professor),
):
    if current.role != ProfessorRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    from app.services.forecast_engine import run_forecast_pipeline
    asyncio.create_task(run_forecast_pipeline())
    return {"message": "Recompute started"}
