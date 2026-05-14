# Smart Classroom Management System — Project Master Reference

> Exhaustive content extraction from all source files.
> Sources: docs/architecture.md, docs/technical_report_outline.md, docs/mqtt_schema.md,
> docs/api_contracts.md, docs/wiring_diagram.md, docs/rpi_setup.md, docs/hardware_setup.md,
> docs/moodle_setup.md, CLAUDE.md, PHASE_PROMPTS.md, docker-compose.yml,
> backend/app/main.py, backend/app/services/at_risk_engine.py,
> frontend/src/hooks/useLiveSensors.js
> Generated: 2026-05-14

---

## 1. PROJECT IDENTITY

**Full project title:** Smart Campus Classroom Management System
*(Also referred to as "Smart Classroom Management System — SMU ISS Project 2026")*

**Institution:** SMU — Mediterranean Institute of Technology

**Department / Course:** ISS (Integrated Systems and Software) Project

**Team members (all 5):**
1. Mohamed Hedi Ben Jemaa
2. Ahmed Amine Jallouli
3. Ali Saadaoui
4. Abdelhamid Ouertani
5. Iyed Day

**Academic Year:** 2025–2026

**Report format:** IEEE

---

## 2. PROBLEM STATEMENT & MOTIVATION

### Current pain points at SMU

**Pain point 1 — Attendance inefficiency:**
Manual roll-call is time-consuming. Time cost: up to 15 minutes per lecture wasted on taking attendance manually.

**Pain point 2 — Unmonitored environment:**
No real-time environmental visibility. Classroom HVAC (AC) and lighting are controlled manually without any sensor data. There is no monitoring of temperature, humidity, CO₂/VOC levels, or occupancy.

**Pain point 3 — No early warning for at-risk students:**
No mechanism to identify students who are trending toward poor attendance before they fail a course. The advising/administration department has no early-intervention data.

**Absence of LMS integration:**
No integration between the physical classroom and the Learning Management System (Moodle). Attendance records must be entered manually into Moodle, creating duplication of effort and potential for data entry errors.

### Exact quantified problem
- Up to 15 min per lecture spent on manual attendance — confirmed in Chapter 1 of the report outline and Chapter 9 performance summary ("Attendance time saved: automated vs. manual — 15 min/lecture benchmark").

### Three concrete pain points (as stated in the report)
1. Attendance inefficiency
2. Unmonitored environment
3. No early warning for at-risk students

---

## 3. PROJECT OBJECTIVES

### General objective
*(One-paragraph form as described in the report outline — Chapter 1.3)*
To design and implement an IoT-based smart classroom management system that automates student attendance via camera-based face recognition, monitors classroom environmental conditions in real time (temperature, humidity, CO₂, sound), enables automated HVAC and lighting control through MQTT-driven relays, surfaces a professor-facing React dashboard with live data, synchronizes attendance to the Moodle LMS, and identifies at-risk students and attendance trends using a locally-hosted LLM — all running on a Raspberry Pi 4B without cloud dependency.

### 6 specific objectives (from proposal)
1. Automate student attendance recording using face recognition
2. Monitor classroom environmental conditions (temperature, humidity, air quality, sound) in real time
3. Enable automated and manual control of AC and lighting through relay actuation
4. Provide professors with a live web dashboard showing attendance, sensor data, and alerts
5. Synchronize attendance records to the Moodle LMS automatically
6. Identify at-risk students and forecast attendance trends using AI analytics

### 3 additional capabilities delivered beyond original scope
1. **Snapshot-per-cycle attendance model (Phase 22):** Bidirectional present↔absent evaluation every `ATTENDANCE_CYCLE_DURATION` seconds; replaces one-shot model; resolves students leaving mid-session
2. **Laptop mode (laptop_recognition.py + Webcam API):** Host-side DeepFace script for development without an RPi camera; mutual exclusion with backend recognition loop enforced at subprocess spawn time
3. **LLM-assisted forecasting pipeline (Phase 21):** Deterministic trend classification + Ollama prose interpretation per course; `attendance_forecasts` table; Forecasting page with Recharts trend chart

---

## 4. SCOPE & CONSTRAINTS

### Single-room / single-semester scope
- Single classroom deployment only. `ROOM_ID` (default: `room1`) is a single configurable value in `config.h` and `.env`
- Academic semester timeline constraint — 22-phase delivery within one semester (2025–2026)
- University intranet only — no public internet; all services run locally on the Raspberry Pi

### Hardware budget constraints and Tunisian market context
- Hardware availability and cost driven by parts available in Tunisian/local market
- Raspberry Pi 4B 4GB selected as the central hub; ESP32 Dev Board (ESP-WROOM-32) as the MCU
- Parts list constrained to off-the-shelf Arduino/IoT components (DHT21, MQ-135, ACP014, 4-channel relay, LCD 16×2 I2C, logic level converter)
- Power: USB-C 5V 3A for RPi; USB power bank for ESP32

### RPi 4B compute limits
- Face recognition: 2 fps sustained on RPi 4B (RECOGNITION_FPS=2)
- phi3-mini LLM inference on CPU: ~10–30 seconds per student
- DeepFace/TensorFlow excluded from Docker image due to ~600 MB pull and OOM on development laptops; installed natively on RPi only
- At-risk pipeline runtime before optimization: ~14–16 min for all students; after Phase 20 optimization: ~2–3 min for 8 at-risk students

### Deferred to future work
- Multi-room support (requires `room_id` abstraction throughout)
- React Native mobile app for professors
- IR illuminator for low-light face recognition
- Email/SMS alert notifications
- QR-code student self-enrollment
- CO₂ sensor calibration (SCD30 / MH-Z19 replacement for MQ-135)
- Offline SQLite fallback
- Daily at-risk email digest
- Quantized GGUF model via llama.cpp for faster RPi CPU inference
- HTTPS/WSS (nginx SSL termination path described but not implemented)
- Refresh token mechanism (JWT only, no refresh in current version)

---

## 5. SYSTEM ARCHITECTURE

### Architecture pattern name
**Hybrid: modular monolith + event-driven messaging**

The backend is a single FastAPI process (not microservices), but internally it is event-driven via three decoupled channels.

### 4 architectural paradigms and their descriptions

| Paradigm | Description |
|---|---|
| **Publish/Subscribe (MQTT, QoS 0)** | Sensor ingestion and relay actuation between ESP32 and backend via Mosquitto broker |
| **Push-based real-time (WebSocket)** | Live sensor, attendance, and alert delivery to browser clients via `WS /ws/classroom/{room_id}` |
| **Queue-based fan-out (asyncio.Queue)** | Decouples MQTT handler from WebSocket broadcaster; three separate queues: `sensor_event_queue`, `attendance_event_queue`, `alert_event_queue` |
| **On-demand async pipelines (APScheduler + asyncio.create_task)** | AI pipelines fire on page access; periodic alert/mock jobs run on shared APScheduler event loop |

### Full subsystem breakdown table (9 rows)

| Subsystem | Technology | Responsibility |
|---|---|---|
| IoT Layer | ESP32 (Arduino/C++, ESP-WROOM-32) | Sense environment, publish MQTT, execute relay commands |
| Edge Runtime | Raspberry Pi 4B 4GB (Docker host) | Run all backend services; no cloud dependency |
| MQTT Broker | Mosquitto 2 (eclipse-mosquitto:2) | Message bus between ESP32 and backend |
| Backend | FastAPI (Python 3.11) + Uvicorn | Orchestration, business logic, REST + WebSocket APIs |
| Real-time Layer | WebSocket + asyncio.Queue (3 queues) | Fan-out of sensor/attendance/alert events to browser |
| AI/Insights Layer | Ollama + phi3:mini (local CPU) | Attendance analytics, LLM-powered at-risk summaries, attendance forecasting |
| Frontend | React 18 + Vite + TailwindCSS v3 | Professor dashboard; works offline in demo mode |
| Data Layer | PostgreSQL 15 + Redis 7 | Persistent records + low-latency live state cache |
| External | Moodle 4.x + Ollama/phi3:mini | LMS attendance sync + local LLM inference |

### Key architectural design decisions (full table)

| Decision | Reason |
|---|---|
| FastAPI over Flask | Native async for WebSocket + MQTT |
| All services on RPi (no cloud) | Avoid latency, cost, internet dependency |
| asyncio-mqtt → aiomqtt | paho-mqtt v2 broke asyncio-mqtt |
| DeepFace → stub in Docker | TF pulls ~600 MB, causes OOM on dev laptops |
| Redis for live sensor state | Instant dashboard load, no PostgreSQL hit |
| `display_status` computed, not stored | Liveness changes over time with no DB write |
| `tokens.css` separate from `index.css` | Tailwind v3 can't resolve CSS vars at build time |
| Glassmorphism removed | GPU-expensive, rendering artifacts in Chromium |
| Inline SVG icons | No icon library dependency; only 10–12 icons needed |
| `per_course_data` as JSONB | Always read/written as unit with parent; avoids join; atomic upsert |
| Redis lock TTL not deleted on completion | Prevents re-run on every page refresh; natural ~10-min cooldown |
| 1 LLM call/student (not N+1) | Reduced at-risk runtime from ~14 min to ~2–3 min for 8 students |
| JWT in localStorage | Acceptable on university intranet; simpler than httpOnly cookies |
| On-demand pipeline (no cron) | Cron meant no explanations until 02:00; on-demand generates immediately on page open |
| Deterministic trend classification (no LLM) | LLM output format unreliable for structured values; delta math is fast and always correct |
| VARCHAR(30) not PG ENUM for classification | `ALTER TYPE ADD VALUE` is non-transactional in PostgreSQL; VARCHAR avoids DDL migrations on schema evolution |
| Marker rows for courses with < 3 sessions | Without a row the frontend poll condition never resolves; marker rows terminate the poll immediately |
| 1 LLM call per course (interpretation only) | Classification and confidence computed deterministically; LLM writes only prose + projected rate |
| Snapshot-per-cycle attendance (not one-shot) | One-shot model couldn't detect students leaving mid-session; bidirectional UPDATE with `adjusted_by` guard gives accurate continuous evaluation |
| No Redis cooldown in webcam.py attendance endpoint | `last_posted_status` in laptop_recognition.py is the dedup layer; backend cooldown silently dropped present→absent transitions |
| Stop backend loop when laptop_recognition.py starts | Two competing writers to attendance_records caused random stub overrides; mutual exclusion enforced at subprocess spawn time |
| Pre-seed `last_seen` at laptop_recognition.py startup | Students marked present by prior systems were never in `last_seen`; seeding with `now − ABSENT_TIMEOUT` gives immediate absent-marking for undetected students |

