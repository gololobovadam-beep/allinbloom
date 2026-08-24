"""make payment state transitions durable and auditable

Revision ID: 0023_payment_reliability
Revises: 0022_auth_session_version
Create Date: 2026-08-20 00:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "0023_payment_reliability"
down_revision = "0022_auth_session_version"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    # PostgreSQL stores this enum natively. SQLite uses a VARCHAR/check
    # representation, so model metadata is sufficient there.
    if dialect == "postgresql":
        for value in (
            "PARTIALLY_REFUNDED",
            "REFUNDED",
            "DISPUTED",
            "CHARGEBACK",
            "REVERSED",
        ):
            op.execute(
                "DO $$ BEGIN "
                f"ALTER TYPE \"OrderStatus\" ADD VALUE IF NOT EXISTS '{value}'; "
                "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            )
    # Payment providers and checkout are intentionally USD-only. Case-only
    # legacy variants are harmless and are normalized; a real foreign currency
    # must be reviewed by an operator instead of silently re-denominating it.
    op.execute(
        'UPDATE "Bouquet" SET "currency" = \'USD\' '
        'WHERE UPPER("currency") = \'USD\' AND "currency" <> \'USD\''
    )
    # Offline Alembic generation has no database result set to inspect.  The
    # PostgreSQL CHECK emitted below still rejects non-USD rows when the SQL
    # is applied; the explicit diagnostic is available during normal online
    # releases where an operator can act on it before the DDL runs.
    if not context.is_offline_mode():
        non_usd_count = bind.execute(
            sa.text(
                'SELECT COUNT(*) FROM "Bouquet" '
                'WHERE "currency" IS NULL OR UPPER("currency") <> \'USD\''
            )
        ).scalar_one()
        if non_usd_count:
            raise RuntimeError(
                "USD-only payment migration found non-USD Bouquet.currency values. "
                "Review and explicitly convert or retire those catalog prices before retrying."
            )
    if dialect == "postgresql":
        op.create_check_constraint(
            "ck_Bouquet_currency_usd", "Bouquet", '"currency" = \'USD\''
        )

    op.add_column("Order", sa.Column("stripePaymentIntentId", sa.String(), nullable=True))
    op.add_column("Order", sa.Column("stripeChargeId", sa.String(), nullable=True))
    op.add_column("Order", sa.Column("paymentProvider", sa.String(), nullable=True))
    op.add_column("Order", sa.Column("checkoutIdempotencyKey", sa.String(), nullable=True))
    op.add_column("Order", sa.Column("checkoutRequestFingerprint", sa.String(), nullable=True))
    op.add_column("Order", sa.Column("checkoutRedirectUrl", sa.String(), nullable=True))
    op.add_column(
        "Order",
        sa.Column("refundedCents", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_Order_stripePaymentIntentId",
        "Order",
        ["stripePaymentIntentId"],
        unique=True,
    )
    op.create_index("ix_Order_stripeChargeId", "Order", ["stripeChargeId"], unique=True)
    op.create_index(
        "ix_Order_checkoutIdempotencyKey",
        "Order",
        ["checkoutIdempotencyKey"],
        unique=True,
    )

    # Existing rows already represent fully processed events. New webhook
    # deliveries start as PROCESSING and are completed atomically by code.
    op.add_column(
        "WebhookEvent",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'PROCESSED'"),
        ),
    )
    op.add_column(
        "WebhookEvent",
        sa.Column("claimedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "WebhookEvent",
        sa.Column("processedAt", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        'UPDATE "WebhookEvent" SET "claimedAt" = "createdAt", '
        '"processedAt" = "createdAt" WHERE "processedAt" IS NULL'
    )
    if dialect == "sqlite":
        # SQLite has no ALTER COLUMN. Batch mode recreates only this isolated
        # webhook table and keeps the migration usable in local/test SQLite.
        with op.batch_alter_table("WebhookEvent") as batch:
            batch.alter_column(
                "claimedAt",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
            batch.alter_column(
                "status",
                existing_type=sa.String(),
                server_default=sa.text("'PROCESSING'"),
            )
    else:
        op.alter_column(
            "WebhookEvent",
            "claimedAt",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        op.alter_column(
            "WebhookEvent",
            "status",
            existing_type=sa.String(),
            server_default=sa.text("'PROCESSING'"),
        )

    op.create_table(
        "NotificationOutbox",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("orderId", sa.String(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'PENDING'")
        ),
        sa.Column(
            "attemptCount", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "availableAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("lockedAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sentAt", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lastError", sa.String(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["orderId"], ["Order.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orderId", "event", name="uq_NotificationOutbox_orderId_event"),
    )
    op.create_index(
        op.f("ix_NotificationOutbox_orderId"),
        "NotificationOutbox",
        ["orderId"],
        unique=False,
    )
    op.create_index(
        "ix_NotificationOutbox_status_availableAt",
        "NotificationOutbox",
        ["status", "availableAt"],
        unique=False,
    )

    # A webhook delivery id is not a financial idempotency key: PayPal can
    # notify both a capture and a refund event for the same refund. Preserve a
    # ledger row keyed by the provider's refund object before changing totals.
    op.create_table(
        "PaymentLedgerEntry",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("orderId", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("entryType", sa.String(), nullable=False),
        sa.Column("externalReference", sa.String(), nullable=False),
        sa.Column("amountCents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("sourceEventId", sa.String(), nullable=True),
        sa.Column(
            "createdAt",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["orderId"], ["Order.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "externalReference",
            name="uq_PaymentLedgerEntry_provider_externalReference",
        ),
    )
    op.create_index(
        op.f("ix_PaymentLedgerEntry_orderId"),
        "PaymentLedgerEntry",
        ["orderId"],
        unique=False,
    )
    op.create_index(
        "ix_PaymentLedgerEntry_orderId_createdAt",
        "PaymentLedgerEntry",
        ["orderId", "createdAt"],
        unique=False,
    )
    op.create_index(
        op.f("ix_PaymentLedgerEntry_sourceEventId"),
        "PaymentLedgerEntry",
        ["sourceEventId"],
        unique=False,
    )

    # The original migration used a cascading FK. Keep the historical ledger
    # when an order is soft-deleted or an accidental hard-delete is attempted.
    if dialect == "postgresql":
        # The historical unnamed PostgreSQL constraint has this deterministic
        # server-generated name.  Offline mode has a MockConnection and
        # cannot inspect it; online mode retains inspection for installations
        # whose schema was created with a custom constraint name.
        payment_event_fk_name = "PaymentEvent_orderId_fkey"
        if not context.is_offline_mode():
            payment_event_fk_name = next(
                (
                    foreign_key.get("name")
                    for foreign_key in sa.inspect(bind).get_foreign_keys("PaymentEvent")
                    if foreign_key.get("constrained_columns") == ["orderId"]
                ),
                None,
            )
        if payment_event_fk_name:
            op.drop_constraint(
                payment_event_fk_name, "PaymentEvent", type_="foreignkey"
            )
        op.create_foreign_key(
            "fk_PaymentEvent_orderId_Order",
            "PaymentEvent",
            "Order",
            ["orderId"],
            ["id"],
            ondelete="RESTRICT",
        )
    elif dialect == "sqlite":
        # The historical SQLite FK was anonymous.  Name it deterministically
        # while rebuilding the table so local databases enforce the same
        # audit-trail retention policy as PostgreSQL.
        with op.batch_alter_table(
            "PaymentEvent",
            recreate="always",
            naming_convention={
                "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            },
        ) as batch:
            batch.drop_constraint("fk_PaymentEvent_orderId_Order", type_="foreignkey")
            batch.create_foreign_key(
                "fk_PaymentEvent_orderId_Order",
                "Order",
                ["orderId"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.drop_constraint(
            "fk_PaymentEvent_orderId_Order", "PaymentEvent", type_="foreignkey"
        )
        op.create_foreign_key(
            "PaymentEvent_orderId_fkey",
            "PaymentEvent",
            "Order",
            ["orderId"],
            ["id"],
            ondelete="CASCADE",
        )
        op.drop_constraint("ck_Bouquet_currency_usd", "Bouquet", type_="check")
    elif dialect == "sqlite":
        with op.batch_alter_table(
            "PaymentEvent",
            recreate="always",
            naming_convention={
                "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            },
        ) as batch:
            batch.drop_constraint("fk_PaymentEvent_orderId_Order", type_="foreignkey")
            batch.create_foreign_key(
                "fk_PaymentEvent_orderId_Order",
                "Order",
                ["orderId"],
                ["id"],
                ondelete="CASCADE",
            )

    op.drop_index(
        op.f("ix_PaymentLedgerEntry_sourceEventId"), table_name="PaymentLedgerEntry"
    )
    op.drop_index(
        "ix_PaymentLedgerEntry_orderId_createdAt", table_name="PaymentLedgerEntry"
    )
    op.drop_index(op.f("ix_PaymentLedgerEntry_orderId"), table_name="PaymentLedgerEntry")
    op.drop_table("PaymentLedgerEntry")

    op.drop_index("ix_NotificationOutbox_status_availableAt", table_name="NotificationOutbox")
    op.drop_index(op.f("ix_NotificationOutbox_orderId"), table_name="NotificationOutbox")
    op.drop_table("NotificationOutbox")

    op.drop_column("WebhookEvent", "processedAt")
    op.drop_column("WebhookEvent", "claimedAt")
    op.drop_column("WebhookEvent", "status")

    op.drop_index("ix_Order_checkoutIdempotencyKey", table_name="Order")
    op.drop_index("ix_Order_stripeChargeId", table_name="Order")
    op.drop_index("ix_Order_stripePaymentIntentId", table_name="Order")
    op.drop_column("Order", "refundedCents")
    op.drop_column("Order", "checkoutRedirectUrl")
    op.drop_column("Order", "checkoutRequestFingerprint")
    op.drop_column("Order", "checkoutIdempotencyKey")
    op.drop_column("Order", "paymentProvider")
    op.drop_column("Order", "stripeChargeId")
    op.drop_column("Order", "stripePaymentIntentId")

    # PostgreSQL enum values are intentionally not removed: PostgreSQL does
    # not support safely deleting enum labels while existing data may use them.
