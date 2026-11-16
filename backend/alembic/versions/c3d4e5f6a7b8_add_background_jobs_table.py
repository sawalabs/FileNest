"""add background jobs table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-16 20:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'background_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_step', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('items_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('managed_folder_id', sa.String(length=36), nullable=True),
        sa.Column('managed_folder_name', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_payload', sa.Text(), nullable=True),
        sa.Column('cancellation_requested', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.String(length=32), nullable=True),
        sa.Column('finished_at', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.String(length=32), nullable=False),
        sa.Column('updated_at', sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name='ck_background_jobs_status'
        ),
    )
    op.create_index('idx_background_jobs_status_created', 'background_jobs', ['status', 'created_at'])
    op.create_index('idx_background_jobs_type', 'background_jobs', ['job_type'])


def downgrade() -> None:
    op.drop_index('idx_background_jobs_type', table_name='background_jobs')
    op.drop_index('idx_background_jobs_status_created', table_name='background_jobs')
    op.drop_table('background_jobs')
