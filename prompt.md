# Claude Code Prompts — Insights System (Phases 19–22)
# Smart Classroom Management System — SMU
# Run these prompts sequentially. Complete each phase fully before starting the next.

---

## ⚠️ Before Running Any Phase

1. Open `CLAUDE.md` in the project root and read it fully.
2. Ensure `docker compose up -d` is running and `docker compose exec backend python seed.py` has been executed.
3. Confirm the existing test suite passes: `docker compose exec backend python e2e_test.py`

---

---

# PHASE 19 — Insights Backend Engine + API Endpoints

## Goal
Build the analytics backend that powers all insight data. No frontend changes yet. All logic lives in two new files (`insights_engine.py`, `insights.py`) plus schema additions.

## Prompt

```
Read CLAUDE.md in full before writing a single line of code.

You are implementing Phase 19 of the Smart Classroom Management System: the Insights Backend.

### What to build

**1. `backend/app/services/insights_engine.py`**

Create an async service class `InsightsEngine` with the following methods. All methods accept an async SQLAlchemy session. Use raw SQLAlchemy core queries or ORM — no pandas.

- `get_overview(professor_id: UUID | None) -> dict`
  Returns: total_sessions (int), avg_attendance_rate (float 0–1), active_alerts_count (int), comfort_score (float, from latest Redis sensor readings for room1), at_risk_count (int).
  If professor_id is provided, scope sessions and courses to that professor only.

- `get_attendance_trend(course_id: UUID | None, weeks: int = 8) -> list[dict]`
  Returns a list of {week_label: str, attendance_rate: float} for the last N weeks.
  If course_id is None, aggregate across all courses (scoped by professor if auth provides it).

- `get_attendance_heatmap(professor_id: UUID | None) -> list[dict]`
  Returns list of {day_of_week: int (0=Mon), hour_slot: int (0=morning/1=afternoon/2=evening), avg_rate: float}.
  Derive day and hour from sessions.started_at.

- `get_attendance_decay(professor_id: UUID | None) -> list[dict]`
  Returns list of {course_code: str, first_session_rate: float, last_session_rate: float, delta: float}.

- `get_at_risk_students(professor_id: UUID | None, threshold: float = 0.70, consecutive: int = 3) -> list[dict]`
  A student is at-risk if:
  - Their attendance rate across all ended sessions in any of their courses is below `threshold`, OR
  - They have `consecutive` or more consecutive absent records in any course.
  Returns list of {student_id, name, institutional_id, attendance_rate, consecutive_absences, courses_at_risk: list[str]}.
  Professor sees only students in their courses. Admin (professor_id=None) sees all.

- `get_student_profile(student_id: UUID) -> dict`
  Returns: name, institutional_id, overall_attendance_rate, risk_level (high/medium/low), per_course breakdown [{course_code, sessions_attended, sessions_total, rate}], recent_sessions list [{date, course_code, status}] (last 10).

- `get_comfort_score(room_id: str, redis_client) -> float`
  Reads latest temp, humidity, air_quality from Redis (keys: `sensor:{room_id}:temperature`, etc.).
  Formula:
  ```
  score = 100
  score -= max(0, temp - 26) * 5
  score -= max(0, 18 - temp) * 5
  score -= max(0, humidity - 65) * 2
  score -= max(0, (air_quality - 300) / 50)
  return max(0, min(100, score))
  ```
  If a sensor value is missing from Redis, skip its penalty (treat as ideal).

- `get_environment_trends(room_id: str, from_dt: datetime, to_dt: datetime) -> list[dict]`
  Returns list of {date: str, temp_avg, temp_min, temp_max, humidity_avg, air_quality_avg} — one row per day.
  Query from sensor_readings table.

- `get_ac_effectiveness(room_id: str) -> dict`
  For each ended session in room_id where AC was turned ON during the session (infer from alerts or relay log if available, otherwise use the first sensor reading above TEMP_AC_ON_THRESHOLD as proxy):
  compute average minutes from AC ON event to first temperature reading below TEMP_AC_OFF_THRESHOLD.
  Returns {avg_lag_minutes: float, sample_size: int}.
  If no data, return {avg_lag_minutes: null, sample_size: 0}.

- `get_temp_vs_attendance(professor_id: UUID | None) -> list[dict]`
  One point per ended session. Returns list of {session_id, course_code, date, avg_temp: float, attendance_rate: float}.
  Join sensor_readings (type=temperature, within session time window) with attendance_records.

- `get_airquality_vs_sound(room_id: str) -> list[dict]`
  One point per ended session in room_id. Returns {session_id, date, avg_air_quality: float, pct_sound_detected: float}.


**2. `backend/app/api/insights.py`**

FastAPI router with prefix `/api/insights`. Mount it in `main.py`.

Implement all endpoints listed in the CLAUDE.md Insights API section.
- Each endpoint calls the appropriate `InsightsEngine` method.
- Pass `professor_id` from JWT token if `REQUIRE_AUTH=true`, otherwise accept optional `?professor_id=` query param for testing.
- Use `Depends(get_db)` and `Depends(get_redis)` for session/cache injection.
- Return 200 with JSON. Return 404 if student/course not found.


**3. `backend/app/models/schemas.py` additions**

Add the following Pydantic response models (append to existing file):
- `InsightsOverview`
- `AttendanceTrendPoint`
- `HeatmapCell`
- `DecayPoint`
- `AtRiskStudent`
- `StudentProfile`
- `EnvironmentTrendDay`
- `AcEffectiveness`
- `CorrelationPoint`

Each model should match the dict shapes returned by InsightsEngine methods.


**4. `requirements.txt`**

No new dependencies are needed for Phase 19. All queries use existing SQLAlchemy + Redis.


### Constraints
- All InsightsEngine methods must be async (use `await session.execute(...)`).
- Do not modify any existing file other than `main.py` (to mount the router) and `schemas.py` (to append models).
- Do not add any new DB tables or Alembic migrations — all insights are computed from existing tables.
- The `get_at_risk_students` method must handle the case where a student has no attendance records (treat as 0% attendance → at-risk).
- Every endpoint must handle empty data gracefully (return empty list, not 500).


### Verification
After implementing, run:
```bash
docker compose build backend && docker compose up -d backend
curl http://localhost:8000/api/insights/overview
curl http://localhost:8000/api/insights/students/at-risk
curl "http://localhost:8000/api/insights/attendance/trend?weeks=4"
curl http://localhost:8000/api/insights/environment/comfort-score?room_id=room1
curl http://localhost:8000/api/insights/correlations/temp-vs-attendance
```
All five must return valid JSON without error. Update CLAUDE.md Phase 19 row to ✅.
```

