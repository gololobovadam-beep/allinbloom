"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    role_enum = postgresql.ENUM("ADMIN", "CUSTOMER", name="Role", create_type=False)
    flower_enum = postgresql.ENUM(
        "ROSE",
        "TULIP",
        "LILY",
        "PEONY",
        "ORCHID",
        "MIXED",
        name="FlowerType",
        create_type=False,
    )
    style_enum = postgresql.ENUM(
        "ROMANTIC",
        "MODERN",
        "GARDEN",
        "MINIMAL",
        name="BouquetStyle",
        create_type=False,
    )
    order_status_enum = postgresql.ENUM(
        "PENDING",
        "PAID",
        "FAILED",
        "CANCELED",
        name="OrderStatus",
        create_type=False,
    )

    role_enum.create(op.get_bind(), checkfirst=True)
    flower_enum.create(op.get_bind(), checkfirst=True)
    style_enum.create(op.get_bind(), checkfirst=True)
    order_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "User",
        sa.Column("id", sa.String(), primary_key=True, server_default="default"),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("role", role_enum, nullable=False, server_default="CUSTOMER"),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_User_email", "User", ["email"], unique=True)

    op.create_table(
        "VerificationCode",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("codeHash", sa.String(), nullable=False),
        sa.Column("salt", sa.String(), nullable=False),
        sa.Column("expiresAt", sa.DateTime(timezone=True), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_VerificationCode_email", "VerificationCode", ["email"], unique=False)

    op.create_table(
        "Bouquet",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("priceCents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("flowerType", flower_enum, nullable=False),
        sa.Column("style", style_enum, nullable=False),
        sa.Column("colors", sa.String(), nullable=False),
        sa.Column("isMixed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("isFeatured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("discountPercent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discountNote", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=False),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "Order",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("stripeSessionId", sa.String(), nullable=True),
        sa.Column("totalCents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("status", order_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("isRead", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_Order_email", "Order", ["email"], unique=False)
    op.create_index("ix_Order_stripeSessionId", "Order", ["stripeSessionId"], unique=True)

    op.create_table(
        "OrderItem",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("orderId", sa.String(), nullable=False),
        sa.Column("bouquetId", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("priceCents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("image", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["orderId"], ["Order.id"]),
        sa.ForeignKeyConstraint(["bouquetId"], ["Bouquet.id"]),
    )

    op.create_table(
        "PromoSlide",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=False),
        sa.Column("link", sa.String(), nullable=True),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "StoreSettings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("globalDiscountPercent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("globalDiscountNote", sa.String(), nullable=True),
        sa.Column("categoryDiscountPercent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("categoryDiscountNote", sa.String(), nullable=True),
        sa.Column("categoryFlowerType", sa.String(), nullable=True),
        sa.Column("categoryStyle", sa.String(), nullable=True),
        sa.Column("categoryMixed", sa.String(), nullable=True),
        sa.Column("categoryColor", sa.String(), nullable=True),
        sa.Column("categoryMinPriceCents", sa.Integer(), nullable=True),
        sa.Column("categoryMaxPriceCents", sa.Integer(), nullable=True),
        sa.Column("firstOrderDiscountPercent", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("firstOrderDiscountNote", sa.String(), nullable=True),
        sa.Column("updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("StoreSettings")
    op.drop_table("PromoSlide")
    op.drop_table("OrderItem")
    op.drop_index("ix_Order_stripeSessionId", table_name="Order")
    op.drop_index("ix_Order_email", table_name="Order")
    op.drop_table("Order")
    op.drop_table("Bouquet")
    op.drop_index("ix_VerificationCode_email", table_name="VerificationCode")
    op.drop_table("VerificationCode")
    op.drop_index("ix_User_email", table_name="User")
    op.drop_table("User")

    # SQLite has no standalone enum types; the PostgreSQL ENUM declarations
    # above are represented as text there.  Avoid PostgreSQL-only DDL when
    # using SQLite for local development and migration regression tests.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS \"OrderStatus\"")
        op.execute("DROP TYPE IF EXISTS \"BouquetStyle\"")
        op.execute("DROP TYPE IF EXISTS \"FlowerType\"")
        op.execute("DROP TYPE IF EXISTS \"Role\"")
