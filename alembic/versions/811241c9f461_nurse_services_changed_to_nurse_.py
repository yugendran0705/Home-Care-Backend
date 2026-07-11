"""nurse_services changed to nurse_associated_services

Revision ID: 811241c9f461
Revises: 79f915f97305
Create Date: 2026-05-28 16:37:36.129010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '811241c9f461'
down_revision: Union[str, Sequence[str], None] = '79f915f97305'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # If the destination table already exists (for example from another branch),
    # treat this migration step as already applied.
    if 'nurse_associated_services' in table_names:
        return

    if 'nurse_services' in table_names:
        op.rename_table('nurse_services', 'nurse_associated_services')
        op.drop_constraint(
            op.f('nurse_services_nurse_id_fkey'),
            'nurse_associated_services',
            type_='foreignkey',
        )
        op.drop_constraint(
            op.f('nurse_services_service_id_fkey'),
            'nurse_associated_services',
            type_='foreignkey',
        )
        op.create_foreign_key(
            op.f('nurse_associated_services_nurse_id_fkey'),
            'nurse_associated_services',
            'nurses',
            ['nurse_id'],
            ['nurse_id'],
        )
        op.create_foreign_key(
            op.f('nurse_associated_services_service_id_fkey'),
            'nurse_associated_services',
            'nursing_services',
            ['service_id'],
            ['service_id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if 'nurse_services' in table_names:
        return

    if 'nurse_associated_services' in table_names:
        op.drop_constraint(
            op.f('nurse_associated_services_nurse_id_fkey'),
            'nurse_associated_services',
            type_='foreignkey',
        )
        op.drop_constraint(
            op.f('nurse_associated_services_service_id_fkey'),
            'nurse_associated_services',
            type_='foreignkey',
        )
        op.rename_table('nurse_associated_services', 'nurse_services')
        op.create_foreign_key(
            op.f('nurse_services_nurse_id_fkey'),
            'nurse_services',
            'nurses',
            ['nurse_id'],
            ['nurse_id'],
        )
        op.create_foreign_key(
            op.f('nurse_services_service_id_fkey'),
            'nurse_services',
            'nursing_services',
            ['service_id'],
            ['service_id'],
        )
