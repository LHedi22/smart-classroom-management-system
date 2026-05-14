# Smart Classroom Management System — Full System Architecture

> Reverse-engineered from source. Generated 2026-05-12.

---

## 1. SYSTEM OVERVIEW

**What it does:** An IoT-backed classroom management platform for SMU Mediterranean Institute of Technology. It automates student attendance via camera-based face recognition, monitors classroom environment in real time (temperature, humidity, CO₂, sound), controls AC and lighting through MQTT-driven relays, surfaces a professor-facing React dashboard, syncs attendance to Moodle LMS, and identifies at-risk students and attendance trends using a locally-hosted LLM.

**Core subsystems and their responsibilities:**

| Subsystem | Responsibility |
|---|---|
| **IoT Layer** (ESP32) | Sense environment, publish MQTT, execute relay commands |
| **Edge Runtime** (RPi/Docker) | Run all backend services; no cloud dependency |
| **MQTT Broker** (Mosquitto) | Message bus between ESP32 and backend |
| **Backend** (FastAPI) | Orchestration, business logic, REST + WebSocket APIs |
| **Real-time Layer** | Fan-out of sensor/attendance/alert events to browser |
| **AI/Insights Layer** | Attendance analytics, LLM-powered at-risk summaries, forecasting |
| **Frontend** (React) | Professor dashboard; works offline in demo mode |
| **Data Layer** (PostgreSQL + Redis) | Persistent records + low-latency live state cache |
| **External** (Moodle, Ollama) | LMS sync + local LLM inference |

---

## 2. ARCHITECTURE STYLE

**Hybrid: modular monolith + event-driven messaging**

The backend is a single FastAPI process (not microservices), but internally it is event-driven via three decoupled channels:

```
ESP32 ──MQTT──▶ Mosquitto ──▶ Backend MQTT Bridge
                                     │
               ┌─────────────────────┼──────────────────┐
               ▼                     ▼                   ▼
           Redis cache          PostgreSQL         asyncio.Queue
           (live state)         (durable)         (WS fan-out)
                                                         │
                                                    WebSocket ──▶ Browser
```

**Key paradigms:**
- **Publish/Subscribe (MQTT, QoS 0):** sensor ingestion and relay actuation
- **Push-based real-time (WebSocket):** live sensor, attendance, and alert delivery to clients
- **Queue-based fan-out (asyncio.Queue):** decouples MQTT handler from WebSocket broadcaster; three separate queues for sensor, attendance, and alert event types
- **On-demand async pipelines (APScheduler + asyncio.create_task):** AI pipelines fire on page access; periodic jobs run on the shared APScheduler event loop

---

## 3. FULL COMPONENT BREAKDOWN

### 3a. IoT Layer — ESP32 Firmware

**File:** `firmware/classroom_node/classroom_node.ino`

**Responsibilities:** Physical sensor acquisition and relay actuation. The edge node with no internet dependency.

**Inputs:**
- DHT21 → temperature + humidity (every 5 s)
- MQ-135 (ADC) → air quality ppm (every 5 s)
- Digital sound sensor → presence detection (every 5 s)
- MQTT subscribe: `classroom/room1/relay/ac`, `classroom/room1/relay/lighting`

**Outputs:**
- MQTT publish: `classroom/{room_id}/sensors/temperature|humidity|air_quality|sound` → JSON `{value, unit, ts}`
- MQTT publish: `classroom/{room_id}/status` → `{online: true, ts}` heartbeat every 30 s
- GPIO: drives 4-channel opto-isolated relay (AC ch1, lighting ch2)
- I2C: LCD 16×2 displays live T/H/AQ/sound

**Auto-control on device:** If `acAutoMode=true`, the ESP32 itself applies temperature threshold logic to the relay — independently of the backend. This is a deliberate redundancy: the backend's alert engine also sends relay commands, but the device acts locally if the MQTT connection drops.

**Dependencies:** PubSubClient, DHT, LiquidCrystal_I2C, ArduinoJson, WiFi

**Communication:** WiFi 802.11 → Mosquitto broker via TCP/1883, MQTT QoS 0

---

### 3b. Edge Layer — Raspberry Pi 4B (or Docker host)

