from __future__ import annotations

import unittest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
)
from app.routes import operations_admin


class OperationsAdminRouteTests(unittest.TestCase):
    def _client(self, *, require_admin=None, summary_reader=None):
        app = FastAPI()

        app.include_router(
            operations_admin.build_router(
                require_admin=(
                    require_admin
                    or (lambda request: None)
                ),
                database_url="postgresql://db.example/sportabase",
                timeout_seconds=2,
                summary_reader=(
                    summary_reader
                    or (
                        lambda **kwargs: {
                            "state": "ready",
                            "window_days": kwargs["days"],
                        }
                    )
                ),
            )
        )

        return TestClient(app)

    def test_admin_guard_runs_before_summary(self):
        calls = []

        def deny(_request):
            calls.append("guard")
            raise HTTPException(status_code=401, detail="denied")

        def summary(**_):
            calls.append("summary")
            return {}

        response = self._client(
            require_admin=deny,
            summary_reader=summary,
        ).get("/admin/operations/summary?days=7")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(calls, ["guard"])

    def test_days_are_forwarded(self):
        seen = []

        def summary(**kwargs):
            seen.append(kwargs)
            return {
                "state": "ready",
                "window_days": kwargs["days"],
            }

        response = self._client(
            summary_reader=summary,
        ).get("/admin/operations/summary?days=14")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["window_days"], 14)
        self.assertEqual(seen[0]["days"], 14)
        self.assertEqual(seen[0]["timeout_seconds"], 2)

    def test_invalid_days_are_rejected_by_fastapi(self):
        response = self._client().get(
            "/admin/operations/summary?days=31"
        )
        self.assertEqual(response.status_code, 422)

    def test_unavailable_store_maps_to_503(self):
        def unavailable(**_):
            raise PersistentOperationsStoreUnavailable("down")

        response = self._client(
            summary_reader=unavailable,
        ).get("/admin/operations/summary")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Persistent operations telemetry is unavailable.",
        )

    def test_misconfigured_store_maps_to_503_without_detail_leak(self):
        def misconfigured(**_):
            raise PersistentOperationsStoreMisconfigured("secret config")

        response = self._client(
            summary_reader=misconfigured,
        ).get("/admin/operations/summary")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Persistent operations telemetry is misconfigured.",
        )
        self.assertNotIn("secret config", response.text)


if __name__ == "__main__":
    unittest.main()
