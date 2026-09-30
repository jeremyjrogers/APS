"""add capacity exception categories to enum

Revision ID: 5af0526a1c9e
Revises: 9c9bc2939a00
Create Date: 2026-08-22 15:48:28.988433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5af0526a1c9e'
down_revision: Union[str, Sequence[str], None] = '9c9bc2939a00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_VALUES = ("CAPACITY_CONSTRAINED_LATE", "CAPACITY_INFEASIBLE")


def upgrade() -> None:
    """Add the finite-capacity exception categories.

    Alembic autogenerate does not detect new members of an existing Postgres
    enum type, so this has to be written by hand.
    """
    for value in NEW_VALUES:
        op.execute(f"ALTER TYPE exceptioncategory ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Postgres cannot drop a value from an enum type in place; reversing this
    means recreating the type, which is not worth doing for a POC."""
    pass
