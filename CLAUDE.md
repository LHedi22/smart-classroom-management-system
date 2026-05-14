Smart Classroom Management System — CLAUDE.md Summary
Project Overview
An IoT-based Smart Classroom Management System for SMU – Mediterranean Institute of Technology, built by a 5-person team. The system automates student attendance via face recognition, monitors classroom environment in real time, controls AC/lighting via relays, streams data to a professor-facing React dashboard, syncs attendance to Moodle, and identifies at-risk students using a local Ollama LLM (phi3-mini).

Repository Structure
smart-classroom/
├── docker-compose.yml         # postgres, redis, mosquitto, backend, frontend, ollama, moodle (optional profile)
├── mosquitto/mosquitto.conf
├── firmware/classroom_node/   # ESP32 Arduino sketch (classroom_node.ino + config.h)
├── backend/app/
│   ├── main.py, config.py, database.py, redis_client.py
│   ├── api/        → sensors, attendance, control, sessions, alerts, enrollment, at_risk, forecast, websocket
│   ├── services/   → mqtt_bridge, face_recognition_service, recognition_loop, alert_engine,
│   │                  mock_sensor, moodle_client, at_risk_engine, forecast_engine
│   └── models/     → db_models.py (SQLAlchemy ORM), schemas.py (Pydantic)
├── frontend/src/
│   ├── tokens.css             # CSS design token source of truth
│   ├── index.css              # all component classes; references token vars only
│   ├── pages/  → Dashboard, Attendance, Control, Enrollment, History, AtRisk, Forecasting, Login
│   ├── components/ → Layout (240px blue sidebar), DemoModeBanner
│   ├── hooks/useLiveSensors.js
│   └── api/client.js
└── docs/ → mqtt_schema, api_contracts, wiring_diagram, rpi_setup.md

Hardware
ComponentModelRoleSBCRaspberry Pi 4B 4GBCentral hub, runs all servicesCameraRPi Camera Module v2 8MPFace recognition inputMCUESP32 Dev Board (ESP-WROOM-32)Sensor node + relay controllerTemp/HumidityDHT21 (AM2301)Environmental monitoringAir QualityMQ-135CO₂/VOC proxySoundACP014Occupancy proxy, noise levelRelay4-Channel Opto-IsolatedAC (ch1), Lighting (ch2), spare (ch3/4)DisplayLCD 16×2 I2CLocal room statusVoltage ConverterLogic Level 3.3V↔5VESP32 ↔ Relay safe commsPowerUSB-C 5V 3ARPi supply
ESP32 ↔ RPi communication: WiFi + MQTT (Mosquitto broker on RPi)

Tech Stack
Firmware (ESP32)

Arduino IDE, C++
Libraries: PubSubClient (MQTT), DHT, LiquidCrystal_I2C, WiFi.h

Backend (RPi — Python 3.11)

FastAPI (async) + Uvicorn
SQLAlchemy 2.0 (async) + Alembic migrations
PostgreSQL 15 (DB), Redis 7 (cache)
aiomqtt 2.x (MQTT bridge)
DeepFace (Facenet, 128-d) + opencv-python-headless — RPi only; Docker uses stub
APScheduler (alert engine, mock sensor, periodic jobs)
httpx (Moodle + Ollama REST client)
Ollama → phi3-mini LLM (local, no API key)

Frontend (React 18 + Vite)

TailwindCSS v3 + CSS custom properties (tokens.css)
DM Sans (headings 600/700) + Inter (body 400/500)
Recharts — AreaChart + linearGradient sparklines
Native WebSocket via custom hook
axios HTTP client

