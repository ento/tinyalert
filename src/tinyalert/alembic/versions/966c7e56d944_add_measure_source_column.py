"""Add measure_source column

Revision ID: 966c7e56d944
Revises: cabfb49f9f42
Create Date: 2023-05-07 21:49:25.531328

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "966c7e56d944"
down_revision = "cabfb49f9f42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("points", sa.Column("measure_source", sa.TEXT(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("points", "measure_source")
    # ### end Alembic commands ###