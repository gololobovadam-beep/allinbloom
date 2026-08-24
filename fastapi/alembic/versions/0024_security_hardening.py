"""add OTP verification attempt tracking

Revision ID: 0024_security_hardening
Revises: 0023_payment_reliability
Create Date: 2026-08-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_security_hardening"
down_revision = "0023_payment_reliability"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "VerificationCode",
        sa.Column(
            "attemptCount",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade():
    op.drop_column("VerificationCode", "attemptCount")
