"""
At-risk student explanation engine.

Pipeline: compute attendance profiles for flagged students only,
call Ollama once per student, upsert results.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, case, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import (
    AttendanceRecord,
    AttendanceStatus,
    AtRiskExplanation,
    Course,
    SensorReading,
    SensorType,
    Session,
    SessionStatus,
    Student,
    course_students,
)

logger = logging.getLogger(__name__)

_FRESH_SKIP_SECONDS = 600  # skip students explained within the last 10 minutes


def _age_seconds(dt: datetime) -> float:
    """Return seconds elapsed since `dt`, normalising naive datetimes to UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


# ── Batch sensor + peer queries ───────────────────────────────────────────

async def _batch_sensor_avgs(db: AsyncSession, student_id: str) -> dict[str, dict]:
    """Single query: avg temp + air quality during each missed session, grouped by course."""
    missed_sq = (
        select(
            Session.id.label("session_id"),
            Session.course_id,
            Session.room_id,
            Session.started_at,
            Session.ended_at,
        )
        .join(AttendanceRecord, AttendanceRecord.session_id == Session.id)
        .where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.status.in_([AttendanceStatus.absent, AttendanceStatus.late]),
            Session.status == SessionStatus.ended,
            Session.ended_at.is_not(None),
        )
        .subquery()
    )

    rows = (await db.execute(
        select(
            missed_sq.c.course_id,
            SensorReading.sensor_type,
            func.avg(SensorReading.value).label("avg_val"),
        )
        .select_from(missed_sq)
        .join(
            SensorReading,
            and_(
                SensorReading.room_id == missed_sq.c.room_id,
                SensorReading.recorded_at >= missed_sq.c.started_at,
                SensorReading.recorded_at <= missed_sq.c.ended_at,
                SensorReading.sensor_type.in_([SensorType.temperature, SensorType.air_quality]),
            ),
        )
        .group_by(missed_sq.c.course_id, SensorReading.sensor_type)
    )).all()

    # {course_id: {sensor_type: avg_val}}
    result: dict[str, dict] = defaultdict(dict)
    for course_id, s_type, avg_val in rows:
        if avg_val is not None:
            result[course_id][s_type] = avg_val
    return result


async def _batch_peer_rates(db: AsyncSession, student_id: str, course_ids: list[str]) -> dict[str, float]:
    """Single query: class-average attendance rate for each course (excluding this student)."""
    if not course_ids:
        return {}
    rows = (await db.execute(
        select(
            Session.course_id,
            func.sum(case((AttendanceRecord.status == AttendanceStatus.present, 1), else_=0)).label("present"),
            func.count().label("total"),
        )
        .select_from(AttendanceRecord)
        .join(Session, Session.id == AttendanceRecord.session_id)
        .where(
            Session.course_id.in_(course_ids),
            Session.status == SessionStatus.ended,
            AttendanceRecord.student_id != student_id,
        )
        .group_by(Session.course_id)
    )).all()
    return {r.course_id: (r.present / r.total if r.total else None) for r in rows}


# ── Profile builder ───────────────────────────────────────────────────────

