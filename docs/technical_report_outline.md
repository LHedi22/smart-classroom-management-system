# Technical Report Outline
## Smart Campus Classroom Management System
### SMU — Mediterranean Institute of Technology
**Team:** Mohamed Hedi Ben Jemaa, Ahmed Amine Jallouli, Ali Saadaoui, Abdelhamid Ouertani, Iyed Day
**Academic Year:** 2025–2026 | **Format:** IEEE

---

## FRONT MATTER

- **Cover Page** — Project title, team names, institution (SMU MedTech), course name, academic year 2025–2026, submission date
- **Abstract** (≈250 words) — problem statement, proposed solution, key technologies, main results
- **Table of Contents**
- **List of Figures** — all diagrams, architecture visuals, hardware photos, dashboard screenshots
- **List of Tables** — hardware BOM, API endpoints, DB schema tables, performance benchmarks
- **List of Abbreviations** — IoT, MQTT, LMS, JWT, LLM, RPi, NX, TTL, QoS, etc.

---

## CHAPTER 1 — Introduction

### 1.1 Context and Motivation
- Current state of classroom management at SMU: manual attendance, manual HVAC
- Time cost of manual attendance (up to 15 min per lecture)
- Lack of real-time environmental visibility
- Growing adoption of IoT in smart building literature

### 1.2 Problem Statement
- Three concrete pain points: (1) attendance inefficiency, (2) unmonitored environment, (3) no early warning for at-risk students
- Absence of integration between physical classroom and LMS (Moodle)

### 1.3 Project Objectives
- General objective (one paragraph)
- Specific objectives as numbered list (6 items from proposal)

### 1.4 Scope and Limitations
- Single classroom / single room deployment
- University intranet only (no public internet)
- Academic semester timeline constraint
- Hardware budget constraints

### 1.5 Report Structure
- One-sentence description of each chapter

---

## CHAPTER 2 — Literature Review & Related Work

### 2.1 Smart Classroom Systems — State of the Art
- Overview of existing IoT classroom solutions (RFID-based attendance, QR-code systems, face recognition systems in academia)
- Gaps: cloud dependency, no LMS integration, no AI-layer

### 2.2 Face Recognition in Attendance Systems
- DeepFace / FaceNet 128-d embeddings — cosine similarity approach
- Accuracy vs. cost tradeoffs on edge hardware

### 2.3 IoT Protocols for Educational Environments
- MQTT vs. HTTP vs. CoAP — why MQTT fits constrained devices
- QoS levels and their tradeoffs

### 2.4 Local LLM Inference at the Edge
- Ollama + phi3-mini as a deployment pattern
- Rationale for local vs. cloud LLM (privacy, latency, cost, internet independence)

### 2.5 LMS Integration
- Moodle REST API overview
- Prior work on automated Moodle attendance sync

### 2.6 Summary & Positioning of This Work
- Table comparing this system to 3–4 related works across key features

---

## CHAPTER 3 — Requirements Analysis

### 3.1 Stakeholder Analysis
- Professors (primary users): session control, live dashboard, attendance adjustment
- Students (indirect): better comfort, accurate records
- Administration (secondary): resource optimization, compliance data
- Advising department: early intervention via at-risk data

### 3.2 Functional Requirements
- Numbered list, grouped by subsystem: attendance, environment monitoring, control, dashboard, alerts, LMS sync, AI insights

### 3.3 Non-Functional Requirements
- Real-time latency (sensor update ≤ 5s end-to-end)
- Availability (local-only, no internet required)
- Security (JWT auth, bcrypt, university intranet)
- Scalability note (single room scope, design allows multi-room extension)
- Resilience (demo mode, mock sensor fallback, MQTT reconnect with backoff)

### 3.4 Use Case Diagrams
- *[Figure placeholder: UML use case diagram — Professor actor, Admin actor, System boundary]*
- Key use cases: Start Session, View Live Sensors, Override AC/Lighting, View At-Risk Students, Sync to Moodle

### 3.5 Constraints
- Hardware availability and cost (parts list with prices)
- RPi 4B compute limits (face recognition at 2fps, phi3-mini at 10–30s/student)
- Single-semester delivery

---

## CHAPTER 4 — System Architecture

### 4.1 Architecture Overview
- Hybrid modular monolith + event-driven messaging rationale
- *[Figure: Full system layered architecture diagram — IoT → Edge → Backend → Frontend → External]*

### 4.2 Subsystem Breakdown Table
- Table: Subsystem | Technology | Responsibility (9 rows)

### 4.3 IoT Layer — ESP32 Firmware
- Sensor acquisition loop (DHT21, MQ-135, sound sensor) every 5s
- MQTT publish schema: `classroom/{room_id}/sensors/{type}`
- Relay actuation via subscribed topics
- LCD 16×2 local display
- On-device auto-control redundancy (acAutoMode)
- *[Figure: ESP32 wiring diagram / pinout]*
- *[Photo: assembled breadboard with ESP32, sensors, relay module]*

