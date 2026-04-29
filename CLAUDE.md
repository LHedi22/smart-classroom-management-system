# CLAUDE.md — Smart Classroom Management System
# SMU – Mediterranean Institute of Technology
# Team: Ben Jemaa · Jallouli · Saadaoui · Ouertani · Day

> **This file is the single source of truth for this project.**
> Read it at the start of every session. Update it whenever architecture, decisions, or progress change.
> Never contradict what is written here without explicitly noting the change and the reason.

---

## Project Summary

An IoT-based Smart Classroom Management System for SMU that:
- Automates student attendance tracking using face recognition (Raspberry Pi Camera + DeepFace/Facenet — RPi only; Docker uses a lightweight stub)
- Monitors classroom environment in real time (temperature, humidity, air quality, sound)
- Controls AC and lighting via relay module (automatic thresholds + manual override)
- Streams all data to a professor-facing React dashboard over WebSocket
- Syncs attendance to a local Docker Moodle instance via its REST API

---

## Repository Structure
smart-classroom/
├── CLAUDE.md                        ← this file
├── README.md
├── docker-compose.yml               ← all services: postgres, redis, mosquitto, backend, frontend, moodle (profile)
├── .env.example
│
├── mosquitto/
│   └── mosquitto.conf               ← Mosquitto broker config (anonymous, port 1883)
│
├── firmware/                        ← ESP32 Arduino sketch
│   └── classroom_node/
│       ├── classroom_node.ino
│       └── config.h
│
├── backend/                         ← Python FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── redis_client.py
│   │   ├── api/
│   │   │   ├── sensors.py
│   │   │   ├── attendance.py
│   │   │   ├── control.py
│   │   │   ├── sessions.py
│   │   │   ├── alerts.py
│   │   │   ├── enrollment.py
│   │   │   └── websocket.py
│   │   ├── services/
│   │   │   ├── mqtt_bridge.py
│   │   │   ├── face_recognition_service.py  ← stub when FACE_RECOGNITION_ENABLED=false; real DeepFace on RPi
│   │   │   ├── recognition_loop.py          ← real camera loop OR stub emitter (45 s synthetic events)
│   │   │   ├── alert_engine.py
│   │   │   ├── mock_sensor.py       ← Phase 11: mock publisher (active when MOCK_MODE=true)
│   │   │   └── moodle_client.py
│   │   └── models/
│   │       ├── db_models.py         ← SQLAlchemy ORM
│   │       └── schemas.py           ← Pydantic schemas
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── .dockerignore
│   └── Dockerfile
│
├── frontend/                        ← React + Vite + Tailwind
│   ├── src/
│   │   ├── tokens.css               ← NEW Phase 18: CSS custom property design token system (single source of truth)
│   │   ├── index.css                ← MODIFIED Phase 18: all component classes; no glassmorphism; references tokens.css vars only
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        ← MODIFIED Phase 18: AreaChart sparklines, icon circles, token-based stat cards
│   │   │   ├── Attendance.jsx       ← MODIFIED Phase 18: StatPills, illustrated empty state, skeleton loader
│   │   │   ├── Control.jsx          ← MODIFIED Phase 18: tactile relay buttons, sensor pills, auto-rule card
│   │   │   ├── Enrollment.jsx       ← MODIFIED Phase 18: purple avatar list, camera preview, thumbnail grid
│   │   │   ├── History.jsx          ← MODIFIED Phase 18: attendance breakdown bar, course filter, chevron expand
│   │   │   └── Login.jsx            ← MODIFIED Phase 18: branded left panel, click-to-fill demo accounts
│   │   ├── components/
│   │   │   ├── Layout.jsx           ← MODIFIED Phase 18: 240px blue sidebar, inline SVG nav icons, white active border
│   │   │   └── DemoModeBanner.jsx   ← MODIFIED Phase 18/11: token-based warning banner
│   │   ├── hooks/
│   │   │   └── useLiveSensors.js    ← MODIFIED Phase 11: falls back to mock generator after 5s disconnect
│   │   └── api/
│   │       └── client.js
│   ├── package.json
│   ├── vite.config.js
│   ├── nginx.conf
│   ├── .dockerignore
│   └── Dockerfile
│
└── docs/
├── mqtt_schema.md
├── api_contracts.md
├── wiring_diagram.md
└── rpi_setup.md                 ← NEW Phase 12: step-by-step Raspberry Pi setup runbook

