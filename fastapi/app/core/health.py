from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine


def database_is_ready() -> bool:
    """Return whether a lightweight query can reach the primary database.

    This is intentionally separate from liveness.  A process can be alive
    while it cannot safely accept checkout, auth, or webhook traffic.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True
