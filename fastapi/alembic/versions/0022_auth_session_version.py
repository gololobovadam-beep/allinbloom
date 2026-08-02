"""add a server-side authentication session version

Revision ID: 0022_auth_session_version
Revises: 0021_catalog_products_and_gallery_relations
Create Date: 2026-08-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_auth_session_version"
down_revision = "0021_catalog_products_and_gallery_relations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "User",
        sa.Column(
            "authVersion",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade():
    op.drop_column("User", "authVersion")
