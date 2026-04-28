"""initial

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("student_id", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("professor_name", sa.String(255), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "ended", name="sessionstatus"),
            nullable=False,
            server_default="active",
        ),
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("present", "absent", "late", "excused", name="attendancestatus"),
            nullable=False,
            server_default="present",
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("adjusted_by", sa.String(100), nullable=True),
        sa.Column("adjusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moodle_synced", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "face_encodings",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("encoding", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("room_id", sa.String(50), nullable=False),
        sa.Column(
            "sensor_type",
            sa.Enum("temperature", "humidity", "air_quality", "sound", name="sensortype"),
            nullable=False,
        ),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sensor_readings_room_type_time", "sensor_readings", ["room_id", "sensor_type", "recorded_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("room_id", sa.String(50), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "temp_high", "temp_low", "air_quality_high", "attendance_anomaly", "device_offline",
                name="alerttype",
            ),
            nullable=False,
        ),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_index("ix_sensor_readings_room_type_time", table_name="sensor_readings")
    op.drop_table("sensor_readings")
    op.drop_table("face_encodings")
    op.drop_table("attendance_records")
    op.drop_table("sessions")
    op.drop_table("courses")
    op.drop_table("students")

    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS sensortype")
    op.execute("DROP TYPE IF EXISTS attendancestatus")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