---

## Hardware

| Component | Model | Role |
|---|---|---|
| Single-board computer | Raspberry Pi 4 Model B 4GB | Central hub, runs all backend services |
| Camera | Raspberry Pi Camera Module v2 8MP | Face recognition input |
| Microcontroller | ESP32 Dev Board (ESP-WROOM-32) | Sensor node + relay controller |
| Temp/Humidity | DHT21 (AM2301) | Environmental monitoring |
| Air quality | MQ-135 | CO2/VOC proxy reading |
| Sound | ACP014 | Occupancy proxy, noise level |
| Relay | 4-Channel Opto-Isolated | AC control (ch1), Lighting (ch2), spare (ch3, ch4) |
| Display | LCD 16x2 I2C | Local room status display |
| Voltage converter | Logic Level Converter 3.3V↔5V | ESP32 ↔ Relay safe communication |
| Power | USB-C 5V 3A | Raspberry Pi power supply |

**Communication between ESP32 and Raspberry Pi:** WiFi + MQTT (Mosquitto broker on RPi)

---

## Tech Stack

### Firmware (ESP32)
- Arduino IDE
- Libraries: `PubSubClient` (MQTT), `DHT` (sensor), `LiquidCrystal_I2C` (LCD), `WiFi.h`
- Language: C++ (Arduino)

### Backend (Raspberry Pi)
- **Runtime:** Python 3.11
- **Framework:** FastAPI (async) + Uvicorn
- **ORM:** SQLAlchemy 2.0 (async) + Alembic migrations
- **Database:** PostgreSQL 15
- **Cache:** Redis 7
- **MQTT:** aiomqtt 2.x (bridge between Mosquitto and FastAPI)
- **Face recognition:** DeepFace (Facenet model) + opencv-python-headless — installed natively on RPi only; Docker image runs a stub (`FACE_RECOGNITION_ENABLED=false`)
- **Scheduler:** APScheduler (alert engine, periodic jobs + mock sensor when MOCK_MODE=true)
- **Moodle integration:** httpx (async HTTP client)

### Frontend
- **Framework:** React 18 + Vite
- **Styling:** TailwindCSS v3 + CSS custom properties design token system (`tokens.css`)
- **Typography:** DM Sans (headings, 600/700) + Inter (body, 400/500) via Google Fonts
- **Charts:** Recharts (`AreaChart` + `linearGradient` fill for sparklines)
- **Real-time:** Native WebSocket via custom hook
- **HTTP client:** axios
- **Design system:** `tokens.css` — single source of truth for all colors, shadows, and type scale; all component classes in `index.css` reference CSS vars only; no hardcoded hex values outside `tokens.css`

### Infrastructure
- **MQTT Broker:** Mosquitto 2 (Docker — `eclipse-mosquitto:2`, anonymous, port 1883)
- **Database:** PostgreSQL 15 (Docker)
- **Cache:** Redis 7 (Docker)
- **Frontend server:** nginx (Docker — serves compiled Vite bundle, proxies `/api` and `/ws` to backend)
- **LMS:** Moodle 4.x (Docker — optional, start with `--profile moodle`)
- **Container orchestration:** Docker Compose

### Docker Quick Start
```bash
# Start everything (dashboard available at http://localhost:3000)
docker compose up -d

# Start with mock sensor data (no ESP32 needed)
MOCK_MODE=true docker compose up -d

# With Moodle LMS (adds ~5 min init time)
docker compose --profile moodle up -d

# Rebuild after code changes
docker compose build && docker compose up -d

# Seed demo data (35 students, 6 courses, 30 sessions, 5 professor accounts)
docker compose exec backend python seed.py
```

| URL | Service |
|---|---|
| http://localhost:3000 | React dashboard (main entry point) |
| http://localhost:8000/docs | FastAPI Swagger UI |
| http://localhost:8000/health | Backend health check |
| http://localhost:1883 | Mosquitto MQTT (for ESP32) |
| http://localhost:8080 | Moodle LMS (if `--profile moodle`) |

---

## MQTT Topic Schema

All topics follow the pattern: `classroom/{room_id}/...`
Default room_id for this project: `room1`