async def build_student_profile(db: AsyncSession, student_id: str) -> dict | None:
    student = await db.get(Student, student_id)
    if not student:
        return None

    # Overall attendance
    overall = (await db.execute(
        select(
            func.sum(case((AttendanceRecord.status == AttendanceStatus.present, 1), else_=0)).label("present"),
            func.count().label("total"),
        )
        .join(Session, Session.id == AttendanceRecord.session_id)
        .where(
            AttendanceRecord.student_id == student_id,
            Session.status == SessionStatus.ended,
        )
    )).one()

    total_sessions = overall.total or 0
    if total_sessions == 0:
        return {
            "student_id": student_id,
            "student_name": student.name,
            "student_number": student.student_id,
            "overall_attendance_rate": 0.0,
            "total_sessions": 0,
            "courses": [],
        }

    overall_rate = (overall.present or 0) / total_sessions

    # All records with session + course context — one query
    rows = (await db.execute(
        select(AttendanceRecord, Session, Course)
        .join(Session, Session.id == AttendanceRecord.session_id)
        .join(Course, Course.id == Session.course_id)
        .where(
            AttendanceRecord.student_id == student_id,
            Session.status == SessionStatus.ended,
        )
        .order_by(Course.id, Session.started_at)
    )).all()

    courses_map: dict[str, dict] = defaultdict(lambda: {"course": None, "present": 0, "total": 0, "missed": 0})
    for ar, sess, course in rows:
        entry = courses_map[course.id]
        entry["course"] = course
        entry["total"] += 1
        if ar.status == AttendanceStatus.present:
            entry["present"] += 1
        elif ar.status in (AttendanceStatus.absent, AttendanceStatus.late):
            entry["missed"] += 1

    course_ids = list(courses_map.keys())

    # Batch queries — replaces N×M individual queries
    sensor_avgs = await _batch_sensor_avgs(db, student_id)
    peer_rates = await _batch_peer_rates(db, student_id, course_ids)

    courses_list = []
    for course_id, data in courses_map.items():
        course = data["course"]
        total = data["total"]
        present = data["present"]
        missed_count = data["missed"]
        rate = present / total if total > 0 else 0.0

        avgs = sensor_avgs.get(course_id, {})
        avg_temp = avgs.get(SensorType.temperature)
        avg_aq = avgs.get(SensorType.air_quality)

        peer_rate = peer_rates.get(course_id)
        peer_delta = round(rate - peer_rate, 4) if peer_rate is not None else None

        courses_list.append({
            "course_id": course_id,
            "course_code": course.code,
            "course_name": course.name,
            "attendance_rate": round(rate, 4),
            "sessions_total": total,
            "sessions_missed": missed_count,
            "avg_temp_on_missed": round(avg_temp, 2) if avg_temp is not None else None,
            "avg_aq_on_missed": round(avg_aq, 2) if avg_aq is not None else None,
            "peer_delta": peer_delta,
        })

    return {
        "student_id": student_id,
        "student_name": student.name,
        "student_number": student.student_id,
        "overall_attendance_rate": round(overall_rate, 4),
        "total_sessions": total_sessions,
        "courses": courses_list,
    }


# ── Ollama client ─────────────────────────────────────────────────────────

async def _check_ollama_ready(client: httpx.AsyncClient) -> tuple[bool, str]:
    """Returns (is_ready, reason). Checks reachability and model availability."""
    try:
        resp = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=10.0)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        logger.info("Ollama models available: %s", models)
        base = settings.ollama_model.split(":")[0]
        if not any(m == settings.ollama_model or m.startswith(base + ":") for m in models):
            return False, f"model '{settings.ollama_model}' not found in Ollama (available: {models})"
        return True, "ok"
    except httpx.ConnectError as exc:
        return False, f"cannot connect to Ollama at {settings.ollama_base_url}: {exc}"
    except Exception as exc:
        return False, f"Ollama health check failed: {exc}"


async def call_ollama(client: httpx.AsyncClient, prompt: str) -> str | None:
    """Single call to Ollama. Accepts a shared client to avoid per-call TCP overhead."""
    try:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": 180, "temperature": 0.3},
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        # Surface the actual Ollama error body (e.g. "model not found")
        try:
            body = exc.response.json()
        except Exception:
            body = exc.response.text
        logger.warning("Ollama HTTP %s: %s", exc.response.status_code, body)
        return None
    except Exception as exc:
        logger.warning("Ollama call failed: %s", exc)
        return None


# ── Prompt builder — one call per student ─────────────────────────────────

