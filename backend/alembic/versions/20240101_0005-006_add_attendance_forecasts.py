"""add attendance_forecasts table

Revision ID: 006
Revises: 005
Create Date: 2024-01-01 00:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_forecasts",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("trend_data", postgresql.JSONB, nullable=False),
        sa.Column("expected_next_rate", sa.Float, nullable=True),
        sa.Column("trend_classification", sa.String(30), nullable=True),
        sa.Column("confidence_level", sa.String(10), nullable=True),
        sa.Column("interpretation", sa.Text, nullable=True),
        sa.Column("suggested_action", sa.String(30), nullable=True),
        sa.Column(
            "ollama_reachable",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("attendance_forecasts")
