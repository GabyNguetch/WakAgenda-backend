"""add_task_comments

Revision ID: c4f21a8b3e09
Revises: b3c12d9e0f41
Create Date: 2026-03-01 11:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c4f21a8b3e09"
down_revision: Union[str, None] = "b3c12d9e0f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_comments",
        sa.Column("id",         sa.UUID(),  nullable=False),
        sa.Column("task_id",    sa.UUID(),  nullable=False),
        sa.Column("content",    sa.Text(),  nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_task_comments_task_id"),
    )
    op.create_index(op.f("ix_task_comments_id"),      "task_comments", ["id"],      unique=False)
    op.create_index(op.f("ix_task_comments_task_id"), "task_comments", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_task_comments_task_id"), table_name="task_comments")
    op.drop_index(op.f("ix_task_comments_id"),      table_name="task_comments")
    op.drop_table("task_comments")