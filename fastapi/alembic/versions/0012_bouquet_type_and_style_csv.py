"""add bouquet type and convert style to csv string

Revision ID: 0012_bouquet_type_and_style_csv
Revises: 0011_bouquet_gallery_images
Create Date: 2026-02-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_bouquet_type_and_style_csv"
down_revision = "0011_bouquet_gallery_images"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.add_column("Bouquet", sa.Column("bouquetType", sa.String(), nullable=True))

    if dialect == "postgresql":
        op.execute(
            """
            UPDATE "Bouquet"
            SET "bouquetType" = CASE
                WHEN "style"::text = 'SEASON' THEN 'SEASON'
                WHEN "isMixed" IS TRUE THEN 'MIXED'
                ELSE 'MONO'
            END
            """
        )
        op.execute(
            """
            ALTER TABLE "Bouquet"
            ALTER COLUMN "style"
            TYPE VARCHAR
            USING "style"::text
            """
        )
    else:
        op.execute(
            """
            UPDATE "Bouquet"
            SET "bouquetType" = CASE
                WHEN upper("style") = 'SEASON' THEN 'SEASON'
                WHEN "isMixed" = 1 THEN 'MIXED'
                ELSE 'MONO'
            END
            """
        )

    op.execute(
        """
        UPDATE "Bouquet"
        SET "isMixed" = CASE
            WHEN "bouquetType" = 'MIXED' THEN TRUE
            ELSE FALSE
        END
        """
    )

    # SQLite has no ``ALTER COLUMN``.  Recreate the table through Alembic's
    # batch helper so a clean SQLite test/local database can follow the same
    # migration chain as PostgreSQL.
    if dialect == "sqlite":
        with op.batch_alter_table("Bouquet", recreate="always") as batch_op:
            batch_op.alter_column(
                "bouquetType",
                existing_type=sa.String(),
                nullable=False,
                server_default=sa.text("'MONO'"),
            )
            batch_op.alter_column(
                "style",
                existing_type=sa.String(),
                nullable=False,
            )
    else:
        op.alter_column(
            "Bouquet",
            "bouquetType",
            existing_type=sa.String(),
            nullable=False,
            server_default=sa.text("'MONO'"),
        )
        op.alter_column(
            "Bouquet",
            "style",
            existing_type=sa.String(),
            nullable=False,
        )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            """
            UPDATE "Bouquet"
            SET "style" = CASE
                WHEN "bouquetType" = 'SEASON' THEN 'SEASON'
                ELSE 'GARDEN'
            END
            """
        )
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'BouquetStyle'
                ) THEN
                    CREATE TYPE "BouquetStyle" AS ENUM (
                        'ROMANTIC',
                        'MODERN',
                        'GARDEN',
                        'MINIMAL',
                        'SEASON'
                    );
                END IF;
            END $$;
            """
        )
        op.execute(
            """
            ALTER TABLE "Bouquet"
            ALTER COLUMN "style"
            TYPE "BouquetStyle"
            USING "style"::"BouquetStyle"
            """
        )

    if dialect == "sqlite":
        with op.batch_alter_table("Bouquet", recreate="always") as batch_op:
            batch_op.drop_column("bouquetType")
    else:
        op.drop_column("Bouquet", "bouquetType")
