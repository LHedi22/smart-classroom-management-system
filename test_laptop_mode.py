#!/usr/bin/env python3
"""
Smoke test for the laptop-mode end-to-end pipeline.

Tests the full path:
  MQTT publish → Mosquitto → mqtt_bridge.py → sensor_event_queue
  → _drain_queue task → ConnectionManager.broadcast → WebSocket client

Usage:
  pip install paho-mqtt websocket-client
  python test_laptop_mode.py

Requirements:
  - Docker stack must be running (docker compose ... up -d)
  - MOCK_MODE must be false (real MQTT path, not the mock publisher)
  - Mosquitto reachable at localhost:1883
  - Backend reachable at localhost:8000
"""
import json
import sys
import threading
import time

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "classroom/room1/sensors/temperature"
WS_URL = "ws://localhost:8000/ws/classroom/room1"
TIMEOUT_S = 3.0

# Sentinel value — chosen to be outside normal sensor range so we can
# identify our specific test publish among any other traffic.
TEST_VALUE = 99.7


def _check_imports() -> tuple:
    missing = []
    try:
        import paho.mqtt.client as mqtt_mod
    except ImportError:
        mqtt_mod = None
        missing.append("paho-mqtt")
    try:
        import websocket as ws_mod
    except ImportError:
        ws_mod = None
        missing.append("websocket-client")
    if missing:
        print(f"FAIL — missing packages: {', '.join(missing)}")
        print(f"       Run: pip install {' '.join(missing)}")
        sys.exit(1)
    return mqtt_mod, ws_mod


def _make_mqtt_client(mqtt_mod):
    """Create a paho Client compatible with both v1.x and v2.x APIs."""
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        return mqtt_mod.Client(CallbackAPIVersion.VERSION2, client_id="smartcam-smoke-test")
    except ImportError:
        return mqtt_mod.Client(client_id="smartcam-smoke-test")


def main() -> None:
    mqtt_mod, ws_mod = _check_imports()

    received = threading.Event()
    ws_messages: list[dict] = []
    ws_errors: list[str] = []

    # ── WebSocket listener (background thread) ─────────────────────────────
    def on_message(ws, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return
        ws_messages.append(msg)
        if (
            msg.get("type") == "sensor"
            and msg.get("sensor_type") == "temperature"
            and abs(msg.get("value", 0) - TEST_VALUE) < 0.01
        ):
            received.set()

    def on_error(ws, error) -> None:
        ws_errors.append(str(error))
        received.set()  # unblock the wait so the test fails fast

    def on_open(ws) -> None:
        pass  # snapshot will arrive automatically; we just wait

    ws_app = ws_mod.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_open=on_open,
    )
    ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
    ws_thread.start()

    # Wait for the WebSocket handshake and initial snapshot
    time.sleep(0.8)

    if ws_errors:
        print(f"FAIL — WebSocket connection error: {ws_errors[0]}")
        print(f"       Is the backend running at {WS_URL}?")
        sys.exit(1)

    # ── MQTT publish ───────────────────────────────────────────────────────
    client = _make_mqtt_client(mqtt_mod)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=5)
    except Exception as exc:
        print(f"FAIL — cannot connect to MQTT at {MQTT_HOST}:{MQTT_PORT}: {exc}")
        print("       Is Mosquitto running and port 1883 exposed?")
        sys.exit(1)

    payload = json.dumps({
        "value": TEST_VALUE,
        "unit": "C",
        "ts": int(time.time() * 1000),
    })
    client.publish(MQTT_TOPIC, payload, qos=0)
    client.disconnect()
    print(f"[MQTT]  Published temperature={TEST_VALUE}°C → {MQTT_TOPIC}")

    # ── Wait for the event to echo back on the WebSocket ──────────────────
    arrived = received.wait(timeout=TIMEOUT_S)
    ws_app.close()

    snapshot_count = sum(1 for m in ws_messages if m.get("type") == "snapshot")
    sensor_count   = sum(1 for m in ws_messages if m.get("type") == "sensor")

    print(f"[WS]    Messages received: {len(ws_messages)} "
          f"(snapshot={snapshot_count}, sensor={sensor_count})")

    if ws_errors and not arrived:
        print(f"FAIL — WebSocket error: {ws_errors[0]}")
        sys.exit(1)

    if arrived:
        print(f"PASS — sensor update arrived on WebSocket within {TIMEOUT_S}s")
        print("       Full pipeline: ESP32→Mosquitto→mqtt_bridge→queue→WS is healthy")
        sys.exit(0)
    else:
        print(f"FAIL — sensor update did NOT arrive within {TIMEOUT_S}s")
        print("       Check: docker compose logs backend | grep -E '(MQTT|sensor|broadcast)'")
        sys.exit(1)


if __name__ == "__main__":
    main()