| Topic | Direction | Payload | Description |
|---|---|---|---|
| `classroom/room1/sensors/temperature` | ESP32 → RPi | `{"value": 24.5, "unit": "C", "ts": 1234567890}` | Published every 5s |
| `classroom/room1/sensors/humidity` | ESP32 → RPi | `{"value": 62.1, "unit": "%", "ts": ...}` | Published every 5s |
| `classroom/room1/sensors/air_quality` | ESP32 → RPi | `{"value": 320, "unit": "ppm", "ts": ...}` | MQ135 raw ADC value |
| `classroom/room1/sensors/sound` | ESP32 → RPi | `{"value": 1, "unit": "bool", "ts": ...}` | 1=sound detected, 0=quiet |
| `classroom/room1/relay/ac` | RPi → ESP32 | `{"action": "on"}` | on / off / auto |
| `classroom/room1/relay/lighting` | RPi → ESP32 | `{"action": "off"}` | on / off / auto |
| `classroom/room1/status` | ESP32 → RPi | `{"online": true, "ts": ...}` | Heartbeat every 30s |
| `classroom/room1/alerts` | RPi → ESP32 | `{"type": "temp_high", "value": 36}` | Push alerts to LCD |

---

## Database Schema

### Tables

**professors**
- id (UUID PK)
- name (VARCHAR)
- email (VARCHAR UNIQUE)
- hashed_password (VARCHAR) — bcrypt
- role (ENUM: professor, admin)
- created_at (TIMESTAMP)

**students**
- id (UUID PK)
- name (VARCHAR)
- student_id (VARCHAR UNIQUE) — institutional ID
- created_at (TIMESTAMP)

**courses**
- id (UUID PK)
- code (VARCHAR UNIQUE) — e.g. "CS301"
- professor_id (UUID FK → professors.id, nullable, ON DELETE SET NULL) — added Phase 14
- name (VARCHAR)
- professor_name (VARCHAR)

**sessions**
- id (UUID PK)
- course_id (FK → courses)
- room_id (VARCHAR) — e.g. "room1"
- started_at (TIMESTAMP)
- ended_at (TIMESTAMP NULLABLE)
- status (ENUM: active, ended, upcoming) — `upcoming` added Phase 16 for pre-scheduled sessions
- display_status (computed, NOT stored): `live` = active AND started_at ≤ now | `upcoming` = status==upcoming | `done` = ended

**attendance_records**
- id (UUID PK)
- session_id (FK → sessions)
- student_id (FK → students)
- status (ENUM: present, absent, late, excused)
- detected_at (TIMESTAMP) — when face was first recognized
- adjusted_by (VARCHAR NULLABLE) — "professor" if manually changed
- adjusted_at (TIMESTAMP NULLABLE)
- moodle_synced (BOOLEAN DEFAULT false)

**face_encodings**
- id (UUID PK)
- student_id (FK → students)
- encoding (BYTEA) — serialized numpy array (128-d vector, float32)
- created_at (TIMESTAMP)

**sensor_readings**
- id (UUID PK)
- room_id (VARCHAR)
- sensor_type (ENUM: temperature, humidity, air_quality, sound)
- value (FLOAT)
- unit (VARCHAR)
- recorded_at (TIMESTAMP)

**alerts**
- id (UUID PK)
- room_id (VARCHAR)
- type (ENUM: temp_high, temp_low, air_quality_high, attendance_anomaly, device_offline)
- value (FLOAT NULLABLE)
- message (TEXT)
- acknowledged (BOOLEAN DEFAULT false)
- created_at (TIMESTAMP)

---

## API Endpoints

### Sensors
- `GET /api/sensors/latest` — latest reading from Redis cache
- `GET /api/sensors/history` — query params: `room_id`, `type`, `from`, `to`
- `GET /api/sessions/{id}/sensors/latest` — most recent reading per sensor type within the session's time window (polling fallback for live sessions)
- `GET /api/sessions/{id}/sensors/summary` — avg/min/max per sensor type for a done session (HTTP 400 if session not ended)

### Sessions
- `POST /api/sessions/start` — body: `{course_id, room_id}`
- `POST /api/sessions/{id}/end`
- `GET /api/sessions` — list with filters
- `GET /api/sessions/{id}`

