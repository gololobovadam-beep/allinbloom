from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Keep imports inspectable (for CLI help, test collection, and a useful startup
# error) even when an operator forgot DATABASE_URL.  The application startup
# hook rejects that configuration before it can receive traffic.
_configured_database_url = settings.normalized_database_url()
_database_url = _configured_database_url or "sqlite+pysqlite:///:memory:"
_engine_options: dict = {"pool_pre_ping": True}

# A failed database connection should release workers quickly rather than
# consuming the default driver timeout.  Keep SQLite (used by unit tests) free
# of PostgreSQL-only connect options.
if _database_url.startswith("postgresql"):
    _engine_options.update(
        pool_recycle=30 * 60,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
    )

engine = create_engine(_database_url, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
