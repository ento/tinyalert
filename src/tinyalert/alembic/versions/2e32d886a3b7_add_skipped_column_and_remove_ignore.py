"""add skipped column and remove ignore

Revision ID: 2e32d886a3b7
Revises: 966c7e56d944
Create Date: 2023-05-11 11:59:10.938023

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2e32d886a3b7"
down_revision = "966c7e56d944"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("points") as batch_op:
        batch_op.add_column(
            sa.Column("skipped", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.drop_column("ignore")


def downgrade() -> None:
    with op.batch_alter_table("points") as batch_op:
        batch_op.add_column(sa.Column("ignore", sa.VARCHAR(length=8), nullable=True))
        batch_op.drop_column("skipped")