### Control
- `POST /api/control/ac` — body: `{room_id, action: "on"|"off"|"auto"}` — publishes MQTT + updates Redis
- `POST /api/control/lighting` — same pattern for lighting relay
- `GET /api/control/status/{room_id}` — relay states + live sensor values + device_online

### Alerts
- `GET /api/alerts` — query params: `room_id`, `acknowledged`, `limit=50`
- `PATCH /api/alerts/{id}/acknowledge` — marks acknowledged=true
- `GET /api/alerts/unread-count/{room_id}` — dashboard badge count

### Courses
- `GET /api/courses` — list all courses
- `POST /api/courses` — create course
- `GET /api/courses/{id}` — get course detail
- `POST /api/courses/{id}/enroll` — body: `{student_ids: [...]}`

### Attendance
- `GET /api/sessions/{id}/attendance` — list with student name + number
- `PATCH /api/attendance/{record_id}` — manual adjustment (sets adjusted_by="professor")
- `POST /api/sessions/{id}/mark-absent` — bulk-insert absent records for un-marked enrolled students
- `GET /api/students/{id}/attendance-history` — cross-session attendance history

### Control
- `POST /api/control/ac` — body: `{room_id, action: "on"|"off"|"auto"}`
- `POST /api/control/lighting` — body: `{room_id, action: "on"|"off"|"auto"}`
- `GET /api/control/status/{room_id}`

### Enrollment
- `GET /api/students`
- `POST /api/students` — create student
- `POST /api/students/{id}/enroll-face` — upload face image, compute encoding
- `GET /api/students/{id}/courses`

### Alerts
- `GET /api/alerts` — query params: `room_id`, `acknowledged`
- `PATCH /api/alerts/{id}/acknowledge`

### WebSocket
- `WS /ws/classroom/{room_id}` — streams: sensor updates, attendance events, alerts

---

## Environment Variables (.env)

```env
# ── Database ──────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://smartcam:smartcam@postgres:5432/smartclassroom

# ── Redis ─────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379

# ── MQTT ──────────────────────────────────────────────────────────────────
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883

# ── Moodle ────────────────────────────────────────────────────────────────
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=your_moodle_token_here

# ── Application ───────────────────────────────────────────────────────────
SECRET_KEY=changeme-use-a-long-random-string-in-production
ROOM_ID=room1

# Set to true to publish fake sensor data without ESP32 hardware
MOCK_MODE=false

# Set to true only on Raspberry Pi with DeepFace installed natively (see docs/rpi_setup.md §8)
FACE_RECOGNITION_ENABLED=false

# ── Auth ──────────────────────────────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=480
# Set to true in production to require a valid JWT on all requests
REQUIRE_AUTH=false

# ── Auto-control thresholds ───────────────────────────────────────────────
TEMP_AC_ON_THRESHOLD=28
TEMP_AC_OFF_THRESHOLD=22
AIR_QUALITY_ALERT_THRESHOLD=500
FACE_RECOGNITION_THRESHOLD=0.6
RECOGNITION_FPS=2
```

---

## Auto-Control Rules

| Sensor | Condition | Action |
|---|---|---|
| Temperature | > 28°C AND AC is in auto mode | Turn AC ON |
| Temperature | < 22°C AND AC is in auto mode | Turn AC OFF |
| Air quality | > 500 ppm | Send alert (no relay action — no ventilation relay wired) |
| Sound | Silent for > 30 min during active session | Send attendance anomaly alert |
| Occupancy | headcount > recognized_faces + 2 | Flag discrepancy for professor |

---

## Face Recognition Logic

> Applies only when `FACE_RECOGNITION_ENABLED=true` (Raspberry Pi with DeepFace installed natively).
> In Docker (default), the stub is active — see Stub Mode below.

1. **Enrollment:** Upload up to 5 images → `face_recognition_service.enroll_student_face()` computes a 128-d Facenet encoding per image → averages them → stores as BYTEA in `face_encodings`
2. **Recognition loop:** Run at 2fps (RPi CPU constraint) → detect all faces → compare each to all stored encodings using cosine distance → match if distance < 0.6 → return `student_id` or `UNKNOWN`
3. **Attendance recording:** First match in a session → create `attendance_record` with status=`present` → 30s cooldown to prevent duplicate entries
4. **UNKNOWN faces:** Increment occupancy counter but do not create attendance record → flag if count is high

