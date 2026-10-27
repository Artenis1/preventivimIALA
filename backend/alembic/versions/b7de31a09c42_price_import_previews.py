"""Owner-scoped expiring price-import previews for explicit confirmation."""

from alembic import op
import sqlalchemy as sa

revision = "b7de31a09c42"
down_revision = "aea36f175bbe"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "price_import_previews",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_import_previews_owner_id", "price_import_previews", ["owner_id"]
    )
    op.create_index(
        "ix_price_import_previews_expires_at", "price_import_previews", ["expires_at"]
    )


def downgrade():
    op.drop_index(
        "ix_price_import_previews_expires_at", table_name="price_import_previews"
    )
    op.drop_index(
        "ix_price_import_previews_owner_id", table_name="price_import_previews"
    )
    op.drop_table("price_import_previews")
