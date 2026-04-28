"""
WebSocket endpoint and ConnectionManager for live classroom streaming.
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.redis_client import get_relay_state, get_sensor_latest, is_device_online

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(room_id, set()).add(websocket)
        logger.info("WS connected: room=%s clients=%d", room_id, len(self._connections[room_id]))

    def disconnect(self, websocket: WebSocket, room_id: str) -> None:
        room = self._connections.get(room_id, set())
        room.discard(websocket)
        if not room:
            self._connections.pop(room_id, None)
        logger.info("WS disconnected: room=%s", room_id)

    async def broadcast(self, room_id: str, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(room_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, room_id)

    async def broadcast_all(self, payload: dict[str, Any]) -> None:
        for room_id in list(self._connections):
            await self.broadcast(room_id, payload)

    async def send_snapshot(self, websocket: WebSocket, room_id: str) -> None:
        """Send initial state to a newly connected client."""
        try:
            sensors = await get_sensor_latest(room_id)
            ac = await get_relay_state(room_id, "ac")
            lighting = await get_relay_state(room_id, "lighting")
            online = await is_device_online(room_id)
            snapshot = {
                "type": "snapshot",
                "room_id": room_id,
                "sensors": sensors,
                "relay": {"ac": ac, "lighting": lighting},
                "device_online": online,
            }
            await websocket.send_text(json.dumps(snapshot))
        except Exception as exc:
            logger.warning("Failed to send snapshot for room %s: %s", room_id, exc)


connection_manager = ConnectionManager()


@router.websocket("/classroom/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    await connection_manager.connect(websocket, room_id)
    await connection_manager.send_snapshot(websocket, room_id)

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, room_id)
    except Exception as exc:
        logger.warning("WS error for room %s: %s", room_id, exc)
        connection_manager.disconnect(websocket, room_id)
