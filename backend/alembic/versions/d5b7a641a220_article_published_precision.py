"""Store date-only publication precision for sources without post times."""

import sqlalchemy as sa

from alembic import op

revision = "d5b7a641a220"
down_revision = "b3d0f190d2a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("articles", sa.Column("published_precision", sa.String(16), nullable=True))


def downgrade():
    op.drop_column("articles", "published_precision")