Infrastructure (Docker Compose)
ServiceImagePortPostgreSQL 15postgres:15—Redis 7redis:7—Mosquitto 2eclipse-mosquitto:21883Backendcustom8000Frontend (nginx)custom3000Ollamaollama/ollama:latest11434Moodle 4.x (optional)bitnami/moodle:48080
Docker Quick Start
bashdocker compose up -d                              # full stack
MOCK_MODE=true docker compose up -d              # without ESP32
docker compose --profile moodle up -d            # with Moodle
docker compose exec backend python seed.py        # seed 35 students, 6 courses, 30 sessions, 5 professors
# Manual at-risk pipeline trigger:
docker compose exec backend python -c "import asyncio; from app.services.at_risk_engine import run_at_risk_pipeline; asyncio.run(run_at_risk_pipeline())"
URLServicehttp://localhost:3000React dashboardhttp://localhost:8000/docsFastAPI Swagger UIhttp://localhost:8000/healthHealth checkhttp://localhost:1883Mosquitto MQTThttp://localhost:11434Ollama LLM APIhttp://localhost:8080Moodle (optional)

MQTT Topic Schema
Pattern: classroom/{room_id}/... (default: room1)
TopicDirectionPayload.../sensors/temperatureESP32 → RPi{"value":24.5,"unit":"C","ts":...} every 5s.../sensors/humidityESP32 → RPi{"value":62.1,"unit":"%","ts":...} every 5s.../sensors/air_qualityESP32 → RPi{"value":320,"unit":"ppm","ts":...}.../sensors/soundESP32 → RPi{"value":1,"unit":"bool","ts":...} (1=detected).../relay/acRPi → ESP32{"action":"on|off|auto"}.../relay/lightingRPi → ESP32{"action":"on|off|auto"}.../statusESP32 → RPi{"online":true,"ts":...} every 30s.../alertsRPi → ESP32{"type":"temp_high","value":36} → LCD

Database Schema
professors
id (UUID PK), name, email (UNIQUE), hashed_password (bcrypt), role (ENUM: professor|admin), created_at
students
id (UUID PK), name, student_id (UNIQUE institutional), created_at
courses
id (UUID PK), code (UNIQUE), professor_id (FK→professors, nullable), name, professor_name
sessions
id (UUID PK), course_id (FK), room_id, started_at, ended_at (nullable), status (ENUM: active|ended|upcoming)
display_status — computed, not stored: live = active + started_at ≤ now | upcoming = status==upcoming | done = ended
attendance_records
id (UUID PK), session_id (FK), student_id (FK), status (ENUM: present|absent|late|excused), detected_at, adjusted_by (nullable), adjusted_at (nullable), moodle_synced (BOOL default false)
face_encodings
id (UUID PK), student_id (FK), encoding (BYTEA — serialized 128-d float32 numpy array), created_at
sensor_readings
id (UUID PK), room_id, sensor_type (ENUM: temperature|humidity|air_quality|sound), value (FLOAT), unit, recorded_at
alerts
id (UUID PK), room_id, type (ENUM: temp_high|temp_low|air_quality_high|attendance_anomaly|device_offline), value (FLOAT nullable), message (TEXT), acknowledged (BOOL default false), created_at
at_risk_explanations (Phase 19)
id (UUID PK), student_id (FK → students ON DELETE CASCADE), overall_attendance_rate (FLOAT), summary_explanation (TEXT — LLM narrative), per_course_data (JSONB — array of per-course stats + explanation), generated_at (TIMESTAMP), ollama_reachable (BOOL)
Index: UNIQUE on student_id; upserted on every pipeline run.
attendance_forecasts (Phase 21)
id (UUID PK), course_id (FK → courses ON DELETE CASCADE, UNIQUE), trend_data (JSONB — array of {session_date, rate} points), expected_next_rate (FLOAT nullable), trend_classification (VARCHAR(30) nullable — steady_decline|accelerating_decline|stable|recovering), confidence_level (VARCHAR(10) nullable — low|medium|high), interpretation (TEXT nullable — LLM prose), suggested_action (VARCHAR(30) nullable — monitor_closely|consider_intervention|on_track), ollama_reachable (BOOL), generated_at (TIMESTAMP)
Index: UNIQUE on course_id; upserted on every pipeline run. VARCHAR used (not PG ENUM) to avoid non-transactional ALTER TYPE DDL on schema evolution.

API Endpoints
Sensors

GET /api/sensors/latest — latest from Redis
GET /api/sensors/history?room_id&type&from&to
GET /api/sessions/{id}/sensors/latest — per-type within session window
GET /api/sessions/{id}/sensors/summary — avg/min/max (HTTP 400 if session not ended)

