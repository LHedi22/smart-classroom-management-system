# Claude Code Phase Prompts
# Smart Classroom Management System — SMU ISS Project 2026
#
# HOW TO USE:
# 1. Open Claude Code in your project root (where CLAUDE.md lives)
# 2. Start each phase by pasting the prompt below exactly as written
# 3. At the end of each phase, update CLAUDE.md (Phase Completion Status table)
# 4. Do NOT start the next phase until the current one is fully working
# 5. If Claude Code asks a clarifying question, answer it — do not skip it
# ─────────────────────────────────────────────────────────────────────────────

══════════════════════════════════════════════════════════════════════════════
PHASE 0 — Project Scaffolding & Infrastructure
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything.

Set up the complete project scaffold for the Smart Classroom Management System.
Do the following in order:

1. Create the full directory structure exactly as specified in the "Repository Structure"
   section of CLAUDE.md. Create placeholder files where needed (empty __init__.py,
   .gitkeep, etc.).

2. Create docker-compose.yml that starts three services:
   - PostgreSQL 15 on port 5432, database "smartclassroom", user/pass "smartcam/smartcam"
   - Redis 7 on port 6379
   - Moodle 4.x using the bitnami/moodle Docker image on port 8080, with a MariaDB
     sidecar. Set MOODLE_USERNAME=admin, MOODLE_PASSWORD=admin123.

3. Create .env.example with all variables from the "Environment Variables" section of
   CLAUDE.md. Create a .env copy of it for local development.

4. Create backend/requirements.txt with pinned versions for:
   fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, redis,
   asyncio-mqtt, face_recognition, opencv-python-headless, numpy, httpx,
   apscheduler, python-dotenv, pydantic-settings, pillow

5. Create frontend/package.json with dependencies:
   react, react-dom, react-router-dom, axios, recharts, tailwindcss, vite,
   @vitejs/plugin-react, autoprefixer, postcss

6. Create a root Makefile with targets:
   - `make up` → docker-compose up -d
   - `make down` → docker-compose down
   - `make backend` → cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   - `make frontend` → cd frontend && npm run dev
   - `make install` → pip install -r backend/requirements.txt && cd frontend && npm install

7. Create README.md with: project title, one-paragraph description, prerequisites
   (Docker, Python 3.11, Node 18), and setup instructions using the Makefile.

8. Create a .gitignore that covers Python, Node, Arduino, and environment files.

After completing all steps, run `docker-compose config` to validate the compose file
and report any errors. Update CLAUDE.md Phase 0 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 1 — ESP32 Firmware
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 0 must be complete.

Write the complete ESP32 Arduino firmware in firmware/classroom_node/.

Create firmware/classroom_node/config.h:
- WiFi SSID and password (use placeholders: "YOUR_WIFI_SSID", "YOUR_WIFI_PASSWORD")
- MQTT broker IP (placeholder: "192.168.1.100"), port 1883
- Room ID: "room1"
- Sensor pins: DHT21 on GPIO 4, MQ135 on GPIO 34 (ADC), Sound sensor on GPIO 35 (ADC)
- Relay pins: AC relay on GPIO 26, Lighting relay on GPIO 27
- LCD I2C address: 0x27

Create firmware/classroom_node/classroom_node.ino with the following behavior:

SETUP:
- Initialize Serial at 115200 baud
- Connect to WiFi with retry loop (attempt every 5s, print dots)
- Connect to MQTT broker with client ID "esp32-room1", retry on disconnect
- Initialize DHT21 sensor
- Initialize LCD 16x2 via I2C and show "Smart Classroom" on line 1, "Connecting..." on line 2
- Subscribe to topics: classroom/room1/relay/ac and classroom/room1/relay/lighting
- On successful MQTT connect: update LCD line 2 to "Online"

