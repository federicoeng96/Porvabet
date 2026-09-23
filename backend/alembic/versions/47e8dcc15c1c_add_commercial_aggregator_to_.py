"""add E_COMMERCIAL_AGGREGATOR_API to datasourcecategory enum

Revision ID: 47e8dcc15c1c
Revises: 8f3b1c9d4a21
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47e8dcc15c1c'
down_revision: Union[str, Sequence[str], None] = '8f3b1c9d4a21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add E_COMMERCIAL_AGGREGATOR_API to the datasourcecategory enum — a
    bucket distinct from D for third-party commercial odds-aggregation APIs
    (e.g. The Odds API) that resell/relay other sources' data under their own
    paid-product ToS, rather than being the original source itself accessed
    via the user's own account (see app/models/enums.py and DATA_SOURCES.md
    "Categoria E")."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE datasourcecategory ADD VALUE IF NOT EXISTS "
            "'E_COMMERCIAL_AGGREGATOR_API'"
        )


def downgrade() -> None:
    """Postgres does not support removing an enum value; downgrading this
    migration is a no-op (existing rows using the new value, if any, would
    need to be migrated to another category first, out of scope here)."""
    pass
