from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import SensorReading, SensorType
from app.models.schemas import SensorLatestResponse, SensorReadingResponse
from app.redis_client import get_sensor_latest

router = APIRouter()


@router.get("/latest", response_model=SensorLatestResponse)
async def get_latest_sensors(
    room_id: str = Query(default="room1", description="Room identifier"),
) -> SensorLatestResponse:
    try:
        sensors = await get_sensor_latest(room_id)
    except Exception:
        sensors = {}
    return SensorLatestResponse(room_id=room_id, sensors=sensors)


@router.get("/history", response_model=list[SensorReadingResponse])
async def get_sensor_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    room_id: str = Query(default="room1"),
    sensor_type: SensorType | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, description="ISO-8601 start timestamp"),
    to_ts: datetime | None = Query(default=None, description="ISO-8601 end timestamp"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[SensorReadingResponse]:
    try:
        stmt = (
            select(SensorReading)
            .where(SensorReading.room_id == room_id)
            .order_by(SensorReading.recorded_at.desc())
            .limit(limit)
        )

        if sensor_type is not None:
            stmt = stmt.where(SensorReading.sensor_type == sensor_type)
        if from_ts is not None:
            stmt = stmt.where(SensorReading.recorded_at >= from_ts)
        if to_ts is not None:
            stmt = stmt.where(SensorReading.recorded_at <= to_ts)

        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [SensorReadingResponse.model_validate(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc
