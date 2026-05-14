# Smart Classroom Management System — Eraser AI Diagrams
# Paste each fenced block (without the header comment) into a separate Eraser canvas

---

## DIAGRAM 1 — Full System Architecture

```
// Smart Classroom Management System — Full System Architecture
// direction: right

// ─── Physical Hardware (Left) ───
ESP32 [icon: cpu, color: orange, label: "ESP32\nSensor Node\nESP-WROOM-32"] {
  DHT21 [icon: thermometer, label: "DHT21\nTemp + Humidity\nGPIO 4"]
  MQ135 [icon: wind, label: "MQ-135\nAir Quality ppm\nGPIO 34 ADC"]
  ACP014 [icon: volume-2, label: "ACP014\nSound Binary\nGPIO 35"]
  LCD [icon: monitor, label: "LCD 16x2 I2C\nLocal Display\nGPIO 21-22"]
  Relay [icon: zap, label: "4-CH Relay\nAC + Lighting\nGPIO 26-27 via LLC"]
}

Camera [icon: camera, color: orange, label: "RPi Camera v2\n8MP MIPI CSI-2\nFace Recognition Input"]

// ─── Raspberry Pi 4B (Centre Hub) ───
RPi4 [icon: server, color: blue, label: "Raspberry Pi 4B — 4GB\nEdge Hub / Docker Host\nAll services on-device\nNo cloud dependency"] {

  Mosquitto [icon: radio, color: orange, label: "Mosquitto 2\nMQTT Broker\nTCP :1883"]

  FastAPI [icon: code, color: blue, label: "FastAPI Backend\nPython 3.11 + Uvicorn\n:8000\n7 Module Groups"] {
    MQTTBridge [icon: git-merge, label: "MQTT Bridge\naiomqtt subscriber\nsensor + status topics"]
    RecognitionLoop [icon: eye, label: "Recognition Loop\nDeepFace FaceNet\n2 fps\nSnapshot-per-cycle 60s"]
    AlertEngine [icon: bell, label: "Alert Engine\nAPScheduler 30s\nThreshold checks\nDeduplication"]
    AIEngine [icon: brain, label: "AI Pipelines\nAt-Risk + Forecasting\nVerification Layer"]
    SessionAPI [icon: users, label: "Session & Attendance\nLifecycle mgmt\nManual override guard"]
    ControlAPI [icon: zap, label: "Control API\nRelay dual-write\nRedis + MQTT"]
    WebSocketLayer [icon: wifi, label: "WebSocket\nWS /ws/classroom/room1\n3 asyncio.Queue fan-out\nSnapshot on connect"]
  }

  Postgres [icon: database, color: blue, label: "PostgreSQL 15\n:5432\n10 tables\nFace embeddings BYTEA\nAttendance records"]
  Redis [icon: database, color: red, label: "Redis 7\n:6379\nSensor cache TTL 300s\nDevice presence TTL 60s\nRelay state\nPipeline locks"]
  Ollama [icon: cpu, color: purple, label: "Ollama\nphi3:mini CPU\n:11434\n~2GB model\nLocal inference only"]
  Nginx [icon: globe, color: green, label: "nginx\nFrontend Server\n:3000\nProxy /api + /ws → :8000"]
}

// ─── End Systems (Right) ───
Browser [icon: monitor, color: purple, label: "Professor\nDashboard\nReact 18 SPA\n9 pages\nWebSocket client"]
Moodle [icon: book-open, color: green, label: "Moodle 4.x\nLMS\n:8080\nAttendance sync\nREST API"]

// ─── Connections: ESP32 → RPi4 ───
DHT21 --> ESP32
MQ135 --> ESP32
ACP014 --> ESP32
ESP32 --> Relay: "GPIO 26-27\nLogic Level Converter\n3.3V → 5V"
ESP32 --> LCD: "I2C"
ESP32 --> Mosquitto: "WiFi 802.11\nMQTT QoS 0\nTCP :1883\nSensors every 5s\nHeartbeat every 30s"
Camera --> RecognitionLoop: "MIPI CSI-2\nOpenCV frames\n2 fps"

// ─── Connections: Inside RPi4 ───
Mosquitto --> MQTTBridge: "subscribed topics\nclassroom/+/sensors/#\nclassroom/+/status"
MQTTBridge --> Redis: "sensor cache SET\nTTL 300s"
MQTTBridge --> Postgres: "INSERT sensor_readings"
MQTTBridge --> WebSocketLayer: "sensor_event_queue"
RecognitionLoop --> Postgres: "INSERT attendance_records"
RecognitionLoop --> WebSocketLayer: "attendance_event_queue"
AlertEngine --> Redis: "read sensor cache"
AlertEngine --> Postgres: "INSERT alerts"
AlertEngine --> WebSocketLayer: "alert_event_queue"
AlertEngine --> Mosquitto: "relay commands\nQoS 1"
Mosquitto --> ESP32: "relay/ac\nrelay/lighting\nQoS 1 acknowledged"
AIEngine --> Postgres: "at_risk_explanations\nattendance_forecasts"
AIEngine --> Ollama: "httpx async\nPOST /api/chat\nshared AsyncClient"
AIEngine --> Redis: "pipeline locks\nTTL 600s / 1800s"
SessionAPI --> Postgres: "sessions\nenrollments"
ControlAPI --> Redis: "relay state\ninstant update"
ControlAPI --> Mosquitto: "relay command\ndevice actuation"
WebSocketLayer --> Nginx: "WS fan-out\nbroadcast to clients"
FastAPI --> Moodle: "REST API\nattendance sync\non session end"
Nginx --> Browser: "HTTP :3000\nReact SPA\nWebSocket"
```

---

## DIAGRAM 2 — IoT Layer: ESP32 Internal Architecture

```
// ESP32 Sensor Node — Internal Firmware Architecture

direction down

SensorAcquisition [icon: refresh-cw, color: orange, label: "Sensor Read Loop\nevery 5 seconds\nArduino loop()"] {
  ReadDHT [icon: thermometer, label: "DHT21 — GPIO 4\n10kΩ pull-up to 3.3V\nReads: Temp °C + Humidity %"]
  ReadMQ [icon: wind, label: "MQ-135 — GPIO 34\nADC1 ch6, input-only\nReads: Air Quality ppm"]
  ReadACP [icon: volume-2, label: "ACP014 — GPIO 35\nDigital input-only\nReads: Sound 1=detected 0=quiet"]
}

MQTTPublisher [icon: send, color: blue, label: "MQTT Publish\nPubSubClient\nQoS 0 — fire and forget"] {
  T [label: "classroom/room1/sensors/temperature\n{value:24.5, unit:'C', ts:...}"]
  H [label: "classroom/room1/sensors/humidity\n{value:62.1, unit:'%', ts:...}"]
  AQ [label: "classroom/room1/sensors/air_quality\n{value:320, unit:'ppm', ts:...}"]
  S [label: "classroom/room1/sensors/sound\n{value:1, unit:'bool', ts:...}"]
  HB [label: "classroom/room1/status\n{online:true, ts:...}\nevery 30s → drives Redis TTL 60s"]
}

LocalDisplay [icon: monitor, color: gray, label: "LCD 16x2 I2C\naddr 0x27\nGPIO 21 SDA / 22 SCL\nLine 1: T:24.5C H:62%\nLine 2: AQ:320 Snd:1\nAlert override on backend push"]

RelayActuator [icon: zap, color: red, label: "4-CH Relay Actuation\nLogic Level Converter\n3.3V (ESP32) ↔ 5V (Relay)"] {
  CH1 [label: "CH1 — AC Unit\nGPIO 26 → LLC → IN1\nopto-isolated"]
  CH2 [label: "CH2 — Lighting\nGPIO 27 → LLC → IN2\nopto-isolated"]
  CH34 [label: "CH3 / CH4 — Spare\nGPIO 14 / GPIO 12"]
}

MQTTSubscriber [icon: inbox, color: green, label: "MQTT Subscribe\nExact topic strings\nQoS 1 — acknowledged"] {
  CmdAC [label: "classroom/room1/relay/ac\n{action: on|off|auto}"]
  CmdLight [label: "classroom/room1/relay/lighting\n{action: on|off|auto}"]
  CmdAlert [label: "classroom/room1/alerts\n{type, value}\n→ Override LCD display"]
}

AutoMode [icon: settings, color: green, label: "On-Device Auto-Mode\nacAutoMode = true\nTemp > 28°C → AC ON\nTemp < 22°C → AC OFF\nActs locally if MQTT drops\nDeliberate physical redundancy"]

ReadDHT --> T
ReadDHT --> H
ReadMQ --> AQ
ReadACP --> S
SensorAcquisition --> HB: "every 30s"
SensorAcquisition --> LocalDisplay: "live refresh"

CmdAC --> CH1
CmdLight --> CH2
CmdAlert --> LocalDisplay: "alert override"
AutoMode --> CH1: "local threshold\nno MQTT needed"
```

---

## DIAGRAM 3 — MQTT Communication & Event Fan-out

```
// MQTT Communication Layer + asyncio.Queue Event Fan-out

direction right

ESP32 [icon: cpu, color: orange, label: "ESP32\nWiFi MQTT client"]

Mosquitto [icon: radio, color: blue, label: "Mosquitto 2\nBroker :1883\nTCP on university LAN"]

Bridge [icon: git-merge, color: blue, label: "MQTT Bridge\naiomqtt persistent subscriber\nwildcard: classroom/+/sensors/#\nclassroom/+/status"] {
  HSensor [label: "_handle_sensor()\n1. Redis SET sensor cache TTL 300s\n2. asyncio PostgreSQL INSERT\n3. sensor_event_queue.put_nowait()"]
  HStatus [label: "_handle_status()\nRedis SET device:online TTL 60s\nExpiry triggers device_offline alert"]
  HRelay [label: "publish_mqtt()\nShort-lived client context\nQoS 1 relay commands out"]
}

Queues [icon: layers, color: green, label: "asyncio.Queue — Event Bus\n3 independent queues"] {
  SQ [label: "sensor_event_queue\n← MQTT Bridge"]
  AQ [label: "attendance_event_queue\n← Recognition Loop"]
  ALQ [label: "alert_event_queue\n← Alert Engine"]
}

Drain [icon: arrow-right, color: green, label: "3 Drain Tasks\nasyncio.create_task()\nInfinite loop per queue\nconnection_manager.broadcast(room_id, event)\nDecouples producers from WS"]

WS [icon: wifi, color: purple, label: "WebSocket Endpoint\nWS /ws/classroom/room1\nSnapshot on connect\nKeepalive ping every 30s\n6 message types:\nsnapshot | sensor | attendance\nalert | ping | pong"]

React [icon: monitor, color: purple, label: "React useLiveSensors\nExponential backoff 3s → 30s\n8s demo watchdog\nRoutes by msg.type\nto React state slices"]

ESP32 --> Mosquitto: "QoS 0 sensors 5s\nQoS 0 heartbeat 30s"
Mosquitto --> Bridge: "subscribed\nwildcard topics"
HSensor --> SQ
SQ --> Drain
AQ --> Drain
ALQ --> Drain
Drain --> WS: "broadcast(room_id, event)"
WS --> React: "JSON messages\nHTTP upgrade"
Bridge --> Mosquitto: "QoS 1 relay commands"
Mosquitto --> ESP32: "relay/ac relay/lighting\nQoS 1 → acknowledged"
```

---

## DIAGRAM 4 — FastAPI Backend Internal Modules

```
// FastAPI Backend — 7 Module Groups Internal Architecture

direction down

Auth [icon: lock, color: red, label: "Auth — Group 7\nJWT HS256 — 480min expiry\nbcrypt password hashing\nRBAC: professor | admin\nScope-filtered API responses\napi/auth.py + deps.py"]

G1 [icon: radio, color: orange, label: "Group 1: Ingestion\nmqtt_bridge.py + event_queues.py\nPersistent aiomqtt subscriber\n3 asyncio.Queue instances\nRedis + Postgres writes on sensor msg"]

G2 [icon: users, color: blue, label: "Group 2: Session & Attendance\napi/sessions.py + api/attendance.py\nrecognition_loop.py\nSession lifecycle start → end\nSnapshot-per-cycle bidirectional eval\nadjusted_by guard — no override\nMoodle sync on session end"]

G3 [icon: zap, color: yellow, label: "Group 3: Relay Control\napi/control.py\nDual-write pattern:\n1. Redis SET relay state (instant UI)\n2. MQTT publish to ESP32 (device)\nOn/Off/Auto per channel"]

G4 [icon: bell, color: red, label: "Group 4: Alert Engine\nservices/alert_engine.py\nAPScheduler every 30s\nReads Redis sensor cache\nEvaluates temp / AQ / device-online\nDeduplication: skip if active alert exists\nMoodle retry every 10min\nfires into alert_event_queue"]

G5 [icon: bar-chart-2, color: green, label: "Group 5: SQL Insights\nservices/insights_engine.py\nOn-demand pure SQL analytics\nAttendance trend (weekly)\nHeatmap day/hour-slot\nDecay analysis + scatter plots\nRole-filtered by professor scope"]

G6 [icon: brain, color: purple, label: "Group 6: AI Pipelines\nat_risk_engine.py + forecast_engine.py\nOn-demand triggers (page open)\nRedis pipeline locks + cooldown\nDeterministic classification\nLLM prose only (verification layer)\nshared call_ollama() utility"]

G7 [icon: database, color: gray, label: "Group 7: Data Layer\nPostgreSQL 15 — 10 tables\nRedis 7 — 6 key patterns\nAlembic auto-migration at startup\nSQLAlchemy ORM\nBYTEA face embeddings"]

Auth --> G2: "role filter"
Auth --> G3: "professor scope"
Auth --> G5: "course filter"
Auth --> G6: "admin-only recompute"
G1 --> G2: "attendance_event_queue"
G1 --> G4: "sensor events via Redis"
G1 --> G7: "persist sensor_readings"
G2 --> G7: "attendance_records + sessions"
G3 --> G7: "Redis relay state"
G4 --> G7: "INSERT alerts"
G5 --> G7: "read-only analytics queries"
G6 --> G7: "UPSERT at_risk_explanations\nUPSERT attendance_forecasts"
```

---

## DIAGRAM 5 — Face Recognition Pipeline

```
// Face Recognition Pipeline — Enrollment + Snapshot-per-Cycle Recognition

direction down

Enrollment [icon: user-plus, color: blue, label: "Enrollment Flow\nPOST /api/students/{id}/enroll-face"] {
  Upload [label: "Up to 5 JPEG/PNG images\nmultipart/form-data"]
  Decode [label: "Decode → numpy array\nOpenCV BGR format"]
  FaceNet [label: "DeepFace FaceNet\n128-d embedding per image"]
  Average [label: "Average all embeddings\n→ 1×128-d float32 vector"]
  Store [label: "Serialize numpy.tobytes()\nPostgreSQL BYTEA\nface_encodings table\nOriginal photos discarded"]
  Reload [label: "reload_encodings()\nRefresh in-memory dict"]
}

Recognition [icon: refresh-cw, color: orange, label: "Recognition Loop\nActive when session running\nFACE_RECOGNITION_ENABLED=true"] {
  Capture [label: "OpenCV VideoCapture(0)\nMIPI CSI-2 Camera\n2 fps (RECOGNITION_FPS=2)"]
  Match [label: "DeepFace cosine distance\nvs all stored embeddings\nThreshold < 0.40\n(tightened from 0.60 Phase 22)"]
  SCAN [label: "SCAN Phase — 60s\nATTENDANCE_CYCLE_DURATION\nCollect seen_this_cycle set\nWS event on first detect per cycle"]
  EVAL [label: "EVALUATE Phase\n1 DB transaction\nFor every enrolled student:\n  in set → absent→present\n  not in set → present→absent\nadjusted_by IS NOT NULL → skip\n(professor override protected)"]
  UNKNOWN [label: "UNKNOWN face\nIncrement occupancy counter\nAnomaly detection"]
}

Stub [icon: code, color: gray, label: "Stub Mode\nFACE_RECOGNITION_ENABLED=false\nDocker default (no TF/DeepFace)\n~70% ±2 random students per cycle\nFull bidirectional logic still runs"]

Queue [icon: layers, color: green, label: "attendance_event_queue\n→ WebSocket drain task\n→ React dashboard live update"]

Upload --> Decode --> FaceNet --> Average --> Store --> Reload
Capture --> Match
Match --> SCAN: "distance < 0.40"
Match --> UNKNOWN: "no match"
SCAN --> EVAL: "after 60s"
EVAL --> Queue
Stub --> EVAL: "bypasses camera\nfake seen_this_cycle set"
```

---

## DIAGRAM 6 — AI Pipelines & Verification Layer

```
// AI & Analytics — Deterministic Verification Layer + LLM Prose

direction down

PageOpen [icon: mouse-pointer, color: blue, label: "Professor opens\n/at-risk or /forecasting"]

Lock [icon: lock, color: red, label: "Redis Pipeline Lock\nSET NX EX — not deleted on completion\nat_risk:pipeline:lock TTL 600s (10min)\nforecast:pipeline:lock TTL 1800s (30min)\nPrevents concurrent re-runs\nNatural cooldown mechanism"]

Deterministic [icon: check-square, color: green, label: "DETERMINISTIC LAYER — Python only\nNo LLM involved here"] {
  AtRiskDet [label: "AT-RISK:\nSQL: attendance_rate < 0.70 → at-risk flag\nFreshness gate: skip if < 600s old\nCleanup: DELETE recovered students\n3 batch JOIN queries per student:\n  ① attendance + session + course JOIN\n  ② avg sensor on missed sessions JOIN\n  ③ peer attendance rate GROUP BY"]
  ForecastDet [label: "FORECASTING:\nGET last 8 sessions per course\nCompute 0.0–1.0 rate fractions\ndelta = consecutive differences\nmean_delta < -0.02 → steady_decline\n  2nd half worse by >0.01 → accelerating_decline\nmean_delta > +0.015 → recovering\nelse → stable\nConfidence: ≥6 sessions=high  ≥4=medium  <4=low"]
}

Boundary [icon: shield, color: orange, label: "VERIFICATION BOUNDARY\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\nEverything ABOVE: labels, scores,\nclassifications, thresholds, colors\ncomputed deterministically in Python.\nLLM NEVER writes structured values.\nHallucinations cannot corrupt logic.\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

LLM [icon: brain, color: purple, label: "LLM LAYER — Prose generation only\nOllama phi3:mini — local RPi CPU\nNo external API — no data leaves network"] {
  AtRiskLLM [label: "AT-RISK PROMPT:\n< 500 tokens multi-course block\n1 call per student (was ~7 — 7x speedup)\ntemperature=0.3 num_predict=180\nOutput: 3-4 sentence prose summary\nNo health / family / psychology refs\nNo blame or evaluative judgments"]
  ForecastLLM [label: "FORECAST PROMPT:\n2-line structured prompt per course\nOutput: EXPECTED_NEXT: <int>\n        INTERPRETATION: <sentence>\n_parse_llm_response() → (None, None)\non any failure — system never crashes"]
}

Store [icon: database, color: blue, label: "Store Results\nat_risk_explanations — UPSERT\nattendance_forecasts — UPSERT\ngenerated_at timestamp\nollama_reachable flag"] {
  Fallback [label: "Ollama unreachable:\nollama_reachable = False\nAmber warning card in UI\nDeterministic data still shown\nFrontend never crashes"]
}

Frontend [icon: monitor, color: purple, label: "React Frontend\nAuto-poll GET every 8s\nStop when all generated_at populated\nMarker rows terminate poll\nfor courses with < 3 sessions\nRender: LLM cards + Recharts trend chart"]

PageOpen --> Lock: "GET /api/at-risk\nGET /api/forecasting"
Lock --> Deterministic: "lock acquired\nasyncio.create_task()"
Lock --> Frontend: "lock not acquired\nserve cached rows"
AtRiskDet --> Boundary
ForecastDet --> Boundary
Boundary --> LLM: "pass profile +\ndeterministic labels"
AtRiskLLM --> Store
ForecastLLM --> Store
Store --> Frontend: "populated rows"
```

