"""add course_students association table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_students",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("course_id", "student_id"),
    )


def downgrade() -> None:
    op.drop_table("course_students")
