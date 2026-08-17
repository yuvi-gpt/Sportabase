from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.routes import multimodal_admin
from app.services import browser_capture_inbox as inbox
from app.services import browser_ingestion
from app.services import multimodal_inbox_shadow_orchestration as inbox_shadow
from app.services import multimodal_shadow_orchestration


OBSERVED = "2026-08-17T09:30:00Z"
RECEIVED = "2026-08-17T09:31:00Z"


def subject_payload():
    return {
        "entity_key": "football|club|arsenal",
        "entity_type": "club",
        "canonical_name": "Arsenal",
        "sport_key": "football",
    }


def x_capture(
    *,
    handle="reporter_one",
    status_id="111111",
    observed_at=OBSERVED,
    body="Arsenal transfer update",
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://x.com/"
            + handle
            + "/status/"
            + status_id
        ),
        "observed_at": observed_at,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "x",
            "surface": "post",
            "container_kind": "post",
            "canonical_url": (
                "https://x.com/"
                + handle
                + "/status/"
                + status_id
            ),
            "body": body,
        },
        "actor": {
            "handle": handle,
            "display_name": "Reporter One",
            "profile_url": (
                "https://x.com/"
                + handle
            ),
        },
    }


def web_capture(
    *,
    slug="story-one",
    observed_at=OBSERVED,
):
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://example.com/"
            + slug
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
                "https://example.com/"
                + slug
            ),
            "title": "Article title",
            "body": "Article body",
        },
        "actor": {},
    }


def http_request(
    *,
    admin_key="secret",
    path=(
        "/admin/intelligence/"
        "multimodal-shadow-run-inbox"
    ),
):
    headers = []

    if admin_key:
        headers.append(
            (
                b"x-sportabase-admin-key",
                admin_key.encode("utf-8"),
            )
        )

    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": b"",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    })


