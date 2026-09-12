"""add poisson_count_model to modelfamily enum

Revision ID: 4e74a8790a02
Revises: 77b7230f50b1
Create Date: 2026-09-12 07:16:50.667751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e74a8790a02'
down_revision: Union[str, Sequence[str], None] = '77b7230f50b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add POISSON_COUNT_MODEL to the modelfamily enum (used by the new
    corners/cards attack-defense Poisson model — see MODEL_SPEC.md)."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE modelfamily ADD VALUE IF NOT EXISTS 'POISSON_COUNT_MODEL'")


def downgrade() -> None:
    """Postgres does not support removing an enum value; downgrading this
    migration is a no-op (existing rows using POISSON_COUNT_MODEL, if any,
    would need to be migrated to another family first, out of scope here)."""
    pass
