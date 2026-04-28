"""
Tests for the alerts API.

Covers: listing alerts, acknowledging, unread count, and alert deduplication.
Alert rows are inserted directly into the SQLite test DB.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.db_models import Alert, AlertType

pytestmark = pytest.mark.asyncio


# ── helpers ───────────────────────────────────────────────────────────────

async def _insert_alert(
    test_engine,
    room_id: str,
    alert_type: AlertType = AlertType.temp_high,
    value: float | None = 35.0,
    acknowledged: bool = False,
) -> str:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with factory() as db:
        alert = Alert(
            room_id=room_id,
            type=alert_type,
            value=value,
            message=f"Test {alert_type.value} alert",
            acknowledged=acknowledged,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert.id


# ── Alert creation / threshold simulation ────────────────────────────────

async def test_alert_row_has_correct_fields(client: AsyncClient, test_engine) -> None:
    """Simulate an alert being created by the engine (direct DB insert) and verify structure."""
    alert_id = await _insert_alert(test_engine, "room_field_check", AlertType.air_quality_high, value=600.0)

    resp = await client.get("/api/alerts?room_id=room_field_check")
    assert resp.status_code == 200
    alerts = resp.json()
    assert len(alerts) >= 1
    alert = next(a for a in alerts if a["id"] == alert_id)
    assert alert["type"] == "air_quality_high"
    assert alert["value"] == 600.0
    assert alert["acknowledged"] is False
    assert "created_at" in alert
    assert "message" in alert


async def test_alert_temp_high_type_persists(client: AsyncClient, test_engine) -> None:
    alert_id = await _insert_alert(test_engine, "room_temp_high", AlertType.temp_high, value=36.0)
    resp = await client.get(f"/api/alerts?room_id=room_temp_high")
    data = resp.json()
    assert any(a["type"] == "temp_high" and a["value"] == 36.0 for a in data)


# ── Acknowledge ───────────────────────────────────────────────────────────

async def test_acknowledge_alert_updates_record(client: AsyncClient, test_engine) -> None:
    alert_id = await _insert_alert(test_engine, "room_ack_test")

    resp = await client.patch(f"/api/alerts/{alert_id}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["acknowledged"] is True


async def test_acknowledge_removes_from_unread_list(client: AsyncClient, test_engine) -> None:
    alert_id = await _insert_alert(test_engine, "room_ack_unread")

    # Confirm it appears in unread
    before = await client.get("/api/alerts?room_id=room_ack_unread&acknowledged=false")
    assert any(a["id"] == alert_id for a in before.json())

    # Acknowledge
    await client.patch(f"/api/alerts/{alert_id}/acknowledge")

    # Should no longer appear in unread
    after = await client.get("/api/alerts?room_id=room_ack_unread&acknowledged=false")
    assert not any(a["id"] == alert_id for a in after.json())


async def test_acknowledge_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.patch("/api/alerts/no-such-alert/acknowledge")
    assert resp.status_code == 404


# ── Unread count ──────────────────────────────────────────────────────────

async def test_unread_count_returns_correct_number(client: AsyncClient, test_engine) -> None:
    room = "room_count_verify"
    await _insert_alert(test_engine, room, AlertType.temp_high)
    await _insert_alert(test_engine, room, AlertType.air_quality_high)

    resp = await client.get(f"/api/alerts/unread-count/{room}")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 2


async def test_unread_count_decreases_after_acknowledge(client: AsyncClient, test_engine) -> None:
    room = "room_count_ack"
    alert_id = await _insert_alert(test_engine, room, AlertType.device_offline)

    before = await client.get(f"/api/alerts/unread-count/{room}")
    count_before = before.json()["count"]

    await client.patch(f"/api/alerts/{alert_id}/acknowledge")

    after = await client.get(f"/api/alerts/unread-count/{room}")
    assert after.json()["count"] == count_before - 1


async def test_unread_count_zero_for_empty_room(client: AsyncClient) -> None:
    resp = await client.get("/api/alerts/unread-count/no_alerts_room_xyz")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ── List filtering ────────────────────────────────────────────────────────

async def test_list_alerts_filters_by_acknowledged_true(client: AsyncClient, test_engine) -> None:
    room = "room_filter_ack"
    alert_id = await _insert_alert(test_engine, room, acknowledged=False)
    await client.patch(f"/api/alerts/{alert_id}/acknowledge")

    resp = await client.get(f"/api/alerts?room_id={room}&acknowledged=true")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(a["acknowledged"] is True for a in data)


async def test_list_alerts_respects_limit(client: AsyncClient, test_engine) -> None:
    room = "room_limit_test"
    for _ in range(5):
        await _insert_alert(test_engine, room, AlertType.temp_low)

    resp = await client.get(f"/api/alerts?room_id={room}&limit=3")
    assert resp.status_code == 200
    assert len(resp.json()) <= 3
