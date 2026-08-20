from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest import mock


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]


from app import main
from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.models.api import BrowserCaptureRequest, BrowserCaptureResponse
from app.services import browser_capture_automation as automation
from app.services import browser_capture_inbox as inbox
from app.services import inbox_history_auto_shadow_orchestration as history


ANALYSIS_VERSION = "analysis-current"
SCORING_VERSION = "score-current"
OBSERVED = "2026-08-17T12:00:00Z"


def web_capture(
    *,
    slug="story-one",
    body="Arsenal agree transfer terms with Player One.",
    observed_at=OBSERVED,
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://example.com/" + slug
        ),
        "observed_at": observed_at,
        "extraction_method": (
            "browser_dom+article_extractor"
        ),
        "payload": {
            "platform": "web",
            "surface": "article",
            "container_kind": "article",
            "canonical_url": (
                "https://example.com/" + slug
            ),
            "title": "Transfer update",
            "body": body,
        },
        "actor": {},
    }


def x_capture():
    return {
        "version": "browser-capture-v1",
        "source_url": "https://x.com/reporter/status/1",
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "x",
            "surface": "post",
            "container_kind": "post",
            "canonical_url": "https://x.com/reporter/status/1",
            "body": "Arsenal transfer update",
        },
        "actor": {
            "handle": "reporter",
            "profile_url": "https://x.com/reporter",
        },
    }


