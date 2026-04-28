# MQTT Topic Schema

All topics follow the pattern: `classroom/{room_id}/...`  
Default `room_id` for this project: **`room1`**

MQTT broker: **Mosquitto** running on the Raspberry Pi at port **1883**.  
QoS level: **QoS 0** (at-most-once) is used for all sensor telemetry.  
QoS level: **QoS 1** (at-least-once) is recommended for relay commands so the ESP32 acknowledges receipt.

---

## Topics: ESP32 → Raspberry Pi (Sensor Data)

### `classroom/{room_id}/sensors/temperature`

| Field     | Type   | Description                        |
|-----------|--------|------------------------------------|
| `value`   | float  | Temperature in degrees Celsius     |
| `unit`    | string | Always `"C"`                       |
| `ts`      | int    | Unix timestamp (seconds)           |

**Publish interval:** every 5 seconds  
**Example payload:**
```json
{"value": 24.5, "unit": "C", "ts": 1714300000}
```

---

### `classroom/{room_id}/sensors/humidity`

| Field   | Type   | Description                    |
|---------|--------|--------------------------------|
| `value` | float  | Relative humidity percentage   |
| `unit`  | string | Always `"%"`                   |
| `ts`    | int    | Unix timestamp (seconds)       |

**Publish interval:** every 5 seconds  
**Example payload:**
```json
{"value": 62.1, "unit": "%", "ts": 1714300000}
```

---

### `classroom/{room_id}/sensors/air_quality`

| Field   | Type   | Description                                               |
|---------|--------|-----------------------------------------------------------|
| `value` | int    | MQ-135 ADC reading (proxy for CO₂/VOC concentration)     |
| `unit`  | string | `"ppm"` (approximate, not factory calibrated)            |
| `ts`    | int    | Unix timestamp (seconds)                                  |

**Publish interval:** every 5 seconds  
**Alert threshold:** > 500 ppm triggers an `air_quality_high` alert  
**Example payload:**
```json
{"value": 320, "unit": "ppm", "ts": 1714300000}
```

---

### `classroom/{room_id}/sensors/sound`

| Field   | Type   | Description                            |
|---------|--------|----------------------------------------|
| `value` | int    | `1` = sound detected, `0` = quiet      |
| `unit`  | string | `"bool"`                               |
| `ts`    | int    | Unix timestamp (seconds)               |

**Publish interval:** every 5 seconds  
**Note:** ACP014 is a digital sound sensor — output is binary, not dB level  
**Example payload:**
```json
{"value": 1, "unit": "bool", "ts": 1714300000}
```

---

### `classroom/{room_id}/status`

| Field    | Type    | Description                         |
|----------|---------|-------------------------------------|
| `online` | boolean | `true` when ESP32 is running        |
| `ts`     | int     | Unix timestamp (seconds)            |

**Publish interval:** heartbeat every 30 seconds  
**Backend behavior:** Receiving this message calls `set_device_online(room_id, ttl=60)` in Redis. If no heartbeat arrives within 60 s, `is_device_online()` returns false and the dashboard shows the device as offline.  
**Example payload:**
```json
{"online": true, "ts": 1714300000}
```

---

## Topics: Raspberry Pi → ESP32 (Commands)

### `classroom/{room_id}/relay/ac`

| Field    | Type   | Description                                   |
|----------|--------|-----------------------------------------------|
| `action` | string | `"on"` / `"off"` / `"auto"`                  |

**QoS:** 1 (ESP32 must acknowledge relay commands)  
**auto mode behavior (on ESP32):** relay is controlled by the backend alert engine based on temperature thresholds  
**Example payload:**
```json
{"action": "on"}
```

---

### `classroom/{room_id}/relay/lighting`

Same schema as `relay/ac`. Controls relay channel 2.

**Example payload:**
```json
{"action": "off"}
```

---

### `classroom/{room_id}/alerts`

Push notifications sent to the ESP32 to display on the LCD 16×2.

| Field   | Type   | Description                                     |
|---------|--------|-------------------------------------------------|
| `type`  | string | Alert type string (e.g. `"temp_high"`)          |
| `value` | float  | Measured value that triggered the alert         |

**Example payload:**
```json
{"type": "temp_high", "value": 36.2}
```

---

## QoS Reference

| Direction       | Topic pattern           | QoS | Reason                                    |
|-----------------|-------------------------|-----|-------------------------------------------|
| ESP32 → RPi     | sensors/*               | 0   | High frequency; lost packet is tolerable  |
| ESP32 → RPi     | status                  | 0   | Heartbeat; next one arrives in 30 s       |
| RPi → ESP32     | relay/*                 | 1   | Relay state change must be acknowledged   |
| RPi → ESP32     | alerts                  | 0   | Informational; LCD display only           |

---

## Notes

- **Retained messages:** The backend does not use retained messages (`retain=False`). The Redis cache serves as the authoritative "last known value" store for the dashboard.
- **Reconnect:** The `aiomqtt` bridge in `mqtt_bridge.py` reconnects automatically with exponential backoff on broker disconnect.
- **Broker auth:** Mosquitto runs without authentication in the default classroom setup. For production, configure password auth in `/etc/mosquitto/mosquitto.conf`.
