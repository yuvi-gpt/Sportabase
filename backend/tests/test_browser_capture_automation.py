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
        job = self.claim(now=1000)
        self.assertIsNone(job)

    def test_nonexpired_running_job_is_not_double_claimed(self):
        self.claimed(now=1000)
        second = self.claim(
            worker="worker-b",
            now=1010,
        )
        self.assertIsNone(second)

    def test_expired_lease_is_reclaimed_before_max_attempts(self):
        first = self.claimed(now=1000)
        second = self.claim(
            worker="worker-b",
            now=1040,
        )
        self.assertIsNotNone(second)
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second["lease_owner"], "worker-b")
        self.assertEqual(int(second["attempts"]), 2)

    def test_expired_final_attempt_becomes_failed(self):
        job = self.claimed(now=1000)
        self.execute(
            """
            UPDATE browser_capture_automation_jobs
            SET attempts = max_attempts,
                lease_expires_at_epoch = 1001
            WHERE id = ?
            """,
            (job["id"],),
        )
        next_job = self.claim(
            worker="worker-b",
            now=1040,
        )
        self.assertIsNone(next_job)
        row = self.one(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "failed")
        self.assertEqual(
            row["last_outcome"],
            "lease_expired_retry_exhausted",
        )

    def test_update_rejects_wrong_lease_owner(self):
        job = self.claimed()
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._update_claimed_job(
                job_id=job["id"],
                worker_id="wrong-worker",
                status="completed",
                available_at_epoch=1000,
                last_outcome="completed_shadow",
                error_type="",
                error_detail="",
                result={},
                finished=True,
                connection_factory=self.factory,
                now_provider=lambda: 1000,
            )

    def test_retry_delay_is_exponential(self):
        self.assertEqual(
            automation._retry_delay(
                1,
                base_seconds=10,
                cap_seconds=60,
            ),
            10,
        )
        self.assertEqual(
            automation._retry_delay(
                2,
                base_seconds=10,
                cap_seconds=60,
            ),
            20,
        )

    def test_retry_delay_is_capped(self):
        self.assertEqual(
            automation._retry_delay(
                10,
                base_seconds=10,
                cap_seconds=60,
            ),
            60,
        )

    def test_successful_runner_completes_job(self):
        job = self.claimed()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=lambda **kwargs: safe_shadow_result(
                kwargs["anchor_capture_record_id"]
            ),
        )
        self.assertEqual(result["status"], "completed")
        row = self.one(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["last_outcome"], "completed_shadow")

    def test_success_result_is_compact_audit_summary(self):
        job = self.claimed()
        automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=lambda **kwargs: safe_shadow_result(
                kwargs["anchor_capture_record_id"]
            ),
        )
        row = self.one(
            "SELECT result_json FROM browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        result = json.loads(row["result_json"])
        self.assertEqual(result["claim_id"], "claim-123")
        self.assertFalse(result["policy"]["affects_live_merit"])
        self.assertNotIn("orchestration", result)

    def retry_exception_case(self, error, expected_outcome):
        job = self.claimed()

        def runner(**kwargs):
            raise error

        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            retry_base_seconds=10,
            retry_cap_seconds=60,
            now_provider=lambda: 1000,
            runner=runner,
        )
        self.assertEqual(result["status"], "retry_scheduled")
        row = self.one(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["last_outcome"], expected_outcome)
        self.assertEqual(int(row["available_at_epoch"]), 1010)

    def test_baseline_unavailable_is_retryable(self):
        self.retry_exception_case(
            history.MultimodalInboxHistoryAutoShadowBaselineUnavailable(
                "baseline not ready"
            ),
            "baseline_not_ready",
        )

    def test_lookup_unavailable_is_retryable(self):
        self.retry_exception_case(
            history.MultimodalInboxHistoryAutoShadowLookupError(
                "db busy"
            ),
            "lookup_unavailable",
        )

    def test_provider_unavailable_is_retryable(self):
        self.retry_exception_case(
            history.MultimodalInboxHistoryAutoShadowProviderUnavailable(
                "provider down"
            ),
            "provider_unavailable",
        )

    def test_selection_or_shadow_failure_is_retryable(self):
        self.retry_exception_case(
            history.MultimodalInboxHistoryAutoShadowExecutionError(
                "no peer yet"
            ),
            "selection_or_shadow_not_ready",
        )

    def terminal_exception_case(self, error):
        job = self.claimed()

        def runner(**kwargs):
            raise error

        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=runner,
        )
        self.assertEqual(result["status"], "failed")
        row = self.one(
            "SELECT * FROM browser_capture_automation_jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(row["status"], "failed")
        self.assertEqual(
            row["last_outcome"],
            "terminal_integrity_or_input_failure",
        )

    def test_runner_input_error_is_terminal(self):
        self.terminal_exception_case(
            history.MultimodalInboxHistoryAutoShadowInputError(
                "invalid"
            )
        )

    def test_runner_integrity_error_is_terminal(self):
        self.terminal_exception_case(
            history.MultimodalInboxHistoryAutoShadowIntegrityError(
                "unsafe"
            )
        )

    def test_unexpected_runtime_error_is_retryable(self):
        self.retry_exception_case(
            RuntimeError("temporary bug"),
            "unexpected_runtime_failure",
        )

    def test_missing_client_factory_is_retryable(self):
        job = self.claimed()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=None,
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "retry_scheduled")
        self.assertEqual(
            result["job"]["last_outcome"],
            "provider_unavailable",
        )

    def test_none_client_is_retryable(self):
        job = self.claimed()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: None,
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "retry_scheduled")

    def test_missing_generator_is_retryable(self):
        job = self.claimed()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=None,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "retry_scheduled")

    def test_client_factory_exception_is_retryable(self):
        job = self.claimed()

        def broken_factory():
            raise RuntimeError("provider construction failed")

        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=broken_factory,
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "retry_scheduled")
        self.assertEqual(
            result["job"]["last_outcome"],
            "unexpected_runtime_failure",
        )

    def test_unsafe_completed_result_is_terminal(self):
        job = self.claimed()
        unsafe = safe_shadow_result(
            job["capture_record_id"]
        )
        unsafe["policy"]["affects_live_merit"] = True
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=lambda **kwargs: unsafe,
        )
        self.assertEqual(result["status"], "failed")

    def test_wrong_runner_version_is_terminal(self):
        job = self.claimed()
        unsafe = safe_shadow_result(
            job["capture_record_id"]
        )
        unsafe["version"] = "wrong"
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=lambda **kwargs: unsafe,
        )
        self.assertEqual(result["status"], "failed")

    def test_retry_exhaustion_becomes_failed(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        self.execute(
            "UPDATE browser_capture_automation_jobs SET max_attempts = 1"
        )
        job = self.claim(now=1000)

        def runner(**kwargs):
            raise history.MultimodalInboxHistoryAutoShadowBaselineUnavailable(
                "still unavailable"
            )

        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=runner,
        )
        self.assertEqual(result["status"], "failed")
        self.assertTrue(
            result["job"]["last_outcome"].startswith(
                "retry_exhausted:"
            )
        )

    def test_iteration_is_disabled_by_default(self):
        result = automation.run_browser_capture_automation_iteration(
            worker_id="worker-a",
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            env_getter=self.disabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "disabled")

    def test_iteration_is_idle_without_jobs(self):
        result = automation.run_browser_capture_automation_iteration(
            worker_id="worker-a",
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        self.assertEqual(result["status"], "idle")

    def test_iteration_claims_and_executes_one_job(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        with mock.patch.object(
            automation,
            "execute_claimed_browser_capture_job",
            return_value={"status": "completed"},
        ) as execute:
            result = automation.run_browser_capture_automation_iteration(
                worker_id="worker-a",
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                connection_factory=self.factory,
                gemini_client_factory=lambda: object(),
                gemini_generator=lambda **kwargs: {},
                env_getter=self.enabled_env,
                now_provider=lambda: 1000,
            )
        self.assertEqual(result["status"], "completed")
        execute.assert_called_once()

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
            [item[0] for item in app.handlers],
            ["startup", "shutdown"],
        )

    def test_start_worker_disabled_does_not_spawn(self):
        result = automation.start_browser_capture_automation_worker(
            connection_factory=self.factory,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            env_getter=self.disabled_env,
        )
        self.assertEqual(result["status"], "disabled")

    def test_stop_worker_without_thread_is_safe(self):
        result = automation.stop_browser_capture_automation_worker(
            join_timeout_seconds=0.1
        )
        self.assertEqual(result["status"], "stopped")

    def test_public_preview_enqueues_after_successful_store(self):
        calls = []

        def enqueue(**kwargs):
            calls.append(kwargs)
            return {"status": "enqueued"}

        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=web_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            automation_enqueue=enqueue,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        self.assertTrue(result["capture_persisted"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["capture_record_id"],
            result["capture_record_id"],
        )
        self.assertEqual(
            calls[0]["analysis_version"],
            ANALYSIS_VERSION,
        )
        self.assertEqual(
            calls[0]["scoring_version"],
            SCORING_VERSION,
        )

    def test_public_preview_queue_failure_is_fail_open(self):
        def enqueue(**kwargs):
            raise RuntimeError("queue unavailable")

        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=web_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            automation_enqueue=enqueue,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        self.assertTrue(result["capture_persisted"])
        self.assertEqual(
            result["capture_inbox_status"],
            "stored",
        )

    def test_disabled_inbox_never_calls_enqueue(self):
        calls = []
        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=web_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=(
                lambda key, default=None:
                "0"
                if key == inbox.BROWSER_CAPTURE_INBOX_FLAG
                else default
            ),
            automation_enqueue=lambda **kwargs: calls.append(kwargs),
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        self.assertFalse(result["capture_persisted"])
        self.assertEqual(calls, [])

    def test_replayed_capture_reuses_same_job(self):
        first = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=web_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            automation_enqueue=automation.enqueue_browser_capture_job,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        second = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=web_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            automation_enqueue=automation.enqueue_browser_capture_job,
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
        )
        self.assertEqual(
            first["capture_record_id"],
            second["capture_record_id"],
        )
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            1,
        )

    def test_execute_http_forwards_automation_dependencies(self):
        request = BrowserCaptureRequest(
            capture=web_capture()
        )
        calls = []

        def enqueue(**kwargs):
            calls.append(kwargs)
            return {"status": "enqueued"}

        with mock.patch.object(
            inbox,
            "inbox_enabled",
            return_value=True,
        ):
            response = inbox.execute_browser_capture_http(
                req=request,
                connection_factory=self.factory,
                response_model=BrowserCaptureResponse,
                automation_enqueue=enqueue,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
            )
        self.assertTrue(response.capture_persisted)
        self.assertEqual(len(calls), 1)

    def test_queue_table_references_only_neutral_capture_record(self):
        schema = SCHEMA
        start = schema.find(
            "CREATE TABLE IF NOT EXISTS browser_capture_automation_jobs"
        )
        end = schema.find(
            ");",
            start,
        )
        block = schema[start:end + 2]
        self.assertIn("browser_capture_inbox", block)
        for forbidden in (
            "claim_id",
            "evidence_id",
            "source_id",
            "subject_key",
            "merit_score",
            "intelligence_claims",
        ):
            self.assertNotIn(forbidden, block)

    def test_queue_schema_has_status_check(self):
        self.assertIn(
            "browser_capture_automation_jobs",
            SCHEMA,
        )
        self.assertIn(
            "lease_expires_at_epoch",
            SCHEMA,
        )
        self.assertIn(
            "max_attempts",
            SCHEMA,
        )

    def test_queue_writes_do_not_create_intelligence_records(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        for table in (
            "canonical_entities",
            "intelligence_sources",
            "media_items",
            "intelligence_claims",
            "source_observations",
            "evidence_records",
        ):
            with self.subTest(table=table):
                self.assertEqual(self.count(table), 0)

    def test_main_public_capture_wires_automation_enqueue(self):
        source = Path(main.__file__).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "browser_capture_automation",
            source,
        )
        self.assertIn(
            ".enqueue_browser_capture_job",
            source,
        )

    def test_main_registers_worker_lifecycle(self):
        source = Path(main.__file__).read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            source.count(
                "register_browser_capture_automation_lifecycle("
            ),
            1,
        )

    def test_main_still_defers_database_initialization_to_startup(self):
        source = Path(main.__file__).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'app.add_event_handler(\n    "startup",\n    init_db,\n)',
            source,
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

    def test_worker_uses_persisted_history_auto_shadow_runner(self):
        source = Path(automation.__file__).read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "execute_multimodal_inbox_history_auto_shadow",
            source,
        )

    def test_worker_reconciliation_recovers_missed_enqueue(self):
        stored = self.store_web(slug="missed")
        self.assertEqual(
            self.count("browser_capture_automation_jobs"),
            0,
        )
        automation.reconcile_browser_capture_jobs(
            analysis_version=ANALYSIS_VERSION,
            scoring_version=SCORING_VERSION,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
            now_provider=lambda: 1000,
        )
        row = self.one(
            "SELECT * FROM browser_capture_automation_jobs WHERE capture_record_id = ?",
            (stored["capture_record_id"],),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "pending")

    def test_worker_job_versions_are_server_scoped(self):
        stored = self.store_web()
        self.enqueue(stored["capture_record_id"])
        row = self.one(
            "SELECT analysis_version, scoring_version FROM browser_capture_automation_jobs"
        )
        self.assertEqual(
            row["analysis_version"],
            ANALYSIS_VERSION,
        )
        self.assertEqual(
            row["scoring_version"],
            SCORING_VERSION,
        )

    def test_job_result_never_marks_live_merit_effect(self):
        job = self.claimed()
        result = automation.execute_claimed_browser_capture_job(
            job=job,
            worker_id="worker-a",
            connection_factory=self.factory,
            gemini_client_factory=lambda: object(),
            gemini_generator=lambda **kwargs: {},
            now_provider=lambda: 1000,
            runner=lambda **kwargs: safe_shadow_result(
                kwargs["anchor_capture_record_id"]
            ),
        )
        self.assertFalse(
            result["result"]["policy"]["affects_live_merit"]
        )

    def test_worker_does_not_accept_caller_subject_or_candidate(self):
        parameters = (
            automation.execute_claimed_browser_capture_job
            .__code__
            .co_varnames
        )
        self.assertNotIn(
            "subject_entity_id",
            parameters,
        )
        self.assertNotIn(
            "candidate_capture_record_id",
            parameters,
        )

    def test_automation_has_no_extension_dependency(self):
        source = Path(automation.__file__).read_text(
            encoding="utf-8"
        )
        self.assertNotIn("extension/", source)
        self.assertNotIn("x-sportabase-admin-key", source)


if __name__ == "__main__":
    unittest.main()