The RPi runs the entire stack: Mosquitto broker, FastAPI backend, PostgreSQL, Redis, Ollama, and nginx/React. In Docker deployment, these are containerized services on the same host.

**Camera subsystem** (`backend/app/services/recognition_loop.py`, `face_recognition_service.py`):
- Driven by `asyncio.Task`, runs at 2 fps when a session is active
- Real mode: OpenCV `VideoCapture(0)` → frame → DeepFace/Facenet 128-d cosine matching → attendance record
- Stub mode (`FACE_RECOGNITION_ENABLED=false`): synthetic event every 45 s from a random enrolled student
- 30-second per-student cooldown prevents duplicate records

**Mock sensor mode** (`backend/app/services/mock_sensor.py`):
- Activated by `MOCK_MODE=true`
- APScheduler jobs publish sine-wave sensor values over MQTT every 5 s, heartbeat every 30 s
- The broker receives these just as if an ESP32 sent them — the MQTT bridge is unaware of the source

---

### 3c. Backend Services — FastAPI Modules (Logical Groups)

**Group 1: Ingestion & Real-time** (`mqtt_bridge.py`, `event_queues.py`)
- Persistent `aiomqtt.Client` subscriber loop with exponential backoff reconnection
- On sensor message: (1) Redis SET with 5-min TTL, (2) fire-and-forget PostgreSQL write, (3) non-blocking put to `sensor_event_queue`
- On status message: Redis SET `classroom:{room_id}:online` with 60-s TTL (heartbeat tracking)
- Three `asyncio.Queue` instances (`sensor_event_queue`, `attendance_event_queue`, `alert_event_queue`) decouple production from consumption

**Group 2: Session & Attendance** (`api/sessions.py`, `api/attendance.py`, `services/recognition_loop.py`)
- Session lifecycle: `POST /api/sessions/start` → starts recognition loop → `POST /api/sessions/{id}/end` → stops loop, marks absent
- Manual adjustment: `PATCH /api/attendance/{record_id}`
- Moodle sync: triggered on session end; retry queue in Redis if Moodle is unreachable

**Group 3: Control** (`api/control.py`)
- `POST /api/control/ac|lighting` → simultaneously writes Redis (instant dashboard update) and publishes MQTT (device actuation)
- State is authoritative in Redis; PostgreSQL is not used for relay state

**Group 4: Alert Engine** (`services/alert_engine.py`)
- `AsyncIOScheduler` job runs every 30 s: reads Redis sensor cache → evaluates temp/AQ/device-online thresholds → upserts Alert rows → pushes to `alert_event_queue`
- Deduplication: skips alert creation if an unacknowledged alert of the same type already exists for the room
- Also handles Moodle retry every 10 min via a second scheduled job

**Group 5: Insights & Analytics** (`services/insights_engine.py`, `api/insights.py`)
- Pure SQL analytics served on-demand: attendance trend (weekly), heatmap by day/hour-slot, decay analysis, comfort score (from Redis), AC effectiveness, temp-vs-attendance scatter, air quality vs. sound correlation
- Role-filtered: professors see only their courses; admins see all

**Group 6: AI Pipelines** (`services/at_risk_engine.py`, `services/forecast_engine.py`)
- Described in detail in §3f

**Group 7: Auth** (`api/auth.py`, `api/deps.py`)
- JWT (HS256), bcrypt passwords, stored in `professors` table
- `REQUIRE_AUTH=false` in dev allows all requests without token

---

### 3d. Real-time Layer

**WebSocket endpoint:** `WS /ws/classroom/{room_id}`
- On connect: sends a "snapshot" message with current Redis state (sensors + relay + device_online)
- Keepalive: 30-s timeout → server sends ping; client echo → pong
- `ConnectionManager` maintains a `dict[room_id → set[WebSocket]]` for room-scoped broadcasting

**Fan-out mechanism** (`main.py:_drain_queue`):

Three background tasks (`asyncio.create_task`) each drain one event queue in an infinite loop, calling `connection_manager.broadcast(room_id, event)` for every item. This is the bridge between the MQTT/recognition/alert producers and the WebSocket consumers.

```
MQTT handler ──put_nowait──▶ sensor_event_queue
recognition_loop ───────────▶ attendance_event_queue    ──drain task──▶ WebSocket broadcast
alert_engine ───────────────▶ alert_event_queue
```

