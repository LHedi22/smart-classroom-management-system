from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_professor
from app.database import get_db
from app.models.db_models import Alert, Course, Professor, ProfessorRole, Session, SessionStatus
from app.models.schemas import (
    AcEffectiveness,
    AtRiskStudent,
    AttendanceTrendPoint,
    CorrelationPoint,
    DecayPoint,
    EnvironmentTrendDay,
    HeatmapCell,
    InsightsOverview,
    StudentProfile,
)
from app.redis_client import get_redis
from app.services.insights_engine import insights_engine

router = APIRouter()


def _prof_id(current: Professor) -> str | None:
    """Return None (admin view) for admins, or the professor's own ID."""
    if current.role == ProfessorRole.admin:
        return None
    return current.id


# ── Overview ──────────────────────────────────────────────────────────────

@router.get("/overview", response_model=InsightsOverview)
async def get_overview(
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    return await insights_engine.get_overview(db, _prof_id(current), redis)


# ── Attendance ────────────────────────────────────────────────────────────

@router.get("/attendance/trend", response_model=list[AttendanceTrendPoint])
async def get_attendance_trend(
    course_id: str | None = Query(None),
    weeks: int = Query(8, ge=1, le=52),
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    return await insights_engine.get_attendance_trend(db, course_id, weeks, _prof_id(current))


@router.get("/attendance/heatmap", response_model=list[HeatmapCell])
async def get_attendance_heatmap(
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    return await insights_engine.get_attendance_heatmap(db, _prof_id(current))


@router.get("/attendance/decay", response_model=list[DecayPoint])
async def get_attendance_decay(
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    return await insights_engine.get_attendance_decay(db, _prof_id(current))


# ── Students ──────────────────────────────────────────────────────────────

@router.get("/students/at-risk", response_model=list[AtRiskStudent])
async def get_at_risk_students(
    threshold: float = Query(0.70, ge=0.0, le=1.0),
    consecutive: int = Query(3, ge=1),
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    return await insights_engine.get_at_risk_students(db, _prof_id(current), threshold, consecutive)


@router.get("/students/{student_id}/profile", response_model=StudentProfile)
async def get_student_profile(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
):
    profile = await insights_engine.get_student_profile(db, student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return profile


# ── Environment ───────────────────────────────────────────────────────────

@router.get("/environment/comfort-score")
async def get_comfort_score(
    room_id: str = Query("room1"),
    redis: aioredis.Redis = Depends(get_redis),
    current: Professor = Depends(get_current_professor),
):
    score = await insights_engine.get_comfort_score(room_id, redis)
    return {"room_id": room_id, "comfort_score": round(score, 1)}


@router.get("/environment/trends", response_model=list[EnvironmentTrendDay])
async def get_environment_trends(
    room_id: str = Query("room1"),
    from_param: str | None = Query(None, alias="from"),
    to_param: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
):
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(from_param).replace(tzinfo=timezone.utc) if from_param else now - timedelta(days=30)
    end = datetime.fromisoformat(to_param).replace(tzinfo=timezone.utc) if to_param else now
    return await insights_engine.get_environment_trends(db, room_id, start, end)


@router.get("/environment/ac-effectiveness", response_model=AcEffectiveness)
async def get_ac_effectiveness(
    room_id: str = Query("room1"),
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
):
    return await insights_engine.get_ac_effectiveness(db, room_id)


# ── Correlations ──────────────────────────────────────────────────────────

@router.get("/correlations/temp-vs-attendance", response_model=list[CorrelationPoint])
async def get_temp_vs_attendance(
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
):
    return await insights_engine.get_temp_vs_attendance(db, _prof_id(current))


@router.get("/correlations/airquality-vs-sound", response_model=list[CorrelationPoint])
async def get_airquality_vs_sound(
    room_id: str = Query("room1"),
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
):
    return await insights_engine.get_airquality_vs_sound(db, room_id)


# ── AI Summary ────────────────────────────────────────────────────────────

def _trend_direction(points: list[dict]) -> str:
    """Classify weekly attendance trend as improving/declining/stable."""
    if len(points) < 2:
        return "stable"
    rates = [p["attendance_rate"] for p in points]
    half = len(rates) // 2
    first_avg = sum(rates[:half]) / half
    second_avg = sum(rates[half:]) / (len(rates) - half)
    if second_avg > first_avg + 0.05:
        return "improving"
    if first_avg > second_avg + 0.05:
        return "declining"
    return "stable"


def _anomalies_from_trend(points: list[dict]) -> list[str]:
    anomalies = []
    for i in range(1, len(points)):
        drop = points[i - 1]["attendance_rate"] - points[i]["attendance_rate"]
        if drop >= 0.15:
            anomalies.append(
                f"attendance dropped {round(drop * 100)}% in {points[i]['week_label']}"
            )
    return anomalies


async def _recent_alerts_for_room(db: AsyncSession, room_id: str, limit: int = 10) -> list[str]:
    rows = (await db.execute(
        select(Alert.type, Alert.value)
        .where(Alert.room_id == room_id, Alert.acknowledged == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )).all()
    # Aggregate by type
    counts: dict[str, int] = {}
    for row in rows:
        key = row.type.value if hasattr(row.type, "value") else str(row.type)
        counts[key] = counts.get(key, 0) + 1
    return [f"{k} x{v}" for k, v in counts.items()]


@router.get("/ai-summary")
async def get_ai_summary(
    scope: str = Query(...),
    id: str = Query(...),
    current: Professor = Depends(get_current_professor),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    from app.services.ai_summary import generate_summary

    now = datetime.now(timezone.utc)
    prof_id = _prof_id(current)

    if scope == "course":
        course = await db.get(Course, id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        trend = await insights_engine.get_attendance_trend(db, course_id=id, weeks=8)
        at_risk = await insights_engine.get_at_risk_students(db, prof_id)
        course_at_risk = [s for s in at_risk if id in [
            # match courses_at_risk by code
            *[c for c in s["courses_at_risk"]]
        ] or course.code in s["courses_at_risk"]]

        env = await insights_engine.get_environment_trends(
            db, "room1", now - timedelta(days=30), now
        )
        comfort = await insights_engine.get_comfort_score("room1", redis)
        alerts = await _recent_alerts_for_room(db, "room1")

        avg_temp = round(
            sum(d.get("temp_avg", 0) or 0 for d in env) / len(env), 1
        ) if env else None
        avg_aq = round(
            sum(d.get("air_quality_avg", 0) or 0 for d in env) / len(env), 0
        ) if env else None
        avg_rate = round(
            sum(p["attendance_rate"] for p in trend) / len(trend), 4
        ) if trend else 0.0

        context = {
            "scope": "course",
            "label": f"{course.code} — {course.name}",
            "period": "last 8 weeks",
            "attendance_summary": {
                "avg_rate": avg_rate,
                "trend": _trend_direction(trend),
                "total_sessions": len(trend),
            },
            "at_risk_students": len(course_at_risk),
            "env_summary": {"avg_temp": avg_temp, "avg_air_quality": avg_aq, "comfort_score": comfort},
            "recent_alerts": alerts,
            "anomalies": _anomalies_from_trend(trend),
        }

    elif scope == "session":
        session = await db.get(Session, id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        course = await db.get(Course, session.course_id)
        rate = await insights_engine._session_attendance_rate(db, id)
        end = session.ended_at or now
        env = await insights_engine.get_environment_trends(db, session.room_id, session.started_at, end)
        alerts = await _recent_alerts_for_room(db, session.room_id)

        context = {
            "scope": "session",
            "label": f"{course.code if course else 'Unknown'} — {session.started_at.strftime('%Y-%m-%d')}",
            "period": f"{session.started_at.strftime('%H:%M')}–{end.strftime('%H:%M')}",
            "attendance_summary": {"rate": round(rate, 4)},
            "env_summary": env[0] if env else {},
            "recent_alerts": alerts,
            "anomalies": [],
        }

    elif scope == "room":
        env = await insights_engine.get_environment_trends(db, id, now - timedelta(days=7), now)
        comfort = await insights_engine.get_comfort_score(id, redis)
        alerts = await _recent_alerts_for_room(db, id)

        context = {
            "scope": "room",
            "label": f"Room {id}",
            "period": "last 7 days",
            "env_summary": {
                "comfort_score": comfort,
                "days_monitored": len(env),
            },
            "recent_alerts": alerts,
            "anomalies": [],
        }

    elif scope == "global":
        overview = await insights_engine.get_overview(db, prof_id, redis)
        at_risk = await insights_engine.get_at_risk_students(db, prof_id)
        # Top 3 most-at-risk courses by how many students flagged them
        course_risk_count: dict[str, int] = {}
        for s in at_risk:
            for c in s["courses_at_risk"]:
                course_risk_count[c] = course_risk_count.get(c, 0) + 1
        top3 = sorted(course_risk_count.items(), key=lambda x: -x[1])[:3]

        context = {
            "scope": "global",
            "label": "All courses",
            "period": "all time",
            "overview": overview,
            "top_at_risk_courses": [{"course": c, "flagged_students": n} for c, n in top3],
            "anomalies": [],
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown scope: {scope}")

    return await generate_summary(scope, id, context, redis)


# ── Exports ───────────────────────────────────────────────────────────────

@router.get("/export/session/{session_id}")
async def export_session_pdf(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current: Professor = Depends(get_current_professor),
):
    from app.services.pdf_exporter import export_session_pdf as _export

    session = await db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_bytes = await _export(session_id, db, redis)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"},
    )


@router.get("/export/course/{course_id}")
async def export_course_pdf(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current: Professor = Depends(get_current_professor),
):
    from app.services.pdf_exporter import export_course_pdf as _export

    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    pdf_bytes = await _export(course_id, db, redis)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=course_{course_id}.pdf"},
    )


@router.get("/export/course/{course_id}/csv")
async def export_course_csv(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current: Professor = Depends(get_current_professor),
):
    from app.services.csv_exporter import export_course_csv as _export

    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    csv_str = await _export(course_id, db)
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=course_{course_id}.csv"},
    )
