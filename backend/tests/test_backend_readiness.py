import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.application.readiness import build_backend_readiness
from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.readiness import build_backend_intelligence_readiness
from app.operations.persistent_runtime import PERSISTENT_OPERATIONS_STATE_ATTRIBUTE
from app.routes import intelligence_runtime_admin


NOW = "2026-08-22T10:00:00+00:00"


class BackendReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def test_initialized_database_is_ready(self):
        initialize_database(self.factory, SCHEMA)
        report = build_backend_intelligence_readiness(
            connection_factory=self.factory,
        )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["checks"]["required_tables"], "pass")
        self.assertEqual(report["checks"]["required_indexes"], "pass")
        self.assertFalse(report["policy"]["affects_live_merit"])

    def test_missing_schema_fails_closed(self):
        sqlite3.connect(self.db_path).close()
        report = build_backend_intelligence_readiness(
            connection_factory=self.factory,
        )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("missing_required_tables", report["issues"])
        self.assertIn("missing_required_indexes", report["issues"])

    def test_malformed_structured_claim_metadata_is_not_ready(self):
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, '', 'structured_transfer', ?, ?, ?)
                """,
                (
                    "claim-bad",
                    "structured-claim|bad",
                    "player|one",
                    NOW,
                    NOW,
                    json.dumps({"unexpected": True}),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        report = build_backend_intelligence_readiness(
            connection_factory=self.factory,
        )
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["counts"]["malformed_structured_metadata"], 1)
        self.assertIn("malformed_structured_claim_metadata", report["issues"])

    def test_connection_failure_hides_error_message(self):
        def broken_factory():
            raise RuntimeError("secret database endpoint")

        report = build_backend_intelligence_readiness(
            connection_factory=broken_factory,
        )

        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["error_type"], "RuntimeError")
        self.assertNotIn("secret", json.dumps(report).casefold())

    def test_aggregate_readiness_marks_optional_operations_outage_degraded(self):
        initialize_database(self.factory, SCHEMA)
        app = FastAPI()
        setattr(
            app.state,
            PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
            "unavailable",
        )

        report = build_backend_readiness(
            app=app,
            connection_factory=self.factory,
            operations_database_url="postgresql://configured",
        )

        self.assertEqual(report["status"], "degraded")
        self.assertIn("operations_store_unavailable", report["issues"])
        self.assertFalse(
            report["components"]["persistent_operations"][
                "required_for_product_requests"
            ]
        )

    def test_admin_readiness_routes_are_protected(self):
        initialize_database(self.factory, SCHEMA)
        app = FastAPI()

        def require_admin(request: Request):
            if request.headers.get("x-admin") != "yes":
                raise HTTPException(status_code=401, detail="admin required")

        app.include_router(
            intelligence_runtime_admin.build_router(
                app=app,
                require_admin=require_admin,
                connection_factory=self.factory,
                operations_database_url="",
            )
        )
        client = TestClient(app)

        denied = client.get("/admin/readiness")
        self.assertEqual(denied.status_code, 401)

        allowed = client.get(
            "/admin/readiness",
            headers={"x-admin": "yes"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["status"], "ready")

        intelligence = client.get(
            "/admin/intelligence/readiness",
            headers={"x-admin": "yes"},
        )
        self.assertEqual(intelligence.status_code, 200)
        self.assertEqual(intelligence.json()["status"], "ready")


if __name__ == "__main__":
    unittest.main()