**Frontend WebSocket client** (`useLiveSensors.js`):
- Native WebSocket with exponential backoff reconnection (3 s → 30 s max)
- Demo mode watchdog: if no real data arrives within 8 s of connecting, activates a client-side mock generator and shows `DemoModeBanner`
- Message dispatcher: routes `snapshot|sensor|attendance|alert` type fields to their respective React state slices

---

### 3e. AI / Insights Layer

**At-Risk Pipeline** (`at_risk_engine.py`):

*Trigger:* `GET /api/at-risk` → `asyncio.create_task(run_at_risk_pipeline())`. Redis lock `at_risk:pipeline:lock` (TTL 600 s, NX) prevents concurrent runs.

*Steps:*
1. `InsightsEngine.get_at_risk_students` → find students below 70% threshold
2. Freshness gate: skip students with `generated_at` < 600 s old + `ollama_reachable=true`
3. Cleanup: `DELETE FROM at_risk_explanations WHERE student_id NOT IN (at_risk_ids)`
4. Single shared `httpx.AsyncClient` for all Ollama calls
5. Pre-flight: `GET /api/tags` validates model presence before iterating students
6. Per student: batch JOIN queries (missed-session sensor avgs, peer rates) → build profile → single Ollama call → upsert `at_risk_explanations`

*Prompt design:* compact multi-course block (<500 tokens) → phi3-mini returns 3-4 sentence cross-course prose. Constraints: no health/personal/family references, plain prose, <100 words.

**Forecasting Pipeline** (`forecast_engine.py`):

*Trigger:* `GET /api/forecasting` → background task. Redis lock `forecast:pipeline:lock` (TTL 1800 s).

*Steps:*
1. One JOIN query: all courses + their ended-session count
2. Skip fresh rows (< 1800 s old + Ollama reachable)
3. Courses with < 3 sessions → write empty marker row (ensures frontend poll terminates)
4. Per course: `_get_course_trend()` → last N sessions' attendance rate as fractions
5. `_classify_trend()`: deterministic delta math (no LLM) → `steady_decline|accelerating_decline|stable|recovering` + confidence
6. Ollama call: 2-line structured response → `EXPECTED_NEXT: <int>` + `INTERPRETATION: <sentence>`
7. `_parse_llm_response()`: never raises; returns `(None, None)` on parse failure

Classification is always deterministic — the LLM only produces prose and projected rate. This prevents hallucinated labels breaking the frontend's color-coding logic.

**Shared Ollama utilities:** `call_ollama()` and `_check_ollama_ready()` are defined once in `at_risk_engine.py` and imported directly by `forecast_engine.py`.

---

### 3f. Frontend Layer

**Architecture pattern:** Single-page application, React 18 + Vite, client-side routing via React Router v6.

**Context providers (global state):**
- `AuthContext`: JWT token + professor profile; token stored in `localStorage`; exposes `isAuthenticated`, `professor`, `login`, `logout`
- `SensorContext`: wraps `useLiveSensors` hook; distributes `sensors`, `attendance`, `alerts`, `relayStatus`, `isConnected`, `isDemoMode` to entire app

**Route structure** (nested under authenticated `<Layout>`):

```
/login          → Login (public route)
/dashboard      → Dashboard (live sparklines, session control)
/attendance     → Attendance (session/student table with manual adjustment)
/control        → Control (relay toggles + live sensor cards)
/enrollment     → Enrollment (student registration + face upload)
/history        → History (past sessions + sensor summaries)
/insights       → Insights (charts: trend, heatmap, decay, scatter)
/at-risk        → AtRisk (LLM-explained student cards)
/forecasting    → Forecasting (Recharts trend chart + LLM interpretation)
```

**Styling system:**
- `tokens.css` is the single source of truth for all design tokens (colors, spacing, radius, typography)
- `index.css` contains all component classes that reference token vars only
- TailwindCSS v3 utility classes can coexist but cannot resolve CSS custom properties at build time — hence this split

**Charts:** Recharts `AreaChart` with `linearGradient` fill; 70% dashed `ReferenceLine` on forecasting chart; optional "Next" projected data point appended to trend series.

