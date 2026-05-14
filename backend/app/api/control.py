import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_professor
from app.models.db_models import Professor
from app.models.schemas import ControlStatusResponse, RelayCommand, RelayCommandResponse
from app.redis_client import get_relay_state, get_redis_pool, get_sensor_latest, is_device_online, set_relay_state

logger = logging.getLogger(__name__)

router = APIRouter()

_DEVICES = {"ac", "lighting"}


async def _send_relay_command(room_id: str, device: str, action: str) -> None:
    from app.services.mqtt_bridge import publish_mqtt
    topic = f"classroom/{room_id}/relay/{device}"
    payload = json.dumps({"action": action})
    await publish_mqtt(topic, payload)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── POST /api/control/ac ──────────────────────────────────────────────────
# Any authenticated professor may control classroom equipment.
# Admin-only access was in place previously; relaxed in Phase 21 to match UX spec.

@router.post("/ac", response_model=RelayCommandResponse)
async def control_ac(body: RelayCommand, _: Professor = Depends(get_current_professor)) -> RelayCommandResponse:
    await set_relay_state(body.room_id, "ac", body.action)
    asyncio.create_task(_send_relay_command(body.room_id, "ac", body.action))
    return RelayCommandResponse(
        room_id=body.room_id,
        device="ac",
        action=body.action,
        ts=_now_utc(),
    )


# ── POST /api/control/lighting ────────────────────────────────────────────

@router.post("/lighting", response_model=RelayCommandResponse)
async def control_lighting(body: RelayCommand, _: Professor = Depends(get_current_professor)) -> RelayCommandResponse:
    await set_relay_state(body.room_id, "lighting", body.action)
    asyncio.create_task(_send_relay_command(body.room_id, "lighting", body.action))
    return RelayCommandResponse(
        room_id=body.room_id,
        device="lighting",
        action=body.action,
        ts=_now_utc(),
    )


# ── GET /api/control/status/{room_id} ────────────────────────────────────

@router.get("/status/{room_id}", response_model=ControlStatusResponse)
async def get_control_status(room_id: str) -> ControlStatusResponse:
    try:
        ac_state, lighting_state, online, sensors = await asyncio.gather(
            get_relay_state(room_id, "ac"),
            get_relay_state(room_id, "lighting"),
            is_device_online(room_id),
            get_sensor_latest(room_id),
        )
    except Exception as exc:
        logger.warning("Redis unavailable for control status: %s", exc)
        raise HTTPException(status_code=503, detail="Cache unavailable")

    def _val(key: str) -> float | None:
        entry = sensors.get(key)
        return entry["value"] if entry else None

    return ControlStatusResponse(
        room_id=room_id,
        ac=ac_state,
        lighting=lighting_state,
        device_online=online,
        temperature=_val("temperature"),
        humidity=_val("humidity"),
        air_quality=_val("air_quality"),
    )
