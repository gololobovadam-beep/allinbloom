"""Run Alembic once across concurrent PostgreSQL application replicas.

Every web replica used to invoke ``alembic upgrade head`` independently at
startup.  PostgreSQL advisory locks make the operation single-writer without
requiring a separate migration service.  The lock is tied to the database
connection, so it is automatically released if the process dies.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from time import monotonic, sleep

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings


# Fixed, application-specific 64-bit value.  It does not encode tenant or
# customer data and only serializes All in Bloom migrations on one database.
MIGRATION_ADVISORY_LOCK_KEY = 6_684_210_314_159
DEFAULT_LOCK_TIMEOUT_SECONDS = 120.0


def _lock_timeout_seconds() -> float:
    raw = os.getenv("MIGRATION_LOCK_TIMEOUT_SECONDS", str(DEFAULT_LOCK_TIMEOUT_SECONDS))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError("MIGRATION_LOCK_TIMEOUT_SECONDS must be a positive number.") from exc
    if value <= 0:
        raise RuntimeError("MIGRATION_LOCK_TIMEOUT_SECONDS must be a positive number.")
    return value


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    # Do not depend on the process working directory: the entrypoint and a
    # one-off release job may start this script from different locations.
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return config


def _is_postgresql(url: str) -> bool:
    return make_url(url).get_backend_name() == "postgresql"


def _connect_with_retry(engine: Engine, deadline: float) -> Connection:
    last_error: OperationalError | None = None
    while monotonic() < deadline:
        try:
            return engine.connect()
        except OperationalError as exc:
            last_error = exc
            sleep(min(1.0, max(0.05, deadline - monotonic())))

    raise RuntimeError("Database did not become available before migration timeout.") from last_error


def _acquire_postgresql_lock(connection: Connection, deadline: float) -> None:
    statement = text("SELECT pg_try_advisory_lock(CAST(:lock_key AS BIGINT))")
    while monotonic() < deadline:
        acquired = connection.execute(
            statement,
            {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
        ).scalar_one()
        if acquired:
            return
        sleep(min(0.5, max(0.05, deadline - monotonic())))

    raise RuntimeError("Timed out waiting for another replica to finish database migrations.")


def _release_postgresql_lock(connection: Connection) -> None:
    try:
        connection.execute(
            text("SELECT pg_advisory_unlock(CAST(:lock_key AS BIGINT))"),
            {"lock_key": MIGRATION_ADVISORY_LOCK_KEY},
        )
    except SQLAlchemyError:
        # Connection close still releases a session-level advisory lock.  Do
        # not hide the original migration error with a cleanup failure.
        return


def upgrade_to_head() -> None:
    url = settings.normalized_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL must be configured before running migrations.")

    config = _alembic_config()
    if not _is_postgresql(url):
        command.upgrade(config, "head")
        return

    timeout = _lock_timeout_seconds()
    deadline = monotonic() + timeout
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": min(5, max(1, int(timeout)))},
    )
    connection: Connection | None = None
    try:
        connection = _connect_with_retry(engine, deadline)
        _acquire_postgresql_lock(connection, deadline)
        command.upgrade(config, "head")
    finally:
        if connection is not None:
            _release_postgresql_lock(connection)
            connection.close()
        engine.dispose()


if __name__ == "__main__":
    upgrade_to_head()