**Auto-polling pattern (at-risk and forecasting pages):**
Frontend polls every 8 s while `some(course => !course.generated_at)`. Stops when all rows have been populated by the background pipeline.

---

### 3g. Data Layer

**PostgreSQL 15 — persistent, durable state**

```
professors ──────────────────────────────────────────────────────────────────
  id (UUID PK), name, email (UNIQUE), hashed_password, role ENUM, created_at

students ──── face_encodings ──── at_risk_explanations
  id, name, student_id (UNIQUE)   student_id (FK, UNIQUE)   ← 1:1
                                  overall_attendance_rate, summary_explanation
                                  per_course_data (JSONB), generated_at, ollama_reachable

course_students (M:M join table)
  course_id FK, student_id FK — composite PK

courses ──── attendance_forecasts
  id, code (UNIQUE), name         course_id (FK, UNIQUE)    ← 1:1
  professor_id (FK nullable)      trend_data (JSONB), expected_next_rate
                                  trend_classification (VARCHAR — not ENUM)
                                  confidence_level, interpretation, suggested_action

sessions ──── attendance_records
  id, course_id FK, room_id       id, session_id FK, student_id FK
  started_at, ended_at            status ENUM, detected_at
  status ENUM                     adjusted_by, moodle_synced BOOL

sensor_readings                  alerts
  id, room_id, sensor_type ENUM   id, room_id, type ENUM
  value, unit, recorded_at        value, message, acknowledged BOOL
```

**Key design decisions:**
- `display_status` for sessions is computed at query time (not stored) because liveness changes over time
- `per_course_data` is JSONB — always read/written as a unit with the parent row
- `trend_classification` uses `VARCHAR(30)` not PG ENUM — avoids non-transactional `ALTER TYPE ADD VALUE` DDL
- `face_encodings.encoding` is `BYTEA` — serialized 128-d float32 numpy array

**Redis 7 — ephemeral, sub-millisecond live state**

| Key pattern | Value | TTL |
|---|---|---|
| `classroom:{room_id}:sensors:{type}` | JSON `{value, unit}` | 300 s |
| `classroom:{room_id}:online` | `"1"` | 60 s (renewed by heartbeat) |
| `classroom:{room_id}:relay:{device}` | `"on"/"off"/"auto"` | None (persistent) |
| `at_risk:pipeline:lock` | `"1"` | 600 s (SET NX EX) |
| `forecast:pipeline:lock` | `"1"` | 1800 s (SET NX EX) |
| Moodle retry queue | list of session_ids | None |

The device-online key is a TTL-based presence indicator: if the ESP32 stops sending heartbeats, the key expires and `is_device_online()` returns False — triggering a `device_offline` alert.

---

### 3h. External Integrations

**Moodle 4.x (optional profile)**
- `moodle_client.py` uses `httpx.AsyncClient` to call the Moodle REST API (token-authenticated)
- Called on session end to sync attendance records
- Failures enqueue session_id into Redis retry list; `alert_engine.retry_moodle_sync()` retries up to 10 items every 10 min
- `GET /api/moodle-test` health probe

**Ollama (phi3:mini, local)**
- HTTP REST API at `http://ollama:11434`
- On backend startup: `ensure_model_pulled()` checks `/api/tags`; if model absent, fires `/api/pull` as background task (non-blocking, ~2 GB pull)
- Used by both AI pipelines; shared utilities prevent code duplication
- `stream=false`, `temperature=0.3`, `num_predict=180` — deterministic, concise output
- Both pipelines write `ollama_reachable=False` to DB when Ollama is unavailable — frontend shows amber warning card instead of crashing

---

## 4. DATA FLOW DIAGRAMS

### Flow A: Sensor Ingestion

```
ESP32 (every 5s)
  │ publishFloat("classroom/room1/sensors/temperature", {value:24.5, unit:"C", ts:...})
  ▼
Mosquitto broker (TCP 1883)
  │
  ▼ (subscribed wildcard: classroom/+/sensors/#)
Backend MQTT bridge (_handle_sensor)
  ├─▶ Redis SET classroom:room1:sensors:temperature = {value:24.5, unit:"C"}  TTL=300s
  ├─▶ asyncio.create_task(_persist_sensor) ──▶ PostgreSQL INSERT sensor_readings
  └─▶ sensor_event_queue.put_nowait({type:"sensor", room_id, sensor_type, value, unit})
           │
           ▼ (drain task)
    connection_manager.broadcast("room1", event)
           │
           ▼ (WebSocket)
    React useLiveSensors → setSensors({temperature: {value:24.5, unit:"C"}})
    → Dashboard sparklines update
```

