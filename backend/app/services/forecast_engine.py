"""
Attendance forecasting pipeline.

Per course: pull the last FORECAST_WINDOW ended sessions, compute a trend
sequence, classify it with deterministic delta math, then call Ollama once
to produce an interpretation sentence and a projected next-session rate.

Reuses call_ollama / _check_ollama_ready from at_risk_engine directly —
no duplication of the Ollama HTTP logic.
"""
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.db_models import (
    AttendanceForecast,
    AttendanceRecord,
    AttendanceStatus,
    Course,
    Session,
    SessionStatus,
    course_students,
)
from app.services.at_risk_engine import _age_seconds, _check_ollama_ready, call_ollama

logger = logging.getLogger(__name__)

_MIN_SESSIONS = 3
_FRESH_SKIP_SECONDS = 1800  # matches the Redis lock TTL

_ACTION_MAP = {
    "accelerating_decline": "consider_intervention",
    "steady_decline": "monitor_closely",
    "stable": "on_track",
    "recovering": "on_track",
}


# ── Trend classification (deterministic — no LLM) ─────────────────────────

def _classify_trend(rates: list[float]) -> tuple[str, str]:
    """Return (trend_classification, confidence_level) from a rate sequence.

    Rates are 0.0–1.0 fractions in chronological order. Classification is
    purely mathematical so it works even when Ollama is unreachable.
    """
    if len(rates) < 2:
        return "stable", "low"

    deltas = [rates[i + 1] - rates[i] for i in range(len(rates) - 1)]
    mean_delta = sum(deltas) / len(deltas)

    if len(rates) >= 6:
        confidence = "high"
    elif len(rates) >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    if mean_delta < -0.02:
        # Accelerating: second half of deltas is meaningfully worse than first half
        mid = len(deltas) // 2
        if mid > 0:
            first_avg = sum(deltas[:mid]) / mid
            second_avg = sum(deltas[mid:]) / len(deltas[mid:])
            if second_avg < first_avg - 0.01:
                return "accelerating_decline", confidence
        return "steady_decline", confidence
    elif mean_delta > 0.015:
        return "recovering", confidence
    else:
        return "stable", confidence


# ── Trend data query ──────────────────────────────────────────────────────

async def _get_course_trend(db: AsyncSession, course_id: str, window: int) -> list[dict]:
    """Single query: last `window` ended sessions with per-session attendance rate.

    Rate = (present + late) / enrolled. Returns list in chronological order.
    """
    enrolled_sq = (
        select(func.count())
        .select_from(course_students)
        .where(course_students.c.course_id == course_id)
        .scalar_subquery()
    )

    rows = (await db.execute(
        select(
            Session.id,
            Session.started_at,
            func.coalesce(
                func.sum(case(
                    (AttendanceRecord.status.in_([AttendanceStatus.present, AttendanceStatus.late]), 1),
                    else_=0,
                )),
                0,
            ).label("present_count"),
            enrolled_sq.label("total_enrolled"),
        )
        .select_from(Session)
        .outerjoin(AttendanceRecord, AttendanceRecord.session_id == Session.id)
        .where(
            Session.course_id == course_id,
            Session.status == SessionStatus.ended,
        )
        .group_by(Session.id, Session.started_at)
        .order_by(Session.started_at.desc())
        .limit(window)
    )).all()

    points = []
    for row in reversed(rows):  # DESC query → reverse to chronological
        total = row.total_enrolled or 0
        rate = (row.present_count / total) if total > 0 else 0.0
        points.append({
            "session_date": row.started_at.isoformat(),
            "rate": round(rate, 4),
        })
    return points


# ── LLM prompt & response parsing ────────────────────────────────────────

def build_forecast_prompt(course_code: str, course_name: str, trend_points: list[dict]) -> str:
    """Build the Ollama prompt. Classification is already computed deterministically;
    the LLM only produces a projected rate and a prose interpretation sentence."""
    rates_str = ", ".join(f"{round(p['rate'] * 100, 1)}%" for p in trend_points)
    return (
        "You are an academic attendance analyst. "
        "Analyze the attendance trend below. "
        "Reply with EXACTLY 2 lines and nothing else:\n"
        "EXPECTED_NEXT: <integer 0-100 for expected attendance % at the next session, or N/A>\n"
        "INTERPRETATION: <one sentence, plain prose, under 30 words, "
        "no health or personal reasons>\n\n"
        f"Course: {course_code} — {course_name}\n"
        f"Attendance per session (chronological): {rates_str}"
    )


def _parse_llm_response(text: str) -> tuple[float | None, str | None]:
    """Extract expected_next_rate (0.0–1.0) and interpretation from LLM output.

    Never raises — returns (None, None) on any parse failure so the row is
    still written with ollama_reachable=True but null interpretive fields.
    """
    expected_next_rate: float | None = None
    interpretation: str | None = None

    for line in text.strip().splitlines():
        upper = line.upper().strip()
        if upper.startswith("EXPECTED_NEXT:"):
            val = line.split(":", 1)[1].strip().replace("%", "").strip()
            if val.upper() not in ("N/A", "NA", ""):
                try:
                    candidate = float(val)
                    if 0.0 <= candidate <= 100.0:
                        expected_next_rate = round(candidate / 100.0, 4)
                except ValueError:
                    pass
        elif upper.startswith("INTERPRETATION:"):
            interpretation = line.split(":", 1)[1].strip() or None

    return expected_next_rate, interpretation


# ── Upsert helper ─────────────────────────────────────────────────────────

