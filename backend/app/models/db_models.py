import enum

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    Float,
    ForeignKey,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────

class ProfessorRole(str, enum.Enum):
    professor = "professor"
    admin = "admin"


class SessionStatus(str, enum.Enum):
    active = "active"
    ended = "ended"
    upcoming = "upcoming"  # pre-scheduled, not yet started


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"
    excused = "excused"


class SensorType(str, enum.Enum):
    temperature = "temperature"
    humidity = "humidity"
    air_quality = "air_quality"
    sound = "sound"


class AlertType(str, enum.Enum):
    temp_high = "temp_high"
    temp_low = "temp_low"
    air_quality_high = "air_quality_high"
    attendance_anomaly = "attendance_anomaly"
    device_offline = "device_offline"


# ── Professor ─────────────────────────────────────────────────────────────

class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[ProfessorRole] = mapped_column(
        Enum(ProfessorRole, name="professor_role"),
        nullable=False,
        default=ProfessorRole.professor,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    courses: Mapped[list["Course"]] = relationship("Course", back_populates="professor")


# ── Association table: many-to-many Course ↔ Student ──────────────────────

course_students = Table(
    "course_students",
    Base.metadata,
    Column("course_id", String(36), ForeignKey("courses.id", ondelete="CASCADE")),
    Column("student_id", String(36), ForeignKey("students.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("course_id", "student_id"),
)


# ── ORM Models ─────────────────────────────────────────────────────────────

class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    face_encodings: Mapped[list["FaceEncoding"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="student"
    )
    courses: Mapped[list["Course"]] = relationship(
        secondary=course_students, back_populates="students"
    )
    at_risk_explanation: Mapped["AtRiskExplanation | None"] = relationship(
        back_populates="student", uselist=False, cascade="all, delete-orphan"
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    professor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # FK to professors table — nullable so pre-auth seeded data is unaffected
    professor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("professors.id", ondelete="SET NULL"), nullable=True
    )

    professor: Mapped["Professor | None"] = relationship("Professor", back_populates="courses")
    sessions: Mapped[list["Session"]] = relationship(back_populates="course")
    students: Mapped[list["Student"]] = relationship(
        secondary=course_students, back_populates="courses"
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.active
    )

    course: Mapped["Course"] = relationship(back_populates="sessions")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.present
    )
    detected_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    adjusted_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adjusted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moodle_synced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    session: Mapped["Session"] = relationship(back_populates="attendance_records")
    student: Mapped["Student"] = relationship(back_populates="attendance_records")


class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    encoding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["Student"] = relationship(back_populates="face_encodings")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    room_id: Mapped[str] = mapped_column(String(50), nullable=False)
    sensor_type: Mapped[SensorType] = mapped_column(Enum(SensorType), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    room_id: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AtRiskExplanation(Base):
    __tablename__ = "at_risk_explanations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, server_default=text("gen_random_uuid()")
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    overall_attendance_rate: Mapped[float] = mapped_column(Float, nullable=False)
    summary_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    per_course_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    ollama_reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    student: Mapped["Student"] = relationship(back_populates="at_risk_explanation")
