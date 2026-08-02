"""add catalog product metadata and ordered gallery relations

Revision ID: 0021_catalog_products_and_gallery_relations
Revises: 0020_order_delivery_datetime
Create Date: 2026-08-02 00:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa
from uuid import uuid4


revision = "0021_catalog_products_and_gallery_relations"
down_revision = "0020_order_delivery_datetime"
branch_labels = None
depends_on = None


def _generate_migration_id():
    """Keep this revision importable by Alembic outside the application package."""
    return uuid4().hex


def _unique_urls(values):
    urls = []
    for value in values:
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def upgrade():
    op.create_table(
        "CatalogCategory",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("catalogType", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("isActive", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "createdAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updatedAt", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalogType", "slug", name="uq_CatalogCategory_catalogType_slug"),
        sa.CheckConstraint(
            '"catalogType" IN (\'FLOWERS\', \'BALOONS\', \'GIFTS\', \'EVENT_SPACE\')',
            name="ck_CatalogCategory_catalogType",
        ),
    )
    op.create_index("ix_CatalogCategory_catalogType", "CatalogCategory", ["catalogType"])

    op.add_column(
        "Bouquet",
        sa.Column(
            "catalogType",
            sa.String(),
            nullable=False,
            server_default=sa.text("'FLOWERS'"),
        ),
    )
    op.add_column("Bouquet", sa.Column("categoryId", sa.String(), nullable=True))
    op.add_column("Bouquet", sa.Column("videoUrl", sa.String(), nullable=True))
    op.execute('UPDATE "Bouquet" SET "catalogType" = \'FLOWERS\' WHERE "catalogType" IS NULL')
    op.create_check_constraint(
        "ck_Bouquet_catalogType",
        "Bouquet",
        '"catalogType" IN (\'FLOWERS\', \'BALOONS\', \'GIFTS\', \'EVENT_SPACE\')',
    )
    op.create_index("ix_Bouquet_catalogType", "Bouquet", ["catalogType"])
    op.create_index("ix_Bouquet_categoryId", "Bouquet", ["categoryId"])
    op.create_foreign_key(
        "fk_Bouquet_categoryId_CatalogCategory",
        "Bouquet",
        "CatalogCategory",
        ["categoryId"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "BouquetGalleryImage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bouquetId", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_BouquetGalleryImage_position_nonnegative"),
        sa.ForeignKeyConstraint(["bouquetId"], ["Bouquet.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bouquetId", "position", name="uq_BouquetGalleryImage_bouquetId_position"),
    )
    op.create_index("ix_BouquetGalleryImage_bouquetId", "BouquetGalleryImage", ["bouquetId"])

    op.create_table(
        "EventTier",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bouquetId", sa.String(), nullable=False),
        sa.Column("priceCents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_EventTier_position_nonnegative"),
        sa.CheckConstraint("priceCents >= 0", name="ck_EventTier_price_nonnegative"),
        sa.ForeignKeyConstraint(["bouquetId"], ["Bouquet.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bouquetId", "position", name="uq_EventTier_bouquetId_position"),
    )
    op.create_index("ix_EventTier_bouquetId", "EventTier", ["bouquetId"])

    op.create_table(
        "HomeGalleryImage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("storeSettingsId", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_HomeGalleryImage_position_nonnegative"),
        sa.ForeignKeyConstraint(["storeSettingsId"], ["StoreSettings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storeSettingsId",
            "position",
            name="uq_HomeGalleryImage_storeSettingsId_position",
        ),
    )
    op.create_index("ix_HomeGalleryImage_storeSettingsId", "HomeGalleryImage", ["storeSettingsId"])

    # Backfill normalized rows from the fixed six legacy slots.  The old
    # columns remain in place for a staged, rollback-safe compatibility period.
    # Alembic's offline SQL mode has no database connection to read from, so
    # emit the schema there and leave the data copy to a real online upgrade.
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    bouquet_rows = bind.execute(
        sa.text(
            'SELECT "id", "image", "image2", "image3", "image4", "image5", "image6" '
            'FROM "Bouquet"'
        )
    ).mappings()
    bouquet_images = []
    for row in bouquet_rows:
        for position, url in enumerate(
            _unique_urls(
                [
                    row["image"],
                    row["image2"],
                    row["image3"],
                    row["image4"],
                    row["image5"],
                    row["image6"],
                ]
            )
        ):
            bouquet_images.append(
                {
                    "id": _generate_migration_id(),
                    "bouquetId": row["id"],
                    "url": url,
                    "position": position,
                }
            )
    if bouquet_images:
        op.bulk_insert(
            sa.table(
                "BouquetGalleryImage",
                sa.column("id", sa.String()),
                sa.column("bouquetId", sa.String()),
                sa.column("url", sa.String()),
                sa.column("position", sa.Integer()),
            ),
            bouquet_images,
        )

    settings_rows = bind.execute(
        sa.text(
            'SELECT "id", "homeGalleryImage1", "homeGalleryImage2", '
            '"homeGalleryImage3", "homeGalleryImage4", "homeGalleryImage5", '
            '"homeGalleryImage6" FROM "StoreSettings"'
        )
    ).mappings()
    home_images = []
    for row in settings_rows:
        for position, url in enumerate(
            _unique_urls(
                [
                    row["homeGalleryImage1"],
                    row["homeGalleryImage2"],
                    row["homeGalleryImage3"],
                    row["homeGalleryImage4"],
                    row["homeGalleryImage5"],
                    row["homeGalleryImage6"],
                ]
            )
        ):
            home_images.append(
                {
                    "id": _generate_migration_id(),
                    "storeSettingsId": row["id"],
                    "url": url,
                    "position": position,
                }
            )
    if home_images:
        op.bulk_insert(
            sa.table(
                "HomeGalleryImage",
                sa.column("id", sa.String()),
                sa.column("storeSettingsId", sa.String()),
                sa.column("url", sa.String()),
                sa.column("position", sa.Integer()),
            ),
            home_images,
        )


def downgrade():
    op.drop_index("ix_HomeGalleryImage_storeSettingsId", table_name="HomeGalleryImage")
    op.drop_table("HomeGalleryImage")
    op.drop_index("ix_EventTier_bouquetId", table_name="EventTier")
    op.drop_table("EventTier")
    op.drop_index("ix_BouquetGalleryImage_bouquetId", table_name="BouquetGalleryImage")
    op.drop_table("BouquetGalleryImage")

    op.drop_constraint("fk_Bouquet_categoryId_CatalogCategory", "Bouquet", type_="foreignkey")
    op.drop_constraint("ck_Bouquet_catalogType", "Bouquet", type_="check")
    op.drop_index("ix_Bouquet_categoryId", table_name="Bouquet")
    op.drop_index("ix_Bouquet_catalogType", table_name="Bouquet")
    op.drop_column("Bouquet", "videoUrl")
    op.drop_column("Bouquet", "categoryId")
    op.drop_column("Bouquet", "catalogType")

    op.drop_index("ix_CatalogCategory_catalogType", table_name="CatalogCategory")
    op.drop_table("CatalogCategory")