---

---

# PHASE 20 — AI Summary Service + AiSummaryCard Frontend

## Goal
Integrate the Anthropic API to generate natural-language anomaly narratives. Build the backend service and the single React component that displays it.

## Prompt

```
Read CLAUDE.md in full before writing a single line of code.

You are implementing Phase 20 of the Smart Classroom Management System: AI-generated summaries using the Anthropic API.

Phase 19 must be complete before starting this phase. Confirm `GET /api/insights/overview` returns valid JSON before proceeding.

### What to build

**1. `backend/app/services/ai_summary.py`**

Create an async service with one public function:

```python
async def generate_summary(
    scope: str,          # "session" | "course" | "room" | "global"
    scope_id: str,       # UUID string or room_id string
    context: dict,       # pre-built context blob (see schema below)
    redis_client,
) -> dict:              # returns {narrative: str, generated_at: ISO datetime string}
```

Logic:
1. Build a Redis cache key: `ai_summary:{scope}:{scope_id}`.
2. Check Redis — if cached and not expired (TTL from `AI_SUMMARY_CACHE_TTL` env var, default 600s), return cached value.
3. If not cached, call the Anthropic API:
   - Use the `anthropic` Python SDK (already in requirements.txt after this phase).
   - Model: `claude-sonnet-4-20250514`
   - max_tokens: 300
   - System prompt (exact text):
     ```
     You are an academic analytics assistant for SMU Mediterranean Institute of Technology.
     You analyze smart classroom data and provide concise, actionable insights for professors and administrators.
     Write in plain English. Be specific with numbers. Identify the single most important finding.
     End with one concrete, practical recommendation. Maximum 5 sentences total.
     ```
   - User message: `json.dumps(context, indent=2)`
4. Extract the text content from `response.content[0].text`.
5. Store result in Redis with TTL.
6. Return `{narrative: str, generated_at: datetime.utcnow().isoformat()}`.

Error handling:
- If `ANTHROPIC_API_KEY` env var is not set or is empty, raise `HTTPException(503, "AI summaries not configured — set ANTHROPIC_API_KEY")`.
- If the Anthropic API call fails (network error, rate limit, etc.), log the error and raise `HTTPException(502, "AI summary generation failed")`.
- Never let an AI failure crash other parts of the application.

The context blob that callers must build before calling `generate_summary`:
```json
{
  "scope": "course",
  "label": "CS301 — Introduction to Algorithms",
  "period": "last 8 weeks",
  "attendance_summary": {
    "avg_rate": 0.74,
    "trend": "declining | stable | improving",
    "total_sessions": 12
  },
  "at_risk_students": 3,
  "env_summary": {
    "avg_temp": 28.4,
    "avg_air_quality": 420,
    "comfort_score": 62
  },
  "recent_alerts": ["temp_high x3", "air_quality_high x1"],
  "anomalies": ["attendance dropped 22% in week 6", "3 sessions above 30°C"]
}
```
The `anomalies` list should be populated by the caller by comparing trend data. An empty list is valid.


**2. `backend/app/api/insights.py` — add AI summary endpoint**

Add to the existing insights router (do not recreate the whole file):

```
GET /api/insights/ai-summary
Query params: scope (str), id (str)
```

The endpoint should:
1. Resolve the scope + id to a human-readable label and pull data using InsightsEngine methods.
2. Build the context blob.
3. Call `ai_summary.generate_summary(scope, id, context, redis)`.
4. Return the result.

Build context for each scope type:
- `scope=course`: use `get_attendance_trend`, `get_at_risk_students`, `get_environment_trends`, recent alerts for the course's room.
- `scope=session`: use session attendance rate, sensor summary, any alerts during the session window.
- `scope=room`: last 7 days of environment trends, comfort score, any unacknowledged alerts.
- `scope=global`: overview stats, top 3 at-risk courses, comfort score.


**3. `requirements.txt`**

Add: `anthropic>=0.25.0`


**4. `frontend/src/components/insights/AiSummaryCard.jsx`** (NEW file)

A React component that:
- Accepts props: `scope` (string), `id` (string), `title` (string, default "AI Summary")
- On mount, calls `GET /api/insights/ai-summary?scope={scope}&id={id}` via axios.
- While loading: renders a card with 3 animated skeleton lines (use CSS animation `pulse` from tokens.css or inline keyframes).
- On success: renders a card with:
  - A small robot/sparkle icon (inline SVG, same style as other inline SVG icons in the project)
  - The `title` as card heading
  - The `narrative` text in body font (Inter, 400)
  - `generated_at` formatted as "Generated at HH:MM" in muted text
- On error 503: renders the card with message "AI summaries not configured. Set ANTHROPIC_API_KEY in .env."
- On any other error: renders "Summary unavailable — check backend logs."
- Use CSS var tokens from `tokens.css` for all colors. No hardcoded hex.


### Constraints
- Do not modify any existing backend files except `insights.py` (to add the endpoint) and `requirements.txt`.
- The Anthropic SDK must be imported inside `ai_summary.py` only — nowhere else.
- `AiSummaryCard.jsx` must be self-contained. It fetches its own data. No prop drilling of the narrative.


### Verification
```bash
# Set your API key first
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
docker compose build backend && docker compose up -d backend

