"""delivery overhaul columns

Revision ID: 9d4b8f3a1c21
Revises: 2c478d6a5812
Create Date: 2026-04-27 14:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d4b8f3a1c21"
down_revision = "2c478d6a5812"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("otp_attempts", sa.Integer(), nullable=True, server_default="0"))
        batch_op.add_column(sa.Column("otp_locked_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_online", sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.add_column(sa.Column("last_heartbeat", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_heartbeat")
        batch_op.drop_column("is_online")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("otp_locked_at")
        batch_op.drop_column("otp_attempts")