async def _upsert_forecast(
    db: AsyncSession,
    course_id: str,
    trend_data: list[dict],
    expected_next_rate: float | None,
    trend_classification: str | None,
    confidence_level: str | None,
    interpretation: str | None,
    suggested_action: str | None,
    ollama_reachable: bool,
) -> None:
    existing = (await db.execute(
        select(AttendanceForecast).where(AttendanceForecast.course_id == course_id)
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.trend_data = trend_data
        existing.expected_next_rate = expected_next_rate
        existing.trend_classification = trend_classification
        existing.confidence_level = confidence_level
        existing.interpretation = interpretation
        existing.suggested_action = suggested_action
        existing.ollama_reachable = ollama_reachable
        existing.generated_at = now
    else:
        db.add(AttendanceForecast(
            course_id=course_id,
            trend_data=trend_data,
            expected_next_rate=expected_next_rate,
            trend_classification=trend_classification,
            confidence_level=confidence_level,
            interpretation=interpretation,
            suggested_action=suggested_action,
            ollama_reachable=ollama_reachable,
            generated_at=now,
        ))
    await db.commit()


# ── Main pipeline ─────────────────────────────────────────────────────────

async def run_forecast_pipeline() -> dict:
    """Generate attendance forecasts for all courses.

    Writes a row for every course — including an empty-trend marker row for
    courses with fewer than _MIN_SESSIONS ended sessions. This ensures the
    frontend's auto-poll always terminates (it stops when all generated_at
    values are set).
    """
    processed = skipped_fresh = skipped_insufficient = skipped_ollama_down = 0

    logger.info("Forecast pipeline starting (window=%d)", settings.forecast_window)

    async with AsyncSessionLocal() as db:
        # All courses + their ended-session count in one query
        course_rows = (await db.execute(
            select(
                Course.id,
                Course.code,
                Course.name,
                func.count(Session.id).label("session_count"),
            )
            .outerjoin(Session, and_(
                Session.course_id == Course.id,
                Session.status == SessionStatus.ended,
            ))
            .group_by(Course.id, Course.code, Course.name)
        )).all()

        if not course_rows:
            logger.info("Forecast pipeline: no courses found")
            return {"processed": 0, "skipped_fresh": 0, "skipped_insufficient": 0, "skipped_ollama_down": 0}

        all_ids = [r.id for r in course_rows]

        existing = {
            f.course_id: f for f in (await db.execute(
                select(AttendanceForecast).where(AttendanceForecast.course_id.in_(all_ids))
            )).scalars().all()
        }

        async with httpx.AsyncClient(timeout=300.0) as http:
            ollama_ready, ollama_reason = await _check_ollama_ready(http)
            if not ollama_ready:
                logger.warning("Forecast pipeline: Ollama not ready — %s", ollama_reason)

            for row in course_rows:
                course_id, course_code, course_name = row.id, row.code, row.name
                session_count = row.session_count or 0
                fc = existing.get(course_id)

                # Freshness check — skip if recently generated and Ollama was up
                if fc and fc.ollama_reachable and fc.generated_at:
                    if _age_seconds(fc.generated_at) < _FRESH_SKIP_SECONDS:
                        skipped_fresh += 1
                        continue

                # Insufficient history — write a marker row so the frontend knows
                if session_count < _MIN_SESSIONS:
                    try:
                        await _upsert_forecast(
                            db, course_id, [], None, None, None, None, None, True
                        )
                    except Exception as exc:
                        logger.error("Forecast: failed marker row for course %s: %s", course_id, exc)
                    skipped_insufficient += 1
                    continue

                try:
                    trend_data = await _get_course_trend(db, course_id, settings.forecast_window)
                    if len(trend_data) < _MIN_SESSIONS:
                        await _upsert_forecast(
                            db, course_id, [], None, None, None, None, None, True
                        )
                        skipped_insufficient += 1
                        continue

                    rates = [p["rate"] for p in trend_data]
                    classification, confidence = _classify_trend(rates)
                    action = _ACTION_MAP.get(classification, "on_track")

                    # Deterministic fields are always written — even if Ollama is down
                    if not ollama_ready:
                        await _upsert_forecast(
                            db, course_id, trend_data,
                            None, classification, confidence, None, action, False,
                        )
                        skipped_ollama_down += 1
                        continue

                    prompt = build_forecast_prompt(course_code, course_name, trend_data)
                    logger.info("Forecast pipeline: calling Ollama for course %s (%s)", course_id, course_code)
                    text = await call_ollama(http, prompt)

                    ollama_ok = text is not None
                    expected_next_rate, interpretation = None, None
                    if text:
                        expected_next_rate, interpretation = _parse_llm_response(text)
                    else:
                        logger.warning("Forecast pipeline: Ollama returned None for course %s", course_id)

                    await _upsert_forecast(
                        db, course_id, trend_data,
                        expected_next_rate, classification, confidence,
                        interpretation, action, ollama_ok,
                    )

                    if ollama_ok:
                        processed += 1
                    else:
                        skipped_ollama_down += 1

                except Exception as exc:
                    logger.error(
                        "Forecast pipeline: error processing course %s: %s", course_id, exc, exc_info=True
                    )

    logger.info(
        "Forecast pipeline done — processed=%d fresh=%d insufficient=%d ollama_down=%d",
        processed, skipped_fresh, skipped_insufficient, skipped_ollama_down,
    )
    return {
        "processed": processed,
        "skipped_fresh": skipped_fresh,
        "skipped_insufficient": skipped_insufficient,
        "skipped_ollama_down": skipped_ollama_down,
    }