### Flow B: Attendance Detection

```
Camera frame (2fps) ──▶ face_recognition_service.recognize_faces(frame)
                           │ (cosine distance < 0.6)
                           ▼
                       match: student_id="abc-123", confidence=0.82
                           │
                           ├── cooldown check: now - last_marked["abc-123"] > 30s
                           │
                           ├─▶ asyncio.create_task(_record_attendance(session_id, "abc-123"))
                           │       └─▶ INSERT attendance_records(status=present)
                           │
                           └─▶ attendance_event_queue.put_nowait({type:"attendance", ...})
                                       │
                                       ▼ (drain task → WebSocket)
                               React → setAttendance([{student_name:"Alice", ...}, ...])
                               → Attendance page live table update
```

### Flow C: Alert Generation

```
AlertEngine._scheduler (every 30s)
  │
  ▼ check_thresholds()
  ├─▶ get_sensor_latest("room1") ──▶ Redis MGET [temperature, humidity, air_quality, sound]
  │       temp = 31.2°C, ac_mode = "auto"
  │       → temp > 28°C → auto_relay("room1", "ac", "on")
  │           ├─▶ Redis SET classroom:room1:relay:ac = "on"
  │           └─▶ MQTT publish classroom/room1/relay/ac = {"action":"on"}
  │                   └─▶ ESP32 receives → digitalWrite(RELAY_AC_PIN, HIGH)
  │       → alert_exists check → INSERT alerts(type=temp_high, value=31.2)
  │       → alert_event_queue.put_nowait({type:"alert", ...})
  │               └─▶ WebSocket broadcast → React setAlerts([...])
  │
  └─▶ is_device_online("room1") → Redis EXISTS = 0 (TTL expired)
          → INSERT alerts(type=device_offline)
```

### Flow D: At-Risk Summary Generation

```
Professor navigates to /at-risk
  │
  ▼ GET /api/at-risk
  Backend:
    1. Redis SETNX at_risk:pipeline:lock (TTL 600s)
       → if lock acquired: asyncio.create_task(run_at_risk_pipeline())
       → else: serve cached rows from at_risk_explanations
    2. Query + return existing at_risk_explanations

  Background pipeline (run_at_risk_pipeline):
    1. InsightsEngine.get_at_risk_students() → students below 70%
    2. Skip fresh (generated_at < 600s old + ollama_reachable)
    3. DELETE stale explanations (students recovered above threshold)
    4. httpx.AsyncClient (single shared connection)
       → GET /api/tags → validate phi3:mini present
    5. For each at-risk student:
       a. build_student_profile() → 3 batch SQL queries
          (attendance+session+course JOIN, sensor avg JOIN, peer rate GROUP BY)
       b. build_combined_prompt() → < 500 token prompt
       c. POST /api/chat → phi3:mini → 3-4 sentence summary
       d. UPSERT at_risk_explanations
    6. Pipeline done

  Frontend auto-poll every 8s:
    → GET /api/at-risk
    → if any student has summary_explanation=null → continue polling
    → else → stop polling, render explanations
```

### Flow E: Attendance Forecasting

```
Professor navigates to /forecasting
  │
  ▼ GET /api/forecasting
  Backend:
    1. Redis SETNX forecast:pipeline:lock (TTL 1800s) → background pipeline
    2. Return existing attendance_forecasts rows (may be empty on first load)

  Background pipeline (run_forecast_pipeline):
    1. One JOIN query: all courses + ended session count
    2. For each course:
       a. session_count < 3 → upsert marker row (trend_data=[], generated_at=now)
       b. _get_course_trend() → GROUP BY session → rate fractions
       c. _classify_trend(rates) → deterministic delta math → classification + confidence
       d. build_forecast_prompt() → 2-line structured prompt
       e. call_ollama() → parse EXPECTED_NEXT + INTERPRETATION
       f. _upsert_forecast() → attendance_forecasts

  Frontend:
    → Poll every 8s while any course.generated_at == null
    → On full population: render Recharts AreaChart + classification badge
```