def build_combined_prompt(student_name: str, overall_rate: float, courses: list[dict]) -> str:
    rate_pct = round(overall_rate * 100, 1)
    lines = []
    for c in courses:
        attended = c["sessions_total"] - c["sessions_missed"]
        line = (
            f"- {c['course_code']} ({c['course_name']}): "
            f"attended {attended}/{c['sessions_total']}"
        )
        if c["peer_delta"] is not None:
            delta_pct = round(abs(c["peer_delta"]) * 100, 1)
            direction = "below" if c["peer_delta"] < 0 else "above"
            line += f", {delta_pct}% {direction} class average"
        if c["avg_temp_on_missed"] is not None:
            line += f", avg temp on absent days {c['avg_temp_on_missed']}°C"
        if c["avg_aq_on_missed"] is not None:
            line += f", avg air quality {c['avg_aq_on_missed']} ppm"
        lines.append(line)

    courses_text = "\n".join(lines)
    return (
        "You are an academic attendance analyst. Write 3-4 sentences summarizing this student's "
        "attendance pattern across all their courses. Identify cross-course patterns if present. "
        "Base your response only on the data below. Do not mention health, family, or personal reasons. "
        "No bullet points. Plain prose. Keep under 100 words.\n\n"
        f"Student: {student_name}\n"
        f"Overall attendance: {rate_pct}%\n\n"
        f"Per-course data:\n{courses_text}"
    )


# ── Upsert helper ─────────────────────────────────────────────────────────

