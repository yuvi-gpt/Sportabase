import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


class DatabasePathConfigurationTests(unittest.TestCase):
    def _probe(self, *, database_path: str) -> Path:
        env = os.environ.copy()
        env["SPORTABASE_DB_PATH"] = database_path
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.application.config import DB_PATH; print(DB_PATH)",
            ],
            cwd=BACKEND_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(completed.stdout.strip())

    def test_database_path_can_be_overridden_for_persistent_deployments(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "sportabase-persistent.db"
            configured = self._probe(database_path=str(expected))

        self.assertEqual(configured, expected)

    def test_empty_override_preserves_existing_local_default(self):
        configured = self._probe(database_path="")
        expected = BACKEND_DIR / "data" / "sportabase.db"

        self.assertEqual(configured, expected)


if __name__ == "__main__":
    unittest.main()