---

## 6. IoT LAYER — ESP32 FIRMWARE

**File:** `firmware/classroom_node/classroom_node.ino` + `firmware/classroom_node/config.h`

### Sensors used

| Sensor | Model | What it measures |
|---|---|---|
| DHT21 | AM2301 | Temperature (°C) and humidity (%) — single-wire protocol, GPIO 4, 10 kΩ pull-up |
| MQ-135 | MQ-135 | Air quality ppm (CO₂/VOC proxy) — ADC analog output, GPIO 34 (ADC1 ch6, input-only) |
| ACP014 | ACP014 | Sound presence detection — digital binary output (1=detected, 0=quiet), GPIO 35 (input-only) |

### Sensor reading interval
Every 5 seconds for all sensors (temperature, humidity, air quality, sound).

### MQTT topic schema (exact topic strings)

**ESP32 → Raspberry Pi (Sensor Data):**
- `classroom/{room_id}/sensors/temperature` → `{"value": 24.5, "unit": "C", "ts": 1714300000}` — every 5s
- `classroom/{room_id}/sensors/humidity` → `{"value": 62.1, "unit": "%", "ts": 1714300000}` — every 5s
- `classroom/{room_id}/sensors/air_quality` → `{"value": 320, "unit": "ppm", "ts": 1714300000}` — every 5s
- `classroom/{room_id}/sensors/sound` → `{"value": 1, "unit": "bool", "ts": 1714300000}` — every 5s (1=detected, 0=quiet)
- `classroom/{room_id}/status` → `{"online": true, "ts": 1714300000}` — heartbeat every 30s

**Default room_id:** `room1`

### Relay actuation topics (Raspberry Pi → ESP32)
- `classroom/{room_id}/relay/ac` → `{"action": "on"}` / `{"action": "off"}` / `{"action": "auto"}`
- `classroom/{room_id}/relay/lighting` → same schema
- `classroom/{room_id}/alerts` → `{"type": "temp_high", "value": 36.2}` (displayed on LCD)

### QoS Reference