Sessions

POST /api/sessions/start — {course_id, room_id}
POST /api/sessions/{id}/end
GET /api/sessions (filtered list)
GET /api/sessions/{id}

Control

POST /api/control/ac — {room_id, action: on|off|auto} → MQTT + Redis
POST /api/control/lighting — same pattern
GET /api/control/status/{room_id} — relay states + live sensors + device_online

Alerts

GET /api/alerts?room_id&acknowledged&limit=50
PATCH /api/alerts/{id}/acknowledge
GET /api/alerts/unread-count/{room_id}

Courses

GET /api/courses, POST /api/courses, GET /api/courses/{id}
POST /api/courses/{id}/enroll — {student_ids: [...]}

Attendance

GET /api/sessions/{id}/attendance
PATCH /api/attendance/{record_id} — manual adjustment
POST /api/sessions/{id}/mark-absent — bulk absent fill
GET /api/students/{id}/attendance-history

Enrollment

GET /api/students, POST /api/students
POST /api/students/{id}/enroll-face — upload image → compute encoding
GET /api/students/{id}/courses

At-Risk (Phase 19)

GET /api/at-risk — list at-risk students (< 70%) with latest explanation; professor-filtered by course; ?course_id= param
GET /api/at-risk/{student_id} — full summary + per-course breakdown
POST /api/at-risk/recompute — admin only; fires pipeline, returns 202

Forecasting (Phase 21)

GET /api/forecasting — list all course forecasts; professor-filtered; ?course_id= param; fires pipeline in background
GET /api/forecasting/{course_id} — single course forecast; 403 if not professor's course
POST /api/forecasting/recompute — admin only; bypasses Redis lock, fires pipeline immediately, returns 202

Laptop Mode (Webcam)

GET /api/webcam/encodings — face encodings for all enrolled students (for laptop_recognition.py)
POST /api/webcam/attendance — {student_id, status: present|absent, confidence} — no cooldown; respects adjusted_by
POST /api/webcam/start-recognition — spawn laptop_recognition.py subprocess; stops backend recognition loop
POST /api/webcam/stop-recognition — terminate subprocess
GET /api/webcam/recognition-status — {running, pid}

WebSocket

WS /ws/classroom/{room_id} — streams sensor updates, attendance events, alerts


Environment Variables
envDATABASE_URL=postgresql+asyncpg://smartcam:smartcam@postgres:5432/smartclassroom
REDIS_URL=redis://redis:6379
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=your_moodle_token_here
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=phi3:mini
SECRET_KEY=changeme-use-a-long-random-string-in-production
ROOM_ID=room1
MOCK_MODE=false                      # true = fake sensor MQTT without ESP32
FACE_RECOGNITION_ENABLED=false       # true only on RPi with DeepFace installed
ACCESS_TOKEN_EXPIRE_MINUTES=480
REQUIRE_AUTH=false                   # set true in production
TEMP_AC_ON_THRESHOLD=28
TEMP_AC_OFF_THRESHOLD=22
AIR_QUALITY_ALERT_THRESHOLD=500
FACE_RECOGNITION_THRESHOLD=0.40
RECOGNITION_FPS=2
AT_RISK_THRESHOLD=0.70
FORECAST_WINDOW=8                    # number of past ended sessions to include in trend
ATTENDANCE_CYCLE_DURATION=60         # seconds per scan→evaluate cycle (snapshot-per-cycle model)

Auto-Control Rules
SensorConditionActionTemperature> 28°C + AC in auto modeTurn AC ONTemperature< 22°C + AC in auto modeTurn AC OFFAir quality> 500 ppmSend alert (no relay — no ventilation wired)SoundSilent > 30 min in active sessionSend attendance anomaly alertOccupancyheadcount > recognized_faces + 2Flag discrepancy for professor