---

## DIAGRAM 7 — Data Layer (PostgreSQL + Redis)

```
// Data Layer — PostgreSQL 10 Tables + Redis 6 Key Patterns

direction down

PG [icon: database, color: blue, label: "PostgreSQL 15 — Durable Records\n10 tables"] {
  professors [label: "professors\nid · name · email\npassword_hash (bcrypt)\nrole: professor|admin"]
  courses [label: "courses\nid · name\nprofessor_id FK\nroom_id"]
  students [label: "students\nid · name\nstudent_id (unique)"]
  enrollments [label: "enrollments\nstudent_id FK\ncourse_id FK"]
  face_encodings [label: "face_encodings\nstudent_id FK (1:1)\nencoding BYTEA\n128-d float32 vector\nImages discarded"]
  sessions [label: "sessions\nid · course_id FK\nroom_id\nstarted_at · ended_at\nmoodle_sync_status"]
  attendance_records [label: "attendance_records\nsession_id FK\nstudent_id FK\nstatus: present|absent|late|excused\ndetected_at\nadjusted_by (override guard)"]
  sensor_readings [label: "sensor_readings\nroom_id · sensor_type\nvalue · unit · timestamp"]
  alerts [label: "alerts\nid · room_id · type\nvalue · acknowledged\ncreated_at"]
  at_risk_and_forecasts [label: "at_risk_explanations\n  student_id FK · prose summary\n  attendance_rate · per_course JSONB\n  generated_at · ollama_reachable\n────────────────────\nattendance_forecasts\n  course_id FK\n  trend_classification VARCHAR(30)\n  confidence · trend_data JSONB\n  llm_interpretation · expected_next_rate\n  generated_at"]
}

RD [icon: database, color: red, label: "Redis 7 — Ephemeral Live State\n6 key patterns"] {
  SensorCache [label: "classroom:{room}:sensors:{type}\nValue: {value, unit, ts}\nTTL: 300s\nWrite: MQTT bridge every 5s\nRead: WS snapshot · alert engine · insights"]
  DevicePresence [label: "classroom:{room}:online\nValue: {online:true, ts}\nTTL: 60s renewed by heartbeat\nExpiry = device_offline alert triggered"]
  RelayState [label: "classroom:{room}:relay:{device}\nValue: on | off | auto\nNo TTL\nWrite: Control API + alert engine\nRead: WS snapshot · control page"]
  Locks [label: "at_risk:pipeline:lock TTL 600s\nforecast:pipeline:lock TTL 1800s\nSET NX EX — NOT deleted on complete\nNatural cooldown prevents re-trigger"]
  MoodleQ [label: "moodle:retry_queue\nRedis List\nPUSH: failed session_id on sync error\nPOP: alert engine every 10min\nMax 10 retries per cycle"]
}

professors --> courses: "professor_id"
courses --> enrollments: "course_id"
students --> enrollments: "student_id"
students --> face_encodings: "1:1"
courses --> sessions: "course_id"
sessions --> attendance_records: "session_id"
students --> attendance_records: "student_id"
students --> at_risk_and_forecasts: "student_id"
courses --> at_risk_and_forecasts: "course_id"
```

---

## DIAGRAM 8 — Docker Compose Deployment on RPi4

