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
- **[NEW Phase 19–22]** Provides a full Insights system: at-risk student flagging, attendance × environment correlations, AI-generated anomaly summaries, and exportable PDF/CSV reports

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
│   │   │   ├── websocket.py
│   │   │   └── insights.py          ← NEW Phase 19: all insights endpoints
│   │   ├── services/
│   │   │   ├── mqtt_bridge.py
│   │   │   ├── face_recognition_service.py
│   │   │   ├── recognition_loop.py
│   │   │   ├── alert_engine.py
│   │   │   ├── mock_sensor.py
│   │   │   ├── moodle_client.py
│   │   │   ├── insights_engine.py   ← NEW Phase 19: at-risk detection, comfort score, correlation queries
│   │   │   └── ai_summary.py        ← NEW Phase 20: Ollama/phi3:mini client — anomaly narrative generator (httpx, no extra deps)
│   │   └── models/
│   │       ├── db_models.py         ← SQLAlchemy ORM
│   │       └── schemas.py           ← Pydantic schemas (+ InsightResponse, AtRiskStudent, CorrelationPoint added Phase 19)
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt             ← reportlab added Phase 22; Phase 20 uses httpx (already present)
│   ├── .dockerignore
│   └── Dockerfile
│
├── frontend/                        ← React + Vite + Tailwind
│   ├── src/
│   │   ├── tokens.css
│   │   ├── index.css
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        ← MODIFIED Phase 19: comfort score pill + at-risk mini-card
│   │   │   ├── Attendance.jsx       ← MODIFIED Phase 19: per-student risk badge + streak indicator
│   │   │   ├── Control.jsx
│   │   │   ├── Enrollment.jsx
│   │   │   ├── History.jsx          ← MODIFIED Phase 19: attendance trend arrow per session
│   │   │   ├── Login.jsx
│   │   │   └── Insights.jsx         ← NEW Phase 19: dedicated Insights page (3 tabs: Overview, Students, Environment)
│   │   ├── components/
│   │   │   ├── Layout.jsx           ← MODIFIED Phase 19: Insights nav item added to sidebar
│   │   │   ├── DemoModeBanner.jsx
│   │   │   └── insights/
│   │   │       ├── KpiCards.jsx         ← NEW Phase 19: top-level KPI strip
│   │   │       ├── AttendanceTrendChart.jsx  ← NEW Phase 19: AreaChart week-by-week per course
│   │   │       ├── DayOfWeekHeatmap.jsx      ← NEW Phase 19: attendance heatmap grid
│   │   │       ├── AtRiskTable.jsx           ← NEW Phase 19: flagged students list with drill-down
│   │   │       ├── ComfortScoreCard.jsx      ← NEW Phase 19: composite 0–100 score card
│   │   │       ├── SensorTrendChart.jsx      ← NEW Phase 19: multi-sensor AreaChart over session history
│   │   │       ├── CorrelationScatter.jsx    ← NEW Phase 19: temp vs attendance scatter
│   │   │       ├── AiSummaryCard.jsx         ← NEW Phase 20: AI narrative card with loading skeleton
│   │   │       └── ExportButton.jsx          ← NEW Phase 22: PDF/CSV export trigger
│   │   ├── hooks/
│   │   │   ├── useLiveSensors.js
│   │   │   └── useInsights.js       ← NEW Phase 19: fetches all insights endpoints, exposes loading/error states
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
    └── rpi_setup.md

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
- **[NEW Phase 20] AI summaries:** httpx → Ollama REST API (`/api/chat`) — model `phi3:mini`; no new dependencies; called only for anomaly/alert narratives; URL configured via `OLLAMA_BASE_URL`
- **[NEW Phase 22] PDF export:** ReportLab — server-side PDF generation for session and course reports

### Frontend
- **Framework:** React 18 + Vite
- **Styling:** TailwindCSS v3 + CSS custom properties design token system (`tokens.css`)
- **Typography:** DM Sans (headings, 600/700) + Inter (body, 400/500) via Google Fonts
- **Charts:** Recharts (`AreaChart`, `ScatterChart`, `linearGradient` fill)
- **Real-time:** Native WebSocket via custom hook
- **HTTP client:** axios
- **Design system:** `tokens.css` — single source of truth for all colors, shadows, and type scale