def safe_orchestration_result():
    return {
        "version": (
            multimodal_shadow_orchestration
            .MULTIMODAL_SHADOW_ORCHESTRATION_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": "claim-123",
        "registration": {},
        "shadow": {},
        "policy": {
            "caller_cannot_supply_binding_ids": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
            "live_merit_shadow_only": True,
            "merit_baseline_mode": "legacy_merit",
            "merit_baseline_available": True,
            "merit_shadow_evaluated": True,
            "synthetic_merit_baseline_used": False,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class BrowserCaptureInboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = (
            Path(self.tmp.name)
            / "capture-inbox.db"
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

    def tearDown(self):
        self.tmp.cleanup()

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

    def enabled_env(self, key, default=None):
        values = {
            inbox.BROWSER_CAPTURE_INBOX_FLAG: "1",
            inbox.BROWSER_CAPTURE_INBOX_MAX_BYTES: "131072",
        }
        return values.get(key, default)

    def disabled_env(self, key, default=None):
        values = {
            inbox.BROWSER_CAPTURE_INBOX_FLAG: "0",
        }
        return values.get(key, default)

    def store(self, capture=None):
        return inbox.store_browser_capture(
            raw_capture=(
                capture
                or x_capture()
            ),
            connection_factory=self.factory,
            now_provider=lambda: RECEIVED,
        )

    def test_inbox_flag_defaults_off(self):
        self.assertFalse(
            inbox.inbox_enabled(
                env_getter=(
                    lambda key, default=None: default
                )
            )
        )

    def test_inbox_flag_accepts_true_token(self):
        self.assertTrue(
            inbox.inbox_enabled(
                env_getter=self.enabled_env
            )
        )

    def test_inbox_max_bytes_has_safe_lower_bound(self):
        value = inbox.inbox_max_bytes(
            env_getter=(
                lambda key, default=None: "1"
            )
        )
        self.assertEqual(value, 4096)

    def test_capture_identity_is_deterministic(self):
        first = inbox.capture_record_identity(
            x_capture()
        )
        second = inbox.capture_record_identity(
            x_capture()
        )
        self.assertEqual(first, second)

    def test_observed_time_changes_capture_record_identity(self):
        first = inbox.capture_record_identity(
            x_capture()
        )
        second = inbox.capture_record_identity(
            x_capture(
                observed_at="2026-08-17T09:32:00Z"
            )
        )
        self.assertNotEqual(
            first["capture_record_id"],
            second["capture_record_id"],
        )

    def test_content_change_changes_capture_record_identity(self):
        first = inbox.capture_record_identity(
            x_capture(body="one")
        )
        second = inbox.capture_record_identity(
            x_capture(body="two")
        )
        self.assertNotEqual(
            first["capture_record_id"],
            second["capture_record_id"],
        )

    def test_disabled_preview_does_not_write(self):
        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=x_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.disabled_env,
        )
        self.assertFalse(result["capture_persisted"])
        self.assertEqual(
            result["capture_inbox_status"],
            "disabled",
        )
        self.assertEqual(
            self.count("browser_capture_inbox"),
            0,
        )

    def test_enabled_preview_stores_capture(self):
        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=x_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.enabled_env,
        )
        self.assertTrue(result["capture_persisted"])
        self.assertEqual(
            result["capture_inbox_status"],
            "stored",
        )
        self.assertTrue(
            result["capture_record_id"].startswith("bci_")
        )
        self.assertEqual(
            self.count("browser_capture_inbox"),
            1,
        )

    def test_exact_replay_reuses_record_and_increments_count(self):
        first = self.store()
        second = self.store()
        self.assertEqual(
            first["capture_record_id"],
            second["capture_record_id"],
        )
        self.assertEqual(second["status"], "replayed")
        self.assertEqual(second["receive_count"], 2)
        self.assertEqual(
            self.count("browser_capture_inbox"),
            1,
        )

    def test_distinct_snapshots_create_distinct_records(self):
        self.store(
            x_capture(status_id="111111")
        )
        self.store(
            x_capture(status_id="222222")
        )
        self.assertEqual(
            self.count("browser_capture_inbox"),
            2,
        )

    def test_oversize_capture_skips_persistence(self):
        capture = x_capture(
            body="x" * 10000
        )
        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=capture,
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=(
                lambda key, default=None:
                "1"
                if key == inbox.BROWSER_CAPTURE_INBOX_FLAG
                else "4096"
            ),
        )
        self.assertEqual(
            result["capture_inbox_status"],
            "oversize",
        )
        self.assertFalse(result["capture_persisted"])
        self.assertEqual(
            self.count("browser_capture_inbox"),
            0,
        )

    def test_persistence_failure_is_fail_open_for_preview(self):
        result = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=x_capture(),
            short_video_threshold_seconds=180.0,
            connection_factory=(
                lambda: (_ for _ in ()).throw(
                    sqlite3.OperationalError("down")
                )
            ),
            env_getter=self.enabled_env,
        )
        self.assertEqual(
            result["capture_inbox_status"],
            "unavailable",
        )
        self.assertFalse(result["capture_persisted"])
        self.assertIn("item", result)

    def test_invalid_capture_is_input_error(self):
        capture = x_capture()
        capture["version"] = "wrong"
        with self.assertRaises(
            inbox.BrowserCaptureInboxInputError
        ):
            inbox.preview_and_maybe_store_browser_capture(
                raw_capture=capture,
                short_video_threshold_seconds=180.0,
                connection_factory=self.factory,
                env_getter=self.enabled_env,
            )

    def test_store_writes_only_neutral_inbox(self):
        self.store()
        self.assertEqual(
            self.count("browser_capture_inbox"),
            1,
        )
        for table in (
            "canonical_entities",
            "intelligence_sources",
            "media_items",
            "intelligence_claims",
            "source_observations",
            "evidence_records",
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.count(table),
                    0,
                )

    def test_actor_canonical_entity_id_is_not_promoted(self):
        capture = x_capture()
        capture["actor"][
            "canonical_entity_id"
        ] = "caller-asserted"
        self.store(capture)
        self.assertEqual(
            self.count("canonical_entities"),
            0,
        )

    def test_inbox_metadata_marks_capture_untrusted(self):
        result = self.store()
        row = self.one(
            "SELECT metadata_json FROM browser_capture_inbox WHERE id = ?",
            (result["capture_record_id"],),
        )
        metadata = json.loads(row["metadata_json"])
        self.assertEqual(
            metadata["trust_class"],
            "untrusted_browser_capture",
        )
        self.assertFalse(metadata["affects_live_merit"])

    def test_capture_json_is_canonical_and_recoverable(self):
        capture = x_capture()
        result = self.store(capture)
        row = self.one(
            "SELECT capture_json FROM browser_capture_inbox WHERE id = ?",
            (result["capture_record_id"],),
        )
        self.assertEqual(
            json.loads(row["capture_json"]),
            capture,
        )

    def test_load_returns_exact_capture(self):
        capture = x_capture()
        result = self.store(capture)
        loaded = inbox.load_browser_capture_record(
            capture_record_id=result["capture_record_id"],
            connection_factory=self.factory,
        )
        self.assertEqual(loaded["capture"], capture)
        self.assertTrue(
            loaded["policy"]["record_is_untrusted"]
        )

    def test_load_is_read_only(self):
        result = self.store()
        before = self.one(
            "SELECT receive_count, last_received_at FROM browser_capture_inbox WHERE id = ?",
            (result["capture_record_id"],),
        )
        inbox.load_browser_capture_record(
            capture_record_id=result["capture_record_id"],
            connection_factory=self.factory,
        )
        after = self.one(
            "SELECT receive_count, last_received_at FROM browser_capture_inbox WHERE id = ?",
            (result["capture_record_id"],),
        )
        self.assertEqual(before, after)

    def test_load_missing_record_fails_closed(self):
        with self.assertRaises(
            inbox.BrowserCaptureInboxNotFoundError
        ):
            inbox.load_browser_capture_record(
                capture_record_id="bci_missing",
                connection_factory=self.factory,
            )

    def test_load_detects_capture_json_tamper(self):
        result = self.store()
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE browser_capture_inbox SET capture_json = '{}' WHERE id = ?",
                (result["capture_record_id"],),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            inbox.BrowserCaptureInboxIntegrityError
        ):
            inbox.load_browser_capture_record(
                capture_record_id=result["capture_record_id"],
                connection_factory=self.factory,
            )

    def test_load_detects_hash_tamper(self):
        result = self.store()
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE browser_capture_inbox SET capture_hash = ? WHERE id = ?",
                ("0" * 64, result["capture_record_id"]),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            inbox.BrowserCaptureInboxIntegrityError
        ):
            inbox.load_browser_capture_record(
                capture_record_id=result["capture_record_id"],
                connection_factory=self.factory,
            )

    def test_load_detects_normalized_hash_tamper(self):
        result = self.store()
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE browser_capture_inbox SET normalized_content_hash = ? WHERE id = ?",
                ("bad", result["capture_record_id"]),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            inbox.BrowserCaptureInboxIntegrityError
        ):
            inbox.load_browser_capture_record(
                capture_record_id=result["capture_record_id"],
                connection_factory=self.factory,
            )

    def test_store_requires_database_access(self):
        with self.assertRaises(
            inbox.BrowserCaptureInboxPersistenceError
        ):
            inbox.store_browser_capture(
                raw_capture=x_capture(),
                connection_factory=None,
            )

    def test_preview_payload_matches_existing_ingestion_item(self):
        capture = web_capture()
        expected = browser_ingestion.preview_browser_capture(
            capture
        )
        actual = inbox.preview_and_maybe_store_browser_capture(
            raw_capture=capture,
            short_video_threshold_seconds=180.0,
            connection_factory=self.factory,
            env_getter=self.disabled_env,
        )
        self.assertEqual(actual["item"], expected["item"])
        self.assertEqual(
            actual["processing_plan"],
            expected["processing_plan"],
        )

    def test_http_adapter_maps_invalid_capture_to_422(self):
        req = main.BrowserCaptureRequest(
            capture={
                "version": "wrong",
            }
        )
        with self.assertRaises(HTTPException) as captured:
            inbox.execute_browser_capture_http(
                req=req,
                connection_factory=self.factory,
                response_model=main.BrowserCaptureResponse,
            )
        self.assertEqual(
            captured.exception.status_code,
            422,
        )

    def test_http_adapter_response_exposes_inbox_fields(self):
        req = main.BrowserCaptureRequest(
            capture=x_capture()
        )
        with mock.patch.dict(
            os.environ,
            {
                inbox.BROWSER_CAPTURE_INBOX_FLAG: "1",
            },
            clear=False,
        ):
            response = inbox.execute_browser_capture_http(
                req=req,
                connection_factory=self.factory,
                response_model=main.BrowserCaptureResponse,
            )
        self.assertTrue(response.capture_persisted)
        self.assertTrue(response.capture_record_id)
        self.assertEqual(
            response.capture_inbox_version,
            inbox.BROWSER_CAPTURE_INBOX_VERSION,
        )

    def test_main_browser_capture_endpoint_delegates_to_inbox_service(self):
        req = main.BrowserCaptureRequest(
            capture=x_capture()
        )
        expected = main.BrowserCaptureResponse(
            version="browser-ingestion-v1",
            item={},
            processing_plan={},
            artifact_manifest={},
            capture_record_id="",
            capture_persisted=False,
            capture_inbox_status="disabled",
            capture_inbox_version=(
                inbox.BROWSER_CAPTURE_INBOX_VERSION
            ),
        )
        with mock.patch.object(
            inbox,
            "execute_browser_capture_http",
            return_value=expected,
        ) as service:
            actual = main.browser_capture_preview(req)
        self.assertIs(actual, expected)
        service.assert_called_once()

    def test_openapi_browser_capture_response_exposes_inbox_fields(self):
        schemas = main.app.openapi()[
            "components"
        ]["schemas"]
        properties = schemas[
            "BrowserCaptureResponse"
        ]["properties"]
        self.assertIn(
            "capture_record_id",
            properties,
        )
        self.assertIn(
            "capture_persisted",
            properties,
        )

    def test_schema_contains_neutral_inbox_table(self):
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS browser_capture_inbox",
            SCHEMA,
        )
        self.assertIn(
            "idx_browser_capture_inbox_observed",
            SCHEMA,
        )

    def test_service_source_has_no_intelligence_writes(self):
        source = Path(
            inbox.__file__
        ).read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "INSERT INTO media_items",
            "INSERT INTO intelligence_sources",
            "INSERT INTO canonical_entities",
            "INSERT INTO intelligence_claims",
            "INSERT INTO evidence_records",
            "INSERT INTO source_observations",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_service_source_has_no_live_release_dependency(self):
        source = Path(
            inbox.__file__
        ).read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "apply_certified_live_merit",
            "evaluate_live_merit_release",
            "release_certificate",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)


