"""Remove address_id from Patient and Nurse tables

Revision ID: remove_address_id
Revises: 45910d2620a6
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_address_id'
down_revision: Union[str, Sequence[str], None] = '45910d2620a6'
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
    
    # Drop the index on patients.address_id
    op.drop_index('ix_patients_address_id', table_name='patients')
    
    # Drop the index on nurses.address_id
    op.drop_index('ix_nurses_address_id', table_name='nurses')
    
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
    
    # Recreate the index on patients.address_id
    op.create_index('ix_patients_address_id', 'patients', ['address_id'], unique=False)
    
    # Recreate the index on nurses.address_id
    op.create_index('ix_nurses_address_id', 'nurses', ['address_id'], unique=False)
    
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