Face Recognition Logic
Enrollment: Up to 5 images → Facenet 128-d encoding per image → averaged → stored as float32 BYTEA.
Recognition loop — snapshot-per-cycle model (recognition_loop.py):
  SCAN phase (ATTENDANCE_CYCLE_DURATION seconds at RECOGNITION_FPS): collect set of recognised student IDs (seen_this_cycle). WS event fired on first detection per student per cycle.
  EVALUATE phase (one transaction): for every enrolled student — in seen_this_cycle → absent→present; not in set → present→absent. Records where adjusted_by IS NOT NULL are never touched.
  Threshold: cosine distance < 0.40 (tightened from 0.60). UNKNOWN faces increment occupancy counter.
  On session end: final evaluation runs with partial seen_this_cycle before loop stops.
Stub Mode (FACE_RECOGNITION_ENABLED=false)

Enrollment stores zeroed 128-d float32 placeholder.
_stub_recognition_loop picks ~70% ± 2 of enrolled students randomly each cycle, calls _run_cycle_evaluation — exercises full bidirectional present↔absent logic.
reload_encodings() is a no-op.

Laptop Mode (laptop_recognition.py + webcam API)
Host-side DeepFace script for development without an RPi camera. Fetches encodings via GET /api/webcam/encodings, posts status changes via POST /api/webcam/attendance.
Key behaviours:
  All enrolled students pre-seeded in last_seen at startup with ts = now − ABSENT_TIMEOUT so any student the camera doesn't see in the first pass is immediately marked absent.
  last_posted_status deduplicates posts — only POSTs when status transitions (absent→present or present→absent).
  ABSENT_TIMEOUT=5s: student absent from frame for 5s → POST absent.
When Dashboard "Start Recognition" button is clicked: backend recognition loop (stub or real) is stopped first so the two systems never compete.
webcam.py attendance endpoint: no Redis cooldown (last_posted_status is the dedup layer); respects adjusted_by IS NOT NULL (never overwrites professor manual adjustments).


Mock Sensor Logic (MOCK_MODE=true)
APScheduler job publishes MQTT every 5s:

Temperature: 22–32°C (sine wave + noise)
Humidity: 45–70%
Air quality: 200–550 ppm (occasional spike above 500 threshold)
Sound: 70% detected / 30% quiet
Heartbeat: every 30s

Frontend fallback: If no WS sensor data within 8s of connecting, useLiveSensors.js activates client-side mock generator + renders DemoModeBanner. Works even when backend is fully offline.

At-Risk Explanation Pipeline (Phases 19 & 20)
Trigger
Fired on-demand when GET /api/at-risk is called → asyncio.create_task(run_at_risk_pipeline()). Redis lock at_risk:pipeline:lock (TTL 600s, not deleted on completion) prevents concurrent runs and enforces ~10-min cooldown between invocations.
Pipeline Steps

Identify at-risk students only — query students below AT_RISK_THRESHOLD (avoids iterating all 35+)
Skip fresh explanations — skip students with generated_at < 600s old and ollama_reachable=true
Build profile per student — batched queries:

One query: all attendance records + session/course context
One batch JOIN query: avg temp + air quality across all missed sessions, grouped by course_id
One GROUP BY query: peer attendance rate per enrolled course


One LLM call per student — compact multi-course prompt → 3–4 sentence cross-course prose summary
Upsert at_risk_explanations; remove stale rows for students who recovered above threshold

Prompt Constraints (phi3-mini, ~4k context)

Under 500 tokens per prompt
Reference only data provided
Never mention health, personal life, family, psychology
No blame or evaluative judgments
Plain prose only, under 100 words

Performance (Phase 20 optimizations)
MetricBeforeAfterStudents iteratedAll 35At-risk only ~8Sensor queries/studentN missed sessions × 21 batch JOINPeer-rate queries/student1 per course1 GROUP BYOllama calls/studentcourses + 1 (~7)1HTTP connectionsNew TCP per callShared AsyncClientRuntime (8 students)~14–16 min~2–3 min
Ollama Docker Service
Model persisted in named volume ollama_data. On backend startup: checks GET /api/tags; if model absent, fires POST /api/pull as non-blocking background task.
Frontend

Auto-polls every 8s while any student has generated_at=null, stops when all populated.
If ollama_reachable=false → amber warning card "AI explanation unavailable".
Admin-only "Recompute Now" button → spinner → refreshes list after 3s.


At-Risk Page — Frontend Specification