class MultimodalInboxShadowTests(unittest.TestCase):
    def loaded(self, record_id, capture):
        return {
            "version": inbox.BROWSER_CAPTURE_INBOX_VERSION,
            "capture_record_id": record_id,
            "capture": capture,
            "canonical_url": capture["source_url"],
            "platform": "x",
            "platform_surface": "post",
            "observed_at": OBSERVED,
            "receive_count": 1,
            "policy": {
                "record_is_untrusted": True,
                "integrity_rechecked_on_load": True,
                "load_is_read_only": True,
                "affects_live_merit": False,
            },
        }

    def execute(
        self,
        *,
        left_id="bci_left",
        right_id="bci_right",
        client=object(),
        generator=mock.Mock(),
        loader=None,
        runner=None,
    ):
        if loader is None:
            def loader(
                *,
                capture_record_id,
                connection_factory,
            ):
                capture = (
                    x_capture(
                        handle="left",
                        status_id="111111",
                    )
                    if capture_record_id == left_id
                    else x_capture(
                        handle="right",
                        status_id="222222",
                    )
                )
                return self.loaded(
                    capture_record_id,
                    capture,
                )

        if runner is None:
            runner = mock.Mock(
                return_value=safe_orchestration_result()
            )

        return inbox_shadow.execute_multimodal_inbox_shadow_orchestration(
            subject=subject_payload(),
            left_capture_record_id=left_id,
            right_capture_record_id=right_id,
            legacy_score={"total": 70},
            target_claim_id="claim-target",
            connection_factory=mock.Mock(),
            gemini_client=client,
            gemini_client_key="client-1",
            gemini_generator=generator,
            capture_loader=loader,
            orchestration_runner=runner,
        )

    def test_requires_two_distinct_record_ids(self):
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowInputError
        ):
            self.execute(
                left_id="same",
                right_id="same",
            )

    def test_provider_missing_before_capture_load(self):
        loader = mock.Mock()
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowProviderUnavailable
        ):
            self.execute(
                client=None,
                loader=loader,
            )
        loader.assert_not_called()

    def test_generator_missing_before_capture_load(self):
        loader = mock.Mock()
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowProviderUnavailable
        ):
            self.execute(
                generator=None,
                loader=loader,
            )
        loader.assert_not_called()

    def test_loader_receives_exact_record_ids(self):
        loader = mock.Mock(
            side_effect=[
                self.loaded(
                    "bci_left",
                    x_capture(
                        handle="left",
                        status_id="111111",
                    ),
                ),
                self.loaded(
                    "bci_right",
                    x_capture(
                        handle="right",
                        status_id="222222",
                    ),
                ),
            ]
        )
        self.execute(loader=loader)
        ids = [
            call.kwargs["capture_record_id"]
            for call in loader.call_args_list
        ]
        self.assertEqual(
            ids,
            ["bci_left", "bci_right"],
        )

    def test_missing_capture_maps_to_binding_error(self):
        def loader(**kwargs):
            raise inbox.BrowserCaptureInboxNotFoundError(
                "missing"
            )
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowBindingError
        ):
            self.execute(loader=loader)

    def test_tampered_capture_maps_to_integrity_error(self):
        def loader(**kwargs):
            raise inbox.BrowserCaptureInboxIntegrityError(
                "tampered"
            )
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowIntegrityError
        ):
            self.execute(loader=loader)

    def test_orchestration_receives_loaded_captures_not_record_ids(self):
        runner = mock.Mock(
            return_value=safe_orchestration_result()
        )
        self.execute(runner=runner)
        kwargs = runner.call_args.kwargs
        self.assertEqual(
            kwargs["left_capture"]["actor"]["handle"],
            "left",
        )
        self.assertEqual(
            kwargs["right_capture"]["actor"]["handle"],
            "right",
        )
        self.assertNotIn(
            "left_capture_record_id",
            kwargs,
        )

    def test_orchestration_preserves_subject_score_and_target_claim(self):
        runner = mock.Mock(
            return_value=safe_orchestration_result()
        )
        self.execute(runner=runner)
        kwargs = runner.call_args.kwargs
        self.assertEqual(
            kwargs["subject"]["entity_key"],
            "football|club|arsenal",
        )
        self.assertEqual(
            kwargs["legacy_score"]["total"],
            70,
        )
        self.assertEqual(
            kwargs["target_claim_id"],
            "claim-target",
        )

    def test_orchestration_version_mismatch_fails_closed(self):
        bad = safe_orchestration_result()
        bad["version"] = "wrong"
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowIntegrityError
        ):
            self.execute(
                runner=mock.Mock(return_value=bad)
            )

    def test_orchestration_policy_mismatch_fails_closed(self):
        bad = safe_orchestration_result()
        bad["policy"][
            "shadow_adapter_reverifies_bindings"
        ] = False
        with self.assertRaises(
            inbox_shadow.MultimodalInboxShadowIntegrityError
        ):
            self.execute(
                runner=mock.Mock(return_value=bad)
            )

    def test_result_retains_capture_record_scope(self):
        result = self.execute()
        self.assertEqual(
            result["left_capture_record_id"],
            "bci_left",
        )
        self.assertEqual(
            result["right_capture_record_id"],
            "bci_right",
        )
        self.assertEqual(
            result["claim_id"],
            "claim-123",
        )

    def test_result_policy_keeps_inbox_untrusted(self):
        result = self.execute()
        policy = result["policy"]
        self.assertTrue(
            policy["inbox_records_remain_untrusted"]
        )
        self.assertTrue(
            policy[
                "raw_capture_not_accepted_by_admin_endpoint"
            ]
        )
        self.assertFalse(
            policy["affects_live_merit"]
        )

    def test_service_source_performs_no_direct_sql(self):
        source = Path(
            inbox_shadow.__file__
        ).read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)