```
// Docker Compose — 8 Services on Raspberry Pi 4B

direction down

Host [icon: server, color: blue, label: "Raspberry Pi 4B\nRaspberry Pi OS Lite 64-bit\nhostname: smartclassroom.local\nUniversity Intranet LAN\nDocker Compose host"] {

  postgres [icon: database, color: blue, label: "postgres\npostgres:15-alpine\n:5432\nvol: postgres_data"]
  redis [icon: database, color: red, label: "redis\nredis:7-alpine\n:6379\nvol: redis_data"]
  mosquitto [icon: radio, color: orange, label: "mosquitto\neclipse-mosquitto:2\n:1883\nvol: mosquitto_data"]
  ollama [icon: cpu, color: purple, label: "ollama\nollama/ollama:latest\n:11434\nvol: ollama_data\nphi3:mini CPU inference"]
  backend [icon: code, color: blue, label: "backend\ncustom Dockerfile\nFastAPI :8000\nAlembic migrate on start\ndepends: postgres✓ redis✓\nmosquitto✓ ollama✓"]
  frontend [icon: globe, color: green, label: "frontend\nnginx + React build\n:3000 → :80\nProxy /api/* /ws/* → :8000\ndepends: backend✓"]
  moodle [icon: book-open, color: gray, label: "moodle (optional)\nbitnami/moodle:4\n:8080\n--profile moodle\nvol: moodle_data"]
  mariadb [icon: database, color: gray, label: "mariadb (optional)\nmariadb:10.6\n:3306\n--profile moodle\nvol: mariadb_data"]
}

ESP32 [icon: cpu, color: orange, label: "ESP32 Sensor Node\nWiFi client"]
Professor [icon: monitor, color: purple, label: "Professor Browser\nHTTP :3000"]

postgres --> backend: "healthy ✓"
redis --> backend: "healthy ✓"
mosquitto --> backend: "started ✓"
ollama --> backend: "started ✓"
backend --> frontend: "started ✓"
mariadb --> moodle: "healthy ✓"
ESP32 --> mosquitto: "WiFi MQTT TCP :1883"
Professor --> frontend: "HTTP :3000"
backend --> moodle: "REST API sync\n(optional profile)"
```

---

## DIAGRAM 9 — Moodle + Ollama External Integrations

```
// External Integrations — Moodle LMS Sync + Ollama LLM Service

direction right

SessionEnd [icon: stop-circle, color: blue, label: "Session End\nPOST /api/sessions/{id}/end\nFinal EVALUATE phase runs\nAll absent students marked"]

MoodleIntegration [icon: book-open, color: green, label: "Moodle 4.x Integration\nmoodle_client.py"] {
  Sync [label: "REST API Call\nPOST /webservice/rest/server.php\nwstoken authentication\nmod_attendance_add_attendance\nStatus map:\n  present → 1\n  absent  → 2\n  late    → 3\n  excused → 4"]
  Success [label: "HTTP 200\nUpdate sessions.\nmoodle_sync_status = synced"]
  Fail [label: "Timeout / Error\nPush session_id to\nRedis moodle:retry_queue\nStatus = failed"]
  Retry [label: "APScheduler every 10min\nPOP up to 10 from queue\nRe-attempt sync\nGET /api/moodle-test\n→ health probe"]
}

OllamaIntegration [icon: brain, color: purple, label: "Ollama — phi3:mini\nLocal CPU inference\nhttp://ollama:11434"] {
  Pull [label: "Startup check\nensure_model_pulled()\nGET /api/tags\nIf absent: POST /api/pull\nphi3:mini ~2GB\nNon-blocking background task\nPersisted in ollama_data volume"]
  Config [label: "Inference settings\nstream = false\ntemperature = 0.3\nnum_predict = 180\nShared httpx.AsyncClient\nPrevents TCP connection churn"]
  Utils [label: "Shared utilities\ncall_ollama()\n_check_ollama_ready()\nDefined in at_risk_engine.py\nImported by forecast_engine.py\nNo code duplication"]
  Flag [label: "ollama_reachable flag\nFalse → amber warning card\nFreshness gate disabled\nDeterministic data still served\nSystem does not crash"]
}

SessionEnd --> Sync: "background task"
Sync --> Success: "HTTP 200"
Sync --> Fail: "error / timeout"
Fail --> Retry: "Redis list queue"
Retry --> Sync: "retry pop"

Pull --> Config: "model ready"
Config --> Utils: "reused by\nat_risk + forecast"
Utils --> Flag: "pre-flight check\nbefore each call"
```