### Infrastructure
- **MQTT Broker:** Mosquitto 2 (Docker)
- **Database:** PostgreSQL 15 (Docker)
- **Cache:** Redis 7 (Docker)
- **Frontend server:** nginx (Docker)
- **LMS:** Moodle 4.x (Docker — optional, `--profile moodle`)
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
- status (ENUM: active, ended, upcoming)
- display_status (computed, NOT stored): `live` | `upcoming` | `done`

**attendance_records**
- id (UUID PK)
- session_id (FK → sessions)
- student_id (FK → students)
- status (ENUM: present, absent, late, excused)
- detected_at (TIMESTAMP)
- adjusted_by (VARCHAR NULLABLE)
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
- `GET /api/sensors/latest`
- `GET /api/sensors/history` — params: `room_id`, `type`, `from`, `to`
- `GET /api/sessions/{id}/sensors/latest`
- `GET /api/sessions/{id}/sensors/summary`

### Sessions
- `POST /api/sessions/start`
- `POST /api/sessions/{id}/end`
- `GET /api/sessions`
- `GET /api/sessions/{id}`

### Control
- `POST /api/control/ac`
- `POST /api/control/lighting`
- `GET /api/control/status/{room_id}`

### Alerts
- `GET /api/alerts`
- `PATCH /api/alerts/{id}/acknowledge`
- `GET /api/alerts/unread-count/{room_id}`

### Courses
- `GET /api/courses`
- `POST /api/courses`
- `GET /api/courses/{id}`
- `POST /api/courses/{id}/enroll`

### Attendance
- `GET /api/sessions/{id}/attendance`
- `PATCH /api/attendance/{record_id}`
- `POST /api/sessions/{id}/mark-absent`
- `GET /api/students/{id}/attendance-history`

### Enrollment
- `GET /api/students`
- `POST /api/students`
- `POST /api/students/{id}/enroll-face`
- `GET /api/students/{id}/courses`

### WebSocket
- `WS /ws/classroom/{room_id}`

### Insights (NEW — Phase 19–22)
- `GET /api/insights/overview` — KPI summary: total sessions, avg attendance rate, comfort score trend, active alert count; scoped by `professor_id` for professors, all courses for admin
- `GET /api/insights/attendance/trend` — params: `course_id` (optional), `weeks=8`; returns week-by-week attendance rate array for AreaChart
- `GET /api/insights/attendance/heatmap` — returns a 7×N matrix (day-of-week × time-slot) of avg attendance rates
- `GET /api/insights/attendance/decay` — first-session vs last-session attendance rate per course; detects semester drift
- `GET /api/insights/students/at-risk` — list of students below `threshold` (default 70%) with: name, student_id, attendance_rate, consecutive_absences, courses_at_risk[]; professor sees only their courses, admin sees all
- `GET /api/insights/students/{id}/profile` — full per-student insight: attendance history across all sessions, trend, risk level, course breakdown
- `GET /api/insights/environment/comfort-score` — composite 0–100 score from latest temp/humidity/air_quality readings for a room
- `GET /api/insights/environment/trends` — params: `room_id`, `from`, `to`; avg/min/max per sensor type per day; returns array for multi-sensor AreaChart
- `GET /api/insights/environment/ac-effectiveness` — per-session: time between AC ON and temp drop below threshold; returns avg lag in minutes
- `GET /api/insights/correlations/temp-vs-attendance` — scatter data: each point = one session, x=avg_temp, y=attendance_rate
- `GET /api/insights/correlations/airquality-vs-sound` — scatter: x=avg_air_quality, y=pct_time_sound_detected per session
- `GET /api/insights/ai-summary` — params: `scope` (session|course|room|global), `id`; builds context blob and calls Ollama `/api/chat` with phi3:mini; returns `{narrative: str, generated_at: datetime}`; cached in Redis for 10 min per (scope, id); 503 if Ollama unreachable
- `GET /api/insights/export/session/{id}` — returns PDF binary (ReportLab); attendance list + sensor summary + AI narrative
- `GET /api/insights/export/course/{id}` — returns PDF; all sessions, per-student rates, at-risk flags
- `GET /api/insights/export/course/{id}/csv` — returns CSV of raw attendance records for the course

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