### Stub Mode (`FACE_RECOGNITION_ENABLED=false`)

- **Enrollment:** Stores a zeroed 128-d float32 placeholder vector — DB row is created, student can participate in mock events
- **Recognition loop:** `_stub_recognition_loop` async task emits one synthetic attendance event every 45 seconds for a randomly chosen enrolled student in the active session; event shape is identical to real recognition so WebSocket and frontend need no changes
- **`reload_encodings()`:** No-op — returns immediately without querying the DB

---

## Mock Sensor Logic (MOCK_MODE=true)

When `MOCK_MODE=true` in the environment, `mock_sensor.py` is registered as an APScheduler job at startup and publishes synthetic MQTT messages every 5 seconds to the same topics the ESP32 would use. Values drift realistically over time:

- Temperature: oscillates between 22–32°C using a sine wave with small random noise
- Humidity: oscillates between 45–70%
- Air quality: drifts between 200–550 ppm, occasionally spiking above the 500 alert threshold
- Sound: toggles randomly (weighted 70% detected, 30% quiet to simulate an active classroom)
- Heartbeat (`classroom/room1/status`): published every 30s with `online: true`

The frontend independently detects whether live WebSocket data is arriving. If no sensor message is received within 8 seconds of connecting, `useLiveSensors.js` activates a client-side mock generator and renders a `DemoModeBanner` component. This frontend fallback works even when the backend is unreachable.

---

## Phase Completion Status

| Phase | Description | Status |
|---|---|---|
| Phase 0 | Project scaffolding, Docker Compose, env setup | ✅ Complete |
| Phase 1 | ESP32 firmware — sensors + MQTT publish | ✅ Complete |
| Phase 2 | Backend foundation — FastAPI, DB models, MQTT bridge | ✅ Complete |
| Phase 3 | Face recognition service + enrollment API | ✅ Complete |
| Phase 4 | Session management + attendance engine | ✅ Complete |
| Phase 5 | Control API + alert engine | ✅ Complete |
| Phase 6 | Moodle sync service | ✅ Complete |
| Phase 7 | WebSocket live streaming | ✅ Complete |
| Phase 8 | React frontend | ✅ Complete |
| Phase 9 | Integration testing + documentation | ✅ Complete |
| Phase 10 | Full Docker deployment — frontend nginx, Mosquitto broker, service wiring | ✅ Complete |
| Phase 11 | Mock data fallback — backend publisher + frontend demo mode | ✅ |
| Phase 12 | Raspberry Pi setup runbook (docs/rpi_setup.md) | ✅ |
| Phase 13 | Demo data seed script (backend/seed.py) | ✅ |
| Phase 14 | JWT auth, professors table, role-based API filtering | ✅ |
| Phase 15 | Docker image slim — DeepFace/TF removed; FACE_RECOGNITION_ENABLED stub; seed.py self-migrating | ✅ |
| Phase 16 | Professor Dashboard — session list (live/upcoming/done) + attendance table + sensor cards/sparklines | ✅ |
| Phase 17 | Dashboard bug fixes — total_enrolled from detail endpoint, key-based tab state reset, session count badges, MOCK_MODE enabled | ✅ |
| Phase 18 | Full frontend visual redesign — CSS token system, DM Sans + Inter typography, blue sidebar, Soft Structuralism design language, all pages redesigned | ✅ |

> **Update this table at the end of every phase.** Change ⬜ to ✅ when complete, 🔄 when in progress.

---

## Key Decisions Log

