"""merge migrations from main and local

Revision ID: 79f915f97305
Revises: 690e351fd44e, ccae44bc4921
Create Date: 2026-05-26 17:40:23.180925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79f915f97305'
down_revision: Union[str, Sequence[str], None] = ('690e351fd44e', 'ccae44bc4921')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
