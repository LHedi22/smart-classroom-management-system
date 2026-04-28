# CLAUDE.md — Smart Classroom Management System
# SMU – Mediterranean Institute of Technology
# Team: Ben Jemaa · Jallouli · Saadaoui · Ouertani · Day

> **This file is the single source of truth for this project.**
> Read it at the start of every session. Update it whenever architecture, decisions, or progress change.
> Never contradict what is written here without explicitly noting the change and the reason.

---

## Project Summary

An IoT-based Smart Classroom Management System for SMU that:
- Automates student attendance tracking using face recognition (Raspberry Pi Camera + OpenCV + face_recognition lib)
- Monitors classroom environment in real time (temperature, humidity, air quality, sound)
- Controls AC and lighting via relay module (automatic thresholds + manual override)
- Streams all data to a professor-facing React dashboard over WebSocket
- Syncs attendance to a local Docker Moodle instance via its REST API

---

## Repository Structure

```
smart-classroom/
├── CLAUDE.md                        ← this file
├── README.md
├── docker-compose.yml               ← PostgreSQL + Redis + Moodle
├── .env.example
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
│   │   │   ├── face_recognition_service.py
│   │   │   ├── alert_engine.py
│   │   │   └── moodle_client.py
│   │   └── models/
│   │       ├── db_models.py         ← SQLAlchemy ORM
│   │       └── schemas.py           ← Pydantic schemas
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                        ← React + Vite + Tailwind
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Attendance.jsx
│   │   │   ├── Control.jsx
│   │   │   ├── Enrollment.jsx
│   │   │   └── History.jsx
│   │   ├── components/
│   │   ├── hooks/
│   │   │   └── useLiveSensors.js
│   │   └── api/
│   │       └── client.js
│   ├── package.json
│   └── vite.config.js
│
└── docs/
    ├── mqtt_schema.md
    ├── api_contracts.md
    └── wiring_diagram.md
```

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
- **MQTT:** asyncio-mqtt (bridge between Mosquitto and FastAPI)
- **Face recognition:** face_recognition library (dlib-based) + OpenCV
- **Scheduler:** APScheduler (alert engine, periodic jobs)
- **Moodle integration:** httpx (async HTTP client)

### Frontend
- **Framework:** React 18 + Vite
- **Styling:** TailwindCSS
- **Charts:** Recharts
- **Real-time:** Native WebSocket via custom hook
- **HTTP client:** axios

### Infrastructure
- **MQTT Broker:** Mosquitto (runs on Raspberry Pi)
- **Database:** PostgreSQL 15 (Docker)
- **Cache:** Redis 7 (Docker)
- **LMS:** Moodle 4.x (Docker — local simulation)
- **Container orchestration:** Docker Compose

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

**students**
- id (UUID PK)
- name (VARCHAR)
- student_id (VARCHAR UNIQUE) — institutional ID
- created_at (TIMESTAMP)

**courses**
- id (UUID PK)
- code (VARCHAR UNIQUE) — e.g. "CS301"
- name (VARCHAR)
- professor_name (VARCHAR)

**sessions**
- id (UUID PK)
- course_id (FK → courses)
- room_id (VARCHAR) — e.g. "room1"
- started_at (TIMESTAMP)
- ended_at (TIMESTAMP NULLABLE)
- status (ENUM: active, ended)

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
- encoding (BYTEA) — serialized numpy array (128-d vector)
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

```
# Database
DATABASE_URL=postgresql+asyncpg://smartcam:smartcam@localhost:5432/smartclassroom

# Redis
REDIS_URL=redis://localhost:6379

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Moodle
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=your_moodle_token_here

# App
SECRET_KEY=changeme
ROOM_ID=room1

# Thresholds (auto-control)
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

1. **Enrollment:** Capture 5 frames → compute 128-d encoding for each → average → store as BYTEA in `face_encodings`
2. **Recognition loop:** Run at 2fps (RPi CPU constraint) → detect all faces → compare each to all stored encodings using cosine distance → match if distance < 0.6 → return `student_id` or `UNKNOWN`
3. **Attendance recording:** First match in a session → create `attendance_record` with status=`present` → 30s cooldown to prevent duplicate entries
4. **UNKNOWN faces:** Increment occupancy counter but do not create attendance record → flag if count is high

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

---

## Known Issues & Limitations

| Issue | Description | Workaround |
|---|---|---|
| Camera unavailable on dev machine | face_recognition and OpenCV fail to open `/dev/video0` on non-Pi systems | Backend catches the exception and logs a warning; attendance still works via manual PATCH |
| MQ-135 not factory calibrated | Air quality readings are ADC counts, not true CO₂ ppm | Values are comparative — threshold of 500 is empirically set, not scientifically calibrated |
| face_recognition speed on RPi | dlib 128-d encoding runs at ~2 fps on RPi 4; high classroom density may cause lag | Reduce RECOGNITION_FPS or upgrade to RPi 5 / accelerator |
| MQTT QoS 0 for sensors | A publish during broker restart will be lost | Dashboard simply shows stale data from Redis until next MQTT message arrives |
| Moodle token scope | Moodle REST API requires a token with `core_user_get_users` and `gradereport_user_get_grade_items` permissions; wrong scope causes silent 200 with error body | Check Moodle webservice logs if sync shows `failed > 0` |
| Single-room design | Room ID is hardcoded to `room1` in firmware config.h | Change `ROOM_ID` in `config.h` and `.env` to add a second room; multi-room requires separate ESP32 per room |
| No HTTPS / WSS | Backend listens on plain HTTP; WebSocket is `ws://` not `wss://` | Add nginx reverse proxy with SSL termination for any public-facing deployment |

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