# Test without key (should return 503, not 500)
curl "http://localhost:8000/api/insights/ai-summary?scope=global&id=all"

# Test with key
ANTHROPIC_API_KEY=sk-ant-... docker compose up -d backend
curl "http://localhost:8000/api/insights/ai-summary?scope=global&id=all"
# Should return {"narrative": "...", "generated_at": "..."}

# Run again immediately — should return same result from cache (check logs for "cache hit")
curl "http://localhost:8000/api/insights/ai-summary?scope=global&id=all"
```
Update CLAUDE.md Phase 20 row to ✅.
```

---

---

# PHASE 21 — Insights Frontend Page + Mini-Cards

## Goal
Build the full `Insights.jsx` page with 3 tabs, all chart components, and the mini-cards injected into existing pages.

## Prompt

```
Read CLAUDE.md in full before writing a single line of code.

You are implementing Phase 21 of the Smart Classroom Management System: the Insights frontend.

Phases 19 and 20 must be complete. Confirm the following endpoints return valid JSON before starting:
- GET /api/insights/overview
- GET /api/insights/students/at-risk
- GET /api/insights/ai-summary?scope=global&id=all

### Design rules (apply to every new component)
- Use CSS vars from `tokens.css` for all colors. No hardcoded hex values.
- Use DM Sans 600 for headings, Inter 400/500 for body — already loaded via Google Fonts.
- Follow the existing card/button/badge patterns in `index.css`. Do not add new CSS classes unless absolutely necessary.
- Use Recharts for all charts — it is already in package.json.
- Use inline SVG for any new icons (no icon library import).
- No glassmorphism. No backdrop-filter. Clean flat surfaces with subtle box-shadow from tokens.

---

### What to build

**1. `frontend/src/hooks/useInsights.js`** (NEW)

A custom hook that:
- Exposes: `overview`, `atRiskStudents`, `attendanceTrend`, `heatmap`, `envTrends`, `correlations`, `loading`, `error`.
- Fetches all data in parallel using `Promise.all` on mount.
- Accepts optional `courseId` and `professorId` params (passed as query strings).
- Re-fetches when `courseId` changes.


**2. `frontend/src/components/insights/KpiCards.jsx`** (NEW)

4 stat cards in a row:
- Total Sessions (sessions icon)
- Avg Attendance Rate (shown as %, with trend arrow ↑↓→ vs previous week)
- Comfort Score (colored: green ≥70, amber 40–69, red <40)
- At-Risk Students (red badge if > 0)

Use the same `.stat-card` CSS pattern from the existing Dashboard.jsx.


**3. `frontend/src/components/insights/AttendanceTrendChart.jsx`** (NEW)

Recharts `AreaChart` (same pattern as existing sparklines in Dashboard.jsx):
- X-axis: week labels
- Y-axis: 0–100%
- Area fill: `linearGradient` from `var(--color-primary)` to transparent
- Props: `data` (array of {week_label, attendance_rate}), `height` (default 200)


**4. `frontend/src/components/insights/DayOfWeekHeatmap.jsx`** (NEW)

A 7-column (Mon–Sun) × 3-row (Morning/Afternoon/Evening) grid.
Each cell is a colored square: white (no data) → light blue → dark blue based on attendance_rate.
Label each cell with the rate as a percentage. Use CSS grid layout.


**5. `frontend/src/components/insights/AtRiskTable.jsx`** (NEW)

A sortable table of at-risk students:
- Columns: Name, Student ID, Attendance Rate (with colored bar), Consecutive Absences, Courses At Risk, Risk Level badge (High/Medium)
- Clicking a row expands it to show the student's course breakdown (call `GET /api/insights/students/{id}/profile` on expand).
- Risk level: High if rate < 50% or consecutive_absences ≥ 5. Medium otherwise.
- Empty state: illustrated message "All students are on track 🎉" when list is empty.


**6. `frontend/src/components/insights/ComfortScoreCard.jsx`** (NEW)

A circular gauge SVG showing the comfort score 0–100.
- The arc fills based on the score.
- Color: green (≥70), amber (40–69), red (<40).
- Below the gauge: label "Comfort Score" + a one-line description of which sensor is dragging it down most (derived from the breakdown — compare each penalty component).
- Props: `score` (number), `breakdown` (optional {temp_penalty, humidity_penalty, aq_penalty}).


**7. `frontend/src/components/insights/SensorTrendChart.jsx`** (NEW)

Recharts `LineChart` with multiple lines (one per sensor type).
- Props: `data` (array of {date, temp_avg, humidity_avg, air_quality_avg}), `height`
- Each sensor type has its own color from tokens (use --color-primary, --color-success, --color-warning).
- Legend at top.


**8. `frontend/src/components/insights/CorrelationScatter.jsx`** (NEW)

Recharts `ScatterChart`:
- X axis: avg_temp (°C)
- Y axis: attendance_rate (%)
- Each dot is one session. Tooltip shows: course_code, date, temp, rate.
- Title: "Temperature vs. Attendance"
- Props: `data` (array of {avg_temp, attendance_rate, course_code, date})


**9. `frontend/src/pages/Insights.jsx`** (NEW)

Main insights page with 3 tabs using existing tab pattern (look at how Dashboard.jsx implements tabs):

Tab 1 — **Overview**:
- `<KpiCards />` at the top
- `<AiSummaryCard scope="global" id="all" title="Global AI Summary" />`
- `<AttendanceTrendChart />` (full width)
- `<DayOfWeekHeatmap />` (full width)

Tab 2 — **Students**:
- Course filter dropdown (GET /api/courses to populate)
- `<AiSummaryCard scope="course" id={selectedCourseId} />` — only shown when a course is selected
- `<AtRiskTable />` filtered by selected course (or all if none selected)

Tab 3 — **Environment**:
- `<ComfortScoreCard />` (live, from overview data)
- `<SensorTrendChart />` (last 7 days)
- `<CorrelationScatter />` (temp vs attendance)
- `<AiSummaryCard scope="room" id="room1" title="Room Analysis" />`


**10. `frontend/src/components/Layout.jsx`** — add Insights nav item

Add an "Insights" link to the sidebar navigation, between "History" and any existing bottom items.
Icon: a bar-chart inline SVG (3 vertical bars of ascending height).
Route: `/insights`


**11. Add route in the app router**

In whatever file defines the React Router routes (likely `main.jsx` or `App.jsx`):
```jsx
import Insights from './pages/Insights'
// add:
<Route path="/insights" element={<Insights />} />
```


**12. Mini-cards on existing pages**

Modify these existing files minimally — add only what is specified:

`Dashboard.jsx`: After the existing sensor strip, add a `<ComfortScoreCard score={overview.comfort_score} />` pill (compact version — just the number and color, no gauge). Add a conditional banner: if `overview.at_risk_count > 0`, show `<div className="alert-card">⚠️ {overview.at_risk_count} students are at risk across your courses. <a href="/insights">View in Insights →</a></div>`.

`Attendance.jsx`: In the student list row, add a risk badge next to each student name. Fetch at-risk list from `GET /api/insights/students/at-risk` once on page load; if the student's id is in the list, show a red "At Risk" pill. If they have consecutive_absences ≥ 2 but are not below threshold, show an amber "Watch" pill.

`History.jsx`: In each session row (the expandable row header), after the attendance percentage, add a trend arrow. Compare this session's attendance_rate to the previous session's rate for the same course. ↑ if improved ≥5pp, ↓ if declined ≥5pp, → otherwise. This requires knowing session order — sort by started_at and compute diff client-side from the existing sessions list data.


### Constraints
- Do not modify `tokens.css` or `index.css` unless you need to add max 2 new utility classes.
- All chart components must handle empty `data=[]` gracefully with an "No data yet" empty state.
- The Insights page must work fully in demo mode (when backend is unreachable) — use hardcoded fallback arrays for charts if `loading=false && error` is set.
- Do not install any new npm packages. All chart needs are covered by Recharts already in package.json.


### Verification
```bash
docker compose build frontend && docker compose up -d frontend
# Open http://localhost:3000/insights
# Confirm: 3 tabs render, KPI cards show numbers, AtRiskTable shows students from seed data
# Confirm: comfort score card shows a number with correct color
# Confirm: sidebar shows Insights link and it is active on /insights
# Open http://localhost:3000 (Dashboard) — confirm at-risk banner appears if seed has at-risk students
```
Update CLAUDE.md Phase 21 row to ✅.
```

