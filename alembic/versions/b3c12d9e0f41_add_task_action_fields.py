"""add_task_action_fields

Revision ID: b3c12d9e0f41
Revises: a7bf48c97750
Create Date: 2026-03-01 10:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b3c12d9e0f41"
down_revision: Union[str, None] = "a7bf48c97750"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Table domains ──────────────────────────────────────────────────────
    op.create_table(
        "domains",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_domains_id"),   "domains", ["id"],   unique=False)
    op.create_index(op.f("ix_domains_slug"), "domains", ["slug"], unique=True)

    # ── 2. Nouveaux champs sur tasks ──────────────────────────────────────────
    op.add_column("tasks", sa.Column("accept_token", sa.String(length=36), nullable=True))
    op.add_column("tasks", sa.Column("cancel_token", sa.String(length=36), nullable=True))
    op.add_column("tasks", sa.Column("accepted_at",  sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "domain_id",
            sa.UUID(),
            sa.ForeignKey("domains.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_index(op.f("ix_tasks_accept_token"), "tasks", ["accept_token"], unique=True)
    op.create_index(op.f("ix_tasks_cancel_token"), "tasks", ["cancel_token"], unique=True)
    op.create_index(op.f("ix_tasks_domain_id"),    "tasks", ["domain_id"],    unique=False)

    # ── 3. Étendre l'enum task_status avec LATE et MISSED ─────────────────────
    # PostgreSQL ne supporte pas ALTER TYPE … ADD VALUE dans une transaction.
    # On exécute chaque ALTER hors transaction avec execution_options.
    op.execute(
        sa.text("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'En retard'")
        .execution_options(autocommit=True)  # type: ignore[attr-defined]
    )
    op.execute(
        sa.text("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'Manquée'")
        .execution_options(autocommit=True)  # type: ignore[attr-defined]
    )


def downgrade() -> None:
    # Suppression des index et colonnes ajoutés sur tasks
    op.drop_index(op.f("ix_tasks_domain_id"),    table_name="tasks")
    op.drop_index(op.f("ix_tasks_cancel_token"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_accept_token"), table_name="tasks")

    op.drop_column("tasks", "domain_id")
    op.drop_column("tasks", "accepted_at")
    op.drop_column("tasks", "cancel_token")
    op.drop_column("tasks", "accept_token")

    # Suppression de la table domains
    op.drop_index(op.f("ix_domains_slug"), table_name="domains")
    op.drop_index(op.f("ix_domains_id"),   table_name="domains")
    op.drop_table("domains")

    # Note : PostgreSQL ne permet pas de retirer des valeurs d'un enum existant.
    # Pour rétrograder complètement, il faudrait recréer l'enum sans LATE/MISSED,
    # ce qui nécessiterait de caster toutes les colonnes concernées.
    # Ce downgrade ne retire donc pas les valeurs 'En retard' et 'Manquée' de l'enum.