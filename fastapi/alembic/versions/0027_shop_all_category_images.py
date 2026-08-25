"""add image settings for Shop all category tiles

Revision ID: 0027_shop_all_category_images
Revises: 0026_bouquet_video_orientation
Create Date: 2026-08-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_shop_all_category_images"
down_revision = "0026_bouquet_video_orientation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "StoreSettings",
        sa.Column(
            "shopAllImageFlowers",
            sa.String(),
            nullable=False,
            server_default=sa.text("'/images/hero-bouquet.webp'"),
        ),
    )
    op.add_column(
        "StoreSettings",
        sa.Column(
            "shopAllImageBalloons",
            sa.String(),
            nullable=False,
            server_default=sa.text("'/images/bouquet-2.webp'"),
        ),
    )
    op.add_column(
        "StoreSettings",
        sa.Column(
            "shopAllImageGiftBox",
            sa.String(),
            nullable=False,
            server_default=sa.text("'/images/bouquet-5.webp'"),
        ),
    )
    op.add_column(
        "StoreSettings",
        sa.Column(
            "shopAllImageEventSpace",
            sa.String(),
            nullable=False,
            server_default=sa.text("'/images/bouquet-7.webp'"),
        ),
    )


def downgrade():
    op.drop_column("StoreSettings", "shopAllImageEventSpace")
    op.drop_column("StoreSettings", "shopAllImageGiftBox")
    op.drop_column("StoreSettings", "shopAllImageBalloons")
    op.drop_column("StoreSettings", "shopAllImageFlowers")
