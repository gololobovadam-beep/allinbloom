"""refresh color palette values

Revision ID: 0016_refresh_color_palette
Revises: 0015_refresh_flower_types
Create Date: 2026-03-01 00:00:00.000000
"""

from alembic import op


revision = "0016_refresh_color_palette"
down_revision = "0015_refresh_flower_types"
branch_labels = None
depends_on = None


def _normalize_sql_expression(column_name: str) -> str:
    return f"""
    REGEXP_REPLACE(
        REGEXP_REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(
                                    LOWER(COALESCE({column_name}, '')),
                                    'champange',
                                    'yellow'
                                ),
                                'champagne',
                                'yellow'
                            ),
                            'blush',
                            'pink'
                        ),
                        'ivory',
                        'white'
                    ),
                    'ruby',
                    'burgundy'
                ),
                'sage',
                'light blue'
            ),
            '\\s*,\\s*',
            ', ',
            'g'
        ),
        '\\s+',
        ' ',
        'g'
    )
    """


def _sqlite_normalize_sql_expression(column_name: str) -> str:
    """SQLite equivalent without PostgreSQL-only REGEXP_REPLACE/TRIM syntax."""
    normalized = f"""
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        REPLACE(
                            LOWER(COALESCE({column_name}, '')),
                            'champange', 'yellow'
                        ),
                        'champagne', 'yellow'
                    ),
                    'blush', 'pink'
                ),
                'ivory', 'white'
            ),
            'ruby', 'burgundy'
        ),
        'sage', 'light blue'
    )
    """
    # Normalize comma spacing and collapse the common runs of whitespace
    # without relying on an extension function being registered in SQLite.
    compact = f"""
    REPLACE(REPLACE(REPLACE(REPLACE({normalized}, ', ', ','), ' ,', ','), ',,', ','), '  ', ' ')
    """
    return f"trim(REPLACE(REPLACE({compact}, ',', ', '), '  ', ' '), ', ')"


def upgrade():
    op.execute(
        """
        UPDATE "StoreSettings"
        SET "categoryColor" = CASE
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'blush' THEN 'pink'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'ivory' THEN 'white'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'ruby' THEN 'burgundy'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'sage' THEN 'light blue'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) IN ('champagne', 'champange') THEN 'yellow'
            ELSE LOWER(TRIM(COALESCE("categoryColor", '')))
        END
        WHERE "categoryColor" IS NOT NULL
        """
    )
    colors_expression = (
        _sqlite_normalize_sql_expression('"colors"')
        if op.get_bind().dialect.name == "sqlite"
        else f"TRIM(BOTH ', ' FROM {_normalize_sql_expression('"colors"')})"
    )
    op.execute(
        f"""
        UPDATE "Bouquet"
        SET "colors" = {colors_expression}
        WHERE "colors" IS NOT NULL
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE "StoreSettings"
        SET "categoryColor" = CASE
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'pink' THEN 'blush'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'white' THEN 'ivory'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'burgundy' THEN 'ruby'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'light blue' THEN 'sage'
            WHEN LOWER(TRIM(COALESCE("categoryColor", ''))) = 'yellow' THEN 'champagne'
            ELSE LOWER(TRIM(COALESCE("categoryColor", '')))
        END
        WHERE "categoryColor" IS NOT NULL
        """
    )
    legacy_colors = """
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(
                    REPLACE(
                        LOWER(COALESCE("colors", '')),
                        'pink', 'blush'
                    ),
                    'white', 'ivory'
                ),
                'burgundy', 'ruby'
            ),
            'light blue', 'sage'
        ),
        'yellow', 'champagne'
    )
    """
    colors_expression = (
        f"trim(REPLACE(REPLACE(REPLACE(REPLACE({legacy_colors}, ', ', ','), ' ,', ','), ',', ', '), '  ', ' '), ', ')"
        if op.get_bind().dialect.name == "sqlite"
        else f"TRIM(BOTH ', ' FROM REGEXP_REPLACE({legacy_colors}, '\\s*,\\s*', ', ', 'g'))"
    )
    op.execute(
        f"""
        UPDATE "Bouquet"
        SET "colors" = {colors_expression}
        WHERE "colors" IS NOT NULL
        """
    )
