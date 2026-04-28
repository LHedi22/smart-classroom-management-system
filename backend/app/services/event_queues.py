"""
Shared asyncio queues consumed by the WebSocket broadcaster (Phase 7).

Import these queues from any service to publish events without
creating circular imports between services.
"""
import asyncio

# Sensor readings from MQTT bridge → WebSocket clients
sensor_event_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)

# Attendance events from recognition loop → WebSocket clients
attendance_event_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)

# Alerts from alert engine / recognition loop → WebSocket clients
alert_event_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
