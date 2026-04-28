from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db_models import Alert
from app.models.schemas import AlertResponse

router = APIRouter()


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    room_id: str | None = Query(None),
    acknowledged: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[Alert]:
    q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if room_id is not None:
        q = q.where(Alert.room_id == room_id)
    if acknowledged is not None:
        q = q.where(Alert.acknowledged == acknowledged)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.patch("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(alert_id: str, db: AsyncSession = Depends(get_db)) -> Alert:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/unread-count/{room_id}")
async def unread_count(room_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(func.count()).where(
            Alert.room_id == room_id,
            Alert.acknowledged == False,  # noqa: E712
        )
    )
    return {"count": result.scalar_one()}