---

---

# PHASE 22 — Export System (PDF + CSV)

## Goal
Add server-side PDF generation for session and course reports, and CSV export for raw attendance data.

## Prompt

```
Read CLAUDE.md in full before writing a single line of code.

You are implementing Phase 22 of the Smart Classroom Management System: the Export system.

All previous phases (19, 20, 21) must be complete. The Insights page must be rendering correctly before starting this phase.

### What to build

**1. `requirements.txt`**

Add: `reportlab>=4.1.0`


**2. `backend/app/services/pdf_exporter.py`** (NEW)

Create two async functions:

```python
async def export_session_pdf(session_id: UUID, db, redis) -> bytes
async def export_course_pdf(course_id: UUID, db) -> bytes
```

Both return raw PDF bytes (to be streamed as `application/pdf`).

Use ReportLab's `Platypus` layout engine (`SimpleDocTemplate`, `Table`, `Paragraph`, `Spacer`, `HRFlowable`).

**Session PDF layout** (in order):
1. Header: SMU logo text ("SMU — Mediterranean Institute of Technology") + "Session Report" title
2. Metadata table: Course name, Date, Professor, Room, Duration (ended_at - started_at in minutes)
3. Horizontal rule
4. Section heading: "Attendance"
5. Attendance table: columns = [#, Student Name, Student ID, Status, Detected At, Adjusted By]
   - Status cell: color-coded text (Present=green, Absent=red, Late=orange, Excused=grey)
   - Rows sorted by detected_at ascending, absent rows last
6. Summary line: "Present: N | Absent: N | Late: N | Excused: N | Total Enrolled: N"
7. Horizontal rule
8. Section heading: "Environmental Summary"
9. Sensor table: columns = [Sensor, Average, Min, Max, Unit]
   - One row per sensor type (temperature, humidity, air_quality, sound)
   - Call existing `GET /api/sessions/{id}/sensors/summary` logic directly (reuse the query, don't HTTP call self)
10. Section heading: "AI Summary" — fetch narrative from `ai_summary.generate_summary` (scope=session). If 503, write "AI summaries not configured."
11. Paragraph: render the narrative text
12. Footer: "Generated by Smart Classroom System · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

**Course PDF layout** (in order):
1. Header: same SMU header + "Course Report"
2. Metadata: Course name, Course code, Professor, Total Sessions, Report Period (first session → last session date)
3. Horizontal rule
4. Section: "Attendance Summary"
5. Per-student table: [Student Name, Student ID, Sessions Attended, Total Sessions, Rate %, Risk Flag]
   - Risk Flag: "⚠ At Risk" if rate < AT_RISK_THRESHOLD, "" otherwise
   - Sort by rate ascending (worst attendance first)
6. Section: "Session History"
7. Sessions table: [Date, Duration (min), Present, Absent, Late, Attendance Rate]
   - One row per ended session, sorted by date
8. Section: "AI Summary" — scope=course
9. Paragraph: narrative
10. Footer

Style guide for both PDFs:
- Use only built-in ReportLab fonts: Helvetica (body), Helvetica-Bold (headings)
- Page size: A4
- Margins: 2cm all sides
- Heading font size: 14pt, body: 10pt, footer: 8pt
- Table alternating row colors: white / #F8F9FA (very light grey)
- No images, no external resources — pure text and tables only


**3. `backend/app/services/csv_exporter.py`** (NEW)

```python
async def export_course_csv(course_id: UUID, db) -> str
```

Returns a CSV string. Columns:
`session_date, session_id, student_name, student_id, status, detected_at, adjusted_by, adjusted_at`

One row per attendance record across all ended sessions of the course.
Sort by session_date ascending, then student_name ascending.
Use Python's built-in `csv.DictWriter` with `StringIO`. No pandas.


**4. `backend/app/api/insights.py` — add export endpoints**

Add to the existing insights router (append only):

```
GET /api/insights/export/session/{session_id}
  → Calls pdf_exporter.export_session_pdf()
  → Returns StreamingResponse(iter([pdf_bytes]), media_type="application/pdf",
      headers={"Content-Disposition": f"attachment; filename=session_{session_id}.pdf"})

