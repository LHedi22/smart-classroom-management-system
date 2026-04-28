from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.db_models import AlertType, AttendanceStatus, SensorType, SessionStatus


# ── Student ────────────────────────────────────────────────────────────────

class StudentBase(BaseModel):
    name: str
    student_id: str


class StudentCreate(StudentBase):
    pass


class StudentResponse(StudentBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Course ─────────────────────────────────────────────────────────────────

class CourseBase(BaseModel):
    code: str
    name: str
    professor_name: str


class CourseCreate(CourseBase):
    pass


class CourseResponse(CourseBase):
    id: str

    model_config = {"from_attributes": True}


class CourseEnrollRequest(BaseModel):
    student_ids: list[str]


# ── Session ────────────────────────────────────────────────────────────────

class SessionStart(BaseModel):
    course_id: str
    room_id: str


class SessionResponse(BaseModel):
    id: str
    course_id: str
    room_id: str
    started_at: datetime
    ended_at: datetime | None
    status: SessionStatus

    model_config = {"from_attributes": True}


class SessionWithSummary(SessionResponse):
    present_count: int = 0
    total_students: int = 0
    course: CourseResponse | None = None


# ── Attendance ─────────────────────────────────────────────────────────────

class AttendanceRecordResponse(BaseModel):
    id: str
    session_id: str
    student_id: str
    status: AttendanceStatus
    detected_at: datetime
    adjusted_by: str | None
    adjusted_at: datetime | None
    moodle_synced: bool

    model_config = {"from_attributes": True}


class AttendanceWithStudent(AttendanceRecordResponse):
    student_name: str = ""
    student_number: str = ""  # institutional ID


class AttendanceAdjust(BaseModel):
    status: AttendanceStatus


class StudentHistoryEntry(BaseModel):
    record_id: str
    session_id: str
    course_code: str
    course_name: str
    session_date: datetime
    status: AttendanceStatus
    detected_at: datetime
    adjusted_by: str | None


# ── Sensor readings ────────────────────────────────────────────────────────

class SensorReadingResponse(BaseModel):
    id: str
    room_id: str
    sensor_type: SensorType
    value: float
    unit: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class SensorLatestResponse(BaseModel):
    room_id: str
    sensors: dict[str, Any]  # {sensor_type: {value, unit}}


# ── Alerts ────────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    id: str
    room_id: str
    type: AlertType
    value: float | None
    message: str
    acknowledged: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Control ───────────────────────────────────────────────────────────────

class RelayCommand(BaseModel):
    room_id: str
    action: str

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in {"on", "off", "auto"}:
            raise ValueError("action must be 'on', 'off', or 'auto'")
        return v


class RelayCommandResponse(BaseModel):
    room_id: str
    device: str
    action: str
    ts: datetime


class ControlStatusResponse(BaseModel):
    room_id: str
    ac: str              # on | off | auto
    lighting: str        # on | off | auto
    device_online: bool
    temperature: float | None = None
    humidity: float | None = None
    air_quality: float | None = None


# ── Enrollment ────────────────────────────────────────────────────────────

class EnrollFaceResponse(BaseModel):
    student_id: str
    frames_captured: int
    message: str


# ── Moodle ────────────────────────────────────────────────────────────────

class MoodleSyncResult(BaseModel):
    session_id: str
    synced: int
    failed: int


class MoodleConnectionStatus(BaseModel):
    connected: bool
    moodle_url: str


# ── Health ────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    redis: bool
    db: bool
