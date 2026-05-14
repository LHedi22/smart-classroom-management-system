"""add unique constraint on attendance_records (session_id, student_id)

Revision ID: 007
Revises: 006
Create Date: 2024-01-01 00:06:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicate rows, keeping only the earliest record per (session_id, student_id)
    op.execute("""
        DELETE FROM attendance_records
        WHERE id NOT IN (
            SELECT DISTINCT ON (session_id, student_id) id
            FROM attendance_records
            ORDER BY session_id, student_id, detected_at ASC
        )
    """)
    op.create_unique_constraint(
        "uq_attendance_session_student",
        "attendance_records",
        ["session_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_attendance_session_student",
        "attendance_records",
        type_="unique",
    )