| Decision | Reason | Date |
|---|---|---|
| FastAPI over Flask | Native async needed for WebSocket + MQTT bridge | Project start |
| face_recognition lib over raw OpenCV | Higher accuracy, simpler API, dlib-based 128-d embeddings | Project start |
| Run all services on RPi (no cloud) | Avoid latency, cost, and internet dependency for real-time control | Project start |
| Docker Moodle instead of mock API | Gives real Moodle REST API to code against | Project start |
| Redis for live sensor state | Instant dashboard load without hitting PostgreSQL | Project start |
| asyncio-mqtt for MQTT bridge | Native async, integrates cleanly with FastAPI event loop | Project start |
| Drop Blynk/Adafruit IO | Redundant with custom FastAPI backend | Project start |
| Migrated asyncio-mqtt → aiomqtt | paho-mqtt v2 broke asyncio-mqtt 0.16 (missing message_retry_set) | Phase 2 |
| attendance router mounted at /api prefix | Routes span /api/sessions/*/attendance and /api/attendance/* — single prefix avoids double-mounting | Phase 4 |
| mark-absent as explicit endpoint | Face recognition only marks present; professor must trigger bulk absent-fill at session end | Phase 4 |
| Student name cached per session in recognition_loop | Avoids repeated DB lookup per 2fps frame; name is immutable so cache never goes stale | Phase 4 |
| publish_mqtt uses ephemeral client per call | MQTT subscriber loop cannot be reused for publishing — short-lived client is simplest safe pattern | Phase 5 |
| AlertEngine uses AsyncIOScheduler | Runs on uvicorn event loop, no thread overhead, compatible with async DB calls | Phase 5 |
| Alert deduplication via unacknowledged check | Prevents alert storms when threshold remains breached across multiple 30s check cycles | Phase 5 |
| recognition_loop threads room_id through start_recognition | Phase 7 added room_id param so attendance events and anomaly alerts carry the correct room for WebSocket routing | Phase 7 |
| Moodle sync is fire-and-forget on session end | Failing Moodle must not block a professor from ending a class | Phase 6 |
| Redis retry queue for failed Moodle syncs | AlertEngine retries every 10 min via APScheduler — lightweight alternative to Celery for classroom scale | Phase 6 |
| moodle_client uses lazy httpx.AsyncClient singleton | Avoids reconnecting on every sync call while remaining safe to close on shutdown | Phase 6 |
| WebSocket state lifted to SensorContext | Single WS connection per browser tab shared across all pages via React context — avoids N connections for N pages | Phase 8 |
| Dashboard shows live WS attendance; Attendance page fetches API | Live events (face recognitions) are ephemeral stream data; historical records need full CRUD — two different data needs, two sources | Phase 8 |
| History expandable rows use React.Fragment with key | Bare <> fragments don't support key prop; Fragment import required for keyed sibling row pairs in a table body | Phase 8 |
| Test suite uses SQLite in-memory with gen_random_uuid() shim | Avoids requiring PostgreSQL in CI; shim registered via SQLAlchemy event.listen maps PostgreSQL server_default to SQLite user function | Phase 9 |
| e2e_test.py uses httpx sync client, not pytest | Script runs against a live server with python e2e_test.py — no pytest machinery required, simpler to run on the Pi itself | Phase 9 |
| Migrated face_recognition → DeepFace | face_recognition/dlib requires native C++ compilation and cmake which fails on pip install; DeepFace is fully pip-installable with identical Facenet 128-d embedding functionality | Phase 3 fix |
| face_encodings BYTEA dtype changed float64 → float32 | DeepFace Facenet outputs float32 vectors; both enrollment and reload_encodings must agree on dtype or cosine distance operates on garbage — all new enrollments store float32 | Phase 3 fix |
| Frontend served via nginx container (port 3000) | Vite dev server proxy is dev-only; production build requires a static file server + reverse proxy for /api and /ws — nginx in a multi-stage Docker image is the standard pattern | Phase 10 |
| Mosquitto added as a Docker service | Previously assumed to run on RPi host; for full-stack local Docker deployment it must be containerised — anonymous listener on port 1883, config mounted read-only | Phase 10 |
| Moodle moved to optional Docker profile | bitnami/moodle:4.3 tag was retired; tag updated to bitnami/moodle:4; service gated behind --profile moodle so core stack starts without it | Phase 10 |
| aiomqtt 2.x uses plain async iterator for client.messages | aiomqtt 2.x removed the async context manager protocol from MessagesIterator; `async with client.messages` must be `async for message in client.messages` — discovered at runtime during Docker deployment | Phase 10 |
| Mock sensor uses APScheduler job (backend) | Reuses existing scheduler already running for alert_engine; no new dependency; activated only when MOCK_MODE=true at startup | Phase 11 |
| Frontend fallback mock is client-side, independent of backend | WS timeout of 8s triggers in-browser value generator; dashboard remains demonstrable even when Docker stack is fully offline | Phase 11 |
| RPi setup documented as docs/rpi_setup.md runbook | Single authoritative step-by-step guide covering OS, Docker, ESP32 flash, and verification commands — reduces setup errors during demo day | Phase 12 |
| Seed script is idempotent standalone async script | Runs outside FastAPI lifecycle via direct engine instantiation; deterministic uuid.uuid5 IDs + ON CONFLICT DO NOTHING prevents duplicate runs | Phase 13 |
| JWT stored in localStorage | Acceptable for university intranet without HTTPS; simpler than httpOnly cookies which require CORS credentials config | Phase 14 |
| REQUIRE_AUTH defaults to false | Preserves backward compatibility with seed.py and e2e tests during auth rollout; set to true in production | Phase 14 |
| DeepFace removed from Docker image | TensorFlow pulls ~600 MB wheel causing OOM during docker build on dev laptops; face recognition only runs on RPi natively; Docker image uses a stub service controlled by FACE_RECOGNITION_ENABLED=false | Phase 15 |
| enrollment.py delegates all DeepFace calls to face_recognition_service | Keeps the router free of library-specific imports; stub/real switch is handled entirely inside the service layer without touching the API contract | Phase 15 |
| seed.py calls _run_migrations() before asyncio.run() | seed.py bypasses FastAPI lifespan so alembic upgrade head never ran automatically; calling it synchronously before asyncio.run() avoids nested event loop errors and ensures schema exists before any INSERT | Phase 15 |
| display_status computed at schema/response time, never stored | "Liveness" changes as time passes with no DB write; storing it would require a background job to flip rows. Computing it in _build_summary from (status, started_at, now) is always accurate and free | Phase 16 |
| WebSocket wins for live sensor cards; polling is fallback only | useLiveSensors already owns the WS connection and exposes isDemoMode; the Dashboard watches isDemoMode to decide whether to prefer WS data or the 5-second DB-backed poll. No second WS connection needed | Phase 16 |
| Sensor endpoints live in sessions.py, not sensors.py | URL path /api/sessions/{id}/sensors/... is mounted under the sessions router prefix; splitting by URL namespace is cleaner than by domain concept | Phase 16 |
| Sparkline history stored in a useRef (accumulated) + useState (for renders) | Accumulating in state would trigger a re-render on every WS message; storing in ref and flushing only when a new value differs avoids thrashing while still updating the chart | Phase 16 |
| AttendanceTab receives sessionId prop and fetches SessionDetailResponse internally | total_enrolled only exists on the detail endpoint response, not on the list-endpoint SessionWithSummary — passing the full session object from the list caused total_enrolled to always be undefined | Phase 17 |
| key={session.id} on tab components forces full remount on session switch | More reliable than resetting individual useEffect states; React unmounts and remounts the component, guaranteeing clean slate without stale-data flash between sessions | Phase 17 |
| MOCK_MODE=true set in docker-compose.yml | Development without ESP32 hardware needs mock MQTT publisher to populate sensor_readings table; otherwise sensors tab shows "No data" for all sessions | Phase 17 |
| Session count badges added to left-panel group headers | 31 past sessions require scrolling; without a count indicator users assumed the panel was empty after the visible live/upcoming sessions | Phase 17 |
| tokens.css as design token source of truth, separate from index.css | Tailwind v3 does not resolve CSS vars in arbitrary bracket values at build time; keeping tokens in a dedicated CSS file loaded before index.css lets component classes in index.css reference vars via `var(--color-*)` without Tailwind's build step | Phase 18 |
| CSS class names preserved, visual output changed | Renaming `.glass-card` to `.card` would require touching every JSX file; changing the visual output of existing class names (removing backdrop-filter, updating colors) achieves the redesign with zero JSX churn | Phase 18 |
| Glassmorphism removed entirely | backdrop-filter: blur() is expensive on the GPU, causes rendering artifacts in some Chromium versions, and undermines the "clean surfaces" design archetype chosen for this project | Phase 18 |
| Inline SVG components instead of an icon library | No icon library is in package.json; installing one adds bundle weight and a new dependency; the 10–12 icons needed are simple enough to write inline as functional components | Phase 18 |
| LineChart → AreaChart with linearGradient fill | AreaChart gives more visual weight to the sparkline while using identical Recharts data shape; linearGradient fill (opaque at top, transparent at bottom) communicates trend direction more clearly than a bare line | Phase 18 |
| DemoRow uses imperative onMouseEnter/Leave for hover colors | CSS hover pseudo-class cannot reference CSS vars in Tailwind v3 utility classes; component-level JS event handlers are the escape hatch for token-based hover states that need `var(--color-*)` | Phase 18 |
| `h-screen` kept on Layout root (not min-h-screen) | Dashboard panels use `h-full` which resolves to 100% of the nearest ancestor with a defined height; changing root to min-h-screen breaks the fixed-height two-panel layout | Phase 18 |
| AttendanceBar renders proportional flex segments | Each status segment occupies `(count/total)*100%` width inside a `display:flex; overflow:hidden` container; overflow:hidden clips any sub-pixel rounding error that would otherwise overflow the 100% track | Phase 18 |

---

## Known Issues & Limitations

| Issue | Description | Workaround |
|---|---|---|
| Camera unavailable on dev machine | cv2.VideoCapture(0) fails on non-Pi systems; recognition loop exits immediately | Handled transparently — stub mode (`FACE_RECOGNITION_ENABLED=false`) replaces the loop with a synthetic event emitter; no camera needed in Docker |
| MQ-135 not factory calibrated | Air quality readings are ADC counts, not true CO₂ ppm | Values are comparative — threshold of 500 is empirically set, not scientifically calibrated |
| DeepFace not installed in Docker image | Face recognition is disabled in Docker by default (FACE_RECOGNITION_ENABLED=false); stub emits mock attendance events instead | Set FACE_RECOGNITION_ENABLED=true on RPi with DeepFace installed natively (see docs/rpi_setup.md §8) |
| DeepFace inference speed on RPi | Facenet on CPU is slower than dlib on RPi 4 for the first load; subsequent frames run at ~2fps after model warm-up | Keep RECOGNITION_FPS=2; upgrade to RPi 5 for better throughput |
| MQTT QoS 0 for sensors | A publish during broker restart will be lost | Dashboard simply shows stale data from Redis until next MQTT message arrives |
| Moodle token scope | Moodle REST API requires a token with `core_user_get_users` and `gradereport_user_get_grade_items` permissions; wrong scope causes silent 200 with error body | Check Moodle webservice logs if sync shows `failed > 0` |
| Single-room design | Room ID is hardcoded to `room1` in firmware config.h | Change `ROOM_ID` in `config.h` and `.env` to add a second room; multi-room requires separate ESP32 per room |
| No HTTPS / WSS | Backend listens on plain HTTP; WebSocket is `ws://` not `wss://` | Add nginx reverse proxy with SSL termination for any public-facing deployment |
| Dashboard live but no data (no ESP32) | Without a connected ESP32, MQTT has no publisher so Redis stays empty and WebSocket sends no sensor events | Set MOCK_MODE=true in .env and restart backend, or wait for frontend 8s timeout to trigger client-side demo mode |

---

## Future Work

| Feature | Description |
|---|---|
| Multi-room support | Parametric room_id throughout; single backend instance manages N ESP32 nodes |
| Mobile app | React Native app for professors to view attendance and control relays from their phone |
| Better lighting for face recognition | IR illuminator module for low-light classrooms; automatic brightness compensation in OpenCV preprocessing |
| Email / SMS notifications | Send alert emails via SMTP (or SMS via Twilio) when critical thresholds are breached |
| Student self-enrollment QR codes | Generate QR code per student; scan to trigger face enrollment without professor intervention |
| Attendance analytics dashboard | Per-student attendance rate charts, course-level trends, at-risk student flagging |
| CO₂ sensor calibration | Replace MQ-135 proxy with calibrated SCD30 or MH-Z19 for true CO₂ ppm |
| Offline resilience | Local SQLite fallback on RPi if Docker PostgreSQL container restarts; sync on reconnect |

---

## How to Update This File

After completing each phase, update:
1. The **Phase Completion Status** table (mark ✅)
2. The **Key Decisions Log** if any architectural decision was changed
3. Any schema or API changes made during implementation
4. Any environment variables added

Keep this file committed to the repository. It is the handoff document for every team member.