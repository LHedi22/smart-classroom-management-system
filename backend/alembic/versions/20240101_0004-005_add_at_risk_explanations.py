"""add at_risk_explanations table

Revision ID: 005
Revises: 004
Create Date: 2024-01-01 00:04:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "at_risk_explanations",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "student_id",
            sa.String(36),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("overall_attendance_rate", sa.Float, nullable=False),
        sa.Column("summary_explanation", sa.Text, nullable=True),
        sa.Column("per_course_data", postgresql.JSONB, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ollama_reachable",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_table("at_risk_explanations")
