"""Keep the original publisher distinct from the aggregation provider."""

import sqlalchemy as sa

from alembic import op

revision = "a712e938c0d4"
down_revision = "8d2c19f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("articles", sa.Column("publisher_name", sa.String(200), nullable=True))


def downgrade():
    op.drop_column("articles", "publisher_name")