def safe_shadow_result(anchor):
    return {
        "version": (
            history
            .MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": "claim-123",
        "anchor_capture_record_id": anchor,
        "selected_candidate_capture_record_id": "peer-456",
        "selected_subject_entity_id": "entity-789",
        "baseline_resolution": {
            "legacy_total": 61.0,
        },
        "automatic_selection": {},
        "orchestration": {},
        "policy": {
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class FakeApp:
    def __init__(self):
        self.handlers = []

    def add_event_handler(self, event, handler):
        self.handlers.append((event, handler))


class BrowserCaptureAutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.tmp.name)
            / "automation.db"
        )

        conn = connect_database(
            self.db_path
        )
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

        self.factory = lambda: connect_database(
            self.db_path
        )

        automation.stop_browser_capture_automation_worker(
            join_timeout_seconds=0.5
        )

    def tearDown(self):
        automation.stop_browser_capture_automation_worker(
            join_timeout_seconds=0.5
        )
        self.tmp.cleanup()

    def enabled_env(self, key, default=None):
        values = {
            inbox.BROWSER_CAPTURE_INBOX_FLAG: "1",
            inbox.BROWSER_CAPTURE_INBOX_MAX_BYTES: "131072",
            automation.BROWSER_CAPTURE_AUTOMATION_FLAG: "1",
            automation.BROWSER_CAPTURE_AUTOMATION_POLL_SECONDS: "0.25",
            automation.BROWSER_CAPTURE_AUTOMATION_LEASE_SECONDS: "30",
            automation.BROWSER_CAPTURE_AUTOMATION_MAX_ATTEMPTS: "4",
            automation.BROWSER_CAPTURE_AUTOMATION_RETRY_BASE_SECONDS: "10",
            automation.BROWSER_CAPTURE_AUTOMATION_RETRY_CAP_SECONDS: "60",
        }
        return values.get(key, default)

    def disabled_env(self, key, default=None):
        values = {
            inbox.BROWSER_CAPTURE_INBOX_FLAG: "1",
            automation.BROWSER_CAPTURE_AUTOMATION_FLAG: "0",
        }
        return values.get(key, default)

    def count(self, table):
        conn = self.factory()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM "
                    + table
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def one(self, sql, params=()):
        conn = self.factory()
        try:
            row = conn.execute(
                sql,
                params,
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def execute(self, sql, params=()):
        conn = self.factory()
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def store_web(self, **kwargs):
        return inbox.store_browser_capture(
            raw_capture=web_capture(**kwargs),
            connection_factory=self.factory,
            now_provider=(
                lambda: "2026-08-17T12:01:00Z"
            ),
        )

    def store_x(self):
        return inbox.store_browser_capture(
            raw_capture=x_capture(),
            connection_factory=self.factory,
            now_provider=(
                lambda: "2026-08-17T12:01:00Z"
            ),
        )

    def enqueue(self, capture_id, now=1000):
        return automation.enqueue_browser_capture_job(
            capture_record_id=capture_id,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: now,
        )

    def claim(self, worker="worker-a", now=1000):
        return automation.claim_next_browser_capture_job(
            worker_id=worker,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            lease_seconds=30,
            now_provider=lambda: now,
        )

    def claimed(self, now=1000, worker="worker-a"):
        stored = self.store_web()
        self.enqueue(
            stored["capture_record_id"],
            now=now,
        )
        return self.claim(
            worker=worker,
            now=now,
        )

    def test_version_is_v1(self):
        self.assertEqual(
            automation.BROWSER_CAPTURE_AUTOMATION_VERSION,
            "browser-capture-automation-v1",
        )

    def test_automation_flag_defaults_off(self):
        self.assertFalse(
            automation.automation_enabled(
                env_getter=lambda key, default=None: default
            )
        )

    def test_automation_flag_accepts_true(self):
        self.assertTrue(
            automation.automation_enabled(
                env_getter=self.enabled_env
            )
        )

    def test_poll_seconds_has_lower_bound(self):
        value = automation.automation_poll_seconds(
            env_getter=lambda key, default=None: "0"
        )
        self.assertEqual(value, 0.25)

    def test_lease_seconds_has_lower_bound(self):
        value = automation.automation_lease_seconds(
            env_getter=lambda key, default=None: "1"
        )
        self.assertEqual(value, 30)

    def test_max_attempts_has_lower_bound(self):
        value = automation.automation_max_attempts(
            env_getter=lambda key, default=None: "0"
        )
        self.assertEqual(value, 1)

    def test_retry_base_has_lower_bound(self):
        value = automation.automation_retry_base_seconds(
            env_getter=lambda key, default=None: "0"
        )
        self.assertEqual(value, 1)

    def test_retry_cap_has_lower_bound(self):
        value = automation.automation_retry_cap_seconds(
            env_getter=lambda key, default=None: "0"
        )
        self.assertEqual(value, 10)

    def test_job_id_is_deterministic(self):
        first = automation.automation_job_id(
            capture_record_id="bci_one",
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        second = automation.automation_job_id(
            capture_record_id="bci_one",
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("bcaj_"))

    def test_job_id_changes_with_analysis_version(self):
        first = automation.automation_job_id(
            capture_record_id="bci_one",
            analysis_version="a1",
            scoring_version="s1",
        )
        second = automation.automation_job_id(
            capture_record_id="bci_one",
            analysis_version="a2",
            scoring_version="s1",
        )
        self.assertNotEqual(first, second)

    def test_job_id_requires_analysis_version(self):
        with self.assertRaises(
            automation.BrowserCaptureAutomationInputError
        ):
            automation.automation_job_id(
                capture_record_id="bci_one",
                analysis_version="",
                scoring_version="s1",
            )

    def test_job_id_requires_scoring_version(self):
        with self.assertRaises(
            automation.BrowserCaptureAutomationInputError
        ):
            automation.automation_job_id(
                capture_record_id="bci_one",
                analysis_version="a1",
                scoring_version="",
            )

    def test_disabled_enqueue_does_not_write(self):
        stored = self.store_web()
        result = automation.enqueue_browser_capture_job(
            capture_record_id=stored["capture_record_id"],
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.disabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            0,
        )

    def test_enqueue_requires_existing_capture(self):
        with self.assertRaises(
            automation.BrowserCaptureAutomationInputError
        ):
            self.enqueue("bci_missing")

    def test_social_capture_is_enqueued_for_no_merit_dispatch(self):
        stored = self.store_x()
        result = self.enqueue(
            stored["capture_record_id"]
        )
        self.assertEqual(result["status"], "enqueued")
        self.assertEqual(result["job_status"], "pending")
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_web_capture_enqueues_pending_job(self):
        stored = self.store_web()
        result = self.enqueue(
            stored["capture_record_id"]
        )
        self.assertEqual(result["status"], "enqueued")
        self.assertEqual(result["job_status"], "pending")
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_enqueue_is_idempotent(self):
        stored = self.store_web()
        first = self.enqueue(
            stored["capture_record_id"]
        )
        second = self.enqueue(
            stored["capture_record_id"]
        )
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(second["status"], "existing")
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_new_versions_create_new_job_identity(self):
        stored = self.store_web()
        first = self.enqueue(
            stored["capture_record_id"]
        )
        second = automation.enqueue_browser_capture_job(
            capture_record_id=stored["capture_record_id"],
            analysis_version="analysis-next",
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertNotEqual(first["job_id"], second["job_id"])
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            2,
        )

    def test_enqueue_policy_is_shadow_only(self):
        stored = self.store_web()
        result = self.enqueue(
            stored["capture_record_id"]
        )
        self.assertTrue(
            result["policy"]["persistent_job"]
        )
        self.assertFalse(
            result["policy"]["affects_live_merit"]
        )

    def test_reconcile_disabled_is_noop(self):
        result = automation.reconcile_browser_capture_jobs(
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.disabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "disabled")

    def test_reconcile_creates_missing_web_job(self):
        self.store_web()
        result = automation.reconcile_browser_capture_jobs(
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["created"], 1)
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_reconcile_recovers_missing_social_job(self):
        self.store_x()
        result = automation.reconcile_browser_capture_jobs(
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["created"], 1)
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_reconcile_does_not_duplicate_existing_job(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        result = automation.reconcile_browser_capture_jobs(
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_claim_returns_ready_job(self):
        job = self.claimed()
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "running")
        self.assertEqual(job["lease_owner"], "worker-a")

    def test_claim_increments_attempt_count(self):
        job = self.claimed()
        self.assertEqual(int(job["attempts"]), 1)

    def test_claim_sets_lease_expiry(self):
        job = self.claimed(now=1000)
        self.assertEqual(
            int(job["lease_expires_at_epoch"]),
            1030,
        )

    def test_claim_filters_analysis_version(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        job = automation.claim_next_browser_capture_job(
            worker_id="worker-a",
            analysis_version="wrong",
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            lease_seconds=30,
            now_provider=lambda: 1000,
        )
        self.assertIsNone(job)

    def test_claim_respects_available_at(self):
        stored = self.store_web()
        self.enqueue(
            stored["capture_record_id"],
            now=2000,
        )
        job = automation.claim_next_browser_capture_job(
            worker_id="worker-a",
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            lease_seconds=30,
            now_provider=lambda: 1000,
        )
        self.assertIsNone(job)

    def test_expired_lease_is_requeued(self):
        job = self.claimed(now=1000)
        self.execute(
            "UPDATE browser_capture_automation_jobs "
            "SET lease_expires_at_epoch = 999 "
            "WHERE id = ?",
            (job["id"],),
        )
        reclaimed = self.claim(
            worker="worker-b",
            now=1001,
        )
        self.assertIsNotNone(reclaimed)
        self.assertEqual(
            reclaimed["lease_owner"],
            "worker-b",
        )
        self.assertEqual(
            int(reclaimed["attempts"]),
            2,
        )

    def test_expired_final_lease_is_failed(self):
        job = self.claimed(now=1000)
        self.execute(
            "UPDATE browser_capture_automation_jobs "
            "SET lease_expires_at_epoch = 999, attempts = max_attempts "
            "WHERE id = ?",
            (job["id"],),
        )
        self.assertIsNone(
            self.claim(
                worker="worker-b",
                now=1001,
            )
        )
        row = self.one(
            "SELECT status, last_outcome FROM "
            "browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "failed")
        self.assertEqual(
            row["last_outcome"],
            "lease_expired_retry_exhausted",
        )

    def test_complete_claimed_job(self):
        job = self.claimed(now=1000)
        result = automation.complete_browser_capture_job(
            job_id=job["id"],
            worker_id="worker-a",
            result={"ok": True},
            connection_factory=self.factory,
            now_provider=lambda: 1010,
        )
        self.assertEqual(result["status"], "completed")
        row = self.one(
            "SELECT status, result_json FROM browser_capture_automation_jobs "
            "WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "completed")
        self.assertEqual(
            json.loads(row["result_json"]),
            {"ok": True},
        )

    def test_complete_requires_matching_worker(self):
        job = self.claimed()
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation.complete_browser_capture_job(
                job_id=job["id"],
                worker_id="wrong",
                result={"ok": True},
                connection_factory=self.factory,
                now_provider=lambda: 1001,
            )

    def test_retry_schedules_backoff(self):
        job = self.claimed(now=1000)
        result = automation.retry_browser_capture_job(
            job_id=job["id"],
            worker_id="worker-a",
            outcome="provider_error",
            error_type="RuntimeError",
            error_detail="boom",
            connection_factory=self.factory,
            retry_base_seconds=10,
            retry_cap_seconds=60,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "pending")
        self.assertEqual(
            int(result["available_at_epoch"]),
            1011,
        )

    def test_retry_fails_after_max_attempts(self):
        job = self.claimed(now=1000)
        self.execute(
            "UPDATE browser_capture_automation_jobs "
            "SET attempts = max_attempts WHERE id = ?",
            (job["id"],),
        )
        result = automation.retry_browser_capture_job(
            job_id=job["id"],
            worker_id="worker-a",
            outcome="provider_error",
            error_type="RuntimeError",
            error_detail="boom",
            connection_factory=self.factory,
            retry_base_seconds=10,
            retry_cap_seconds=60,
            now_provider=lambda: 1001,
        )
        self.assertEqual(result["status"], "failed")

    def test_worker_disabled_does_not_start(self):
        result = automation.start_browser_capture_automation_worker(
            connection_factory=self.factory,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            env_getter=self.disabled_env,
        )
        self.assertEqual(result["status"], "disabled")

    def test_worker_starts_once_and_stops(self):
        with mock.patch.object(
            automation,
            "_worker_loop",
            return_value=None,
        ):
            result = automation.start_browser_capture_automation_worker(
                connection_factory=self.factory,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                gemini_client_factory=lambda: object(),
                gemini_generator=lambda **kwargs: {},
                env_getter=self.enabled_env,
            )
            self.assertEqual(result["status"], "started")
            stopped = automation.stop_browser_capture_automation_worker(
                join_timeout_seconds=0.5
            )
            self.assertEqual(stopped["status"], "stopped")

    def test_worker_duplicate_start_is_idempotent(self):
        release = mock.Mock()

        def hold_worker(config):
            del config
            while not automation._WORKER_STOP.is_set():
                automation._WORKER_STOP.wait(0.01)
            release()

        with mock.patch.object(
            automation,
            "_worker_loop",
            side_effect=hold_worker,
        ):
            first = automation.start_browser_capture_automation_worker(
                connection_factory=self.factory,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                gemini_client_factory=lambda: object(),
                gemini_generator=lambda **kwargs: {},
                env_getter=self.enabled_env,
            )
            second = automation.start_browser_capture_automation_worker(
                connection_factory=self.factory,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                gemini_client_factory=lambda: object(),
                gemini_generator=lambda **kwargs: {},
                env_getter=self.enabled_env,
            )
            self.assertEqual(first["status"], "started")
            self.assertEqual(second["status"], "already_running")

        automation.stop_browser_capture_automation_worker(
            join_timeout_seconds=0.5
        )

    def test_lifecycle_registration_requires_app(self):
        with self.assertRaises(
            automation.BrowserCaptureAutomationInputError
        ):
            automation.register_browser_capture_automation_lifecycle(
                app=None,
                connection_factory=self.factory,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                gemini_client_factory=lambda: object(),
                gemini_generator=lambda **kwargs: {},
            )

    def test_lifecycle_registers_startup_and_shutdown(self):
        app = FakeApp()
        result = automation.register_browser_capture_automation_lifecycle(
            app=app,
            connection_factory=self.factory,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            env_getter=self.disabled_env,
        )
        self.assertEqual(result["status"], "registered")
        self.assertEqual(
            [event for event, _ in app.handlers],
            ["startup", "shutdown"],
        )

    def test_lifecycle_registered_once_in_composition(self):
        source = (
            BACKEND_DIR
            / "app"
            / "application"
            / "composition.py"
        ).read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            source.count(
                "register_browser_capture_automation_lifecycle("
            ),
            1,
        )

    def test_main_still_defers_database_initialization_to_startup(self):
        main_source = Path(main.__file__).read_text(
            encoding="utf-8"
        )
        startup_handlers = tuple(
            getattr(
                main.app.state,
                "_sportabase_startup_handlers",
                (),
            )
        )

        self.assertIn(
            "register_startup_handler(\n"
            "    app,\n"
            "    init_db,\n"
            ")",
            main_source,
        )
        self.assertIn(
            main.init_db,
            startup_handlers,
        )

    def test_service_does_not_call_live_merit_release(self):
        source = Path(automation.__file__).read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "apply_certified_live_merit",
            "evaluate_live_merit_release",
            "validate_merit_score_release_certificate",
        ):
            self.assertNotIn(forbidden, source)

    def test_service_policy_marks_live_merit_shadow_only(self):
        source = Path(automation.__file__).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"live_merit_shadow_only": True',
            source,
        )
        self.assertIn(
            '"affects_live_merit": False',
            source,
        )


if __name__ == "__main__":
    unittest.main()
