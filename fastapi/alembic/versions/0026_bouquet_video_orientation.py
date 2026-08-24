"""store the display orientation selected for catalog videos

Revision ID: 0026_bouquet_video_orientation
Revises: 0025_event_tier_titles
Create Date: 2026-08-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_bouquet_video_orientation"
down_revision = "0025_event_tier_titles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "Bouquet",
        sa.Column(
            "videoOrientation",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'HORIZONTAL'"),
        ),
    )


def downgrade():
    op.drop_column("Bouquet", "videoOrientation")
