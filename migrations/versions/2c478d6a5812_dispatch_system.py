"""dispatch system

Revision ID: 2c478d6a5812
Revises: 61b4819273f1
Create Date: 2026-04-12 22:57:21.832592

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '2c478d6a5812'
down_revision = '61b4819273f1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('delivery_boy_stats', schema=None) as batch_op:
        batch_op.alter_column('total_notified',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_accepted',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_rejected',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_expired',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_delivered',
               existing_type=mysql.INTEGER(),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('acceptance_rate',
               existing_type=mysql.FLOAT(),
               nullable=True,
               existing_server_default=sa.text("'1'"))

    with op.batch_alter_table('order_dispatches', schema=None) as batch_op:
        batch_op.alter_column('status',
               existing_type=mysql.VARCHAR(length=20),
               nullable=True,
               existing_server_default=sa.text("'pending'"))
        batch_op.alter_column('notified_at',
               existing_type=mysql.DATETIME(),
               nullable=True,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        # ← removed 3 drop_index calls that conflicted with FK constraints

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column('otp_verified',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=True,
               existing_server_default=sa.text("'0'"))
        batch_op.create_foreign_key(None, 'users', ['delivery_boy_id'], ['id'])


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.alter_column('otp_verified',
               existing_type=mysql.TINYINT(display_width=1),
               nullable=False,
               existing_server_default=sa.text("'0'"))

    with op.batch_alter_table('order_dispatches', schema=None) as batch_op:
        batch_op.alter_column('notified_at',
               existing_type=mysql.DATETIME(),
               nullable=False,
               existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        batch_op.alter_column('status',
               existing_type=mysql.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'pending'"))
        # ← removed 3 create_index calls to match

    with op.batch_alter_table('delivery_boy_stats', schema=None) as batch_op:
        batch_op.alter_column('acceptance_rate',
               existing_type=mysql.FLOAT(),
               nullable=False,
               existing_server_default=sa.text("'1'"))
        batch_op.alter_column('total_delivered',
               existing_type=mysql.INTEGER(),
               nullable=False,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_expired',
               existing_type=mysql.INTEGER(),
               nullable=False,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_rejected',
               existing_type=mysql.INTEGER(),
               nullable=False,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_accepted',
               existing_type=mysql.INTEGER(),
               nullable=False,
               existing_server_default=sa.text("'0'"))
        batch_op.alter_column('total_notified',
               existing_type=mysql.INTEGER(),
               nullable=False,
               existing_server_default=sa.text("'0'"))