class MultimodalInboxShadowRouteTests(unittest.TestCase):
    def request_model(self):
        return (
            multimodal_admin
            .MultimodalInboxShadowRunRequest(
                subject=subject_payload(),
                left_capture_record_id="bci_left",
                right_capture_record_id="bci_right",
                legacy_score={"total": 70},
                target_claim_id="claim-target",
            )
        )

    def safe_result(self):
        return {
            "version": (
                inbox_shadow
                .MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
            ),
            "status": "completed_shadow",
            "claim_id": "claim-123",
            "left_capture_record_id": "bci_left",
            "right_capture_record_id": "bci_right",
            "orchestration": {},
            "policy": {
                "affects_live_merit": False,
            },
        }

    def endpoint(
        self,
        *,
        enabled=True,
        admin_guard=None,
        client_factory=None,
        client_key_resolver=None,
        generator=None,
    ):
        guard = admin_guard or mock.Mock()
        client_factory = (
            client_factory
            if client_factory is not None
            else mock.Mock(return_value=object())
        )
        client_key_resolver = (
            client_key_resolver
            if client_key_resolver is not None
            else mock.Mock(return_value="client-1")
        )
        generator = (
            generator
            if generator is not None
            else mock.Mock()
        )
        router = multimodal_admin.build_router(
            enabled,
            guard,
            mock.Mock(),
            client_factory,
            client_key_resolver,
            generator,
        )
        route = next(
            route
            for route in router.routes
            if route.path == (
                "/admin/intelligence/"
                "multimodal-shadow-run-inbox"
            )
        )
        return (
            route.endpoint,
            guard,
            client_factory,
            client_key_resolver,
            generator,
        )

    def test_request_model_forbids_raw_captures(self):
        with self.assertRaises(ValidationError):
            multimodal_admin.MultimodalInboxShadowRunRequest(
                subject=subject_payload(),
                left_capture_record_id="bci_left",
                right_capture_record_id="bci_right",
                legacy_score={"total": 70},
                left_capture=x_capture(),
            )

    def test_request_model_forbids_binding_ids(self):
        with self.assertRaises(ValidationError):
            multimodal_admin.MultimodalInboxShadowRunRequest(
                subject=subject_payload(),
                left_capture_record_id="bci_left",
                right_capture_record_id="bci_right",
                legacy_score={"total": 70},
                source_id="caller-source",
            )

    def test_disabled_route_returns_404_before_admin(self):
        endpoint, guard, _, _, _ = self.endpoint(
            enabled=False
        )
        with self.assertRaises(HTTPException) as captured:
            endpoint(
                self.request_model(),
                http_request(),
            )
        self.assertEqual(
            captured.exception.status_code,
            404,
        )
        guard.assert_not_called()

    def test_enabled_route_calls_admin_guard(self):
        endpoint, guard, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            return_value=self.safe_result(),
        ):
            endpoint(
                self.request_model(),
                http_request(),
            )
        guard.assert_called_once()

    def test_missing_gemini_returns_503_before_orchestration(self):
        endpoint, _, _, _, _ = self.endpoint(
            client_factory=mock.Mock(return_value=None)
        )
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
        ) as service:
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(
            captured.exception.status_code,
            503,
        )
        service.assert_not_called()

    def test_route_calls_inbox_orchestration_with_record_ids(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            return_value=self.safe_result(),
        ) as service:
            response = endpoint(
                self.request_model(),
                http_request(),
            )
        kwargs = service.call_args.kwargs
        self.assertEqual(
            kwargs["left_capture_record_id"],
            "bci_left",
        )
        self.assertEqual(
            kwargs["right_capture_record_id"],
            "bci_right",
        )
        self.assertEqual(
            response.status,
            "completed_shadow",
        )

    def test_input_error_maps_to_422(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            side_effect=(
                inbox_shadow.MultimodalInboxShadowInputError(
                    "bad input"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(captured.exception.status_code, 422)

    def test_binding_error_maps_to_409(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            side_effect=(
                inbox_shadow.MultimodalInboxShadowBindingError(
                    "missing"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(captured.exception.status_code, 409)

    def test_provider_error_maps_to_503(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            side_effect=(
                inbox_shadow.MultimodalInboxShadowProviderUnavailable(
                    "provider"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(captured.exception.status_code, 503)

    def test_execution_error_maps_to_409(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            side_effect=(
                inbox_shadow.MultimodalInboxShadowExecutionError(
                    "runtime"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(captured.exception.status_code, 409)

    def test_integrity_error_maps_to_generic_500(self):
        endpoint, _, _, _, _ = self.endpoint()
        with mock.patch.object(
            inbox_shadow,
            "execute_multimodal_inbox_shadow_orchestration",
            side_effect=(
                inbox_shadow.MultimodalInboxShadowIntegrityError(
                    "secret detail"
                )
            ),
        ):
            with self.assertRaises(HTTPException) as captured:
                endpoint(
                    self.request_model(),
                    http_request(),
                )
        self.assertEqual(captured.exception.status_code, 500)
        self.assertNotIn(
            "secret detail",
            str(captured.exception.detail),
        )

    def test_openapi_exposes_admin_inbox_shadow_route(self):
        self.assertIn(
            "/admin/intelligence/multimodal-shadow-run-inbox",
            main.app.openapi()["paths"],
        )

    def test_main_stays_within_decomposition_budget(self):
        line_count = len(
            (
                BACKEND_DIR
                / "app"
                / "main.py"
            ).read_text(
                encoding="utf-8"
            ).splitlines()
        )
        self.assertLessEqual(line_count, 2200)


if __name__ == "__main__":
    unittest.main()