MAIN LOOP (every 5 seconds):
- Read DHT21: temperature (°C) and humidity (%)
- Read MQ135: raw ADC value (0-4095)
- Read sound sensor: digital HIGH/LOW
- Publish each reading to its MQTT topic as JSON:
  {"value": X, "unit": "C", "ts": millis()}
  Use topics exactly as defined in CLAUDE.md MQTT Schema section.
- Update LCD line 1: "T:24.5C H:62%" (formatted)
- Update LCD line 2: "AQ:320 Snd:1"

MQTT CALLBACK (relay commands):
- On message to classroom/room1/relay/ac: parse JSON "action" field
  - "on" → digitalWrite relay AC pin HIGH
  - "off" → digitalWrite relay AC pin LOW
  - "auto" → set a flag, let threshold logic in loop handle it
- Same logic for classroom/room1/relay/lighting
- Print action to Serial for debugging

HEARTBEAT (every 30 seconds):
- Publish {"online": true, "ts": millis()} to classroom/room1/status

LIBRARIES NEEDED (add a comment block at the top listing them):
PubSubClient, DHT sensor library, LiquidCrystal_I2C, ArduinoJson, WiFi

Also create firmware/classroom_node/README.md explaining:
- How to install required libraries in Arduino IDE
- How to set the correct board (ESP32 Dev Module) and upload settings
- How to configure config.h before flashing

══════════════════════════════════════════════════════════════════════════════
PHASE 2 — Backend Foundation (FastAPI + DB + MQTT Bridge)
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phases 0 and 1 must be complete.

Build the backend foundation. All code goes in backend/app/.

STEP 1 — Config & database setup:
- backend/app/config.py: Pydantic Settings class that reads all variables from
  .env as defined in CLAUDE.md. Include all thresholds as typed fields.
- backend/app/database.py: SQLAlchemy async engine + session factory using
  DATABASE_URL from config. Provide get_db() async dependency.
- backend/app/redis_client.py: Redis async client using REDIS_URL from config.
  Provide get_redis() dependency and helper functions:
  set_sensor_latest(room_id, sensor_type, value, unit) and
  get_sensor_latest(room_id) → dict of all sensor types.

STEP 2 — Database models:
Create backend/app/models/db_models.py with SQLAlchemy ORM models for ALL
tables defined in the "Database Schema" section of CLAUDE.md. Use:
- UUID primary keys (server_default=text("gen_random_uuid()"))
- Proper relationships and foreign keys
- Enums for status fields (use Python Enum + SQLAlchemy Enum type)
- created_at with server_default=func.now()

Create backend/app/models/schemas.py with Pydantic v2 schemas for every model
(base, create, response variants). Include validators where appropriate.

STEP 3 — Alembic setup:
- Run `alembic init alembic` in the backend/ directory
- Configure alembic.ini to use DATABASE_URL from .env
- Configure alembic/env.py to use the SQLAlchemy metadata from db_models.py
- Create the initial migration: `alembic revision --autogenerate -m "initial"`
- DO NOT run the migration yet — just create the file

STEP 4 — MQTT bridge service:
Create backend/app/services/mqtt_bridge.py:
- AsyncIO MQTT client that connects to Mosquitto broker on startup
- Subscribes to: classroom/+/sensors/# and classroom/+/status
- On receiving a sensor message:
  1. Parse JSON payload
  2. Write to Redis via set_sensor_latest()
  3. Write a SensorReading row to PostgreSQL (async, fire-and-forget)
  4. Put the event on an asyncio.Queue named sensor_event_queue (for WebSocket)
- On receiving a status message:
  1. Update a Redis key "classroom:{room_id}:online" with TTL 60s
- Handle connection errors gracefully with exponential backoff retry

STEP 5 — FastAPI main app:
Create backend/app/main.py:
- FastAPI app with title "Smart Classroom API"
- Include CORS middleware (allow all origins for development)
- On startup: run alembic upgrade head, start mqtt_bridge as background task
- On shutdown: stop mqtt_bridge cleanly
- Mount all routers from backend/app/api/ (create empty stub files for each:
  sensors.py, attendance.py, control.py, sessions.py, alerts.py,
  enrollment.py, websocket.py)
