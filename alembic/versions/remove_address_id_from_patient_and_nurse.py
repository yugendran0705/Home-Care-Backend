"""Remove address_id from Patient and Nurse tables

Revision ID: remove_address_id
Revises: 79f915f97305
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_address_id'
# Base this migration on the current merge head to avoid creating a new
# unintended branch/head in Alembic history.
down_revision: Union[str, Sequence[str], None] = '79f915f97305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - remove address_id from Patient and Nurse tables."""
    # Drop the foreign key constraint for patients.address_id
    op.drop_constraint(
        'patients_address_id_fkey',
        'patients',
        type_='foreignkey'
    )
    
    # Drop the foreign key constraint for nurses.address_id
    op.drop_constraint(
        'nurses_address_id_fkey',
        'nurses',
        type_='foreignkey'
    )
    
    # Indexes on address_id are removed when the column is dropped.
    # Do not drop them explicitly here, as they may already have been removed
    # by an earlier migration (690e351fd44e) in some branches.
    
    # Drop the address_id column from patients table
    op.drop_column('patients', 'address_id')
    
    # Drop the address_id column from nurses table
    op.drop_column('nurses', 'address_id')


def downgrade() -> None:
    """Downgrade schema - restore address_id to Patient and Nurse tables."""
    # Add address_id column back to patients table
    op.add_column('patients', sa.Column('address_id', sa.UUID(), nullable=True))
    
    # Add address_id column back to nurses table
    op.add_column('nurses', sa.Column('address_id', sa.UUID(), nullable=True))
    
    # Note: Do not recreate indexes here. The immediate down_revision (690e351fd44e)
    # does not have these indexes, and its downgrade() will create them, which would
    # fail if they already exist.
    
    # Recreate the foreign key constraint for patients.address_id
    op.create_foreign_key(
        'patients_address_id_fkey',
        'patients',
        'addresses',
        ['address_id'],
        ['address_id']
    )
    
    # Recreate the foreign key constraint for nurses.address_id
    op.create_foreign_key(
        'nurses_address_id_fkey',
        'nurses',
        'addresses',
        ['address_id'],
        ['address_id']
    )
