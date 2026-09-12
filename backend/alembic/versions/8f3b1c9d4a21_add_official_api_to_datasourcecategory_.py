"""add D_OFFICIAL_API_PERSONAL_ACCOUNT to datasourcecategory enum

Revision ID: 8f3b1c9d4a21
Revises: 4e74a8790a02
Create Date: 2026-09-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3b1c9d4a21'
down_revision: Union[str, Sequence[str], None] = '4e74a8790a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add D_OFFICIAL_API_PERSONAL_ACCOUNT to the datasourcecategory enum — a
    new bucket distinct from A/B/C for official, documented APIs accessed via
    the user's own account (e.g. Betfair Exchange), where there is no
    scraping/ToS-risk classification to make (see app/models/enums.py and
    DATA_SOURCES.md)."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE datasourcecategory ADD VALUE IF NOT EXISTS "
            "'D_OFFICIAL_API_PERSONAL_ACCOUNT'"
        )


def downgrade() -> None:
    """Postgres does not support removing an enum value; downgrading this
    migration is a no-op (existing rows using the new value, if any, would
    need to be migrated to another category first, out of scope here)."""
    pass
