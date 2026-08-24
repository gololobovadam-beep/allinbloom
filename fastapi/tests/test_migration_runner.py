from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from scripts import run_migrations


class MigrationRunnerTests(unittest.TestCase):
    def test_identifies_postgresql_urls(self):
        self.assertTrue(run_migrations._is_postgresql("postgresql+psycopg://user:pass@db/app"))
        self.assertFalse(run_migrations._is_postgresql("sqlite+pysqlite:///:memory:"))

    @patch.dict(os.environ, {"MIGRATION_LOCK_TIMEOUT_SECONDS": "0"})
    def test_rejects_non_positive_migration_lock_timeout(self):
        with self.assertRaisesRegex(RuntimeError, "positive"):
            run_migrations._lock_timeout_seconds()

    @patch("scripts.run_migrations.command.upgrade")
    def test_sqlite_runs_without_postgresql_advisory_lock(self, upgrade):
        with patch.object(run_migrations.settings, "database_url", "sqlite+pysqlite:///:memory:"):
            run_migrations.upgrade_to_head()

        upgrade.assert_called_once()

    @patch("scripts.run_migrations.command.upgrade")
    @patch("scripts.run_migrations._release_postgresql_lock")
    @patch("scripts.run_migrations._acquire_postgresql_lock")
    @patch("scripts.run_migrations._connect_with_retry")
    @patch("scripts.run_migrations.create_engine")
    def test_postgresql_serializes_migration_and_releases_lock(
        self,
        create_engine,
        connect,
        acquire_lock,
        release_lock,
        upgrade,
    ):
        engine = MagicMock()
        connection = MagicMock()
        create_engine.return_value = engine
        connect.return_value = connection

        with patch.object(
            run_migrations.settings,
            "database_url",
            "postgresql+psycopg://user:pass@db/app",
        ):
            run_migrations.upgrade_to_head()

        acquire_lock.assert_called_once()
        upgrade.assert_called_once()
        release_lock.assert_called_once_with(connection)
        connection.close.assert_called_once()
        engine.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
