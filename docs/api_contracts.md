# API Contracts — Smart Classroom Management System

Base URL: `http://<raspberry-pi-ip>:8000`  
All request and response bodies are JSON (`Content-Type: application/json`).  
Timestamps are ISO-8601 strings in UTC (e.g. `"2024-06-01T10:30:00Z"`).

---

## Health

### GET /health

Returns the status of the backend and its dependencies.

**Response 200:**
```json
{
  "status": "ok",
  "redis": true,
  "db": true
}
```

---

## Sensors

### GET /api/sensors/latest

Returns the most recent sensor readings from the Redis cache.

**Query parameters:**

| Name      | Type   | Default  | Description           |
|-----------|--------|----------|-----------------------|
| `room_id` | string | `room1`  | Room identifier       |

**Response 200:**
```json
{
  "room_id": "room1",
  "sensors": {
    "temperature": {"value": 24.5, "unit": "C"},
    "humidity": {"value": 62.1, "unit": "%"},
    "air_quality": {"value": 320.0, "unit": "ppm"},
    "sound": {"value": 1.0, "unit": "bool"}
  }
}
```
Note: Keys are absent if no value has been received for that sensor yet.

---

### GET /api/sensors/history

Returns historical sensor readings from PostgreSQL.

**Query parameters:**

| Name          | Type     | Default  | Description                               |
|---------------|----------|----------|-------------------------------------------|
| `room_id`     | string   | `room1`  | Room identifier                           |
| `sensor_type` | string   | —        | One of: `temperature`, `humidity`, `air_quality`, `sound` |
| `from_ts`     | datetime | —        | ISO-8601 start timestamp                  |
| `to_ts`       | datetime | —        | ISO-8601 end timestamp                    |
| `limit`       | int      | 100      | Max records (1–1000)                      |

**Response 200:**
```json
[
  {
    "id": "uuid",
    "room_id": "room1",
    "sensor_type": "temperature",
    "value": 25.3,
    "unit": "C",
    "recorded_at": "2024-06-01T10:00:00Z"
  }
]
```

---

## Courses

### GET /api/courses

Returns all courses.

**Response 200:**
```json
[
  {"id": "uuid", "code": "CS301", "name": "Operating Systems", "professor_name": "Dr. Smith"}
]
```

---

### POST /api/courses

Creates a new course.

**Request body:**
```json
{"code": "CS301", "name": "Operating Systems", "professor_name": "Dr. Smith"}
```

**Response 201:**
```json
{"id": "uuid", "code": "CS301", "name": "Operating Systems", "professor_name": "Dr. Smith"}
```

**Response 409:** Course code already exists.

---

### GET /api/courses/{id}

Returns a single course.

**Response 200:** Same as course object above.  
**Response 404:** Course not found.

---

### POST /api/courses/{id}/enroll

Enrolls students in a course.

**Request body:**
```json
{"student_ids": ["uuid1", "uuid2"]}
```

**Response 200:**
```json
{"enrolled": 2}
```

**Response 404:** Course or any student not found.

---

## Sessions

### POST /api/sessions/start

Starts a new class session. Only one session may be active per room.

**Request body:**
```json
{"course_id": "uuid", "room_id": "room1"}
```

**Response 201:**
```json
{
  "id": "uuid",
  "course_id": "uuid",
  "room_id": "room1",
  "started_at": "2024-06-01T08:00:00Z",
  "ended_at": null,
  "status": "active"
}
```

**Response 404:** Course not found.  
**Response 409:** A session is already active in this room.

---

### POST /api/sessions/{id}/end

Ends an active session and triggers background Moodle sync.

**Response 200:**
```json
{
  "id": "uuid",
  "course_id": "uuid",
  "room_id": "room1",
  "started_at": "2024-06-01T08:00:00Z",
  "ended_at": "2024-06-01T09:30:00Z",
  "status": "ended"
}
```

**Response 404:** Session not found.  
**Response 409:** Session already ended.

---

### GET /api/sessions

Lists sessions with optional filters.

**Query parameters:**

| Name        | Type   | Description                         |
|-------------|--------|-------------------------------------|
| `course_id` | string | Filter by course                    |
| `room_id`   | string | Filter by room                      |
| `status`    | string | `active` or `ended`                 |

**Response 200:** Array of session-with-summary objects:
```json
[
  {
    "id": "uuid",
    "course_id": "uuid",
    "room_id": "room1",
    "started_at": "2024-06-01T08:00:00Z",
    "ended_at": null,
    "status": "active",
    "present_count": 12,
    "total_students": 20,
    "course": {"id": "uuid", "code": "CS301", "name": "Operating Systems", "professor_name": "Dr. Smith"}
  }
]
```

---

### GET /api/sessions/{id}

Returns a single session with attendance summary.

**Response 200:** Session-with-summary object (same as list item above).  
**Response 404:** Session not found.

---

## Attendance

### GET /api/sessions/{session_id}/attendance

Returns all attendance records for a session, including student names.

**Response 200:**
```json
[
  {
    "id": "uuid",
    "session_id": "uuid",
    "student_id": "uuid",
    "status": "present",
    "detected_at": "2024-06-01T08:05:00Z",
    "adjusted_by": null,
    "adjusted_at": null,
    "moodle_synced": false,
    "student_name": "Hedi Ben Jemaa",
    "student_number": "MED2024001"
  }
]
```

