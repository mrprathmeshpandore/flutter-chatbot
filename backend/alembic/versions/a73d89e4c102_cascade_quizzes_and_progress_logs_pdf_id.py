"""cascade quizzes and progress logs pdf id

Revision ID: a73d89e4c102
Revises: 28e6378281b7
Create Date: 2026-10-30 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a73d89e4c102'
down_revision: Union[str, Sequence[str], None] = '28e6378281b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. Fix quizzes.pdf_id foreign key constraint to CASCADE
    # ---------------------------------------------------------
    # In live PostgreSQL, quizzes_pdf_id_fkey currently has ON DELETE SET NULL.
    # We drop it and recreate it with ON DELETE CASCADE.
    op.drop_constraint('quizzes_pdf_id_fkey', 'quizzes', type_='foreignkey')
    op.create_foreign_key(
        'quizzes_pdf_id_fkey',
        'quizzes',
        'pdf_documents',
        ['pdf_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # ---------------------------------------------------------
    # 2. Add pdf_id column to progress_logs table
    # ---------------------------------------------------------
    op.add_column(
        'progress_logs',
        sa.Column('pdf_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f('ix_progress_logs_pdf_id'),
        'progress_logs',
        ['pdf_id'],
        unique=False,
    )

    # ---------------------------------------------------------
    # 3. Clean up orphaned activity logs of previously deleted PDFs
    # ---------------------------------------------------------
    # In PostgreSQL, metadata_json is type 'json' (not 'jsonb').
    # We use (metadata_json->>'pdf_id') IS NOT NULL instead of the '?' operator.
    op.execute(
        """
        DELETE FROM progress_logs
        WHERE metadata_json IS NOT NULL
          AND (metadata_json->>'pdf_id') IS NOT NULL
          AND (metadata_json->>'pdf_id') ~ '^[0-9]+$'
          AND CAST(metadata_json->>'pdf_id' AS INTEGER) NOT IN (SELECT id FROM pdf_documents);
        """
    )

    # ---------------------------------------------------------
    # 4. Backfill pdf_id for active existing PDFs
    # ---------------------------------------------------------
    # Link remaining valid PDF-related logs to their active parent PDF document
    op.execute(
        """
        UPDATE progress_logs
        SET pdf_id = CAST(metadata_json->>'pdf_id' AS INTEGER)
        WHERE metadata_json IS NOT NULL
          AND (metadata_json->>'pdf_id') IS NOT NULL
          AND (metadata_json->>'pdf_id') ~ '^[0-9]+$'
          AND CAST(metadata_json->>'pdf_id' AS INTEGER) IN (SELECT id FROM pdf_documents);
        """
    )

    # ---------------------------------------------------------
    # 5. Add Foreign Key on progress_logs.pdf_id with CASCADE
    # ---------------------------------------------------------
    op.create_foreign_key(
        'progress_logs_pdf_id_fkey',
        'progress_logs',
        'pdf_documents',
        ['pdf_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    # Drop progress_logs foreign key, index, and column
    op.drop_constraint('progress_logs_pdf_id_fkey', 'progress_logs', type_='foreignkey')
    op.drop_index(op.f('ix_progress_logs_pdf_id'), table_name='progress_logs')
    op.drop_column('progress_logs', 'pdf_id')

    # Revert quizzes foreign key back to SET NULL
    op.drop_constraint('quizzes_pdf_id_fkey', 'quizzes', type_='foreignkey')
    op.create_foreign_key(
        'quizzes_pdf_id_fkey',
        'quizzes',
        'pdf_documents',
        ['pdf_id'],
        ['id'],
        ondelete='SET NULL',
    )
