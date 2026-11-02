"""add profile_image and phone_number to users

Revision ID: c91f083d3214
Revises: a73d89e4c102
Create Date: 2026-11-02 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c91f083d3214'
down_revision: Union[str, Sequence[str], None] = 'a73d89e4c102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('phone_number', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('profile_image', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'profile_image')
    op.drop_column('users', 'phone_number')
