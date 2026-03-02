"""domain_varchar

Revision ID: 57d381c70465
Revises: c4f21a8b3e09
Create Date: 2026-03-02 10:02:20.325621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57d381c70465'
down_revision: Union[str, None] = 'c4f21a8b3e09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE tasks ALTER COLUMN domain TYPE VARCHAR(100) USING domain::VARCHAR;")

def downgrade():
    pass