Route: /at-risk | Nav: "At-Risk" with warning triangle SVG icon
Access: All professors (filtered to their courses) + admins (all students)

Left panel (~320px): Scrollable student cards sorted by overall_attendance_rate ascending (worst first). Each card: name, student ID, colored % badge (red < 50%, amber 50–69%), "Updated X ago".
Right panel (detail): Student header → LLM summary card → per-course expandable cards (collapsed: code + name + rate pill; expanded: sessions_total, sessions_missed, avg_temp_on_missed, avg_aq_on_missed, peer delta, per-course text) → "Updated [relative time]" footer.
Empty states: No at-risk students → illustrated "All students on track". Null explanation (Ollama down) → amber card with retry message. Admin recompute button with spinner.

Forecasting Pipeline (Phase 21)
Trigger
Fired on-demand when GET /api/forecasting is called → asyncio.create_task(_maybe_run_pipeline()). Redis lock forecast:pipeline:lock (TTL 1800s / 30 min, SET NX EX) prevents pile-ups. POST /api/forecasting/recompute (admin only) bypasses the lock.
Pipeline Steps

Query all courses with ended-session count in one JOIN query
Skip fresh rows — skip if generated_at < 1800s old and ollama_reachable=true
Courses with < 3 ended sessions → write marker row (trend_data=[], generated_at=now()) so frontend polling terminates
Compute trend data — single GROUP BY query: last FORECAST_WINDOW sessions, present+late / enrolled per session
Classify trend deterministically — mean delta of attendance-rate sequence: < -0.02 → decline (accelerating if second half worsens); > +0.015 → recovering; else stable
Call Ollama once per course — 2-line prompt response: EXPECTED_NEXT: <int> + INTERPRETATION: <sentence>
Upsert attendance_forecasts

Trend Classification Logic (deterministic)
rates = chronological list of 0.0–1.0 fractions; deltas = consecutive differences
mean_delta < -0.02: steady_decline (or accelerating_decline if second-half deltas are > 0.01 worse than first half)
mean_delta > +0.015: recovering
else: stable
Confidence: high ≥ 6 sessions, medium ≥ 4, low < 4

Reuses call_ollama and _check_ollama_ready from at_risk_engine directly — no duplication of Ollama HTTP logic.

Forecasting Page — Frontend Specification

Route: /forecasting | Nav: "Forecasting" with trend arrow SVG icon
Access: All professors (filtered to their courses) + admins (all courses)

Left panel (~320px): Scrollable course cards sorted by severity (accelerating_decline first). Each card: monospace course code, classification badge, course name, last attendance rate chip, "Updated X ago".
Right panel (detail): Course header → Recharts AreaChart (linearGradient fill, 70% dashed ReferenceLine, optional projected "Next" point) → 3-col stats grid (sessions analyzed, expected next rate, confidence) → LLM interpretation glass-card → action banner (color-coded by suggested_action) → admin Recompute button.
Empty states: No selection → prompt. Generating (null generated_at) → spinner. Insufficient history → informational card. Ollama down → amber warning.
Auto-polls every 8s while any course has generated_at=null; stops when all populated.

Phase Completion Status
PhaseDescriptionStatus0Project scaffolding, Docker Compose, env setup✅1ESP32 firmware — sensors + MQTT publish✅2Backend foundation — FastAPI, DB models, MQTT bridge✅3Face recognition service + enrollment API✅4Session management + attendance engine✅5Control API + alert engine✅6Moodle sync service✅7WebSocket live streaming✅8React frontend✅9Integration testing + documentation✅10Full Docker deployment — nginx, Mosquitto, service wiring✅11Mock data fallback — backend publisher + frontend demo mode✅12Raspberry Pi setup runbook✅13Demo data seed script✅14JWT auth, professors table, role-based API filtering✅15Docker image slim — DeepFace/TF removed, stub, seed.py self-migrating✅16Professor Dashboard — session list + attendance table + sensor sparklines✅17Dashboard bug fixes — total_enrolled, key-based tab reset, count badges, MOCK_MODE✅18Full frontend visual redesign — CSS token system, typography, blue sidebar, Soft Structuralism✅19At-Risk Explanation — Ollama/phi3-mini, pipeline, DB table, At-Risk page✅20At-Risk pipeline performance — on-demand trigger, N+1 elimination, 1 LLM call/student, Redis cooldown, frontend auto-poll✅21LLM-Assisted Forecasting — deterministic trend classification + Ollama interpretation per course, attendance_forecasts table, Forecasting page with Recharts trend chart✅22Snapshot-per-cycle attendance — bidirectional present↔absent evaluation every ATTENDANCE_CYCLE_DURATION seconds; laptop_recognition.py two-system conflict resolved; adjusted_by guard; recognition threshold tightened to 0.40✅

