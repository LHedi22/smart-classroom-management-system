"""add professors table and professor_id FK on courses

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:02:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the professor_role enum type first
    op.execute("CREATE TYPE professor_role AS ENUM ('professor', 'admin')")

    op.create_table(
        "professors",
        sa.Column(
            "id", sa.String(36), nullable=False,
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("professor", "admin", name="professor_role", create_type=False),
            nullable=False,
            server_default="professor",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=True,
        ),
        sa.UniqueConstraint("email", name="uq_professors_email"),
    )

    op.add_column(
        "courses",
        sa.Column("professor_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_courses_professor_id",
        "courses", "professors",
        ["professor_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_courses_professor_id", "courses", type_="foreignkey")
    op.drop_column("courses", "professor_id")
    op.drop_table("professors")
    op.execute("DROP TYPE IF EXISTS professor_role")