**Response 404:** Session not found.

---

### PATCH /api/attendance/{record_id}

Manually adjusts an attendance record status. Sets `adjusted_by = "professor"`.

**Request body:**
```json
{"status": "excused"}
```
Valid statuses: `present`, `absent`, `late`, `excused`

**Response 200:** Updated attendance record.  
**Response 404:** Record not found.  
**Response 422:** Invalid status value.

---

### POST /api/sessions/{session_id}/mark-absent

Bulk-inserts absent records for enrolled students who have no record yet. Called at session end.

**Response 200:** Array of newly created absent records.  
**Response 404:** Session not found.

---

### GET /api/students/{student_id}/attendance-history

Returns a student's full cross-session attendance history.

**Response 200:**
```json
[
  {
    "record_id": "uuid",
    "session_id": "uuid",
    "course_code": "CS301",
    "course_name": "Operating Systems",
    "session_date": "2024-06-01T08:00:00Z",
    "status": "present",
    "detected_at": "2024-06-01T08:05:00Z",
    "adjusted_by": null
  }
]
```

---

## Control

### POST /api/control/ac

Controls the AC relay.

**Request body:**
```json
{"room_id": "room1", "action": "on"}
```
Valid actions: `on`, `off`, `auto`

**Response 200:**
```json
{"room_id": "room1", "device": "ac", "action": "on", "ts": "2024-06-01T10:00:00Z"}
```

**Response 422:** Invalid action value.

---

### POST /api/control/lighting

Controls the lighting relay. Same schema as `/api/control/ac`.

---

### GET /api/control/status/{room_id}

Returns current relay states and live sensor values.

**Response 200:**
```json
{
  "room_id": "room1",
  "ac": "auto",
  "lighting": "off",
  "device_online": true,
  "temperature": 25.3,
  "humidity": 60.0,
  "air_quality": 310.0
}
```

**Response 503:** Redis unavailable.

---

## Alerts

### GET /api/alerts

Lists alerts with optional filters.

**Query parameters:**

| Name           | Type    | Description                              |
|----------------|---------|------------------------------------------|
| `room_id`      | string  | Filter by room                           |
| `acknowledged` | boolean | `true` / `false`                         |
| `limit`        | int     | Max records (1–500, default 50)          |

**Response 200:**
```json
[
  {
    "id": "uuid",
    "room_id": "room1",
    "type": "temp_high",
    "value": 36.2,
    "message": "Temperature 36.2°C exceeded threshold of 28°C",
    "acknowledged": false,
    "created_at": "2024-06-01T11:00:00Z"
  }
]
```

Alert types: `temp_high`, `temp_low`, `air_quality_high`, `attendance_anomaly`, `device_offline`

---

### PATCH /api/alerts/{id}/acknowledge

Marks an alert as acknowledged.

**Response 200:** Updated alert object.  
**Response 404:** Alert not found.

---

### GET /api/alerts/unread-count/{room_id}

Returns the count of unacknowledged alerts (used for the dashboard badge).

**Response 200:**
```json
{"count": 3}
```

---

## Enrollment

### GET /api/students

Returns all students.

**Response 200:**
```json
[
  {"id": "uuid", "name": "Hedi Ben Jemaa", "student_id": "MED2024001", "created_at": "2024-01-01T00:00:00Z"}
]
```

---

### POST /api/students

Creates a new student.

**Request body:**
```json
{"name": "Hedi Ben Jemaa", "student_id": "MED2024001"}
```

**Response 201:** Student object.  
**Response 409:** Student ID already exists.

---

### POST /api/students/{id}/enroll-face

Uploads a face image for enrollment. Computes and stores the 128-d encoding.

**Request:** `multipart/form-data` with field `file` (JPEG/PNG image).

**Response 200:**
```json
{"student_id": "uuid", "frames_captured": 1, "message": "Face encoding stored."}
```

**Response 400:** No face detected in image.  
**Response 404:** Student not found.

---

### GET /api/students/{id}/courses

Returns courses the student is enrolled in.

**Response 200:** Array of course objects.

---

## Moodle

### GET /api/moodle-test

Tests the Moodle connection.

**Response 200:**
```json
{"connected": true, "moodle_url": "http://localhost:8080"}
```

---

### POST /api/sessions/{id}/sync-moodle

Manually triggers Moodle sync for a session.

**Response 200:**
```json
{"session_id": "uuid", "synced": 18, "failed": 2}
```

---

## WebSocket

### WS /ws/classroom/{room_id}

Live event stream for the dashboard.

**Events pushed by server:**

```json
{"type": "sensor_update", "room_id": "room1", "sensor_type": "temperature", "value": 25.1, "unit": "C", "ts": 1714300000}
```
```json
{"type": "attendance_event", "room_id": "room1", "student_id": "uuid", "student_name": "Hedi Ben Jemaa", "session_id": "uuid", "status": "present"}
```
```json
{"type": "alert", "room_id": "room1", "alert_type": "temp_high", "value": 36.2, "message": "Temperature exceeded threshold"}
```

**Connection:** The React frontend uses a single WebSocket per tab, shared across pages via `SensorContext`.