MOCK_MODE=false
FACE_RECOGNITION_ENABLED=false

# ── Auth ──────────────────────────────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=480
REQUIRE_AUTH=false

# ── Auto-control thresholds ───────────────────────────────────────────────
TEMP_AC_ON_THRESHOLD=28
TEMP_AC_OFF_THRESHOLD=22
AIR_QUALITY_ALERT_THRESHOLD=500
FACE_RECOGNITION_THRESHOLD=0.6
RECOGNITION_FPS=2

# ── Insights (NEW Phase 19–22) ────────────────────────────────────────────
# Ollama base URL — required for AI summary endpoint (Phase 20)
# Local: http://localhost:11434  |  Docker service: http://ollama:11434
# If Ollama is unreachable the endpoint returns 503, no crash
OLLAMA_BASE_URL=http://localhost:11434

# At-risk threshold: students below this attendance rate are flagged
AT_RISK_THRESHOLD=0.70

# Consecutive absences threshold: triggers at-risk flag regardless of overall rate
AT_RISK_CONSECUTIVE_ABSENCES=3

# AI summary cache TTL in seconds (default 600 = 10 minutes)
AI_SUMMARY_CACHE_TTL=600
```

---

## Auto-Control Rules

| Sensor | Condition | Action |
|---|---|---|
| Temperature | > 28°C AND AC is in auto mode | Turn AC ON |
| Temperature | < 22°C AND AC is in auto mode | Turn AC OFF |
| Air quality | > 500 ppm | Send alert |
| Sound | Silent for > 30 min during active session | Send attendance anomaly alert |
| Occupancy | headcount > recognized_faces + 2 | Flag discrepancy for professor |

---

## Insights System (Phase 19–22)

### At-Risk Student Detection Logic
A student is flagged as at-risk if either condition is true:
1. Their attendance rate across all ended sessions for a course is below `AT_RISK_THRESHOLD` (default 70%)
2. They have `AT_RISK_CONSECUTIVE_ABSENCES` (default 3) or more consecutive absences in any course

Computed at query time by `insights_engine.get_at_risk_students()`. Not stored — always fresh. Professors see only students in their own courses. Admins see all.

### Comfort Score Formula
```
comfort_score = 100
  - max(0, temp - 26) * 5          # penalty above 26°C, -5 per degree
  - max(0, 18 - temp) * 5          # penalty below 18°C
  - max(0, humidity - 65) * 2      # penalty above 65% humidity
  - max(0, (air_quality - 300) / 50)  # penalty above 300 ppm
