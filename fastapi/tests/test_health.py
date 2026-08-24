from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.core.health import database_is_ready
from app.core.config import settings
from app.main import validate_runtime_config


class DatabaseHealthTests(unittest.TestCase):
    @patch("app.core.health.engine")
    def test_database_is_ready_runs_a_lightweight_query(self, mock_engine):
        connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = connection

        self.assertTrue(database_is_ready())
        connection.execute.assert_called_once()

    @patch("app.core.health.engine")
    def test_database_is_ready_returns_false_on_connection_failure(self, mock_engine):
        mock_engine.connect.side_effect = OperationalError("SELECT 1", {}, RuntimeError("down"))

        self.assertFalse(database_is_ready())

    def test_startup_rejects_missing_database_url(self):
        with (
            patch.object(settings, "environment", "test"),
            patch.object(settings, "auth_secret", "test-secret-1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            patch.object(settings, "site_url", "http://localhost:3000"),
            patch.object(settings, "database_url", ""),
        ):
            with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
                validate_runtime_config()


if __name__ == "__main__":
    unittest.main()
