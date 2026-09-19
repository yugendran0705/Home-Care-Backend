"""merge parallel heads

Revision ID: 67199b98b760
Revises: 811241c9f461, remove_address_id
Create Date: 2026-06-10 00:04:33.315373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67199b98b760'
down_revision: Union[str, Sequence[str], None] = ('811241c9f461', 'remove_address_id')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
