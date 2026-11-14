"""add drive root fields to managed folders

Revision ID: a1b2c3d4e5f6
Revises: feffb39d7374
Create Date: 2026-11-14 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'feffb39d7374'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('managed_folders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('root_type', sa.String(length=32), nullable=False, server_default='directory'))
        batch_op.add_column(sa.Column('volume_label', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('volume_serial', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('is_available', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    with op.batch_alter_table('managed_folders', schema=None) as batch_op:
        batch_op.drop_column('is_available')
        batch_op.drop_column('volume_serial')
        batch_op.drop_column('volume_label')
        batch_op.drop_column('root_type')
