"""add optional titles to event tiers

Revision ID: 0025_event_tier_titles
Revises: 0024_security_hardening
Create Date: 2026-08-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_event_tier_titles"
down_revision = "0024_security_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("EventTier", sa.Column("title", sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column("EventTier", "title")