GET /api/insights/export/course/{course_id}
  → Calls pdf_exporter.export_course_pdf()
  → Returns StreamingResponse for PDF

GET /api/insights/export/course/{course_id}/csv
  → Calls csv_exporter.export_course_csv()
  → Returns Response(csv_string, media_type="text/csv",
      headers={"Content-Disposition": f"attachment; filename=course_{course_id}.csv"})
```

Return 404 if session or course not found.
Return 400 if session is not ended (session PDF requires ended session).


**5. `frontend/src/components/insights/ExportButton.jsx`** (NEW)

A React component:
- Props: `type` ("session" | "course"), `id` (UUID string), `courseName` (string, for display)
- Renders a button group with 2 buttons:
  - "Export PDF" — on click, calls `GET /api/insights/export/{type}/{id}` and triggers browser download using `window.URL.createObjectURL`.
  - "Export CSV" (only shown when type="course") — calls `GET /api/insights/export/course/{id}/csv`.
- While downloading: button shows spinner + "Generating..." text (disabled).
- On error: show inline error message "Export failed. Try again."
- Use existing button styles from `index.css`.


**6. Wire ExportButton into the Insights page**

In `Insights.jsx`:
- On the Overview tab: add `<ExportButton type="course" id={selectedCourseId} />` below the AI Summary card (only shown when a course is selected in the course filter).
- On the Students tab: add an Export button per row in AtRiskTable — small "Export" link button that triggers a session export is NOT needed; instead add a course-level export at the top of the Students tab.

In `History.jsx` (existing page):
- In each expanded session row (the detail panel), add `<ExportButton type="session" id={session.id} />`.


### Constraints
- `pdf_exporter.py` and `csv_exporter.py` must not make HTTP calls to self. They must import and call DB query functions directly.
- Do not add any new DB tables or models.
- The PDF must be fully generated server-side. No client-side PDF libraries.
- Export endpoints must work even if `ANTHROPIC_API_KEY` is not set (AI section in PDF gracefully omitted).
- `ExportButton` must not block the UI — use async fetch + blob download pattern.


### Verification
```bash
docker compose build backend && docker compose up -d backend