Key Architectural Decisions (selected highlights)
DecisionReasonFastAPI over FlaskNative async for WebSocket + MQTTAll services on RPi (no cloud)Avoid latency, cost, internet dependencyasyncio-mqtt → aiomqttpaho-mqtt v2 broke asyncio-mqttDeepFace → stub in DockerTF pulls ~600MB, causes OOM on dev laptopsRedis for live sensor stateInstant dashboard load, no PostgreSQL hitdisplay_status computed, not storedLiveness changes over time with no DB writetokens.css separate from index.cssTailwind v3 can't resolve CSS vars at build timeGlassmorphism removedGPU-expensive, rendering artifacts in ChromiumInline SVG iconsNo icon library dependency, only 10–12 icons neededper_course_data as JSONBAlways read/written as unit with parent; avoids join; atomic upsertRedis lock TTL not deleted on completionPrevents re-run on every page refresh; natural ~10-min cooldown1 LLM call/student (not N+1)Reduced runtime from ~14 min to ~2–3 min for 8 studentsJWT in localStorageAcceptable on university intranet; simpler than httpOnly cookiesOn-demand pipeline (no cron)Cron meant no explanations until 02:00; on-demand generates immediately on page openDeterministic trend classification (no LLM)LLM output format is unreliable for structured values; delta math is fast and always correctVARCHAR(30) not PG ENUM for classificationALTER TYPE ADD VALUE is non-transactional in PostgreSQL; VARCHAR avoids DDL migrations on schema evolutionMarker rows for courses with < 3 sessionsWithout a row the frontend poll condition (some c => !c.generated_at) never resolves; marker rows terminate the poll immediately1 LLM call per course (interpretation only)Classification and confidence are computed deterministically; LLM writes only prose + projected rateSnapshot-per-cycle attendance (not one-shot)One-shot model couldn't detect students leaving mid-session; bidirectional UPDATE with adjusted_by guard gives accurate continuous evaluationNo Redis cooldown in webcam.py attendance endpointlast_posted_status in laptop_recognition.py is the dedup layer; backend cooldown silently dropped present→absent transitions and had no retry pathStop backend loop when laptop_recognition.py startsTwo competing writers to attendance_records caused random stub overrides; mutual exclusion enforced at subprocess spawn timePre-seed last_seen at laptop_recognition.py startupStudents marked present by prior systems (stub loop) were never in last_seen so timeout never fired; seeding with now−ABSENT_TIMEOUT gives immediate absent-marking for undetected students

Known Issues & Limitations
IssueWorkaroundCamera fails on non-PiStub mode replaces recognition loop transparentlyMQ-135 uncalibratedValues are comparative; threshold empirically set at 500DeepFace inference slow on RPi 4Keep RECOGNITION_FPS=2; upgrade to RPi 5 for better throughputMQTT QoS 0 (sensor loss during broker restart)Dashboard shows stale Redis data until next messageSingle-room designChange ROOM_ID in config.h + .envNo HTTPS/WSSAdd nginx SSL termination for public deploymentphi3-mini slow on RPi CPU (~10–30s/student)Frontend progressive polling every 8sphi3-mini first-run pull (~2GB)Startup pull non-blocking; re-open page after pull completes

Future Work
Multi-room support, React Native mobile app, IR illuminator for low-light face recognition, email/SMS alerts, QR-code student self-enrollment, attendance analytics dashboard, CO₂ sensor calibration (SCD30/MH-Z19), offline SQLite fallback, daily at-risk email digest, quantized GGUF model via llama.cpp for faster RPi inference.