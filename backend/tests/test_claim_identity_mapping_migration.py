from __future__ import annotations

import tempfile
from pathlib import Path

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA


def test_initialize_database_creates_claim_identity_mapping_schema():
    with tempfile.TemporaryDirectory() as tempdir:
        db_path = Path(tempdir) / "sportabase.sqlite3"

        def factory():
            return connect_database(db_path)

        initialize_database(factory, SCHEMA)

        conn = factory()
        try:
            table = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'claim_identity_mappings'
                """
            ).fetchone()
            canonical_index = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'idx_claim_identity_mappings_canonical'
                """
            ).fetchone()
            subject_index = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'idx_claim_identity_mappings_subject'
                """
            ).fetchone()
        finally:
            conn.close()

        assert table is not None
        assert canonical_index is not None
        assert subject_index is not None
