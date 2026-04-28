"""
Tests for the WebSocket ConnectionManager and endpoint.

WebSocket integration tests are unit-level: they instantiate ConnectionManager
directly and pass AsyncMock WebSocket objects, avoiding the need for a live
server or special async WS client library.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ── ConnectionManager unit tests ──────────────────────────────────────────

async def test_broadcast_reaches_connected_clients() -> None:
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws, "room1")

    await manager.broadcast("room1", {"type": "test", "room_id": "room1"})

    ws.send_text.assert_called_once()
    payload = json.loads(ws.send_text.call_args[0][0])
    assert payload["type"] == "test"


async def test_broadcast_does_not_reach_other_rooms() -> None:
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws_r1 = AsyncMock()
    ws_r2 = AsyncMock()
    await manager.connect(ws_r1, "room1")
    await manager.connect(ws_r2, "room2")

    await manager.broadcast("room1", {"type": "ping"})

    ws_r1.send_text.assert_called_once()
    ws_r2.send_text.assert_not_called()


async def test_disconnect_removes_client() -> None:
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws = AsyncMock()
    await manager.connect(ws, "room1")
    manager.disconnect(ws, "room1")

    await manager.broadcast("room1", {"type": "ping"})

    ws.send_text.assert_not_called()


async def test_broadcast_all_reaches_all_rooms() -> None:
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws_r1 = AsyncMock()
    ws_r2 = AsyncMock()
    await manager.connect(ws_r1, "room1")
    await manager.connect(ws_r2, "room2")

    await manager.broadcast_all({"type": "global"})

    ws_r1.send_text.assert_called_once()
    ws_r2.send_text.assert_called_once()


async def test_dead_client_removed_on_broadcast() -> None:
    """A WebSocket that raises on send should be auto-removed."""
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws = AsyncMock()
    ws.send_text = AsyncMock(side_effect=Exception("connection closed"))
    await manager.connect(ws, "room1")

    await manager.broadcast("room1", {"type": "ping"})

    # Client should be removed after failed send
    assert ws not in manager._connections.get("room1", set())


async def test_snapshot_content() -> None:
    from app.api.websocket import ConnectionManager

    manager = ConnectionManager()
    ws = AsyncMock()

    with (
        patch(
            "app.api.websocket.get_sensor_latest",
            new_callable=AsyncMock,
            return_value={"temperature": {"value": 25.0, "unit": "C"}},
        ),
        patch(
            "app.api.websocket.get_relay_state",
            new_callable=AsyncMock,
            return_value="auto",
        ),
        patch(
            "app.api.websocket.is_device_online",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        await manager.connect(ws, "room1")
        await manager.send_snapshot(ws, "room1")

    ws.send_text.assert_called_once()
    payload = json.loads(ws.send_text.call_args[0][0])
    assert payload["type"] == "snapshot"
    assert payload["room_id"] == "room1"
    assert payload["device_online"] is True
    assert "relay" in payload
    assert "sensors" in payload


# ── WebSocket route registration ──────────────────────────────────────────

async def test_ws_route_registered(client) -> None:  # noqa: F811 — client fixture
    """The /ws/classroom/{room_id} route should be registered in the app."""
    from app.main import app

    ws_routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert any("classroom" in p for p in ws_routes), (
        f"No /ws/classroom route found. Routes: {ws_routes}"
    )