- Add a GET /health endpoint that returns {"status": "ok", "redis": bool, "db": bool}

STEP 6 — Sensor API (first real endpoint):
In backend/app/api/sensors.py:
- GET /api/sensors/latest?room_id=room1 → reads from Redis, returns all sensor values
- GET /api/sensors/history → query params: room_id, sensor_type, from_ts, to_ts, limit=100
  Returns paginated SensorReading records from PostgreSQL

Test: start the backend with `uvicorn app.main:app --reload` from the backend/
directory and verify /health returns 200 and /docs loads the OpenAPI UI.
Fix any import or startup errors before marking this phase complete.
Update CLAUDE.md Phase 2 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 3 — Face Recognition Service & Enrollment API
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 2 must be complete and
the backend must start without errors.

Build the face recognition system.

STEP 1 — Face recognition service:
Create backend/app/services/face_recognition_service.py:

Class FaceRecognitionService with:

__init__:
- Load all face encodings from PostgreSQL into memory as a dict:
  {student_id: numpy_array_128d}
- Store as self.known_encodings

async reload_encodings():
- Re-query PostgreSQL and refresh self.known_encodings
- Call this after any new enrollment

recognize_faces(frame: np.ndarray) -> list[dict]:
- Input: BGR frame from OpenCV
- Resize frame to 50% for speed
- Detect face locations using face_recognition.face_locations()
- Compute face encodings for detected faces
- For each encoding, compare to self.known_encodings using
  face_recognition.face_distance() (NOT compare_faces)
- If minimum distance < FACE_RECOGNITION_THRESHOLD (from config):
  return matched student_id
- Else: return "UNKNOWN"
- Return list of: {"student_id": str|"UNKNOWN", "confidence": float,
  "location": [top, right, bottom, left]}

count_heads(frame: np.ndarray) -> int:
- Use OpenCV HOG people detector (cv2.HOGDescriptor_getDefaultPeopleDetector)
  as a fallback occupancy count
- Return integer count of detected people

STEP 2 — Recognition loop (background task):
Create backend/app/services/recognition_loop.py:
- Background task that runs when a session is active
- Opens RPi camera (cv2.VideoCapture(0))
- Captures frame every 0.5s (2fps)
- Calls FaceRecognitionService.recognize_faces()
- For each recognized student_id (not UNKNOWN):
  - Check if already marked present in current session (30s cooldown)
  - If not: create AttendanceRecord with status=present
  - Put event on attendance_event_queue for WebSocket
