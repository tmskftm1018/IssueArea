"""Track provider update and delete events independently of inserts."""

import sqlalchemy as sa

from alembic import op

revision = "8d2c19f3a4b5"
down_revision = "06c8bea3b273"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "collection_runs",
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "collection_runs",
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Match ORM defaults after backfilling existing runs. SQLite keeps server defaults.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column("collection_runs", "updated_count", server_default=None)
        op.alter_column("collection_runs", "deleted_count", server_default=None)


def downgrade():
    op.drop_column("collection_runs", "deleted_count")
    op.drop_column("collection_runs", "updated_count")
