"""add cross scope fields to change plan items

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-14 20:47:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('change_plan_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_managed_folder_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('destination_managed_folder_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('source_canonical_path', sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column('destination_canonical_path', sa.String(length=1024), nullable=True))
        batch_op.add_column(sa.Column('move_type', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('conflict_resolution', sa.String(length=32), nullable=True, server_default='fail'))


def downgrade() -> None:
    with op.batch_alter_table('change_plan_items', schema=None) as batch_op:
        batch_op.drop_column('conflict_resolution')
        batch_op.drop_column('move_type')
        batch_op.drop_column('destination_canonical_path')
        batch_op.drop_column('source_canonical_path')
        batch_op.drop_column('destination_managed_folder_id')
        batch_op.drop_column('source_managed_folder_id')
