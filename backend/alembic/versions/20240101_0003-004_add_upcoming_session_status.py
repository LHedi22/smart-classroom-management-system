"""add upcoming value to session_status enum

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 00:03:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The enum was created as "sessionstatus" (no underscore) by SQLAlchemy in migration 001.
    # PostgreSQL 15 — ALTER TYPE ADD VALUE is safe inside a transaction.
    # IF NOT EXISTS guards against re-running on a DB that was already patched manually.
    op.execute("ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'upcoming'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; downgrade is a no-op.
    pass