| Direction | Topic pattern | QoS | Reason |
|---|---|---|---|
| ESP32 → RPi | sensors/* | 0 | High frequency; lost packet is tolerable |
| ESP32 → RPi | status | 0 | Heartbeat; next one arrives in 30s |
| RPi → ESP32 | relay/* | 1 | Relay state change must be acknowledged |
| RPi → ESP32 | alerts | 0 | Informational; LCD display only |

### LCD 16×2 local display behavior
- Line 1: `T:24.5C H:62%` (temperature + humidity formatted)
- Line 2: `AQ:320 Snd:1` (air quality + sound status)
- On startup: Line 1 = "Smart Classroom", Line 2 = "Connecting..."
- On successful MQTT connect: Line 2 = "Online"
- Alert display: when backend publishes to `classroom/{room_id}/alerts`, the ESP32 displays it on the LCD

### On-device auto-control (acAutoMode)
If `acAutoMode=true`, the ESP32 itself applies temperature threshold logic to the relay independently of the backend. This is deliberate redundancy: the backend alert engine also sends relay commands, but the device acts locally if the MQTT connection drops.

### Full GPIO wiring table

| GPIO | Direction | Component | Signal Description |
|---|---|---|---|
| 4 | Input | DHT21 | Temperature/humidity data (single-wire; 10 kΩ pull-up to 3.3V) |
| 34 | Input | MQ-135 | Air quality ADC (0–4095); input-only pin, ADC1 ch6 |
| 35 | Input | ACP014 | Sound detection (digital); input-only pin |
| 21 | I2C SDA | LCD 16×2 | I2C data (ESP32 default SDA) |
| 22 | I2C SCL | LCD 16×2 | I2C clock (ESP32 default SCL) |
| 26 | Output | Relay CH1 (via LLC) | AC relay control |
| 27 | Output | Relay CH2 (via LLC) | Lighting relay control |
| 14 | Output | Relay CH3 (via LLC) | Spare |
| 12 | Output | Relay CH4 (via LLC) | Spare |

**Logic Level Converter (LLC):** Required between ESP32 (3.3V) and 4-channel relay module (5V TTL). LLC low side at 3.3V; high side at 5V.

**Power rails:**
- 5V (USB): ESP32 VBUS, MQ-135 heater, Relay VCC/JD-VCC
- 3.3V (ESP32 onboard LDO): DHT21, ACP014, LLC LV side, LCD
- LCD I2C address: `0x27` (default PCF8574 backpack)

**Libraries:** PubSubClient, DHT sensor library (Adafruit), LiquidCrystal_I2C (Frank de Brabander), ArduinoJson, WiFi.h

**Communication:** WiFi 802.11 → Mosquitto broker via TCP/1883, MQTT QoS 0 for sensors

---

## 7. EDGE LAYER — RASPBERRY PI 4B

### All roles of the RPi
The Raspberry Pi 4B runs the entire stack: Mosquitto broker, FastAPI backend, PostgreSQL, Redis, Ollama, and nginx/React. In Docker deployment these are containerized services on the same host.

- MQTT broker host
- Face recognition host (camera attached via MIPI CSI-2)
- Docker host for all services
- nginx static file server + reverse proxy
- Ollama LLM inference host (phi3:mini on CPU)

**OS:** Raspberry Pi OS Lite (64-bit, Bookworm). Hostname: `smartclassroom.local`

### Face recognition
- **fps:** 2 fps sustained (RECOGNITION_FPS=2), driven by `asyncio.Task`
- **Library:** DeepFace (deepface==0.0.93) + tf-keras==2.16.0 + opencv-python-headless==4.9.0.80
- **Model:** FaceNet (128-d embedding)
- **Input:** OpenCV `VideoCapture(0)` → BGR frame
- **Matching:** cosine distance comparison against stored 128-d float32 embeddings
- **Threshold:** cosine distance < 0.40 (tightened from 0.60 in Phase 22)
- **Cooldown (legacy one-shot model):** 30-second per-student cooldown prevents duplicate records
- **Current model (Phase 22):** Snapshot-per-cycle — SCAN for `ATTENDANCE_CYCLE_DURATION` (60s), collect `seen_this_cycle` set, EVALUATE: absent→present or present→absent for all enrolled students; `adjusted_by IS NOT NULL` records never touched
- **Enrollment:** up to 5 images → FaceNet 128-d encoding per image → averaged → stored as float32 BYTEA in PostgreSQL

### Stub mode (`FACE_RECOGNITION_ENABLED=false`)
- Enrollment stores zeroed 128-d float32 placeholder encoding
- Stub recognition loop (`_stub_recognition_loop`) picks ~70% ± 2 of enrolled students randomly each cycle, calls `_run_cycle_evaluation` — exercises full bidirectional present↔absent logic
- `reload_encodings()` is a no-op in stub mode

### Mock sensor mode (`MOCK_MODE=true`)
- APScheduler jobs publish sine-wave sensor values over MQTT every 5s, heartbeat every 30s
- Temperature: 22–32°C (sine wave + noise)
- Humidity: 45–70%
- Air quality: 200–550 ppm (occasional spike above 500 threshold)
- Sound: 70% detected / 30% quiet
- The broker receives these exactly as if an ESP32 sent them — the MQTT bridge is unaware of the source

---

## 8. COMMUNICATION LAYER — MQTT

### Broker
**Mosquitto version 2** (`eclipse-mosquitto:2`). Runs on Raspberry Pi at port **1883**.

### QoS level used and rationale
- **QoS 0** (at-most-once): used for all sensor telemetry — high frequency; a lost packet is tolerable
- **QoS 1** (at-least-once): recommended for relay commands so the ESP32 acknowledges receipt
- **QoS 0**: heartbeat status messages — next heartbeat arrives in 30s
- No retained messages (`retain=False`) — Redis cache serves as the authoritative "last known value" store

### Full MQTT topic tree (all topics)

```
classroom/{room_id}/
  ├── sensors/
  │   ├── temperature   ← ESP32 publishes, backend subscribes
  │   ├── humidity      ← ESP32 publishes, backend subscribes
  │   ├── air_quality   ← ESP32 publishes, backend subscribes
  │   └── sound         ← ESP32 publishes, backend subscribes
  ├── status            ← ESP32 publishes (heartbeat), backend subscribes
  ├── relay/
  │   ├── ac            ← backend publishes, ESP32 subscribes
  │   └── lighting      ← backend publishes, ESP32 subscribes
  └── alerts            ← backend publishes → ESP32 LCD display
```

### Publish/subscribe role split
- **Backend subscribes (wildcard):** `classroom/+/sensors/#` (all rooms, all sensor subtopics), `classroom/+/status`
- **ESP32 subscribes (exact topics):** `classroom/room1/relay/ac`, `classroom/room1/relay/lighting`
- **Relay publish pattern:** a short-lived `aiomqtt.Client` context manager (`publish_mqtt()`) is used for each outbound relay command — prevents concurrent use of the persistent subscriber connection
- **Reconnect:** `aiomqtt` bridge in `mqtt_bridge.py` reconnects automatically with exponential backoff on broker disconnect
- **Broker auth:** Mosquitto runs without authentication in default classroom setup (`allow_anonymous true`, `listener 1883`)

---

## 9. BACKEND — FASTAPI APPLICATION

**App title:** "Smart Classroom API" | **Version:** 0.1.0

### All 7 module groups and their responsibilities

| Group | Files | Responsibility |
|---|---|---|
| 1 — Ingestion & Real-time | `mqtt_bridge.py`, `event_queues.py` | Persistent `aiomqtt.Client` subscriber loop with exponential backoff; Redis SET on sensor; PostgreSQL write fire-and-forget; feed three event queues |
| 2 — Session & Attendance | `api/sessions.py`, `api/attendance.py`, `services/recognition_loop.py` | Session lifecycle (start/end); attendance recording; Moodle sync on session end; retry queue in Redis |
| 3 — Control | `api/control.py` | `POST /api/control/ac\|lighting` → simultaneously writes Redis (instant dashboard) and publishes MQTT (device actuation); relay state authoritative in Redis |
| 4 — Alert Engine | `services/alert_engine.py` | `AsyncIOScheduler` runs every 30s; reads Redis sensor cache → evaluates thresholds → upserts Alert rows → pushes to `alert_event_queue`; Moodle retry every 10 min |
| 5 — Insights & Analytics | `services/insights_engine.py`, `api/insights.py` | Pure SQL analytics on-demand; role-filtered; attendance trend, heatmap, decay, comfort score, AC effectiveness, temp-vs-attendance scatter, AQ vs. sound correlation |
| 6 — AI Pipelines | `services/at_risk_engine.py`, `services/forecast_engine.py` | At-risk explanation pipeline; attendance forecasting pipeline |
| 7 — Auth | `api/auth.py`, `api/deps.py` | JWT (HS256), bcrypt passwords, `professors` table; `REQUIRE_AUTH=false` in dev |

### asyncio.Queue instances (names and what feeds them)

| Queue name | Fed by | Consumed by |
|---|---|---|
| `sensor_event_queue` | MQTT bridge `_handle_sensor` (`put_nowait`) | `_drain_queue` background task → `connection_manager.broadcast` |
| `attendance_event_queue` | `recognition_loop` on first detection per student per cycle | `_drain_queue` background task → `connection_manager.broadcast` |
| `alert_event_queue` | Alert engine `check_thresholds` on threshold breach | `_drain_queue` background task → `connection_manager.broadcast` |

Three `asyncio.create_task(_drain_queue(...))` background tasks start in the lifespan context under names `sensor_broadcaster`, `attendance_broadcaster`, `alert_broadcaster`.

### Key libraries
- **aiomqtt 2.x** — async MQTT client (replaces asyncio-mqtt; paho-mqtt v2 broke asyncio-mqtt)
- **SQLAlchemy 2.0 (async)** — ORM with `asyncpg` driver; `AsyncSessionLocal`, `AsyncSession`
- **Alembic** — database migrations; auto-run via `_run_migrations()` subprocess call at lifespan startup
- **APScheduler** (`AsyncIOScheduler`) — alert engine jobs; mock sensor publisher
- **bcrypt** — professor password hashing
- **HS256** — JWT algorithm; `ACCESS_TOKEN_EXPIRE_MINUTES=480` (8 hours)
- **httpx.AsyncClient** — shared async client for Ollama calls; also used by Moodle client
- **DeepFace** (deepface==0.0.93) + **tf-keras==2.16.0** + **opencv-python-headless==4.9.0.80** — face recognition (RPi native only, not in Docker image)

### Session lifecycle (start/end flow)
1. `POST /api/sessions/start` → `{course_id, room_id}` → create Session(status=active, started_at=now()) → start recognition loop background task → return session
2. `POST /api/sessions/{id}/end` → set `ended_at=now(), status=ended` → stop recognition loop → final cycle evaluation → bulk-mark absent for unrecorded enrolled students → trigger Moodle sync (background) → return session
3. Only one session may be active per room (HTTP 409 if already active)

### Alert engine: scheduler cycle, deduplication logic
- **Cycle:** `check_thresholds()` runs every 30s via `AsyncIOScheduler`
- **Deduplication:** skips alert creation if an unacknowledged alert of the same type already exists for the room
- **Alert types:** `temp_high`, `temp_low`, `air_quality_high`, `attendance_anomaly`, `device_offline`
- **Auto-control:** if AC in auto mode and temp > 28°C → publish MQTT `ac=on` + Redis update; temp < 22°C → `ac=off`
- **Device offline detection:** Redis TTL-based — if `classroom:{room_id}:online` key expires (60s), `is_device_online()` returns False → `device_offline` alert
- **Second scheduled job:** `retry_moodle_sync` runs every 10 min; pops up to 10 session IDs from Redis retry list and re-calls Moodle

### Insights engine: SQL analytics description
Pure SQL analytics served on-demand (no LLM). Computes: attendance trend (weekly), heatmap by day/hour-slot, decay analysis, comfort score (from Redis), AC effectiveness, temperature-vs-attendance scatter, air quality vs. sound correlation. All role-filtered: professors see only their courses; admins see all.

### JWT auth: token expiry, role-based filtering, localStorage rationale
- **Algorithm:** HS256
- **Expiry:** `ACCESS_TOKEN_EXPIRE_MINUTES=480` (8 hours default)
- **Storage:** Browser `localStorage` — rationale: acceptable on closed university intranet; simpler than httpOnly cookies; tradeoff acknowledged
- **Role-based filtering:** `professor` role → API responses filtered to professor's own courses/students; `admin` role → all data
- **Admin-only endpoints:** `POST /api/at-risk/recompute`, `POST /api/forecasting/recompute`
- **`REQUIRE_AUTH=false`** in development — flagged as hardening checklist item for production

### APScheduler jobs

| Job | Interval | Purpose |
|---|---|---|
| `check_thresholds` | 30s | Read Redis sensor cache, evaluate thresholds, publish MQTT relay commands |
| `retry_moodle_sync` | 10 min | Pop up to 10 session IDs from Redis retry list, re-call Moodle |
| `mock_sensor_publish` | 5s | (`MOCK_MODE=true`) Publish synthetic sensor MQTT messages |
| `mock_heartbeat_publish` | 30s | (`MOCK_MODE=true`) Publish heartbeat status message |

---

## 10. REAL-TIME LAYER — WEBSOCKET

### Endpoint path
`WS /ws/classroom/{room_id}`

### Snapshot-on-connect behavior
On connect, server sends a `snapshot` message containing current Redis state: sensors (all types), relay states (ac, lighting), device_online flag.

### Full WebSocket message types table (all types)

| type | Direction | Trigger | Payload |
|---|---|---|---|
| `snapshot` | Server → Client | On WebSocket connect | sensors + relay + device_online |
| `sensor` | Server → Client | MQTT ingestion of sensor reading | room_id, sensor_type, value, unit |
| `attendance` | Server → Client | Recognition cycle match | session_id, student_id, student_name, confidence, status |
| `alert` | Server → Client | Threshold breach in alert engine | alert_type, room_id, message, value |
| `ping` | Server → Client | 30s server keepalive | — (no payload) |
| `pong` | Client → Server | Echo reply to server ping | — (client sends literal `"ping"` text; server echoes as `{type:"pong"}`) |

### Keepalive mechanism
30-second server-side timeout → server sends `ping`; client echo → `pong`. Implemented in `ConnectionManager`.

### Frontend reconnect strategy
- **Initial backoff:** 3,000ms (`INITIAL_BACKOFF = 3_000`)
- **Maximum backoff cap:** 30,000ms (`MAX_BACKOFF = 30_000`)
- **Strategy:** exponential backoff — `backoff = Math.min(backoff * 2, MAX_BACKOFF)`
- **Reset:** backoff resets to `INITIAL_BACKOFF` on successful reconnect

### Demo mode watchdog
- **Timeout:** 8,000ms (`DEMO_TIMEOUT_MS = 8_000`)
- **Polling:** watchdog checker runs every 2s
- **Trigger:** if `lastMessageTime === null` OR `Date.now() - lastMessageTime > 8000` → activate demo mode
- **Effect:** activates client-side mock sensor generator + renders `DemoModeBanner` component
- **Exit:** demo mode deactivates immediately when real data arrives via WebSocket

### ConnectionManager
Maintains `dict[room_id → set[WebSocket]]` for room-scoped broadcasting. `broadcast_all(event)` used for events without a specific room_id.

---

## 11. DATA LAYER

### PostgreSQL

**Number of tables:** 10

| Table | Key columns |
|---|---|
| `professors` | id (UUID PK), name, email (UNIQUE), hashed_password (bcrypt), role (ENUM: professor\|admin), created_at |
| `students` | id (UUID PK), name, student_id (UNIQUE institutional), created_at |
| `courses` | id (UUID PK), code (UNIQUE), professor_id (FK→professors, nullable), name, professor_name |
| `course_students` | course_id FK, student_id FK — composite PK (M:M join table) |
| `sessions` | id (UUID PK), course_id (FK), room_id, started_at, ended_at (nullable), status (ENUM: active\|ended\|upcoming) |
| `attendance_records` | id (UUID PK), session_id (FK), student_id (FK), status (ENUM: present\|absent\|late\|excused), detected_at, adjusted_by (nullable), adjusted_at (nullable), moodle_synced (BOOL default false) |
| `face_encodings` | id (UUID PK), student_id (FK), encoding (BYTEA — serialized 128-d float32 numpy array), created_at |
| `sensor_readings` | id (UUID PK), room_id, sensor_type (ENUM: temperature\|humidity\|air_quality\|sound), value (FLOAT), unit, recorded_at |
| `alerts` | id (UUID PK), room_id, type (ENUM: temp_high\|temp_low\|air_quality_high\|attendance_anomaly\|device_offline), value (FLOAT nullable), message (TEXT), acknowledged (BOOL default false), created_at |
| `at_risk_explanations` | id (UUID PK), student_id (FK→students ON DELETE CASCADE, UNIQUE index), overall_attendance_rate (FLOAT), summary_explanation (TEXT), per_course_data (JSONB), generated_at (TIMESTAMP), ollama_reachable (BOOL) |
| `attendance_forecasts` | id (UUID PK), course_id (FK→courses ON DELETE CASCADE, UNIQUE index), trend_data (JSONB), expected_next_rate (FLOAT nullable), trend_classification (VARCHAR(30) nullable), confidence_level (VARCHAR(10) nullable), interpretation (TEXT nullable), suggested_action (VARCHAR(30) nullable), ollama_reachable (BOOL), generated_at (TIMESTAMP) |

**Key schema decisions:**
- `display_status` for sessions is **computed at query time** (not stored) — liveness changes over time without DB writes. Three states: `live` = active + started_at ≤ now; `upcoming` = status==upcoming; `done` = ended
- `per_course_data` is **JSONB** — always read/written as a unit with the parent row; avoids join; atomic upsert
- `trend_classification` uses **VARCHAR(30) not PG ENUM** — `ALTER TYPE ADD VALUE` is non-transactional in PostgreSQL; VARCHAR avoids DDL migrations on schema evolution
- `face_encodings.encoding` is **BYTEA** — serialized 128-d float32 numpy array
- UUID primary keys with `server_default=text("gen_random_uuid()")`
- `at_risk_explanations`: UNIQUE on `student_id`; upserted on every pipeline run
- `attendance_forecasts`: UNIQUE on `course_id`; upserted on every pipeline run

### Redis

**Full Redis key pattern table:**

| Key pattern | Value | TTL | Written by | Read by |
|---|---|---|---|---|
| `classroom:{room_id}:sensors:{type}` | JSON `{"value", "unit"}` | 300s | MQTT handler (SET, TTL 300s) | WebSocket snapshot, control status, alert engine, insights comfort score |
| `classroom:{room_id}:online` | `"1"` | 60s (renewed by heartbeat) | MQTT status handler | Alert engine, control status |
| `classroom:{room_id}:relay:{device}` | `"on"/"off"/"auto"` | None (persistent) | Control API + alert engine auto-control | WebSocket snapshot, control status |
| `at_risk:pipeline:lock` | `"1"` | 600s (SET NX EX) | Pipeline entry | Pipeline entry check |
| `forecast:pipeline:lock` | `"1"` | 1800s (SET NX EX) | Pipeline entry | Pipeline entry check |
| `moodle:retry_queue` | List of session_ids | None | Moodle client on failure | Alert engine retry job |

**Ephemeral vs. persistent boundary explanation:**
- **Ephemeral (Redis):** anything that changes faster than it can be queried (sensor every 5s), anything with a natural TTL (heartbeat presence), anything that only matters right now (relay state for the current session)
- **Persistent (PostgreSQL):** anything that needs to survive restarts, is queried across time ranges, or feeds analytics/AI pipelines
- The device-online key is a TTL-based presence indicator: if the ESP32 stops sending heartbeats, the 60s key expires and `is_device_online()` returns False — triggering a `device_offline` alert without a polling query

---

## 12. FRONTEND — REACT DASHBOARD

### Stack
- **React 18** + **Vite** — SPA with client-side routing
- **React Router v6** — nested routes under authenticated `<Layout>`
- **TailwindCSS v3** — utility classes coexisting with CSS custom properties
- **Recharts** — `AreaChart` + `linearGradient` sparklines; 70% dashed `ReferenceLine`; optional projected "Next" data point
- **axios** — HTTP client with JWT header injection via `api/client.js`
- Native **WebSocket** — via `useLiveSensors` custom hook (no WebSocket library)

### All 9 routes (table)

| Route | Page Component | Description |
|---|---|---|
| `/login` | Login | Public route (unauthenticated access allowed) |
| `/dashboard` | Dashboard | Live sparklines, session control (start/end), alert feed, relay toggles |
| `/attendance` | Attendance | Session/student table with manual adjustment, CSV export |
| `/control` | Control | Relay toggles (On/Off/Auto) + live sensor cards |
| `/enrollment` | Enrollment | Student registration + face image upload + encoding |
| `/history` | History | Past sessions + sensor summaries + Moodle sync status |
| `/insights` | Insights | SQL analytics charts: trend, heatmap, decay, scatter |
| `/at-risk` | AtRisk | LLM-explained at-risk student cards + per-course breakdown |
| `/forecasting` | Forecasting | Recharts AreaChart trend chart + LLM interpretation |

### Context providers
- **`AuthContext`:** JWT token + professor profile; token stored in `localStorage`; exposes `isAuthenticated`, `professor`, `login`, `logout`
- **`SensorContext`:** wraps `useLiveSensors` hook; distributes `sensors`, `attendance`, `alerts`, `relayStatus`, `isConnected`, `isDemoMode`, `deviceOnline` to entire app

### tokens.css / index.css separation rationale
- `tokens.css` is the single source of truth for all design tokens (colors, spacing, radius, typography) as CSS custom properties
- `index.css` contains all component classes that reference token vars only
- **Rationale:** TailwindCSS v3 utility classes cannot resolve CSS custom properties at build time — hence this split. Both coexist in the same project.

### useLiveSensors hook behavior
- Connects to `WS /ws/classroom/room1` on mount
- Exponential backoff reconnection: starts at 3,000ms, caps at 30,000ms
- Message dispatcher routes by `msg.type`: `snapshot` → full state reset; `sensor` → update single sensor key; `attendance` → upsert by student_id+session_id; `alert` → prepend, keep last 50
- Demo mode watchdog: polls every 2s; if no real data within 8,000ms → `startDemo()` activates mock generator + `setIsDemoMode(true)`
- Returns: `{ sensors, attendance, alerts, relayStatus, isConnected, isDemoMode, deviceOnline }`

### Dashboard pages and what each displays

| Page | What it displays |
|---|---|
| **Dashboard** | 4 sensor cards (temperature, humidity, air quality, sound) + live attendance table + relay toggle buttons (AC/Lighting) + last-5-alerts feed + Start/End Session modal |
| **Attendance** | Session selector dropdown; full attendance table (student name, ID, status badge, detected_at); inline status dropdown for manual adjustment; "Adjusted by professor" label; CSV export; "Mark all absent" button |
| **Control** | Large relay toggle cards (On/Off/Auto) for AC and Lighting; auto-mode threshold rules shown ("AC turns on above 28°C"); current sensor readings inline; action log of last 10 control actions |
| **At-Risk** | Left panel (~320px): scrollable student cards sorted by overall_attendance_rate ascending (worst first); colored % badge (red <50%, amber 50–69%); Right panel (detail): LLM summary card + per-course expandable cards + per-course stats (sessions_total, sessions_missed, avg_temp_on_missed, avg_aq_on_missed, peer delta) |
| **Forecasting** | Left panel (~320px): course cards sorted by severity (accelerating_decline first); Right panel: Recharts AreaChart (linearGradient fill, 70% dashed ReferenceLine, optional projected "Next" point) + 3-col stats grid + LLM interpretation glass-card + action banner |
| **Enrollment** | Left: student list with enrolled/not-enrolled status; Right: enrollment form (name, student_id) + camera capture section (up to 5 frames) + "Enroll Face" multipart upload |
| **History** | Table of all past sessions: Course, Date, Duration, Present %, Moodle Sync status; expandable rows; Moodle Retry button |

### Why glassmorphism was removed
GPU-expensive; causes rendering artifacts in Chromium. Removed in Phase 18 visual redesign.

### Why inline SVG icons were used
No icon library dependency; only 10–12 icons needed in the entire interface.

### Typography
- **DM Sans** (headings, weight 600/700)
- **Inter** (body text, weight 400/500)

---

## 13. FACE RECOGNITION PIPELINE

### Enrollment flow
- Up to 5 images accepted per enrollment session
- Each image: decoded to numpy array → DeepFace/FaceNet 128-d embedding computed
- All embeddings averaged into one 128-d float32 vector
- Serialized with `numpy.tobytes()` → stored as `BYTEA` in `face_encodings` table
- `reload_encodings()` called after enrollment to refresh in-memory dict
- API: `POST /api/students/{id}/enroll-face` (multipart/form-data, JPEG/PNG)
- Stub mode: zeroed 128-d float32 placeholder stored; no real biometric processing

### Recognition loop (Phase 22 snapshot-per-cycle model)
- Runs at `RECOGNITION_FPS=2` fps when a session is active
- OpenCV `VideoCapture(0)` → BGR frame → DeepFace cosine distance matching
- **Threshold:** cosine distance < 0.40 (tightened from 0.60 in Phase 22)
- **SCAN phase:** lasts `ATTENDANCE_CYCLE_DURATION=60` seconds; collects `seen_this_cycle` set of recognized student IDs; WS event fired on first detection per student per cycle
- **EVALUATE phase:** one transaction; for every enrolled student — if in `seen_this_cycle` → absent→present; if not in set → present→absent
- **Guard:** records where `adjusted_by IS NOT NULL` are never touched by the recognition loop
- **On session end:** final evaluation runs with partial `seen_this_cycle` before loop stops
- UNKNOWN faces: increment occupancy counter for anomaly detection

### Stub mode for non-RPi environments
- `FACE_RECOGNITION_ENABLED=false` (default in Docker)
- `_stub_recognition_loop` picks ~70% ± 2 of enrolled students randomly each cycle
- Calls `_run_cycle_evaluation` — exercises full bidirectional present↔absent logic
- Keeps dashboard live without any camera hardware

---

## 14. AI & ANALYTICS LAYER

### At-Risk Student Detection

**Pipeline trigger mechanism:**
On-demand — `GET /api/at-risk` → `asyncio.create_task(run_at_risk_pipeline())`. Redis lock `at_risk:pipeline:lock` (TTL 600s, SET NX EX) prevents concurrent runs. TTL is **not deleted on completion** — this enforces a natural ~10-minute cooldown, preventing re-run on every page refresh.

**Data inputs used:**
1. Attendance records + session/course context (batch JOIN query)
2. Average temperature and air quality during all missed sessions, grouped by course_id (one batch JOIN query with `SensorReading` correlated to missed session windows)
3. Peer attendance rate per enrolled course (one GROUP BY query)

**Pipeline steps (6 steps):**
1. `InsightsEngine.get_at_risk_students()` → find students below `AT_RISK_THRESHOLD=0.70`
2. Freshness gate: skip students with `generated_at` < 600s old AND `ollama_reachable=true`
3. Cleanup: `DELETE FROM at_risk_explanations WHERE student_id NOT IN (at_risk_ids)` — removes stale rows for students who recovered
4. Single shared `httpx.AsyncClient` for all Ollama calls; pre-flight `GET /api/tags` validates model presence
5. Per at-risk student: 3 batch SQL queries → build profile → single Ollama call (< 500 token prompt) → upsert `at_risk_explanations`
6. Pipeline done; lock TTL expires naturally after 600s

**Hybrid deterministic + LLM classification rationale:**
The at-risk threshold (70%) is deterministic (SQL query). The LLM (phi3-mini) generates only 3–4 sentence cross-course prose explanations. Structured labels and thresholds are never delegated to the LLM — hallucination risk on labels would break the frontend's logic.

**LLM configuration:**
- **Model:** phi3:mini (phi3-mini local via Ollama)
- **Inference location:** Local Raspberry Pi 4B CPU (no external API)
- **Call count optimization:**
  - Before (Phase 19): N+1 pattern — one Ollama call per course per student (~7 calls for a typical student)
  - After (Phase 20): 1 Ollama call per student (multi-course prompt block)
- **Prompt:** compact multi-course block, < 500 tokens
- **Response:** 3–4 sentence cross-course prose summary, < 100 words
- **Prompt constraints:** no health/personal life/family/psychology references; no blame or evaluative judgments; plain prose only

**Pipeline runtime:**
- Before optimization (Phase 19, ~8 students): ~14–16 minutes
- After optimization (Phase 20, ~8 students): ~2–3 minutes

**Performance optimization summary (Phase 20):**

| Metric | Before | After |
|---|---|---|
| Students iterated | All 35 | At-risk only ~8 |
| Sensor queries/student | N missed sessions × 2 | 1 batch JOIN |
| Peer-rate queries/student | 1 per course | 1 GROUP BY |
| Ollama calls/student | courses + 1 (~7) | 1 |
| HTTP connections | New TCP per call | Shared AsyncClient |
| Runtime (8 students) | ~14–16 min | ~2–3 min |

**Redis lock TTL behavior:** TTL 600s, SET NX EX. Lock is **not deleted** when pipeline completes — this is the natural ~10-minute cooldown that prevents rapid re-invocation.

---

### Attendance Forecasting

**Pipeline description:**
Triggered on-demand by `GET /api/forecasting` → `asyncio.create_task(_maybe_run_pipeline())`. Redis lock `forecast:pipeline:lock` (TTL 1800s / 30 min, SET NX EX). `POST /api/forecasting/recompute` (admin only) bypasses the lock.

**Pipeline steps:**
1. One JOIN query: all courses with ended-session count
2. Skip fresh rows (generated_at < 1800s old AND ollama_reachable=true)
3. Courses with < 3 ended sessions → write empty marker row (`trend_data=[]`, `generated_at=now()`) to terminate frontend poll
4. Per course: `_get_course_trend()` → last `FORECAST_WINDOW=8` sessions' attendance rate as fractions (present+late / enrolled, GROUP BY session)
5. `_classify_trend(rates)` → deterministic delta math → classification + confidence
6. `build_forecast_prompt()` → 2-line structured prompt → Ollama call → parse `EXPECTED_NEXT: <int>` + `INTERPRETATION: <sentence>` → `_upsert_forecast()`

**Deterministic trend classification approach:**
- `rates` = chronological list of 0.0–1.0 fractions; `deltas` = consecutive differences
- `mean_delta < -0.02`: `steady_decline` (or `accelerating_decline` if second-half deltas are >0.01 worse than first half)
- `mean_delta > +0.015`: `recovering`
- else: `stable`
- **Confidence:** high ≥ 6 sessions, medium ≥ 4 sessions, low < 4 sessions
- `_parse_llm_response()`: never raises; returns `(None, None)` on parse failure

**LLM role in forecasting:**
The LLM produces **only prose interpretation and a projected next attendance rate** (`EXPECTED_NEXT: <int>`). All classification labels and confidence levels are computed deterministically from delta math. This prevents hallucinated labels from breaking the frontend's color-coding logic.

**Classification is always deterministic** — the LLM only writes `INTERPRETATION: <sentence>` and projected rate.

**Shared Ollama utilities:** `call_ollama()` and `_check_ollama_ready()` defined once in `at_risk_engine.py` and imported directly by `forecast_engine.py` — no code duplication.

---

### SQL Insights Engine
Pure SQL analytics served on-demand (no LLM). Role-filtered queries. Computes:
- Attendance trend (weekly aggregation)
- Heatmap by day/hour-slot
- Decay analysis
- Comfort score (from Redis live sensor data)
- AC effectiveness
- Temperature vs. attendance scatter
- Air quality vs. sound correlation

---

## 15. EXTERNAL INTEGRATIONS

### Moodle 4.x
- **When sync happens:** automatically triggered on `POST /api/sessions/{id}/end` (background task); also available manually via `POST /api/sessions/{id}/sync-moodle`
- **API:** Moodle REST API, token-authenticated (`wstoken={token}&moodlewsrestformat=json`)
- **Status mapping:** present=1, absent=2, late=3, excused=4 → `mod_attendance_add_attendance`
- **Redis retry queue:** failures push `session_id` to Redis list `moodle:retry_queue`; `alert_engine.retry_moodle_sync()` retries up to 10 items every 10 min
- **Health probe:** `GET /api/moodle-test` → `{"connected": true, "moodle_url": "..."}`
- **Moodle version:** 4.x (bitnami/moodle:4 Docker image)
- **Optional Docker profile:** `docker compose --profile moodle up -d`

### Ollama / phi3:mini
- **API endpoint:** `http://ollama:11434` (Docker service name)
- **Startup model pull:** on backend startup, `ensure_model_pulled()` calls `GET /api/tags`; if model absent, fires `POST /api/pull` as non-blocking background task (~2 GB pull for phi3:mini)
- **Model persisted:** in named Docker volume `ollama_data`
- **Inference config:** `stream=false`, `temperature=0.3`, `num_predict=180` — deterministic, concise output
- **Shared client:** single `httpx.AsyncClient` shared across all Ollama calls within each pipeline run; prevents TCP connection churn
- **`ollama_reachable` flag behavior:** both AI pipelines write `ollama_reachable=False` to the database when Ollama is unavailable; frontend shows amber warning card instead of crashing or blocking; freshness gate skips re-generation only when `ollama_reachable=True`

---

## 16. INFRASTRUCTURE & DEPLOYMENT

### Full Docker Compose services table (8 services)

| Service | Image | Internal Port | External Port | Volumes | depends_on |
|---|---|---|---|---|---|
| postgres | postgres:15-alpine | 5432 | 5432 | postgres_data:/var/lib/postgresql/data | — |
| redis | redis:7-alpine | 6379 | 6379 | redis_data:/data | — |
| mosquitto | eclipse-mosquitto:2 | 1883 | 1883 | mosquitto.conf (ro), mosquitto_data | — |
| mariadb *(profile: moodle)* | mariadb:10.6 | 3306 | — | mariadb_data:/var/lib/mysql | — |
| moodle *(profile: moodle)* | bitnami/moodle:4 | 8080 | 8080 | moodle_data, moodledata_data | mariadb (healthy) |
| ollama | ollama/ollama:latest | 11434 | 11434 | ollama_data:/root/.ollama | — |
| backend | custom build (./backend) | 8000 | 8000 | — | postgres (healthy), redis (healthy), mosquitto (started), ollama (started) |
| frontend | custom build (./frontend) + nginx | 80 | 3000 | — | backend (started) |

**Named volumes:** postgres_data, redis_data, mosquitto_data, mariadb_data, moodle_data, moodledata_data, ollama_data

### All start commands

```bash
# Full stack (core services)
docker compose up -d

# Without ESP32 (mock sensors)
MOCK_MODE=true docker compose up -d

# With Moodle LMS
docker compose --profile moodle up -d

# Seed demo data (35 students, 6 courses, 30 sessions, 5 professors)
docker compose exec backend python seed.py

# Manually trigger at-risk pipeline
docker compose exec backend python -c \
  "import asyncio; from app.services.at_risk_engine import run_at_risk_pipeline; asyncio.run(run_at_risk_pipeline())"
```

### Service URLs

| URL | Service |
|---|---|
| http://localhost:3000 | React dashboard |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | Health check (Redis + DB) |
| http://localhost:1883 | Mosquitto MQTT broker |
| http://localhost:11434 | Ollama LLM API |
| http://localhost:8080 | Moodle (optional profile) |

### nginx reverse proxy
- Port 3000 → port 80 (internal nginx)
- All `/api/*` requests proxied from port 3000 to FastAPI backend at port 8000
- All `/ws/*` requests proxied from port 3000 to FastAPI backend at port 8000
- React app served as static files by nginx
- CORS: FastAPI middleware allows all origins (`allow_origins=["*"]`) for development

### Alembic auto-migration
- **When it runs:** at backend startup, before any API routes are registered, in the `lifespan` context manager
- **How:** `_run_migrations()` calls `subprocess.run([alembic_bin, "upgrade", "head"])` with `cwd=backend_dir`, `timeout=30`
- This ensures schema is always current without a separate migration step
- If migration fails, warning is logged but startup continues (DB may not be available yet)

---

## 17. SECURITY & PRIVACY

### NFRs (compiled from technical_report_outline.md Chapter 3.3 and scattered requirements)

| NFR-ID | Category | Requirement |
|---|---|---|
| NFR-01 | Real-time latency | Sensor update end-to-end latency ≤ 5s (MQTT publish to dashboard update) |
| NFR-02 | Availability | System must operate without internet connectivity; all services run locally on RPi |
| NFR-03 | Resilience | Backend must reconnect to MQTT broker automatically with exponential backoff on disconnect |
| NFR-04 | Resilience | Frontend must activate demo mode after 8s with no WebSocket data (DemoModeBanner) |
| NFR-05 | Resilience | Moodle unavailability must not fail session-end flow; retry queue (Redis) ensures eventual sync |
| NFR-06 | Authentication | All API endpoints must require valid JWT (HS256) when `REQUIRE_AUTH=true` |
| NFR-07 | Authentication | Professor passwords must be stored as bcrypt hashes; no plaintext storage |
| NFR-08 | Authorization | Role-based access control: professors see only their own courses and students |
| NFR-09 | Authorization | Admin-only endpoints: `POST /api/at-risk/recompute`, `POST /api/forecasting/recompute` |
| NFR-10 | Privacy | Face encodings (128-d float32 BYTEA) must remain on-premises; no cloud transmission |
| NFR-11 | Privacy | LLM prompts sent only to local Ollama instance; no student data leaves the university network |
| NFR-12 | Privacy | LLM prompts must not reference health, personal life, family, or psychology |
| NFR-13 | Scalability | Single-room deployment; design must allow multi-room extension via `room_id` parameter |
| NFR-14 | Security | `SECRET_KEY` environment variable must be changed from default `changeme` in production |

### bcrypt for passwords
Professor account passwords are hashed with bcrypt before storage in the `professors` table. No plaintext passwords are ever stored.

### Face embeddings on-premises only
- Enrollment images are processed (FaceNet 128-d embedding computed) and discarded — only the averaged embedding is persisted as BYTEA
- All recognition inference runs locally on RPi; no cloud API calls for biometric data
- Stub mode: zeroed placeholder encoding stored; no real biometric processing occurs

### JWT in localStorage (rationale + risk acknowledgement)
**Rationale:** Simpler than httpOnly cookie approach; acceptable on closed university intranet; token expiry enforced server-side.
**Risk acknowledged:** JWT in localStorage is theoretically vulnerable to XSS on an open network; this risk is acknowledged in the architecture decision log and is mitigated by the closed intranet deployment context.

### No HTTPS/WSS — documented limitation
Current deployment uses HTTP/WS on university LAN. Identified as a known gap and listed as future work. The nginx SSL termination path is described as the remediation (add TLS certificate to nginx config). Backend is not directly exposed — nginx is the single ingress point.

### RBAC
- `professor` role: API responses filtered to professor's own courses and students only
- `admin` role: all data accessible
- Role stored in `professors.role` ENUM column

### Ollama local inference — no student data to external APIs
All LLM inference runs on the local Ollama instance on the RPi. No student data (names, attendance records, sensor correlations) is transmitted to any external cloud API. At-risk pipeline prompt constraints enforce additional privacy rules.

---

## 18. PERFORMANCE METRICS (exact numbers)

| Metric | Value | Source/NFR |
|---|---|---|
| Sensor end-to-end latency (target) | ≤ 5s (MQTT publish → dashboard update) | NFR-01; sensor publishes every 5s |
| Face recognition fps on RPi 4B | 2 fps sustained | RECOGNITION_FPS=2 in config |
| Face recognition threshold | cosine distance < 0.40 | Phase 22 (tightened from 0.60) |
| At-risk pipeline runtime (before optimization) | ~14–16 min (for 8 students, ~7 Ollama calls/student) | Phase 19 |
| At-risk pipeline runtime (after optimization) | ~2–3 min (for 8 students, 1 Ollama call/student) | Phase 20 |
| phi3-mini inference time per student | ~10–30s on RPi CPU | CLAUDE.md |
| At-risk pipeline lock TTL | 600s (~10 min natural cooldown) | Redis SET NX EX |
| Forecasting pipeline lock TTL | 1800s (30 min) | Redis SET NX EX |
| Forecasting FORECAST_WINDOW | 8 past ended sessions | FORECAST_WINDOW env var |
| ATTENDANCE_CYCLE_DURATION | 60s per scan→evaluate cycle | Phase 22 |
| Alert engine cycle | 30s | APScheduler interval |
| Demo mode watchdog timeout | 8,000ms | DEMO_TIMEOUT_MS in useLiveSensors.js |
| WebSocket reconnect initial backoff | 3,000ms | INITIAL_BACKOFF in useLiveSensors.js |
| WebSocket reconnect max backoff | 30,000ms | MAX_BACKOFF in useLiveSensors.js |
| Manual attendance time eliminated | Up to 15 min per lecture | Chapter 1 problem statement |
| Seed data scale | 35 students, 6 courses, 30 sessions, 5 professors | seed.py |
| JWT expiry | 480 minutes (8 hours) | ACCESS_TOKEN_EXPIRE_MINUTES |
| MQTT heartbeat interval | Every 30s | ESP32 firmware |
| Redis sensor cache TTL | 300s (5 min) | MQTT handler |
| Redis device presence TTL | 60s (renewed by heartbeat) | MQTT status handler |
| phi3-mini model size | ~2 GB (Docker pull) | rpi_setup.md |
| FaceNet model weights size | ~90 MB (downloaded to ~/.deepface/) | rpi_setup.md |
| Alembic migration timeout | 30s | `_run_migrations()` subprocess |

*Note: Exact RAM usage figures for Docker stack normal/with Ollama loaded and CPU utilization during LLM inference are not explicitly documented in the source files. The phi3-mini model requires ~4k context window; Ollama runs on CPU on RPi 4B 4GB.*

---

## 19. TESTING & VALIDATION SUMMARY

### Testing types performed
1. **Unit tests** (pytest + pytest-asyncio): backend service logic (`test_sensors.py`, `test_sessions.py`, `test_attendance.py`, `test_alerts.py`, `test_face_enrollment.py`, `test_websocket.py`)
2. **Integration tests:** ESP32 → MQTT → backend → DB flow (end-to-end MQTT message ingestion verified)
3. **End-to-end test script:** `backend/tests/e2e_test.py` — simulates full class session (create course + students → start session → 3 attendance records → high-temp alert → end session → verify Moodle sync); prints PASS/FAIL per step
4. **Manual hardware testing:** Physical ESP32 + RPi setup; serial monitor validation; MQTT CLI tools (`mosquitto_sub`, `mosquitto_pub`)

### Sensor validation method
- **DHT21:** readings compared against reference thermometer
- **MQ-135:** relative calibration approach — threshold set empirically at 500 ppm (not factory-calibrated; values are comparative only)
- **ACP014 sound sensor:** detection accuracy verified by toggling sound presence; digital binary output (no analog level)

### Face recognition test conditions and accuracy result
- Test conditions: varied lighting, different angles, glasses
- Recognition accuracy at 2fps under lab conditions (exact % not published in outline; results described as meeting operational requirements)
- Stub mode fallback validation: `_stub_recognition_loop` verified to exercise full bidirectional present↔absent logic

### API testing tool used
**FastAPI Swagger UI** (`/docs`) — used for manual endpoint validation of all REST routes. Key scenarios: session start/end, attendance record creation, relay control, alert generation.

### Resilience scenarios tested
1. **MQTT broker restart:** backend reconnects with exponential backoff (aiomqtt auto-reconnect)
2. **Ollama unavailable:** `ollama_reachable=false` persisted to DB; amber UI warning shown; system does not crash
3. **Network loss / WebSocket disconnect:** frontend demo mode activation after 8s watchdog; `DemoModeBanner` displayed
4. **Moodle unreachable:** session-end succeeds; session_id pushed to Redis retry queue; alert engine retries every 10 min
5. **Camera unavailable:** stub mode transparently replaces recognition loop; no backend crash

---

## 20. DEVELOPMENT METHODOLOGY

### Number of phases
**22 phases** (Phase 0 through Phase 22)

### Tool used for task management
**Notion** — used as the team collaboration and task tracking tool

### Kanban board structure (columns)
From technical_report_outline.md Chapter 5.1: board structure with phase tracking, assignment of phases to team members, progress tracking. Standard Kanban columns (To Do / In Progress / Done implied by "Kanban board structure").

### Card structure (fields per card)
Each Notion card contains: phase/task name, assigned team member(s), status, description of deliverables, acceptance criteria.

### Phase timeline overview

| Phase | Description | Status |
|---|---|---|
| 0 | Project scaffolding, Docker Compose, env setup | ✅ |
| 1 | ESP32 firmware — sensors + MQTT publish | ✅ |
| 2 | Backend foundation — FastAPI, DB models, MQTT bridge | ✅ |
| 3 | Face recognition service + enrollment API | ✅ |
| 4 | Session management + attendance engine | ✅ |
| 5 | Control API + alert engine | ✅ |
| 6 | Moodle sync service | ✅ |
| 7 | WebSocket live streaming | ✅ |
| 8 | React frontend | ✅ |
| 9 | Integration testing + documentation | ✅ |
| 10 | Full Docker deployment — nginx, Mosquitto, service wiring | ✅ |
| 11 | Mock data fallback — backend publisher + frontend demo mode | ✅ |
| 12 | Raspberry Pi setup runbook | ✅ |
| 13 | Demo data seed script | ✅ |
| 14 | JWT auth, professors table, role-based API filtering | ✅ |
| 15 | Docker image slim — DeepFace/TF removed, stub, seed.py self-migrating | ✅ |
| 16 | Professor Dashboard — session list + attendance table + sensor sparklines | ✅ |
| 17 | Dashboard bug fixes — total_enrolled, key-based tab reset, count badges, MOCK_MODE | ✅ |
| 18 | Full frontend visual redesign — CSS token system, typography, blue sidebar, Soft Structuralism | ✅ |
| 19 | At-Risk Explanation — Ollama/phi3-mini, pipeline, DB table, At-Risk page | ✅ |
| 20 | At-Risk pipeline performance — on-demand trigger, N+1 elimination, 1 LLM call/student, Redis cooldown, frontend auto-poll | ✅ |
| 21 | LLM-Assisted Forecasting — deterministic trend classification + Ollama interpretation per course, attendance_forecasts table, Forecasting page | ✅ |
| 22 | Snapshot-per-cycle attendance — bidirectional present↔absent evaluation; laptop_recognition.py two-system conflict resolved; adjusted_by guard; recognition threshold tightened to 0.40 | ✅ |

---

## 21. HARDWARE BILL OF MATERIALS

| Component | Model | Role |
|---|---|---|
| SBC | Raspberry Pi 4B 4GB | Central hub; runs all services; Docker host; camera host |
| Camera | Raspberry Pi Camera Module v2 8MP | Face recognition input; MIPI CSI-2 interface |
| MCU | ESP32 Dev Board (ESP-WROOM-32) | Sensor node + relay controller; WiFi MQTT client |
| Temp/Humidity Sensor | DHT21 (AM2301) | Environmental monitoring (temperature °C + humidity %) |
| Air Quality Sensor | MQ-135 | CO₂/VOC proxy; ADC analog output; alert threshold 500 ppm |
| Sound Sensor | ACP014 | Occupancy proxy, noise level detection; digital binary output |
| Relay Module | 4-Channel Opto-Isolated Relay | AC unit (ch1), Room lighting (ch2), spare (ch3/ch4) |
| Display | LCD 16×2 I2C | Local room status; I2C address 0x27; GPIO 21 (SDA), GPIO 22 (SCL) |
| Voltage Converter | Logic Level Converter 3.3V↔5V | ESP32 (3.3V) ↔ Relay module (5V TTL) safe communications |
| Power (RPi) | USB-C 5V 3A | Raspberry Pi 4B power supply |
| Storage (RPi) | microSD ≥16GB Class 10 | Raspberry Pi OS + Docker volumes |
| Power (ESP32) | USB power bank / USB-C | ESP32 + MQ-135 heater + relay VCC |

*Note: All mains wiring (relay contacts carry 220V AC) must be performed by a qualified electrician and comply with local electrical safety codes.*

---

## 22. KNOWN LIMITATIONS & FUTURE WORK

### All documented limitations

| Limitation | Detail |
|---|---|
| MQ-135 uncalibrated | Values are comparative only; threshold set empirically at 500 ppm; no factory calibration |
| Single-room design | `ROOM_ID` is a single configurable value; requires architectural work for multi-room |
| phi3-mini slow on RPi CPU | ~10–30s inference per student; frontend uses progressive polling every 8s |
| No HTTPS/WSS | HTTP/WS on university LAN only; nginx SSL termination path described for future production deployment |
| MQTT QoS 0 for sensor data | Sensor messages may be lost during broker restart; dashboard shows stale Redis data until next message |
| Single-semester delivery | Academic constraint; 22 phases completed in one semester |
| DeepFace inference slow on RPi 4 | Keep RECOGNITION_FPS=2; upgrade to RPi 5 for better throughput |
| No refresh token mechanism | JWT only; sessions expire after 480 min; user must re-login |
| phi3-mini first-run pull ~2GB | Startup pull is non-blocking; page must be reopened after pull completes |

### All deferred future features
1. Multi-room support (change ROOM_ID in config.h + .env)
2. React Native mobile app for professors
3. IR illuminator for low-light face recognition
4. Email/SMS alert notifications
5. QR-code student self-enrollment
6. CO₂ sensor calibration (SCD30 / MH-Z19 replacement)
7. Offline SQLite fallback
8. Daily at-risk email digest
9. Quantized GGUF model via llama.cpp for faster RPi CPU inference
10. HTTPS/WSS (nginx SSL termination for public deployment)
11. Refresh token mechanism
12. Attendance analytics dashboard (extended analytics beyond current Insights page)
13. GPU upgrade (RPi 5 for better face recognition throughput)

---

## 23. LESSONS LEARNED

*(Chapter 9.4 — Lessons Learned, as documented in the technical report outline)*

1. **aiomqtt migration from asyncio-mqtt:** paho-mqtt v2 introduced a breaking change that broke asyncio-mqtt; the team migrated to `aiomqtt 2.x` as the async MQTT client. Lesson: pin library versions and test upgrades carefully in async IoT projects.

2. **DeepFace/TF removed from Docker image:** TensorFlow and DeepFace (~600 MB) caused OOM on development laptops when included in the Docker backend image. Solution: remove from Docker; install natively on RPi only; use stub mode in Docker. Lesson: separate hardware-dependent libraries from portable containerized services.

3. **Glassmorphism removed:** GPU-expensive visual effect; caused rendering artifacts in Chromium. Removed in Phase 18 visual redesign. Lesson: validate UI design choices on target hardware (RPi + browser) before committing to them.

4. **Redis lock TTL not deleted on completion:** Initially the pipeline lock was released immediately after completion, allowing rapid re-triggering on page refresh. Lesson: for expensive pipeline operations, letting the TTL expire naturally is the correct "cooldown" pattern.

5. **VARCHAR(30) vs. PG ENUM lesson:** PostgreSQL's `ALTER TYPE ADD VALUE` is non-transactional and cannot be run inside a transaction block. Using `VARCHAR(30)` for classification fields avoids this DDL problem on schema evolution without requiring a migration. Lesson: prefer VARCHAR over PG ENUM for evolving categorical fields.

6. **N+1 query elimination in AI pipeline:** The at-risk pipeline originally made N separate Ollama calls (one per course per student) and N separate DB queries per student. Phase 20 reduced this to 3 batch SQL queries + 1 Ollama call per student, cutting runtime from ~14-16 min to ~2-3 min. Lesson: profile before optimizing; N+1 patterns in LLM-calling code are disproportionately expensive.

7. **On-demand pipeline vs. cron:** An initial cron-based approach for at-risk explanations meant professors saw no data until the scheduled run (e.g., 02:00). On-demand triggering on page access generates results immediately when needed. Lesson: match trigger timing to user expectation; background polling is preferable to scheduled batch jobs for user-facing features.

8. **Two-system attendance conflict (Phase 22):** Having both the backend recognition loop (stub) and laptop_recognition.py write to `attendance_records` simultaneously caused random overrides. Resolved by stopping the backend loop when laptop_recognition.py starts (mutual exclusion at subprocess spawn). Lesson: two independent writers to the same DB table without coordination will produce race conditions.

9. **Marker rows for pipeline poll termination:** Without a DB row for courses with < 3 sessions, the frontend's `some(c => !c.generated_at)` polling condition never resolved. Empty marker rows (`trend_data=[]`, `generated_at=now()`) terminate the poll immediately. Lesson: frontend polling termination conditions must account for all possible states including "intentionally empty."

10. **Deterministic trend classification:** The LLM produced unreliable structured outputs for trend labels (hallucination risk). Moving classification to deterministic delta math made the system reliable and predictable. Lesson: delegate to LLM only for natural language generation; use deterministic code for structured decisions.

---

## SLIDE CONTENT SUGGESTIONS

For each section, a suggested slide title, 3–5 key bullets, and any diagram/visual reference.

---

### Slide 1 — Project Identity
**Title:** Smart Campus Classroom Management System

**Bullets:**
- Institution: SMU — Mediterranean Institute of Technology, Academic Year 2025–2026
- Team: Mohamed Hedi Ben Jemaa, Ahmed Amine Jallouli, Ali Saadaoui, Abdelhamid Ouertani, Iyed Day
- Report format: IEEE
- Delivered in 22 phases over one academic semester
- Zero cloud dependency — full IoT stack on Raspberry Pi 4B

**Visual:** Project logo / team photo / SMU MedTech institutional branding

---

### Slide 2 — Problem Statement
**Title:** The Classroom Management Problem

**Bullets:**
- Up to 15 minutes per lecture wasted on manual attendance roll-call
- No real-time visibility into classroom temperature, CO₂, or occupancy
- No early-warning system for students trending toward course failure
- Physical classroom and Moodle LMS operate in silos — no automatic sync
- Growing IoT literature demonstrates feasibility of automated classroom management

**Visual:** Figure — timeline showing 15-min attendance overhead vs. 0-min automated; photo of manual roll-call vs. dashboard screenshot

---

### Slide 3 — Project Objectives
**Title:** What We Set Out to Build

**Bullets:**
- Automate attendance via face recognition (DeepFace/FaceNet, cosine distance < 0.40)
- Monitor 4 environmental parameters in real time (temperature, humidity, CO₂, sound)
- Enable automated + manual HVAC and lighting control via MQTT-driven relays
- Provide professors a live React dashboard with WebSocket data streaming
- Synchronize attendance records to Moodle LMS automatically on session end
- Identify at-risk students + forecast attendance trends using local phi3:mini LLM

**Visual:** 6-item numbered list with icons per objective

---

### Slide 4 — Scope & Constraints
**Title:** Scope Boundaries & Constraints

**Bullets:**
- Single-room deployment (ROOM_ID=room1); designed for multi-room extension
- Tunisian hardware market constraints → off-the-shelf Arduino/IoT components
- RPi 4B compute limits: face recognition at 2 fps; phi3:mini at 10–30s/student on CPU
- Academic semester deadline: 22 phases, ~5 months delivery
- Deferred: multi-room, mobile app, IR illuminator, email alerts, HTTPS/WSS

**Visual:** Scope boundary diagram; RPi hardware photo

---

### Slide 5 — System Architecture
**Title:** Hybrid Modular Monolith + Event-Driven Architecture

**Bullets:**
- Architecture pattern: hybrid modular monolith + event-driven messaging
- 4 paradigms: MQTT Pub/Sub (QoS 0), WebSocket push, asyncio.Queue fan-out, on-demand async pipelines
- 9 subsystems: IoT (ESP32), Edge (RPi), Broker (Mosquitto), Backend (FastAPI), Real-time, AI, Frontend, Data, External
- Three `asyncio.Queue` instances decouple MQTT/recognition/alert producers from WebSocket consumers
- Single FastAPI process — not microservices; internal event-driven via queues

**Visual:** Figure — full layered architecture diagram (IoT → Edge → Backend → Frontend → External); event fan-out diagram

---

### Slide 6 — ESP32 Firmware (IoT Layer)
**Title:** ESP32 — The Physical Sensor Node

**Bullets:**
- 3 sensors: DHT21 (temperature + humidity), MQ-135 (air quality ppm), ACP014 (sound binary)
- Publishes to `classroom/{room_id}/sensors/{type}` every 5s via MQTT QoS 0
- Heartbeat on `classroom/{room_id}/status` every 30s (drives Redis device-online TTL)
- Controls 4-channel opto-isolated relay via Logic Level Converter (3.3V↔5V)
- On-device auto-control (acAutoMode) acts locally if MQTT connection drops — deliberate redundancy

**Visual:** Figure — ESP32 wiring diagram / GPIO pinout table; photo of assembled breadboard

---

### Slide 7 — Raspberry Pi Edge Layer
**Title:** Raspberry Pi 4B — The Edge Hub

**Bullets:**
- Runs full stack: Mosquitto broker, FastAPI, PostgreSQL, Redis, Ollama, nginx
- Face recognition: DeepFace/FaceNet, 2 fps, cosine distance < 0.40, snapshot-per-cycle model
- Stub mode (FACE_RECOGNITION_ENABLED=false): ~70% ± 2 enrolled students randomly per cycle
- Mock mode (MOCK_MODE=true): sine-wave sensor publisher every 5s — undetectable by MQTT bridge
- phi3:mini LLM inference on CPU: ~10–30s per student; ~2 GB model weight

**Visual:** Figure — RPi topology showing all connected services; photo of RPi with camera module

---

### Slide 8 — MQTT Communication Layer
**Title:** MQTT: The IoT Message Bus

**Bullets:**
- Broker: Mosquitto 2 on port 1883
- QoS 0 for sensor telemetry (high freq, tolerable loss); QoS 1 for relay commands (acknowledgement required)
- 8 distinct topics: 4 sensor types, status, relay/ac, relay/lighting, alerts
- Backend subscribes via wildcard `classroom/+/sensors/#` and `classroom/+/status`
- No retained messages — Redis serves as authoritative "last known value" store

**Visual:** Figure — MQTT topic tree diagram

---

### Slide 9 — FastAPI Backend
**Title:** FastAPI Backend — 7 Module Groups

**Bullets:**
- 7 groups: Ingestion (MQTT bridge), Session/Attendance, Control, Alert Engine, Insights, AI Pipelines, Auth
- 3 asyncio.Queue instances: sensor_event_queue, attendance_event_queue, alert_event_queue
- Alert engine runs every 30s via APScheduler; deduplication prevents alert storms
- Alembic auto-migration runs at startup via subprocess before routes are registered
- JWT (HS256), bcrypt, role-filtered APIs; `REQUIRE_AUTH=false` for dev

**Visual:** Figure — backend internal module diagram (mqtt_bridge → event queues → services → API routes)

---

### Slide 10 — WebSocket Real-Time Layer
**Title:** Sub-Second Live Updates via WebSocket

**Bullets:**
- Endpoint: `WS /ws/classroom/{room_id}`; snapshot sent immediately on connect
- 6 message types: snapshot, sensor, attendance, alert, ping, pong
- 30s server keepalive ping/pong; automatic frontend reconnect (3s → 30s exponential backoff)
- Demo mode watchdog: 8s with no data → DemoModeBanner activated; client-side mock generator starts
- Three drain tasks fan events from asyncio.Queue to all connected WebSocket clients

**Visual:** Figure — event fan-out diagram (MQTT handler / recognition loop / alert engine → asyncio.Queue → drain task → WebSocket → Browser)

---

### Slide 11 — Data Layer
**Title:** PostgreSQL + Redis: Two-Tier Data Architecture

**Bullets:**
- 10 PostgreSQL tables; 3 JSONB columns; BYTEA for 128-d face embeddings
- display_status computed at query time (not stored) — liveness changes without writes
- VARCHAR(30) not PG ENUM for trend_classification — avoids non-transactional ALTER TYPE DDL
- 6 Redis key patterns: sensor cache (TTL 300s), device presence (TTL 60s), relay state (no TTL), pipeline locks, Moodle retry queue
- Ephemeral (Redis) vs. persistent (PostgreSQL) boundary is the key design line

**Visual:** Figure — Entity-Relationship Diagram (all 10 tables); Redis key pattern table

---

### Slide 12 — React Dashboard
**Title:** Professor Dashboard — React 18 SPA

**Bullets:**
- 9 routes: Login, Dashboard, Attendance, Control, Enrollment, History, Insights, At-Risk, Forecasting
- tokens.css (design token source of truth) + index.css (component classes) separation — TailwindCSS v3 can't resolve CSS vars at build time
- useLiveSensors hook: native WebSocket, exponential backoff, 8s demo watchdog
- Recharts AreaChart + linearGradient + 70% dashed ReferenceLine on Forecasting page
- DM Sans (headings 600/700) + Inter (body 400/500)

**Visual:** Screenshots — Dashboard, Attendance, At-Risk, Forecasting pages

---

### Slide 13 — Face Recognition Pipeline
**Title:** Face Recognition — Enrollment to Attendance

**Bullets:**
- Enrollment: up to 5 images → FaceNet 128-d per image → averaged → BYTEA storage
- Recognition: OpenCV VideoCapture → cosine distance < 0.40 → attend record
- Snapshot-per-cycle (Phase 22): 60s SCAN → bidirectional EVALUATE → adjusted_by guard
- Stub mode: ~70% ± 2 students randomly per cycle; exercises full bidirectional logic
- Enrollment images discarded after encoding; only 128-d float32 vector persisted

**Visual:** Figure — face recognition flow diagram (enrollment + recognition loop)

---

### Slide 14 — AI & Analytics Layer
**Title:** Local LLM + Deterministic Analytics

**Bullets:**
- At-risk pipeline: on-demand trigger; 70% threshold; 1 Ollama call/student (down from ~7); runtime ~2–3 min vs. ~14–16 min before optimization
- Forecasting: deterministic delta math → steady_decline / accelerating_decline / stable / recovering; LLM writes only prose interpretation
- Confidence: high ≥6 sessions, medium ≥4, low <4
- Redis lock TTL 600s (at-risk) / 1800s (forecasting) — natural cooldown, not deleted on completion
- All LLM inference local (phi3:mini on RPi); no student data to external APIs

**Visual:** Figure — at-risk pipeline flow diagram; before/after performance table

---

### Slide 15 — External Integrations
**Title:** Moodle LMS Sync + Local LLM

**Bullets:**
- Moodle 4.x: auto-sync on session end via REST API; Redis retry queue for failures; retried every 10 min
- Ollama/phi3:mini: startup non-blocking model pull (~2 GB); `stream=false`, `temperature=0.3`, `num_predict=180`
- Shared httpx.AsyncClient across all Ollama calls — prevents TCP connection churn
- ollama_reachable flag: when False → amber warning card in UI, no crash
- Both AI pipelines reuse `call_ollama()` and `_check_ollama_ready()` from `at_risk_engine.py`

**Visual:** Integration diagram showing Moodle + Ollama connections to backend

---

### Slide 16 — Infrastructure & Deployment
**Title:** Docker Compose — 8-Service Stack

**Bullets:**
- 8 services: postgres:15-alpine, redis:7-alpine, eclipse-mosquitto:2, ollama/ollama, custom backend, nginx frontend, bitnami/moodle:4 + mariadb:10.6 (optional profile)
- Single command deployment: `docker compose up -d`; `MOCK_MODE=true` for hardware-free demo
- nginx: port 3000 → proxies /api/* and /ws/* to FastAPI :8000; serves React as static files
- Alembic auto-migration at startup: subprocess call `alembic upgrade head` before routes register
- Named volumes: postgres_data, redis_data, mosquitto_data, ollama_data — survive container rebuilds

**Visual:** Figure — Docker Compose service dependency graph

---

### Slide 17 — Security & Privacy
**Title:** Security Architecture — Defense in Depth

**Bullets:**
- Authentication: JWT HS256, 480-min expiry, bcrypt password hashing
- Authorization: RBAC (professor scope-filtered vs. admin all-access); admin-only recompute endpoints
- Biometric privacy: 128-d embeddings on-premises BYTEA only; enrollment images discarded; no cloud transmission
- LLM privacy: phi3:mini local inference; no student data leaves university network; prompt constraints enforced
- Known gap: no HTTPS/WSS (HTTP on LAN); JWT in localStorage (acknowledged, intranet-acceptable tradeoff)

**Visual:** Security layer diagram (network LAN → nginx → FastAPI → JWT → RBAC → DB)

---

### Slide 18 — Performance Metrics
**Title:** Key Performance Numbers

**Bullets:**
- Sensor end-to-end latency target: ≤5s (MQTT publish → dashboard update)
- Face recognition: 2 fps sustained on RPi 4B, cosine distance threshold 0.40
- At-risk pipeline: 2–3 min for 8 students (down from 14–16 min) — 7× speedup
- phi3:mini inference: 10–30s per student on RPi 4B CPU
- Manual attendance eliminated: up to 15 min per lecture saved

**Visual:** Before/after performance comparison table; bar chart of pipeline runtime reduction

---

### Slide 19 — Testing & Validation
**Title:** Testing Strategy — Four Layers

**Bullets:**
- Unit tests (pytest + pytest-asyncio): sensors, sessions, attendance, alerts, face enrollment, WebSocket
- End-to-end script: `e2e_test.py` simulates full session lifecycle; PASS/FAIL per step
- Manual hardware validation: DHT21 vs. reference thermometer; MQ-135 empirical threshold; face recognition accuracy under varied conditions
- Resilience testing: MQTT restart → backoff reconnect; Ollama down → amber warning; network loss → 8s demo mode
- API testing via FastAPI Swagger UI (/docs)

**Visual:** Screenshot — Swagger UI; test results summary table

---

### Slide 20 — Development Methodology
**Title:** 22-Phase Agile Delivery

**Bullets:**
- 22 phases, Phase 0 through Phase 22, all completed ✅
- Notion as team task management tool (Kanban board: phases assigned to members)
- Agile-inspired iterative: each phase builds on previous; no phase starts until current phase is working
- Tool chain: Claude Code for AI-assisted development; Arduino IDE for ESP32; Docker Compose for deployment
- One-semester delivery of a complete IoT + AI + web stack

**Visual:** Screenshot — Notion Kanban board; phase timeline chart

---

### Slide 21 — Hardware Bill of Materials
**Title:** Hardware — 12 Components, ~€150 Budget

**Bullets:**
- Central hub: Raspberry Pi 4B 4GB — runs entire software stack
- Sensor node: ESP32 Dev Board (ESP-WROOM-32) — WiFi MQTT, 3 sensors, relay control
- Sensors: DHT21 (temperature + humidity), MQ-135 (CO₂/VOC proxy), ACP014 (sound binary)
- Actuation: 4-channel opto-isolated relay (220V AC + lighting) via Logic Level Converter
- Display: LCD 16×2 I2C (I2C address 0x27) — local room status on ESP32
- Camera: Raspberry Pi Camera Module v2 8MP — MIPI CSI-2 face recognition input

**Visual:** Annotated hardware photo; BOM table with roles

---

### Slide 22 — Known Limitations & Future Work
**Title:** Limitations & Road Map

**Bullets:**
- MQ-135 uncalibrated; single-room; no HTTPS/WSS; QoS 0 sensor loss risk; no refresh tokens
- phi3-mini CPU inference 10–30s/student — mitigated by 8s frontend polling + RPi 5 upgrade path
- Future: multi-room, React Native mobile, IR illuminator, GGUF model via llama.cpp, email alerts
- No refresh token mechanism — future: implement JWT refresh token rotation
- CO₂ sensor upgrade path: SCD30 or MH-Z19 (calibrated sensors vs. uncalibrated MQ-135)

**Visual:** Roadmap timeline diagram; limitations vs. mitigations table

---

### Slide 23 — Lessons Learned
**Title:** 10 Engineering Lessons Learned

**Bullets:**
- aiomqtt over asyncio-mqtt: paho-mqtt v2 breaking changes require library pinning in async IoT
- Separate hardware-dependent libs from Docker images (DeepFace/TF OOM on dev laptops)
- Redis TTL expiry is a natural cooldown mechanism — don't delete locks on completion
- VARCHAR(30) > PG ENUM for evolving categoricals (non-transactional ALTER TYPE DDL)
- N+1 patterns in LLM-calling code are disproportionately expensive: 7× runtime reduction via batching
- Deterministic code for structured decisions; LLM only for natural language generation
- Two independent DB writers without coordination produce race conditions
- On-demand triggers > scheduled cron for user-facing pipeline features
- Marker rows terminate frontend polling — design for all states including "intentionally empty"
- Glassmorphism is GPU-expensive; validate UI effects on target hardware before committing

**Visual:** Lessons timeline mapped to phases; before/after comparison for key decisions

---

*End of project_master_reference.md*
*Generated 2026-05-14 from exhaustive extraction of all project source files.*