---

## 5. EVENT SYSTEM DESIGN

### MQTT Topic Architecture

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

Subscription patterns:
- Backend subscribes: `classroom/+/sensors/#` (wildcard room + all sensor subtopics)
- Backend subscribes: `classroom/+/status`
- ESP32 subscribes: exact topics for `relay/ac` and `relay/lighting`

QoS: 0 (fire-and-forget). No message persistence across broker restarts.

Publish pattern for relay commands: a short-lived `aiomqtt.Client` context manager (`publish_mqtt()`) is used for each outbound message rather than the persistent subscriber client — prevents concurrent use of the same connection.

### WebSocket Event Channels

Single endpoint per room: `WS /ws/classroom/{room_id}`

**Message types (server → client):**

| type | Trigger | Payload |
|---|---|---|
| `snapshot` | On connect | sensors + relay + device_online |
| `sensor` | MQTT ingestion | room_id, sensor_type, value, unit |
| `attendance` | Recognition match | session_id, student_id, student_name, confidence, status |
| `alert` | Threshold breach | alert_type, room_id, message, value |
| `ping` | 30s server keepalive | — |

Client → server: only `"ping"` text (echoed as `{type:"pong"}`).

### Redis Usage Patterns

| Pattern | Key | Write | Read |
|---|---|---|---|
| Sensor cache | `classroom:{room}:sensors:{type}` | MQTT handler (SET, TTL 300s) | WebSocket snapshot, control status, alert engine, insights comfort score |
| Device presence | `classroom:{room}:online` | MQTT status handler (SET, TTL 60s) | Alert engine, control status |
| Relay state | `classroom:{room}:relay:{device}` | Control API + alert engine auto-control | WebSocket snapshot, control status |
| Pipeline locks | `at_risk:pipeline:lock`, `forecast:pipeline:lock` | Pipeline entry (SET NX EX) | Pipeline entry check |
| Moodle retry | Redis list | Moodle client on failure | Alert engine retry job |

### Async Job Scheduling

APScheduler `AsyncIOScheduler` (runs on uvicorn event loop):

| Job | Interval | Purpose |
|---|---|---|
| `check_thresholds` | 30 s | Reads Redis, evaluates sensor thresholds, publishes MQTT relay commands |
| `retry_moodle_sync` | 10 min | Pops up to 10 session IDs from Redis retry list, re-calls Moodle |
| `mock_sensor_publish` | 5 s | (`MOCK_MODE=true`) Publishes synthetic sensor MQTT messages |
| `mock_heartbeat_publish` | 30 s | (`MOCK_MODE=true`) Publishes heartbeat status message |

All jobs share the single `alert_engine._scheduler` instance. The mock publisher borrows this scheduler handle explicitly.

---

## 6. STATE MANAGEMENT

### What lives where

| State | Location | Durability | Rationale |
|---|---|---|---|
| Live sensor readings | Redis (TTL 300s) | Ephemeral | Sub-millisecond read; WebSocket snapshot; no PostgreSQL hit on page load |
| Device online flag | Redis (TTL 60s) | Ephemeral (TTL-based) | Heartbeat-renewed presence; expiry = offline |
| Relay states (ac, lighting) | Redis (no TTL) | Persistent across restarts | Commands may outlast sessions |
| Historical sensor readings | PostgreSQL `sensor_readings` | Durable | Analytics, history page, LLM pipeline |
| Sessions / Attendance / Students / Courses | PostgreSQL | Durable | Source of truth |
| Face encodings | PostgreSQL `face_encodings` (BYTEA) | Durable | Large binary; queried rarely |
| At-risk explanations | PostgreSQL `at_risk_explanations` | Durable (upserted) | Survives pipeline restarts |
| Attendance forecasts | PostgreSQL `attendance_forecasts` | Durable (upserted) | 30-min freshness window |
| Pipeline locks | Redis (SET NX EX) | Ephemeral (TTL-bounded) | Prevents concurrent pipeline runs |
| JWT tokens | Browser `localStorage` | Session-persisted | Acceptable on university intranet |
| Live sensor state (frontend) | React state (`useLiveSensors`) | In-memory | Re-populated from WebSocket snapshot on reconnect |
| Attendance event log (frontend) | React state | In-memory | Append-only list from WebSocket; not persisted in browser |
| Recognition cooldowns | In-memory `dict[student_id → timestamp]` | Ephemeral (per task) | Only meaningful for the duration of one active session |