async def _upsert_explanation(
    db: AsyncSession,
    student_id: str,
    overall_rate: float,
    per_course_data: list[dict],
    summary: str | None,
    ollama_ok: bool,
) -> None:
    existing = (await db.execute(
        select(AtRiskExplanation).where(AtRiskExplanation.student_id == student_id)
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.overall_attendance_rate = overall_rate
        existing.per_course_data = per_course_data
        existing.summary_explanation = summary
        existing.ollama_reachable = ollama_ok
        existing.generated_at = now
    else:
        db.add(AtRiskExplanation(
            student_id=student_id,
            overall_attendance_rate=overall_rate,
            per_course_data=per_course_data,
            summary_explanation=summary,
            ollama_reachable=ollama_ok,
            generated_at=now,
        ))
    await db.commit()


# ── Main pipeline ─────────────────────────────────────────────────────────

async def run_at_risk_pipeline() -> dict:
    from app.services.insights_engine import insights_engine

    threshold = settings.at_risk_threshold
    processed = skipped_fresh = skipped_no_data = skipped_ollama_down = 0

    logger.info("At-risk pipeline starting (threshold=%.0f%%)", threshold * 100)

    async with AsyncSessionLocal() as db:
        # 1. Only fetch at-risk student IDs — skip the full-table scan
        try:
            flagged = await insights_engine.get_at_risk_students(db, professor_id=None, threshold=threshold)
        except Exception as exc:
            logger.error("At-risk pipeline: failed to fetch flagged students: %s", exc, exc_info=True)
            raise
        if not flagged:
            logger.info("At-risk pipeline: no at-risk students found")
            return {"processed": 0, "skipped_fresh": 0, "skipped_no_data": 0, "skipped_ollama_down": 0}
        logger.info("At-risk pipeline: %d at-risk students found", len(flagged))

        at_risk_ids = [f["student_id"] for f in flagged]
        at_risk_id_set = set(at_risk_ids)

        # 2. Load ALL existing explanations — needed both for freshness check and stale cleanup
        all_existing_expls = {
            e.student_id: e for e in (await db.execute(
                select(AtRiskExplanation)
            )).scalars().all()
        }
        existing_expls = {sid: e for sid, e in all_existing_expls.items() if sid in at_risk_id_set}

        # 3. Remove stale rows for students who recovered above threshold
        stale_ids = [sid for sid in all_existing_expls if sid not in at_risk_id_set]
        if stale_ids:
            await db.execute(delete(AtRiskExplanation).where(AtRiskExplanation.student_id.in_(stale_ids)))
            await db.commit()

        # 4. Process each at-risk student with a single shared HTTP client
        async with httpx.AsyncClient(timeout=300.0) as http:
            # Pre-flight: check Ollama is up and model is present before iterating students
            ollama_ready, ollama_reason = await _check_ollama_ready(http)
            if not ollama_ready:
                logger.error("At-risk pipeline: Ollama not ready — %s. Writing rows with ollama_reachable=False.", ollama_reason)
                for student_id in at_risk_ids:
                    expl = existing_expls.get(student_id)
                    if expl and expl.ollama_reachable is False:
                        continue  # already marked unavailable, no point re-writing
                    try:
                        profile = await build_student_profile(db, student_id)
                        if not profile or profile["total_sessions"] == 0:
                            continue
                        per_course_data = [{**c, "explanation": None} for c in profile["courses"]]
                        await _upsert_explanation(db, student_id, profile["overall_attendance_rate"], per_course_data, None, False)
                    except Exception as exc:
                        logger.error("Error writing unavailable row for student %s: %s", student_id, exc)
                skipped_ollama_down = len(at_risk_ids)
                return {"processed": 0, "skipped_fresh": skipped_fresh, "skipped_no_data": 0, "skipped_ollama_down": skipped_ollama_down}

            for student_id in at_risk_ids:
                expl = existing_expls.get(student_id)

                # 4a. Skip if explanation was generated recently and Ollama was reachable
                if expl and expl.ollama_reachable and expl.generated_at:
                    if _age_seconds(expl.generated_at) < _FRESH_SKIP_SECONDS:
                        skipped_fresh += 1
                        continue

                try:
                    profile = await build_student_profile(db, student_id)
                    if not profile or profile["total_sessions"] == 0:
                        skipped_no_data += 1
                        continue

                    # 4b. One Ollama call per student instead of N+1
                    ollama_ok = True
                    summary = None
                    if profile["courses"]:
                        prompt = build_combined_prompt(
                            profile["student_name"],
                            profile["overall_attendance_rate"],
                            profile["courses"],
                        )
                        logger.info("At-risk pipeline: calling Ollama for student %s (%s)", student_id, profile["student_name"])
                        summary = await call_ollama(http, prompt)
                        if summary is None:
                            logger.warning("At-risk pipeline: Ollama returned None for student %s — marking ollama_reachable=False", student_id)
                            ollama_ok = False
                            skipped_ollama_down += 1
                        else:
                            logger.info("At-risk pipeline: Ollama succeeded for student %s", student_id)

                    # per_course_data carries numerical stats; explanation field is null
                    # (the summary covers all courses in one prose block)
                    per_course_data = [{**c, "explanation": None} for c in profile["courses"]]

                    await _upsert_explanation(
                        db,
                        student_id,
                        profile["overall_attendance_rate"],
                        per_course_data,
                        summary,
                        ollama_ok,
                    )
                    processed += 1

                except Exception as exc:
                    logger.error("Error processing student %s: %s", student_id, exc)

    logger.info(
        "At-risk pipeline done — processed=%d skipped_fresh=%d skipped_no_data=%d skipped_ollama_down=%d",
        processed, skipped_fresh, skipped_no_data, skipped_ollama_down,
    )
    return {
        "processed": processed,
        "skipped_fresh": skipped_fresh,
        "skipped_no_data": skipped_no_data,
        "skipped_ollama_down": skipped_ollama_down,
    }


# ── Model pull on startup ─────────────────────────────────────────────────

async def ensure_model_pulled() -> None:
    model_name = settings.ollama_model
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            # Normalize: "phi3:mini" matches "phi3:mini", "phi3:mini:latest", etc.
            base = model_name.split(":")[0]
            if any(m == model_name or m.startswith(base + ":") for m in models):
                logger.info("Model %s already present in Ollama", model_name)
                return
            logger.info("%s not found in Ollama — pulling in background", model_name)
            asyncio.create_task(_pull_model(model_name))
    except Exception as exc:
        logger.warning("Ollama unreachable at startup (model pull skipped): %s", exc)


async def _pull_model(model_name: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            await client.post(
                f"{settings.ollama_base_url}/api/pull",
                json={"name": model_name, "stream": False},
            )
            logger.info("Model %s pulled successfully", model_name)
    except Exception as exc:
        logger.warning("Model pull failed for %s: %s", model_name, exc)
