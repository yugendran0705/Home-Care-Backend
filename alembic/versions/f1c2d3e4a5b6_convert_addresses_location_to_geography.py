"""Convert addresses.location from varchar to geography point

Revision ID: f1c2d3e4a5b6
Revises: 889c029914b9
Create Date: 2026-06-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1c2d3e4a5b6"
down_revision: Union[str, Sequence[str], None] = "889c029914b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Revision 889c029914b9 (this migration's down_revision) already adds
    # addresses.location directly as geography(POINT,4326). Only perform the
    # varchar -> geography conversion if the column is still text-typed, so
    # this migration is a safe no-op when that's already the case.
    op.execute("""
        DO $$
        BEGIN
            IF (
                SELECT udt_name FROM information_schema.columns
                WHERE table_name = 'addresses' AND column_name = 'location'
            ) <> 'geography' THEN
                EXECUTE 'DROP INDEX IF EXISTS idx_addresses_location';
                EXECUTE $sql$
                    ALTER TABLE addresses
                    ALTER COLUMN location TYPE geography(POINT,4326)
                    USING CASE
                        WHEN location IS NULL OR btrim(location) = '' THEN NULL
                        ELSE ST_GeogFromText(location)
                    END
                $sql$;
            END IF;
        END $$;
        """)

    op.create_index(
        "idx_addresses_location",
        "addresses",
        ["location"],
        unique=False,
        postgresql_using="gist",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_addresses_location")

    op.execute("""
        ALTER TABLE addresses
        ALTER COLUMN location TYPE VARCHAR(64)
        USING CASE
            WHEN location IS NULL THEN NULL
            ELSE ST_AsText(location)
        END
        """)

    op.create_index(
        "idx_addresses_location",
        "addresses",
        ["location"],
        unique=False,
    )