clamped to [0, 100]
```

### AI Summary Context Schema
`ai_summary.py` builds a structured context blob and POSTs it to Ollama's `/api/chat` endpoint with model `phi3:mini`. The fixed system prompt instructs the model to produce a 3–5 sentence narrative identifying the most important finding and one concrete recommendation. If Ollama is unreachable, the endpoint returns HTTP 503 with a message indicating the expected URL — no crash. Results are cached in Redis per `(scope, id)` key for `AI_SUMMARY_CACHE_TTL` seconds.

Context blob shape (JSON, passed as user message):
```json
{
  "scope": "course",
  "course_name": "CS301",
  "period": "last 8 weeks",
  "attendance_summary": { "avg_rate": 0.74, "trend": "declining", "sessions": 12 },
  "at_risk_students": 3,
  "env_summary": { "avg_temp": 28.4, "avg_air_quality": 420, "comfort_score": 62 },
  "recent_alerts": ["temp_high x3", "air_quality_high x1"],
  "anomalies": ["attendance dropped 22% in week 6", "3 sessions above 30°C"]
}
```

### Export Format
- **Session PDF**: cover (course, date, professor), attendance table (name, status, detected_at), sensor summary table (avg/min/max per type), AI narrative paragraph, alert log
- **Course PDF**: cover, per-session attendance bar chart (rendered as ASCII table fallback if chart lib unavailable), per-student rate table with at-risk flag, AI narrative
- **Course CSV**: raw rows — `session_date, student_name, student_id, status, detected_at, adjusted_by`

PDF generation uses ReportLab's `Platypus` (Paragraph, Table, SimpleDocTemplate). No external font dependencies.

### Mini-Cards on Existing Pages
| Page | What is added |
|---|---|
| Dashboard | Comfort score pill (top of sensor strip) + "N students at risk" warning card if N > 0 |
| Attendance | Risk badge (🔴/🟡) next to each student row; streak indicator "absent 3×" in subtitle |
| History | Trend arrow (↑↓→) next to each session's attendance percentage |
| Control | "AC ON for 2h, no occupancy detected" efficiency nudge card (from insights_engine) |

---

## Face Recognition Logic

> Applies only when `FACE_RECOGNITION_ENABLED=true` (Raspberry Pi with DeepFace installed natively).

1. **Enrollment:** Upload up to 5 images → compute 128-d Facenet encoding → average → store as BYTEA float32
2. **Recognition loop:** 2fps → detect faces → cosine distance < 0.6 → match → return `student_id` or `UNKNOWN`
3. **Attendance recording:** First match per session → `attendance_record` status=`present` → 30s cooldown
4. **UNKNOWN faces:** Increment occupancy counter → flag if high

### Stub Mode (`FACE_RECOGNITION_ENABLED=false`)
- Enrollment: stores zeroed 128-d float32 placeholder
- Recognition loop: emits one synthetic attendance event every 45s for a random enrolled student
- `reload_encodings()`: no-op

---

## Mock Sensor Logic (MOCK_MODE=true)

`mock_sensor.py` publishes synthetic MQTT messages every 5s:
- Temperature: 22–32°C sine wave + noise
- Humidity: 45–70%
- Air quality: 200–550 ppm, occasional spike above 500
- Sound: 70% detected / 30% quiet
- Heartbeat: every 30s

Frontend activates client-side demo mode if no WS sensor message within 8s.

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
| Phase 11 | Mock data fallback — backend publisher + frontend demo mode | ✅ Complete |
| Phase 12 | Raspberry Pi setup runbook (docs/rpi_setup.md) | ✅ Complete |
| Phase 13 | Demo data seed script (backend/seed.py) | ✅ Complete |
| Phase 14 | JWT auth, professors table, role-based API filtering | ✅ Complete |
| Phase 15 | Docker image slim — DeepFace/TF removed; FACE_RECOGNITION_ENABLED stub; seed.py self-migrating | ✅ Complete |
| Phase 16 | Professor Dashboard — session list (live/upcoming/done) + attendance table + sensor cards/sparklines | ✅ Complete |
| Phase 17 | Dashboard bug fixes — total_enrolled, key-based tab reset, session count badges, MOCK_MODE enabled | ✅ Complete |
| Phase 18 | Full frontend visual redesign — CSS token system, DM Sans + Inter, blue sidebar, Soft Structuralism | ✅ Complete |
| Phase 19 | Insights backend — insights_engine.py, all analytics endpoints, at-risk logic, comfort score | ✅ |
| Phase 20 | AI summaries — ai_summary.py, Ollama/phi3:mini via httpx, Redis caching, AiSummaryCard frontend | ✅ |
| Phase 21 | Insights frontend — Insights.jsx page (3 tabs), all chart components, mini-cards on existing pages | ✅ |
| Phase 22 | Export system — ReportLab PDF (session + course), CSV download, ExportButton component | ✅ |

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
| recognition_loop threads room_id through start_recognition | Phase 7 added room_id param so attendance events and anomaly alerts carry correct room for WebSocket routing | Phase 7 |
| Moodle sync is fire-and-forget on session end | Failing Moodle must not block a professor from ending a class | Phase 6 |
| Redis retry queue for failed Moodle syncs | AlertEngine retries every 10 min via APScheduler | Phase 6 |
| moodle_client uses lazy httpx.AsyncClient singleton | Avoids reconnecting on every sync call while remaining safe to close on shutdown | Phase 6 |
| WebSocket state lifted to SensorContext | Single WS connection per browser tab shared across all pages | Phase 8 |
| Dashboard shows live WS attendance; Attendance page fetches API | Live events are ephemeral; historical records need full CRUD | Phase 8 |
| History expandable rows use React.Fragment with key | Bare <> fragments don't support key prop | Phase 8 |
| Test suite uses SQLite in-memory with gen_random_uuid() shim | Avoids requiring PostgreSQL in CI | Phase 9 |
| e2e_test.py uses httpx sync client, not pytest | Simpler to run on the Pi itself | Phase 9 |
| Migrated face_recognition → DeepFace | dlib/cmake fails on pip install; DeepFace is fully pip-installable | Phase 3 fix |
| face_encodings BYTEA dtype changed float64 → float32 | DeepFace Facenet outputs float32; dtype mismatch corrupts cosine distance | Phase 3 fix |
| Frontend served via nginx container (port 3000) | Production build requires static file server + reverse proxy | Phase 10 |
| Mosquitto added as a Docker service | Containerised for full-stack local Docker deployment | Phase 10 |
| Moodle moved to optional Docker profile | bitnami/moodle:4.3 retired; gated behind --profile moodle | Phase 10 |
| aiomqtt 2.x uses plain async iterator for client.messages | async with removed in 2.x; must use async for | Phase 10 |
| Mock sensor uses APScheduler job (backend) | Reuses existing scheduler; activated only when MOCK_MODE=true | Phase 11 |
| Frontend fallback mock is client-side, independent of backend | WS timeout of 8s triggers in-browser generator; works fully offline | Phase 11 |
| RPi setup documented as docs/rpi_setup.md runbook | Reduces setup errors during demo day | Phase 12 |
| Seed script is idempotent standalone async script | Deterministic uuid.uuid5 IDs + ON CONFLICT DO NOTHING | Phase 13 |
| JWT stored in localStorage | Acceptable for university intranet without HTTPS | Phase 14 |
| REQUIRE_AUTH defaults to false | Preserves backward compatibility with seed.py and e2e tests | Phase 14 |
| DeepFace removed from Docker image | TF pulls ~600 MB; OOM on dev laptops; runs natively on RPi only | Phase 15 |
| enrollment.py delegates all DeepFace calls to face_recognition_service | Stub/real switch handled entirely inside service layer | Phase 15 |
| seed.py calls _run_migrations() before asyncio.run() | Avoids nested event loop errors; ensures schema before any INSERT | Phase 15 |
| display_status computed at schema/response time, never stored | Liveness changes with time; storing requires a background job to flip rows | Phase 16 |
| WebSocket wins for live sensor cards; polling is fallback only | useLiveSensors owns WS; Dashboard watches isDemoMode to choose source | Phase 16 |
| Sensor endpoints live in sessions.py, not sensors.py | URL namespace cleaner than domain namespace | Phase 16 |
| Sparkline history stored in useRef + useState | Accumulating in state thrashes renders; ref flushes only on value change | Phase 16 |
| AttendanceTab receives sessionId prop and fetches detail internally | total_enrolled only on detail endpoint, not list-endpoint | Phase 17 |
| key={session.id} on tab components forces full remount on switch | More reliable than resetting individual useEffect states | Phase 17 |
| MOCK_MODE=true set in docker-compose.yml | Dev without ESP32 needs mock MQTT to populate sensor_readings | Phase 17 |
| Session count badges added to left-panel group headers | 31 past sessions require scrolling; count prevents "empty panel" confusion | Phase 17 |
| tokens.css as design token source, separate from index.css | Tailwind v3 does not resolve CSS vars in bracket values at build time | Phase 18 |
| CSS class names preserved, visual output changed | Zero JSX churn while achieving full redesign | Phase 18 |
| Glassmorphism removed entirely | backdrop-filter expensive on GPU, causes Chromium artifacts | Phase 18 |
| Inline SVG components instead of icon library | 10–12 icons; no extra bundle weight | Phase 18 |
| LineChart → AreaChart with linearGradient fill | More visual weight; communicates trend direction clearly | Phase 18 |
| DemoRow uses imperative onMouseEnter/Leave for hover colors | CSS hover cannot reference CSS vars in Tailwind v3 | Phase 18 |
| h-screen kept on Layout root | h-full on panels requires ancestor with defined height | Phase 18 |
| AttendanceBar renders proportional flex segments | overflow:hidden clips sub-pixel rounding | Phase 18 |
| At-risk computed at query time, never stored | Rate changes after every session; storing requires background job | Phase 19 |
| Comfort score formula is purely arithmetic, no ML | Reproducible, explainable, zero inference latency | Phase 19 |
| AI summary scoped to anomaly/alert context only | Avoids overly broad AI calls; focused narrative is more actionable | Phase 20 |
| AI summary uses Ollama/phi3:mini via httpx | No Anthropic SDK dependency; httpx already in requirements; zero new packages; model is local and free | Phase 20 |
| AI summary cached in Redis with 10-min TTL | Ollama inference on CPU takes 2–5s — unacceptable on every page load | Phase 20 |
| OLLAMA_BASE_URL defaults to localhost:11434 | Works out-of-box for local Ollama; override to http://ollama:11434 when running Ollama as a Docker service | Phase 20 |
| ReportLab chosen for PDF over WeasyPrint | ReportLab is pure Python, no system font/CSS dependencies; works in Docker without extra apt packages | Phase 22 |
| CSV export is raw SQL result serialized via csv.DictWriter | No pandas dependency; lighter on the Pi | Phase 22 |

---

## Known Issues & Limitations

| Issue | Description | Workaround |
|---|---|---|
| Camera unavailable on dev machine | cv2.VideoCapture(0) fails on non-Pi systems | Stub mode active by default |
| MQ-135 not factory calibrated | ADC counts, not true CO₂ ppm | Threshold of 500 is empirically set |
| DeepFace not installed in Docker image | FACE_RECOGNITION_ENABLED=false by default | Set true on RPi with DeepFace natively installed |
| DeepFace inference speed on RPi | ~2fps after warm-up | Keep RECOGNITION_FPS=2 |
| MQTT QoS 0 for sensors | Publishes lost during broker restart | Dashboard shows stale Redis data until next message |
| Moodle token scope | Wrong scope causes silent 200 with error body | Check Moodle webservice logs |
| Single-room design | Room ID hardcoded to room1 | Change ROOM_ID in config.h and .env |
| No HTTPS / WSS | Plain HTTP only | Add nginx SSL termination for public deployment |
| Dashboard live but no data (no ESP32) | Redis empty without MQTT publisher | Set MOCK_MODE=true |
| AI summary latency | Ollama/phi3:mini inference takes 2–5s on CPU | Cached in Redis for 10 min; AiSummaryCard shows skeleton loader on first request |
| AI summary unavailable | 503 if Ollama is not running or unreachable | AiSummaryCard renders a clear "not reachable" message instead of crashing |

---

## Future Work

| Feature | Description |
|---|---|
| Multi-room support | Parametric room_id throughout |
| Mobile app | React Native for professors |
| Better lighting for face recognition | IR illuminator module |
| Email / SMS notifications | SMTP or Twilio for critical alerts |
| Student self-enrollment QR codes | Scan to trigger face enrollment |
| CO₂ sensor calibration | Replace MQ-135 with SCD30 or MH-Z19 |
| Offline resilience | Local SQLite fallback on RPi |
| Attendance analytics — scheduled email digest | Weekly at-risk report emailed to professors automatically |
| Predictive at-risk model | Logistic regression trained on attendance + sensor data to predict dropout risk |

---

## How to Update This File

After completing each phase, update:
1. The **Phase Completion Status** table (mark ✅)
2. The **Key Decisions Log** if any architectural decision was changed
3. Any schema or API changes made during implementation
4. Any environment variables added

Keep this file committed to the repository. It is the handoff document for every team member.