### 4.4 Edge Layer — Raspberry Pi 4B
- Roles: MQTT broker, face recognition host, all Docker services
- Camera subsystem: 2fps recognition loop, DeepFace/FaceNet, 30s cooldown
- Stub mode and mock sensor mode for development
- *[Photo: RPi setup with camera module]*

### 4.5 Communication Layer — MQTT
- Mosquitto broker configuration
- Topic architecture diagram
- *[Figure: MQTT topic tree — classroom/room1/sensors/#, relay/ac, relay/lighting, status, alerts]*
- QoS 0 rationale, publish/subscribe role split

### 4.6 Backend — FastAPI Application
- Module group overview (7 groups)
- *[Figure: Backend internal module diagram — mqtt_bridge → event queues → services → API routes]*
- Group 1: MQTT ingestion + asyncio queue fan-out
- Group 2: Session lifecycle + attendance recording
- Group 3: Control API (relay state in Redis + MQTT)
- Group 4: Alert engine (APScheduler, deduplication logic)
- Group 5: Insights engine (SQL analytics)
- Group 6: AI pipelines (covered in Chapter 6)
- Group 7: JWT authentication

### 4.7 Real-Time Layer — WebSocket
- *[Figure: Event fan-out diagram — MQTT handler / recognition loop / alert engine → asyncio.Queue → drain task → WebSocket → Browser]*
- Snapshot on connect, keepalive ping/pong
- Frontend reconnect with exponential backoff
- Demo mode watchdog (8s timeout → DemoModeBanner)

### 4.8 Data Layer
- *[Figure: Entity-Relationship Diagram — all 10 tables]*
- PostgreSQL schema: rationale for key decisions (display_status computed, VARCHAR vs ENUM, JSONB for per_course_data, BYTEA for face encodings)
- Redis key pattern table (sensor cache, device presence, relay state, pipeline locks, Moodle retry queue)
- Ephemeral vs. persistent boundary discussion

### 4.9 Frontend — React Dashboard
- SPA architecture (React 18 + Vite + React Router v6)
- Context providers: AuthContext, SensorContext
- Route structure table (9 routes)
- Design system: tokens.css, index.css, TailwindCSS v3 coexistence
- *[Screenshot: Dashboard page — live sparklines + session control]*
- *[Screenshot: Attendance page — session/student table]*
- *[Screenshot: Control page — relay toggles + sensor cards]*
- *[Screenshot: At-Risk page — student cards + LLM explanation panel]*
- *[Screenshot: Forecasting page — Recharts AreaChart + classification badge]*
- *[Screenshot: Enrollment page — student registration + face upload]*
- *[Screenshot: History page — past sessions]*

### 4.10 External Integrations
- Moodle 4.x: REST API sync on session end, Redis retry queue
- Ollama/phi3-mini: startup model pull, shared AsyncClient, stream=false config

---

## CHAPTER 5 — Implementation

### 5.1 Development Methodology & Task Management
- Agile-inspired iterative approach (22 phases)
- Notion as the team collaboration and task tracking tool — board structure, assignment of phases to team members, progress tracking
- *[Screenshot: Notion board showing task breakdown]*
- Phase completion timeline overview

### 5.2 Hardware Assembly
- Bill of Materials table (all 12 components with roles)
- Wiring procedure: logic level converter (3.3V↔5V) between ESP32 and relay
- Power supply considerations (5V 3A for RPi)
- *[Photo: full assembled hardware setup]*
- *[Photo: close-up of relay module wiring]*

### 5.3 Firmware Development (ESP32)
- Arduino IDE setup, library installation
- `config.h` parameters: WiFi credentials, MQTT broker IP, room ID, thresholds
- Sensor reading loop and MQTT publish logic
- Relay actuation on subscribed commands
- LCD status display

### 5.4 Backend Development
- FastAPI project structure (`backend/app/` layout)
- Database setup: SQLAlchemy 2.0 async, Alembic auto-migration on startup
- MQTT bridge implementation: aiomqtt persistent subscriber, exponential backoff
- Session and attendance engine: start/end lifecycle, face recognition integration
- Alert engine: APScheduler jobs, threshold table, deduplication
- JWT authentication: bcrypt, HS256, role-based filtering

### 5.5 Face Recognition Pipeline
- Enrollment flow: up to 5 images → FaceNet 128-d → averaged → BYTEA storage
- Recognition loop: OpenCV VideoCapture → DeepFace cosine distance < 0.6 → attendance record
- Stub mode for non-RPi environments
- *[Figure: face recognition flow diagram]*

### 5.6 Frontend Development
- Vite + React 18 scaffolding
- CSS token system (tokens.css → index.css separation rationale)
- useLiveSensors hook: WebSocket state management, demo mode fallback
- Recharts integration: AreaChart with linearGradient, 70% dashed ReferenceLine
- API client (axios) with JWT header injection

### 5.7 Infrastructure & Deployment
- Docker Compose service graph
- *[Figure: Docker Compose dependency graph — postgres/redis/mosquitto → backend → frontend + ollama]*
- nginx reverse proxy configuration (`/api/*` and `/ws/*` proxied to :8000)
- Alembic auto-migration in lifespan context
- Named volumes for data persistence

### 5.8 Seed Data & Demo Environment
- `seed.py`: 35 students, 6 courses, 30 sessions, 5 professors
- MOCK_MODE operation: sine-wave sensor publisher, synthetic attendance events
- Demo mode banner in frontend

---

## CHAPTER 6 — AI & Analytics Layer

### 6.1 Overview and Motivation
- Why a local LLM instead of cloud API (privacy, no internet dependency, cost)
- phi3-mini characteristics: ~4k context, low VRAM, runs on CPU

### 6.2 At-Risk Student Detection Pipeline
- *[Figure: at-risk pipeline flow — GET /api/at-risk → Redis lock → asyncio.create_task → pipeline steps]*
- Threshold: 70% attendance rate
- Redis lock mechanism (TTL 600s, SET NX) — cooldown rationale
- Pipeline steps in detail (5 steps)
- Batch query optimization: before vs. after performance table (Phase 20)
- Prompt design: <500 tokens, multi-course block, constraints (no health/personal references)
- DB upsert: `at_risk_explanations` table, JSONB per_course_data
- Frontend: auto-poll every 8s, amber warning on Ollama unavailable, admin recompute button

### 6.3 Attendance Forecasting Pipeline
- *[Figure: forecasting pipeline flow]*
- Trigger: GET /api/forecasting → Redis lock (TTL 1800s)
- Deterministic trend classification algorithm: delta math, mean_delta thresholds
- Classification outcomes: steady_decline, accelerating_decline, stable, recovering
- Confidence levels: high ≥6 sessions, medium ≥4, low <4
- Ollama role: prose interpretation + EXPECTED_NEXT rate only (structured values always deterministic)
- Marker rows for courses with <3 sessions (ensures frontend poll terminates)
- *[Screenshot: Forecasting page with AreaChart]*

### 6.4 Insights Engine
- SQL-driven analytics (no LLM): attendance trend weekly, heatmap by day/hour-slot, decay analysis, comfort score, AC effectiveness, temp-vs-attendance scatter, AQ vs. sound correlation
- Role-filtered queries

### 6.5 Key Design Decision: Deterministic Classification vs. LLM
- Why LLM output is unreliable for structured values (hallucination risk on labels)
- Delta math is fast, deterministic, and never breaks frontend color-coding
- LLM constrained to prose only

---

## CHAPTER 7 — Security & Privacy

### 7.1 Security Architecture Overview
- Threat model: university intranet deployment, professor-facing system, student biometric data
- Defense layers: network (LAN-only), application (JWT), data (bcrypt, BYTEA encodings), transport (nginx termination point)

### 7.2 Authentication & Authorization
- JWT (HS256) with configurable expiry (default 480 min)
- bcrypt password hashing for professor accounts
- Role-based access control: professor vs. admin distinction
- Role-filtered API responses (professors see only their own courses/students)
- `REQUIRE_AUTH` flag — disabled in dev, must be enabled in production
- Admin-only endpoints: `POST /api/at-risk/recompute`, `POST /api/forecasting/recompute`

### 7.3 Biometric Data Handling
- Face encodings stored as 128-d float32 numpy arrays (BYTEA) — not raw images
- Enrollment images are processed and discarded; only the averaged embedding is persisted
- No cloud transmission of biometric data — all inference runs locally on RPi
- Stub mode: zeroed placeholder encoding stored, no real biometric processing

### 7.4 Data Privacy Considerations
- All data remains on-premises (RPi / Docker host) — zero cloud dependency
- Student attendance records are institution-internal only
- LLM prompts sent to Ollama (local) — no student data leaves the network
- At-risk explanations: prompt constraints enforced (no health, personal life, family, psychology references)
- Moodle sync over local network only (optional profile)

### 7.5 Transport & Network Security
- Current deployment: HTTP/WS on university LAN (acceptable for intranet)
- nginx as the single ingress point — backend not directly exposed
- Known gap: no HTTPS/WSS — identified as future work, nginx SSL termination path described
- MQTT QoS 0 on local broker — no external exposure of sensor data

### 7.6 Session & Token Security
- JWT stored in browser `localStorage` — tradeoff acknowledged (acceptable on closed intranet vs. httpOnly cookie complexity)
- Token expiry enforced server-side
- No refresh token mechanism in current version

### 7.7 Operational Security
- `SECRET_KEY` environment variable — must be replaced from default in production
- `REQUIRE_AUTH=false` default flagged as a hardening checklist item
- Docker named volumes isolate persistent data
- No default credentials in seed data for production use

---

## CHAPTER 8 — Testing & Validation

### 8.1 Testing Strategy
- Unit tests (backend service logic)
- Integration tests (ESP32 → MQTT → backend → DB flow)
- End-to-end tests (full session lifecycle)
- Manual testing on physical hardware

### 8.2 Sensor Data Validation
- DHT21 readings vs. reference thermometer comparison
- MQ-135 relative calibration approach (threshold set empirically at 500ppm)
- Sound sensor detection accuracy

### 8.3 Face Recognition Accuracy
- Test conditions: varied lighting, different angles, glasses
- Results: recognition accuracy at 2fps under lab conditions
- Stub mode fallback validation

### 8.4 API Testing
- FastAPI Swagger UI (`/docs`) used for manual endpoint validation
- *[Screenshot: Swagger UI showing API endpoints]*
- Key scenarios tested: session start/end, attendance record creation, relay control, alert generation

### 8.5 Real-Time Performance
- WebSocket latency: sensor publish → dashboard update (end-to-end)
- Alert engine response time (30s scheduler cycle)
- Face recognition throughput (2fps sustained on RPi 4B)

### 8.6 AI Pipeline Performance
- At-risk pipeline: before optimization (~14–16 min) vs. after (~2–3 min for 8 students)
- Forecasting pipeline: per-course Ollama call timing
- phi3-mini response quality: sample prompt + output examples

### 8.7 Resilience Testing
- MQTT broker restart → reconnect with exponential backoff
- Ollama unavailable → amber UI warning, ollama_reachable=false persisted
- Network loss → frontend demo mode activation after 8s watchdog

---

## CHAPTER 9 — Results & Discussion

### 9.1 System Demonstration
- Full walkthrough of a simulated classroom session (start → detection → end → Moodle sync)
- *[Screenshots: session lifecycle on dashboard]*

### 9.2 Key Achievements vs. Objectives
- Table: Objective | Status | Evidence (mapped to 6 specific objectives from Chapter 1)

### 9.3 Performance Summary
- Attendance time saved: automated vs. manual (15 min/lecture benchmark)
- Sensor update latency achieved
- AI pipeline runtime

### 9.4 Lessons Learned
- aiomqtt migration from asyncio-mqtt (paho-mqtt v2 breaking change)
- DeepFace/TF removed from Docker image (OOM on dev laptops → stub mode)
- Glassmorphism removed (GPU-expensive, Chrome rendering artifacts)
- Redis lock TTL not deleted on completion (natural cooldown pattern)
- VARCHAR(30) vs. PG ENUM lesson (non-transactional ALTER TYPE DDL)

### 9.5 Limitations
- MQ-135 uncalibrated (comparative only)
- Single-room design
- phi3-mini slow on RPi CPU
- No HTTPS/WSS in current deployment
- QoS 0 MQTT (sensor loss during broker restart)

---

## CHAPTER 10 — Conclusion & Future Work

### 10.1 Summary of Contributions
- IoT + edge AI in a single deployable stack
- 22-phase iterative delivery within one semester
- Local LLM integration without cloud dependency

### 10.2 Future Work
- Multi-room support
- React Native mobile app for professors
- IR illuminator for low-light face recognition
- Email/SMS alert notifications
- QR-code student self-enrollment
- CO₂ sensor calibration (SCD30 / MH-Z19)
- Offline SQLite fallback
- Daily at-risk email digest
- Quantized GGUF model via llama.cpp for faster RPi inference
- HTTPS/WSS for public deployment

---

## REFERENCES
*(IEEE numbered format [1], [2], ...)*

- IoT classroom systems papers
- DeepFace / FaceNet papers
- MQTT protocol specification
- FastAPI, React, Ollama, Moodle official documentation
- phi3-mini model technical report

---

## APPENDICES

- **Appendix A** — Full API Endpoint Reference (table of all REST routes with methods, descriptions, auth requirements)
- **Appendix B** — MQTT Topic Schema (full topic tree with payload JSON schemas)
- **Appendix C** — Database Schema (full DDL or detailed table definitions)
- **Appendix D** — Environment Variables Reference (all `.env` keys with descriptions and defaults)
- **Appendix E** — Hardware Wiring Diagram (full annotated schematic)
- **Appendix F** — Docker Compose Configuration Summary
- **Appendix G** — Notion Task Board (full screenshot of project management board)
