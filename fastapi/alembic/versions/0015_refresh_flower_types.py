"""refresh flower types enum

Revision ID: 0015_refresh_flower_types
Revises: 0014_bouquet_default_flower_qty
Create Date: 2026-03-01 00:00:00.000000
"""

from alembic import op


revision = "0015_refresh_flower_types"
down_revision = "0014_bouquet_default_flower_qty"
branch_labels = None
depends_on = None


def upgrade():
    # Safety migration for older data/settings that may still reference LILY.
    op.execute(
        """
        UPDATE "StoreSettings"
        SET "categoryFlowerType" = 'HYDRANGEAS'
        WHERE UPPER(COALESCE("categoryFlowerType", '')) = 'LILY'
        """
    )

    # SQLite stores PostgreSQL ENUM values as plain text.  The data repair is
    # still required there, but PostgreSQL's ALTER TYPE commands are not
    # supported (and are unnecessary).
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            UPDATE "Bouquet"
            SET "flowerType" = 'HYDRANGEAS'
            WHERE UPPER(COALESCE("flowerType", '')) = 'LILY'
            """
        )
        op.execute(
            """
            UPDATE "Bouquet"
            SET "style" = REPLACE(
                REPLACE(COALESCE("style", ''), 'LILY', 'HYDRANGEAS'),
                'lily',
                'hydrangeas'
            )
            WHERE UPPER(COALESCE("style", '')) LIKE '%LILY%'
            """
        )
        return

    op.execute('ALTER TYPE "FlowerType" RENAME TO "FlowerType_old"')
    op.execute(
        """
        CREATE TYPE "FlowerType" AS ENUM (
            'ROSE',
            'TULIP',
            'PEONY',
            'ORCHID',
            'HYDRANGEAS',
            'SPRAY_ROSES',
            'RANUNCULUSES',
            'MIXED'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE "Bouquet"
        ALTER COLUMN "flowerType" TYPE "FlowerType"
        USING (
            CASE
                WHEN "flowerType"::text = 'LILY' THEN 'HYDRANGEAS'
                ELSE "flowerType"::text
            END::"FlowerType"
        )
        """
    )
    op.execute('DROP TYPE "FlowerType_old"')
    op.execute(
        """
        UPDATE "Bouquet"
        SET "style" = REPLACE(
            REPLACE(COALESCE("style", ''), 'LILY', 'HYDRANGEAS'),
            'lily',
            'hydrangeas'
        )
        WHERE UPPER(COALESCE("style", '')) LIKE '%LILY%'
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE "StoreSettings"
        SET "categoryFlowerType" = 'LILY'
        WHERE UPPER(COALESCE("categoryFlowerType", '')) IN (
            'HYDRANGEAS',
            'SPRAY_ROSES',
            'RANUNCULUSES'
        )
        """
    )

    # See the SQLite branch in upgrade(): it has no native ENUM type to
    # replace, so only restore the values.
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            UPDATE "Bouquet"
            SET "flowerType" = 'LILY'
            WHERE UPPER(COALESCE("flowerType", '')) IN (
                'HYDRANGEAS', 'SPRAY_ROSES', 'RANUNCULUSES'
            )
            """
        )
        op.execute(
            """
            UPDATE "Bouquet"
            SET "style" = REPLACE(
                REPLACE(
                    REPLACE(UPPER(COALESCE("style", '')), 'HYDRANGEAS', 'LILY'),
                    'SPRAY_ROSES',
                    'LILY'
                ),
                'RANUNCULUSES',
                'LILY'
            )
            WHERE UPPER(COALESCE("style", '')) LIKE '%HYDRANGEAS%'
               OR UPPER(COALESCE("style", '')) LIKE '%SPRAY_ROSES%'
               OR UPPER(COALESCE("style", '')) LIKE '%RANUNCULUSES%'
            """
        )
        return

    op.execute('ALTER TYPE "FlowerType" RENAME TO "FlowerType_new"')
    op.execute(
        """
        CREATE TYPE "FlowerType" AS ENUM (
            'ROSE',
            'TULIP',
            'LILY',
            'PEONY',
            'ORCHID',
            'MIXED'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE "Bouquet"
        ALTER COLUMN "flowerType" TYPE "FlowerType"
        USING (
            CASE
                WHEN "flowerType"::text IN ('HYDRANGEAS', 'SPRAY_ROSES', 'RANUNCULUSES')
                    THEN 'LILY'
                ELSE "flowerType"::text
            END::"FlowerType"
        )
        """
    )
    op.execute('DROP TYPE "FlowerType_new"')
    op.execute(
        """
        UPDATE "Bouquet"
        SET "style" = REPLACE(
            REPLACE(
                REPLACE(UPPER(COALESCE("style", '')), 'HYDRANGEAS', 'LILY'),
                'SPRAY_ROSES',
                'LILY'
            ),
            'RANUNCULUSES',
            'LILY'
        )
        WHERE UPPER(COALESCE("style", '')) LIKE '%HYDRANGEAS%'
           OR UPPER(COALESCE("style", '')) LIKE '%SPRAY_ROSES%'
           OR UPPER(COALESCE("style", '')) LIKE '%RANUNCULUSES%'
        """
    )