### Ephemeral vs. persistent boundary

The Redis-to-PostgreSQL boundary is the key design line:

- **Ephemeral (Redis):** anything that changes faster than it can be queried (sensor every 5 s), anything with a natural TTL (heartbeat), anything that only matters right now (relay state for the current session)
- **Persistent (PostgreSQL):** anything that needs to survive restarts, is queried across time ranges, or feeds analytics/AI pipelines

---

## 7. DEPLOYMENT ARCHITECTURE

### Docker Compose Service Graph

```
                     ┌────────────┐
                     │  postgres  │ postgres:15-alpine
                     │  :5432     │ vol: postgres_data
                     └─────▲──────┘
                           │ depends_on (healthy)
┌─────────┐          ┌─────┴──────┐          ┌──────────┐
│  redis  │◄─────────│  backend   │──────────▶│  ollama  │
│  :6379  │          │  :8000     │ depends_on│ :11434   │
│ vol:    │          │ custom img │ (started) │ vol:     │
│ redis_  │          └─────┬──────┘           │ ollama_  │
│ data    │                │ depends_on        │ data     │
└─────────┘                │ (started)        └──────────┘
                     ┌─────▼──────┐
                     │ mosquitto  │ eclipse-mosquitto:2
                     │  :1883     │ vol: mosquitto_data
                     └────────────┘

┌────────────┐
│  frontend  │◄── depends_on backend (started)
│  :3000→80  │
│ nginx img  │
└────────────┘

Optional --profile moodle:
  mariadb:10.6 → moodle:bitnami/moodle:4 (:8080)
  backend MOODLE_URL points to moodle container
```

### Service Dependencies (startup order)

```
postgres (healthy) ──┐
redis (healthy) ──────┼──▶ backend (started) ──▶ frontend (started)
mosquitto (started) ──┘
ollama (started) ─────┘
```

### Runtime Topology (Raspberry Pi production)

```
┌─────────────────────────── Raspberry Pi 4B ──────────────────────────────┐
│                                                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │PostgreSQL│  │  Redis   │  │Mosquitto │  │ FastAPI  │  │  Ollama  │  │
│  │  :5432   │  │  :6379   │  │  :1883   │  │  :8000   │  │ :11434   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────┬─────┘  └──────────┘  │
│                                                  │                        │
│  ┌──────────┐  ┌──────────┐                     │                        │
│  │  nginx   │  │ Camera   │◄────────────────────┘ recognition_loop       │
│  │  :3000   │  │ Module   │                                               │
│  └──────────┘  └──────────┘                                               │
│                                                                            │
└─────────────────────── WiFi ───────────────────────────────────────────── ┘
                            │
                     ┌──────▼──────┐
                     │   ESP32     │  (classroom hardware)
                     │  MQTT :1883 │  DHT21, MQ-135, Sound
                     │  Relay ch1  │  → AC
                     │  Relay ch2  │  → Lighting
                     │  LCD 16×2   │
                     └─────────────┘

Professor browser (laptop/tablet on LAN):
  HTTP  → http://rpi-ip:3000        (nginx → React static files)
  WS    → ws://rpi-ip:3000/ws/...   (nginx proxy → FastAPI :8000)
  HTTP  → http://rpi-ip:3000/api/.. (nginx proxy → FastAPI :8000)
```

**nginx reverse proxy** (`frontend/nginx.conf`): all `/api/*` and `/ws/*` requests are proxied from port 3000 to the backend at port 8000. The React app is served as static files.

### Migration Strategy

Alembic runs automatically at backend startup via `_run_migrations()` in the lifespan context — a subprocess call to the `alembic` CLI (`upgrade head`) before any API routes are registered, ensuring schema is always current without a separate migration step.

### Quick-start Commands

```bash
# Full stack
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
| http://localhost:1883 | Mosquitto MQTT |
| http://localhost:11434 | Ollama LLM API |
| http://localhost:8080 | Moodle (optional profile) |