# Get a session ID from seed data
SESSION_ID=$(curl -s http://localhost:8000/api/sessions | python3 -c "import sys,json; sessions=[s for s in json.load(sys.stdin) if s['status']=='ended']; print(sessions[0]['id'])")

# Download session PDF
curl -o /tmp/session_test.pdf "http://localhost:8000/api/insights/export/session/$SESSION_ID"
file /tmp/session_test.pdf   # must report: PDF document

# Get a course ID
COURSE_ID=$(curl -s http://localhost:8000/api/courses | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Download course PDF
curl -o /tmp/course_test.pdf "http://localhost:8000/api/insights/export/course/$COURSE_ID"
file /tmp/course_test.pdf

# Download course CSV
curl -o /tmp/course_test.csv "http://localhost:8000/api/insights/export/course/$COURSE_ID/csv"
head /tmp/course_test.csv   # must show CSV headers
```

Open http://localhost:3000/history, expand a session, and confirm the Export PDF button downloads a valid PDF in the browser.

Update CLAUDE.md Phase 22 row to ✅.
```

---

## Summary of All Phases

| Phase | Key Output | New Files |
|---|---|---|
| 19 | Analytics backend — all insights queries, at-risk logic, comfort score, correlations | `insights_engine.py`, `insights.py` (backend) |
| 20 | AI summaries — Anthropic SDK, Redis cache, AiSummaryCard | `ai_summary.py` (backend), `AiSummaryCard.jsx` (frontend) |
| 21 | Full Insights page — 3 tabs, all charts, mini-cards on existing pages | `Insights.jsx`, `useInsights.js`, 7 chart components, Layout.jsx update |
| 22 | PDF + CSV export — ReportLab server-side, ExportButton component | `pdf_exporter.py`, `csv_exporter.py`, `ExportButton.jsx` |