- Cross-check: if count_heads() > recognized_count + 2: put anomaly alert on alert_queue
- Expose: start_recognition(session_id), stop_recognition()
- Handle camera not available gracefully (log warning, don't crash)

STEP 3 — Enrollment API:
In backend/app/api/enrollment.py implement:

POST /api/students
- Body: {name: str, student_id: str}
- Creates Student record
- Returns created student

GET /api/students
- Returns list of all students with their enrolled status

POST /api/students/{id}/enroll-face
- Accepts multipart form: images[] (up to 5 image files)
- For each image: decode to numpy array, compute 128-d encoding
- Average all encodings into one vector
- Serialize with numpy (tobytes()) and store in face_encodings table
- Call FaceRecognitionService.reload_encodings()
- Return {"enrolled": true, "student_id": id}

GET /api/students/{id}
- Returns student with enrollment status

STEP 4 — Integration test:
Write backend/tests/test_face_enrollment.py:
- Test that POSTing a student creates the DB record
- Test that uploading a face image creates a face_encoding record
- Use pytest with pytest-asyncio
- Mock the face_recognition library calls (do not require a real camera)

Run tests with `pytest backend/tests/` and fix any failures.
Update CLAUDE.md Phase 3 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 4 — Session Management & Attendance Engine
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 3 must be complete.

Build session management and the full attendance API.

STEP 1 — Sessions API:
In backend/app/api/sessions.py implement:

POST /api/sessions/start
- Body: {course_id: UUID, room_id: str}
- Check no other session is active for that room
- Create Session record with status=active, started_at=now()
- Start the recognition loop background task (recognition_loop.start_recognition)
- Return created session

POST /api/sessions/{id}/end
- Set session.ended_at=now(), status=ended
- Stop the recognition loop (recognition_loop.stop_recognition)
- Return updated session

GET /api/sessions
- Query params: room_id, status, course_id
- Returns list of sessions with attendance summary (present_count, total_students)

GET /api/sessions/{id}
- Returns session detail with full attendance list

STEP 2 — Attendance API:
In backend/app/api/attendance.py implement:

GET /api/sessions/{id}/attendance
- Returns all AttendanceRecord rows for the session
- Include student name and student_id from join

PATCH /api/attendance/{record_id}
- Body: {status: "present"|"absent"|"late"|"excused"}
- Updates the record, sets adjusted_by="professor", adjusted_at=now()
- Returns updated record

POST /api/sessions/{id}/attendance/mark-absent
- For all enrolled students NOT yet in attendance_records for this session:
  create records with status=absent
- Called when session ends to ensure all students have a record

GET /api/students/{id}/history
- Returns all attendance records for a student across all sessions
- Include session and course info from joins

STEP 3 — Courses API (needed for session creation):
In backend/app/api/sessions.py also add:

GET /api/courses → list all courses
POST /api/courses → body: {code, name, professor_name}
POST /api/courses/{id}/enroll → body: {student_ids: [UUID]} → enroll students

(Create a course_students association table if not already in the schema.
Add it to db_models.py and create a new Alembic migration.)

STEP 4 — Attendance event queue integration:
In backend/app/services/recognition_loop.py (update from Phase 3):
- After creating an AttendanceRecord, put this event on the shared
  attendance_event_queue:
  {"type": "attendance", "student_id": str, "student_name": str,
   "status": "present", "session_id": str, "ts": ISO timestamp}

STEP 5 — Alembic migration:
If you added the course_students table, run:
`alembic revision --autogenerate -m "add course students association"`
Commit the migration file.

Test: manually call POST /api/courses, POST /api/students, enroll students,
start a session, and verify the session is created and recognition loop starts.
Update CLAUDE.md Phase 4 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 5 — Control API & Alert Engine
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 4 must be complete.

Build the relay control system and the alert engine.

STEP 1 — Control API:
In backend/app/api/control.py implement:

POST /api/control/ac
- Body: {room_id: str, action: "on"|"off"|"auto"}
- Publish MQTT message to classroom/{room_id}/relay/ac with {"action": action}
- Update Redis key "classroom:{room_id}:relay:ac" with the action
- Return {"room_id": str, "device": "ac", "action": action, "ts": datetime}

POST /api/control/lighting
- Same pattern for lighting relay

GET /api/control/status/{room_id}
- Read from Redis: current relay states + latest sensor values
- Return {"ac": "on"|"off"|"auto", "lighting": "on"|"off"|"auto",
  "temperature": float, "humidity": float, "air_quality": float}

STEP 2 — Alert engine:
Create backend/app/services/alert_engine.py:

Class AlertEngine using APScheduler:

check_thresholds() — runs every 30 seconds:
- Read latest sensor values from Redis for all active rooms
- Apply rules from CLAUDE.md "Auto-Control Rules" section:

  TEMPERATURE rules (only if relay is in "auto" mode):
  - If temp > TEMP_AC_ON_THRESHOLD: publish MQTT ac=on, update Redis
  - If temp < TEMP_AC_OFF_THRESHOLD: publish MQTT ac=off, update Redis

  AIR QUALITY alert:
  - If air_quality > AIR_QUALITY_ALERT_THRESHOLD:
    Create Alert record (type=air_quality_high) if no unacknowledged alert exists
    Put alert event on alert_event_queue

  DEVICE OFFLINE check:
  - If Redis key "classroom:{room_id}:online" is expired (TTL gone):
    Create Alert record (type=device_offline)

check_attendance_anomaly() — called from recognition_loop when triggered:
- Create Alert record (type=attendance_anomaly, message="Headcount mismatch")
- Put alert on alert_event_queue

start() / stop() — lifecycle methods called from main.py startup/shutdown

STEP 3 — Alerts API:
In backend/app/api/alerts.py implement:

GET /api/alerts
- Query params: room_id, acknowledged (bool), limit=50
- Returns list of Alert records ordered by created_at desc

PATCH /api/alerts/{id}/acknowledge
- Sets acknowledged=true, returns updated alert

GET /api/alerts/unread-count/{room_id}
- Returns {"count": int} — used for dashboard badge

STEP 4 — Wire up alert engine in main.py:
- Import AlertEngine
- On startup: create AlertEngine instance, call alert_engine.start()
- On shutdown: call alert_engine.stop()

Test: use the /api/control/ac endpoint to send an on command and verify via
MQTT explorer (or mosquitto_sub on the RPi) that the message arrives.
Manually insert a sensor reading with high temperature and verify an alert
is created after 30 seconds.
Update CLAUDE.md Phase 5 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 6 — Moodle Sync Service
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 5 must be complete.

Build the Moodle integration.

STEP 1 — Moodle client:
Create backend/app/services/moodle_client.py:

Class MoodleClient using httpx.AsyncClient:

__init__:
- Base URL from config.MOODLE_URL
- Token from config.MOODLE_TOKEN
- All requests use ?wstoken={token}&moodlewsrestformat=json

async get_courses() -> list[dict]:
- Call core_course_get_courses Moodle web service function
- Return list of course objects

async get_enrolled_users(course_id: int) -> list[dict]:
- Call core_enrol_get_enrolled_users
- Return list of user objects

async sync_attendance(session_id: UUID) -> dict:
- Fetch all AttendanceRecord rows for the session from DB
- For each record, map our status → Moodle attendance status code:
  present=1, absent=2, late=3, excused=4
- Call mod_attendance_add_attendance Moodle web service
- On success: update all synced records with moodle_synced=true
- On failure: log the error, store failure in session metadata
- Return {"synced": int, "failed": int, "session_id": str}

async test_connection() -> bool:
- Call core_webservice_get_site_info
- Return True if successful

STEP 2 — Sync endpoint:
In backend/app/api/sessions.py add:

POST /api/sessions/{id}/sync-moodle
- Call moodle_client.sync_attendance(session_id)
- Return sync result

POST /api/sessions/{id}/end (update from Phase 4):
- After ending session, automatically trigger sync-moodle
- If sync fails, log the error but do not fail the end-session call

STEP 3 — Moodle setup in Docker:
Add to docs/moodle_setup.md:
- Instructions to get the Moodle web service token:
  1. Log into localhost:8080 as admin
  2. Site Admin → Plugins → Web services → Manage tokens
  3. Create a token for the admin user
  4. Add token to .env as MOODLE_TOKEN
- Instructions to enable web services:
  Site Admin → Advanced features → Enable web services ✓

STEP 4 — Fallback for Moodle down:
In moodle_client.sync_attendance():
- Wrap all HTTP calls in try/except
- If Moodle is unreachable, add the session_id to a Redis retry queue:
  "moodle:retry_queue" (Redis list, RPUSH)
- In AlertEngine, add a job that checks the retry queue every 10 minutes
  and retries failed syncs

Test: start Docker Moodle, obtain a token, set it in .env, call
GET /api/moodle-test (add a temporary test endpoint) and verify connection.
Call sync for a session with attendance records and verify moodle_synced=true.
Update CLAUDE.md Phase 6 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 7 — WebSocket Live Streaming
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 5 must be complete.

Build the real-time WebSocket layer that the frontend will consume.

STEP 1 — Shared event queues:
In backend/app/main.py (or a new backend/app/events.py):
Create three module-level asyncio.Queue instances:
- sensor_event_queue
- attendance_event_queue
- alert_event_queue

These are already referenced in previous phases — wire them up here as the
single shared instances imported by mqtt_bridge, recognition_loop, and alert_engine.

STEP 2 — WebSocket connection manager:
Create backend/app/api/websocket.py:

Class ConnectionManager:
- self.active_connections: dict[str, list[WebSocket]]  # room_id → connections
- async connect(room_id, websocket): add to list, send initial state snapshot
- disconnect(room_id, websocket): remove from list
- async broadcast(room_id, message: dict): send JSON to all connections for room

Initial state snapshot on connect:
- Read latest sensor values from Redis
- Read current relay status from Redis
- Read active session info from DB
- Read unacknowledged alert count
- Send as {"type": "snapshot", "data": {...}}

STEP 3 — WebSocket endpoint:
In backend/app/api/websocket.py implement:

WS /ws/classroom/{room_id}:
- Accept connection via manager.connect()
- Keep connection alive with ping every 30s
- On disconnect: manager.disconnect()

STEP 4 — Event broadcaster background task:
In backend/app/main.py, add a startup background task:
event_broadcaster():
- Runs forever, reads from all three queues
- On sensor event: broadcast to relevant room_id with {"type": "sensor", "data": ...}
- On attendance event: broadcast with {"type": "attendance", "data": ...}
- On alert event: broadcast with {"type": "alert", "data": ...}
- Use asyncio.gather or asyncio.wait with FIRST_COMPLETED to drain all queues

STEP 5 — Test the WebSocket:
Add backend/tests/test_websocket.py:
- Use FastAPI TestClient with websocket context
- Connect to /ws/classroom/room1
- Verify snapshot message is received on connect
- Put a fake event on sensor_event_queue and verify it's broadcast
Run tests and fix failures.
Update CLAUDE.md Phase 7 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 8 — React Frontend
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. Phase 7 must be complete and the
WebSocket endpoint must be working.

Build the complete professor-facing React dashboard.

STEP 1 — Project setup:
In frontend/:
- Initialize Vite React project (already scaffolded in Phase 0)
- Install all dependencies from package.json
- Configure TailwindCSS (tailwind.config.js + postcss.config.js)
- Configure vite.config.js proxy: /api → http://localhost:8000,
  /ws → ws://localhost:8000
- Create frontend/src/api/client.js: axios instance with baseURL=/api

STEP 2 — WebSocket hook:
Create frontend/src/hooks/useLiveSensors.js:
- Connect to /ws/classroom/room1 on mount
- Reconnect automatically on disconnect (3s delay, exponential backoff max 30s)
- Parse incoming JSON messages by type: "snapshot", "sensor", "attendance", "alert"
- Return: {sensors, attendance, alerts, relayStatus, isConnected}
- Handle each message type to update the relevant slice of state

STEP 3 — Dashboard page (main view):
Create frontend/src/pages/Dashboard.jsx:

Left column — Sensor cards (4 cards):
- Temperature card: current value + unit + color indicator (blue<22, green 22-28, red>28)
- Humidity card: current value + %
- Air Quality card: current PPM value + status label (Good/Moderate/Poor)
- Sound card: Active / Quiet indicator

Center column — Live attendance table:
- Columns: Student Name, Student ID, Status badge, Detected At
- Status badges: Present=green, Absent=gray, Late=yellow, Excused=blue
- Unknown detections shown as a count at the bottom: "X unidentified faces"
- Real-time updates via useLiveSensors attendance events

Right column — Controls & Alerts:
- AC control: 3 toggle buttons (On/Off/Auto), current state highlighted
- Lighting control: same pattern
- Alert feed: last 5 alerts with type icon + message + time ago
  (e.g. 🌡 "Temperature exceeded 28°C — 3 min ago")
- Unread badge on Alerts nav link

STEP 4 — Attendance page:
Create frontend/src/pages/Attendance.jsx:
- Session selector at top (dropdown of sessions for today)
- Full attendance table with all fields
- Each row: click status badge to open an inline dropdown
  (Present / Absent / Late / Excused) → calls PATCH /api/attendance/{id}
- Show "Adjusted by professor" label on manually changed records
- Export button: downloads attendance as CSV (client-side, no backend needed)
- "Mark all absent" button for students not yet in the list

STEP 5 — Control page:
Create frontend/src/pages/Control.jsx:
- Large toggle cards for AC and Lighting (On / Off / Auto)
- Auto mode: show the threshold rules ("AC turns on above 28°C")
- Current sensor readings shown inline for context
- Action log: last 10 control actions with timestamp (stored in component state)

STEP 6 — Enrollment page:
Create frontend/src/pages/Enrollment.jsx:
- Left panel: student list with enrolled/not-enrolled status indicator
- Right panel: enrollment form
  - Text fields: Full Name, Student ID
  - "Create Student" button → POST /api/students
  - Once created: show camera capture section
  - Camera preview using getUserMedia (laptop webcam or RPi camera stream)
  - "Capture" button: takes a snapshot, adds to a list of up to 5 captures
  - Thumbnails of captured frames shown below
  - "Enroll Face" button: sends all captured images to
    POST /api/students/{id}/enroll-face as multipart form data
  - Success message on completion

STEP 7 — Session history page:
Create frontend/src/pages/History.jsx:
- Table of all past sessions: Course, Date, Duration, Present %, Moodle Sync status
- Click a row to expand: shows full attendance breakdown for that session
- Moodle sync status shows "Synced ✓" or "Retry" button that calls
  POST /api/sessions/{id}/sync-moodle

STEP 8 — Navigation & layout:
Create frontend/src/components/Layout.jsx:
- Sidebar navigation with links: Dashboard, Attendance, Control, Enrollment, History
- Alert badge on nav (unread count from useLiveSensors)
- Connection status dot (green=connected, red=disconnected) in top right
- SMU logo placeholder + "Smart Classroom" title in sidebar header

STEP 9 — Start session flow:
Add a "Start Session" modal to Dashboard.jsx:
- Button in the header: "Start Session"
- Modal: Course selector (GET /api/courses), Room ID (default: room1)
- "Start" button → POST /api/sessions/start
- Active session banner shown while session is running
- "End Session" button → POST /api/sessions/{id}/end

Test: run `npm run dev` and verify all pages load. Connect to the backend and
verify live sensor data appears on the dashboard if the backend is running.
Update CLAUDE.md Phase 8 status to ✅.

══════════════════════════════════════════════════════════════════════════════
PHASE 9 — Integration Testing & Documentation
══════════════════════════════════════════════════════════════════════════════

Read CLAUDE.md fully before doing anything. All previous phases must be complete.

Final integration, testing, and documentation pass.

STEP 1 — Backend test suite:
Create the following test files using pytest + pytest-asyncio:

backend/tests/test_sensors.py:
- Test GET /api/sensors/latest returns correct structure
- Test GET /api/sensors/history with date filters returns correct records
- Test that writing to Redis and reading back works

backend/tests/test_sessions.py:
- Test POST /api/sessions/start creates a session and returns it
- Test POST /api/sessions/{id}/end updates status to ended
- Test that starting a session when one is already active returns 409

backend/tests/test_attendance.py:
- Test GET /api/sessions/{id}/attendance returns correct records
- Test PATCH /api/attendance/{id} correctly updates status and sets adjusted_by
- Test POST /api/sessions/{id}/attendance/mark-absent creates absent records

backend/tests/test_alerts.py:
- Test alert creation when threshold is exceeded (mock the sensor read)
- Test PATCH /api/alerts/{id}/acknowledge updates the record
- Test GET /api/alerts/unread-count returns correct count

Run full test suite: `pytest backend/tests/ -v`
Fix all failures. Aim for all tests passing before proceeding.

STEP 2 — End-to-end integration test script:
Create backend/tests/e2e_test.py — a manual integration script (not pytest)
that can be run with `python e2e_test.py` to simulate a full class session:
1. Create a course and 3 students via API
2. Start a session
3. Simulate 3 attendance records (POST directly, since we can't use real camera in test)
4. Trigger a high-temperature alert by POSTing a fake sensor reading
5. End the session
6. Verify moodle sync was attempted
7. Print a summary: PASS/FAIL for each step

STEP 3 — Documentation:
Update docs/mqtt_schema.md: complete MQTT topic reference (copy from CLAUDE.md,
add example payloads and notes on QoS settings).

Update docs/api_contracts.md: full API reference — for every endpoint list:
method, path, request body schema, response schema, example request/response.

Create docs/wiring_diagram.md: text-based wiring table showing which GPIO pin
on the ESP32 connects to which component pin, with voltage levels and any
level converter connections.

Create docs/hardware_setup.md: step-by-step RPi setup:
1. OS installation (Raspberry Pi OS Lite 64-bit)
2. Enable camera interface
3. Install Python 3.11 and pip
4. Install system dependencies for face_recognition (cmake, dlib prerequisites)
5. Install Mosquitto and configure as service
6. Clone repo and install Python requirements
7. Configure .env
8. Test camera: python3 -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"

STEP 4 — Final CLAUDE.md update:
Update CLAUDE.md:
- Mark all phases ✅ in the Phase Completion Status table
- Add any new Key Decisions made during development
- Add any schema changes made during implementation that differ from the original plan
- Add a "Known Issues & Limitations" section with any edge cases not fully handled
- Add a "Future Work" section with: multi-room support, mobile app, better
  lighting condition handling for face recognition, email notifications

STEP 5 — Production readiness checklist:
Verify the following and fix any gaps:
- [ ] All .env secrets are in .env.example with placeholder values, not real values
- [ ] No hardcoded IPs or credentials in any source file
- [ ] All database migrations are committed and apply cleanly from scratch
- [ ] `make up && make backend` starts the system without manual intervention
- [ ] The /health endpoint returns {"status": "ok"} with both redis and db true
- [ ] Face recognition threshold and all sensor thresholds are configurable via .env
- [ ] Camera unavailable does not crash the backend (graceful degradation)
- [ ] Moodle unreachable does not crash the session-end flow (retry queue)

Update CLAUDE.md Phase 9 status to ✅.
Commit everything with message: "feat: complete ISS Smart Classroom System"

# ─────────────────────────────────────────────────────────────────────────────
# END OF PHASE PROMPTS
# ─────────────────────────────────────────────────────────────────────────────
#
# TIPS FOR WORKING WITH CLAUDE CODE:
#
# - If Claude Code makes a decision that differs from CLAUDE.md, tell it:
#   "Update CLAUDE.md to reflect this change before continuing."
#
# - If a phase takes more than one session, start the next session with:
#   "Read CLAUDE.md and tell me the current status of the project."
#
# - If something breaks in a later phase, say:
#   "Something broke. Read CLAUDE.md and check Phase X assumptions are still valid."
#
# - After each phase, commit to git:
#   git add . && git commit -m "feat: complete Phase X - [description]"
#
# - If Claude Code gets confused about file locations, say:
#   "Read CLAUDE.md Repository Structure section and verify all files are in
#   the correct locations."
