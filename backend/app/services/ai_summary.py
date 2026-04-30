from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a classroom analytics assistant. "
    "Given smart classroom data, write 2-3 sentences: identify the single most important finding "
    "and give one concrete recommendation. Use numbers. Plain English only."
)


def _model() -> str:
    return os.getenv("OLLAMA_MODEL", "phi3:latest")


def _ollama_base() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _context_to_prompt(context: dict) -> str:
    """Flatten a context dict into a compact sentence string for small LLMs."""
    scope = context.get("scope", "unknown")
    label = context.get("label", "")
    period = context.get("period", "")
    parts = [f"Scope: {scope} — {label} ({period})."]

    if "overview" in context:
        ov = context["overview"]
        parts.append(
            f"Sessions: {ov.get('total_sessions', 0)}. "
            f"Avg attendance: {round(ov.get('avg_attendance_rate', 0) * 100)}%. "
            f"At-risk students: {ov.get('at_risk_count', 0)}. "
            f"Active alerts: {ov.get('active_alerts_count', 0)}. "
            f"Comfort: {ov.get('comfort_score', 'N/A')}/100."
        )

    if "attendance_summary" in context:
        att = context["attendance_summary"]
        rate = att.get("avg_rate") or att.get("rate") or 0
        trend = att.get("trend", "")
        sessions = att.get("total_sessions", "")
        line = f"Attendance: {round(rate * 100)}%"
        if trend:
            line += f" ({trend} trend)"
        if sessions:
            line += f". Sessions analysed: {sessions}"
        parts.append(line + ".")

    if "at_risk_students" in context:
        parts.append(f"Students at risk: {context['at_risk_students']}.")

    if "env_summary" in context:
        env = context["env_summary"]
        env_parts = []
        if env.get("comfort_score") is not None:
            env_parts.append(f"comfort {env['comfort_score']}/100")
        if env.get("avg_temp") is not None:
            env_parts.append(f"avg temp {env['avg_temp']}°C")
        if env.get("avg_air_quality") is not None:
            env_parts.append(f"avg AQ {env['avg_air_quality']} ppm")
        if env.get("days_monitored") is not None:
            env_parts.append(f"{env['days_monitored']} days monitored")
        if env_parts:
            parts.append(f"Environment: {', '.join(env_parts)}.")

    if context.get("top_at_risk_courses"):
        courses = ", ".join(
            f"{c['course']} ({c['flagged_students']} flagged)"
            for c in context["top_at_risk_courses"]
        )
        parts.append(f"At-risk courses: {courses}.")

    if context.get("recent_alerts"):
        parts.append(f"Recent alerts: {', '.join(context['recent_alerts'])}.")

    if context.get("anomalies"):
        parts.append(f"Anomalies: {'; '.join(context['anomalies'])}.")

    return " ".join(parts)


async def generate_summary(
    scope: str,
    scope_id: str,
    context: dict,
    redis_client,
) -> dict:
    cache_key = f"ai_summary:{scope}:{scope_id}"
    ttl = int(os.getenv("AI_SUMMARY_CACHE_TTL", "600"))

    cached = await redis_client.get(cache_key)
    if cached:
        logger.info("AI summary cache hit: %s", cache_key)
        return json.loads(cached)

    url = f"{_ollama_base()}/api/chat"
    payload = {
        "model": _model(),
        "stream": False,
        "options": {
            "num_predict": 120,
            "temperature": 0.5,
        },
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _context_to_prompt(context)},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            narrative = resp.json()["message"]["content"].strip()
    except httpx.TransportError as exc:
        logger.error("Ollama transport error at %s: %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Ollama not reachable — ensure it is running at {_ollama_base()}",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama returned HTTP %s: %s", exc.response.status_code, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Ollama error ({exc.response.status_code}) — model '{_model()}' may not be available",
        )
    except Exception as exc:
        logger.error("Ollama request failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI summary generation failed")

    result = {
        "narrative": narrative,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    await redis_client.set(cache_key, json.dumps(result), ex=ttl)
    return result
