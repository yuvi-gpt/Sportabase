from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.routes import inbox_history_auto_shadow_admin
from app.services import analysis_cache
from app.services import article_rules
from app.services import browser_capture_inbox
from app.services import inbox_auto_shadow_orchestration
from app.services import inbox_history_auto_shadow_orchestration as runtime
from app.services import live_merit_release


ANALYSIS_VERSION = "article-test-v1"
SCORING_VERSION = "merit-test-v1"
ANCHOR_ID = "bci_anchor"
CANONICAL_URL = "https://example.com/story"
TITLE = "Arsenal complete a transfer"
BODY = "Arsenal have completed a transfer after talks with the player."


def content_hash():
    return analysis_cache.analysis_content_hash(
        TITLE + "\n" + BODY,
        clean_html=article_rules.clean_html,
    )


def loaded_capture(
    *,
    record_id=ANCHOR_ID,
    platform="web",
    surface="article",
    title=TITLE,
    body=BODY,
    canonical_url=CANONICAL_URL,
):
    return {
        "version": browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION,
        "capture_record_id": record_id,
        "capture": {
            "version": "browser-capture-v1",
            "source_url": canonical_url,
            "observed_at": "2026-08-17T00:00:00Z",
            "extraction_method": "browser_dom+article_extractor",
            "payload": {
                "platform": platform,
                "surface": surface,
                "container_kind": "article",
                "canonical_url": canonical_url,
                "title": title,
                "body": body,
            },
            "actor": {},
        },
        "canonical_url": canonical_url,
        "platform": platform,
        "platform_surface": surface,
        "observed_at": "2026-08-17T00:00:00Z",
        "receive_count": 1,
        "policy": {
            "record_is_untrusted": True,
            "integrity_rechecked_on_load": True,
            "load_is_read_only": True,
            "affects_live_merit": False,
        },
    }


def valid_auto_result(anchor_id=ANCHOR_ID):
    return {
        "version": inbox_auto_shadow_orchestration.MULTIMODAL_INBOX_AUTO_SHADOW_VERSION,
        "status": "completed_shadow",
        "claim_id": "claim_1",
        "anchor_capture_record_id": anchor_id,
        "selected_candidate_capture_record_id": "bci_peer",
        "selected_subject_entity_id": "entity_1",
        "automatic_selection": {
            "eligible_count": 1,
        },
        "orchestration": {},
        "policy": {
            "automatic_selection_is_candidate_routing_only": True,
            "automatic_selection_requires_exactly_one_eligible_candidate": True,
            "eligible_candidate_requires_exactly_one_shared_entity": True,
            "candidate_score_is_not_a_truth_confidence": True,
            "selected_subject_is_not_verified_by_auto_selection": True,
            "downstream_candidate_gate_revalidates_selection": True,
            "downstream_exact_common_claim_required": True,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class HistoryDb:
    def __init__(self):
        temporary = tempfile.NamedTemporaryFile(
            suffix=".sqlite3",
            delete=False,
        )
        temporary.close()
        self.path = Path(temporary.name)
        self._initialize()

    def close(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def connect(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        conn = self.connect()
        try:
            conn.executescript(
                """
                CREATE TABLE media_items (
                  id TEXT,
                  canonical_url TEXT,
                  mode TEXT
                );

                CREATE TABLE analysis_snapshots (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  media_item_id TEXT,
                  analyzed_at TEXT,
                  mode TEXT,
                  analysis_version TEXT,
                  scoring_version TEXT,
                  content_hash TEXT,
                  context_hash TEXT,
                  merit_score REAL,
                  score_calculation_json TEXT,
                  response_json TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def add_media(
        self,
        *,
        media_id="media_1",
        canonical_url=CANONICAL_URL,
        mode="article",
    ):
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO media_items VALUES (?, ?, ?)",
                (media_id, canonical_url, mode),
            )
            conn.commit()
        finally:
            conn.close()

    def add_snapshot(
        self,
        *,
        media_id="media_1",
        analyzed_at="2026-08-17T01:00:00Z",
        context_hash="ctx_1",
        legacy_total=72,
        live_total=None,
        applied=False,
        release_status=None,
        analysis_version=ANALYSIS_VERSION,
        scoring_version=SCORING_VERSION,
        snapshot_content_hash=None,
        snapshot_merit=None,
        response_merit=None,
        release_version=None,
        score_calculation=None,
        release_patch=None,
        response_patch=None,
    ):
        if live_total is None:
            live_total = legacy_total

        if snapshot_merit is None:
            snapshot_merit = live_total

        if response_merit is None:
            response_merit = live_total

        if release_status is None:
            release_status = (
                "applied"
                if applied
                else "legacy_fallback"
            )

        if release_version is None:
            release_version = (
                live_merit_release
                .LIVE_MERIT_RELEASE_RUNTIME_VERSION
            )

        release = {
            "version": release_version,
            "status": release_status,
            "score_effect_applied": applied,
            "legacy_total": legacy_total,
            "live_total": live_total,
        }

        if release_patch:
            release.update(release_patch)

        response = {
            "merit_score": response_merit,
            "debug": {
                "live_merit_release": release,
            },
        }

        if response_patch:
            response.update(response_patch)

        if score_calculation is None:
            score_calculation = (
                {
                    "legacy_total_before_certified_corroboration": legacy_total,
                    "final_total": live_total,
                }
                if applied
                else {}
            )

        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO analysis_snapshots (
                  media_item_id,
                  analyzed_at,
                  mode,
                  analysis_version,
                  scoring_version,
                  content_hash,
                  context_hash,
                  merit_score,
                  score_calculation_json,
                  response_json
                ) VALUES (?, ?, 'article', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_id,
                    analyzed_at,
                    analysis_version,
                    scoring_version,
                    snapshot_content_hash or content_hash(),
                    context_hash,
                    snapshot_merit,
                    json.dumps(score_calculation),
                    json.dumps(response),
                ),
            )
            conn.commit()
        finally:
            conn.close()


class HistoryAutoShadowTests(unittest.TestCase):
    def setUp(self):
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot()

    def tearDown(self):
        self.db.close()

    def execute(self, **overrides):
        captured = {}

        def loader(**kwargs):
            return loaded_capture(
                record_id=kwargs["capture_record_id"]
            )

        def auto_runner(**kwargs):
            captured.update(kwargs)
            return valid_auto_result(
                kwargs["anchor_capture_record_id"]
            )

        values = {
            "anchor_capture_record_id": ANCHOR_ID,
            "analysis_version": ANALYSIS_VERSION,
            "scoring_version": SCORING_VERSION,
            "target_claim_id": "",
            "scan_limit": 100,
            "max_candidates": 12,
            "connection_factory": self.db.connect,
            "gemini_client": object(),
            "gemini_client_key": "client-a",
            "gemini_generator": lambda **_: None,
            "capture_loader": loader,
            "auto_shadow_runner": auto_runner,
        }
        values.update(overrides)
        result = runtime.execute_multimodal_inbox_history_auto_shadow(
            **values
        )
        return result, captured

    def test_success_version(self):
        result, _ = self.execute()
        self.assertEqual(
            result["version"],
            runtime.MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION,
        )

    def test_success_status(self):
        result, _ = self.execute()
        self.assertEqual(result["status"], "completed_shadow")

    def test_success_claim_id(self):
        result, _ = self.execute()
        self.assertEqual(result["claim_id"], "claim_1")

    def test_success_anchor_scope(self):
        result, _ = self.execute()
        self.assertEqual(result["anchor_capture_record_id"], ANCHOR_ID)

    def test_success_selected_candidate(self):
        result, _ = self.execute()
        self.assertEqual(
            result["selected_candidate_capture_record_id"],
            "bci_peer",
        )

    def test_success_selected_subject(self):
        result, _ = self.execute()
        self.assertEqual(
            result["selected_subject_entity_id"],
            "entity_1",
        )

    def test_success_recovers_legacy_total(self):
        result, _ = self.execute()
        self.assertEqual(
            result["baseline_resolution"]["legacy_total"],
            72,
        )

    def test_success_passes_minimal_legacy_score(self):
        _, captured = self.execute()
        self.assertEqual(captured["legacy_score"], {"total": 72})

    def test_success_passes_target_claim(self):
        _, captured = self.execute(target_claim_id="target_1")
        self.assertEqual(captured["target_claim_id"], "target_1")

    def test_success_passes_limits(self):
        _, captured = self.execute(scan_limit=44, max_candidates=7)
        self.assertEqual(captured["scan_limit"], 44)
        self.assertEqual(captured["max_candidates"], 7)

    def test_success_passes_connection_factory(self):
        _, captured = self.execute()
        self.assertIs(captured["connection_factory"].__self__, self.db)

    def test_success_passes_gemini_client(self):
        client = object()
        _, captured = self.execute(gemini_client=client)
        self.assertIs(captured["gemini_client"], client)

    def test_success_normalizes_empty_client_key(self):
        _, captured = self.execute(gemini_client_key="   ")
        self.assertEqual(captured["gemini_client_key"], "anonymous")

    def test_success_baseline_provenance_versions(self):
        result, _ = self.execute()
        baseline = result["baseline_resolution"]
        self.assertEqual(baseline["analysis_version"], ANALYSIS_VERSION)
        self.assertEqual(baseline["scoring_version"], SCORING_VERSION)

    def test_success_baseline_exact_content_hash(self):
        result, _ = self.execute()
        self.assertEqual(
            result["baseline_resolution"]["content_hash"],
            content_hash(),
        )

    def test_success_baseline_exact_url(self):
        result, _ = self.execute()
        self.assertEqual(
            result["baseline_resolution"]["canonical_url"],
            CANONICAL_URL,
        )

    def test_success_policy_blocks_live_effect(self):
        result, _ = self.execute()
        self.assertFalse(result["policy"]["affects_live_merit"])
        self.assertFalse(result["policy"]["score_effect_applied"])

    def test_success_policy_caller_cannot_supply_score(self):
        result, _ = self.execute()
        self.assertTrue(
            result["policy"]["caller_cannot_supply_legacy_score"]
        )

    def test_applied_live_score_recovers_pre_live_total(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(
            legacy_total=72,
            live_total=78,
            applied=True,
        )
        result, captured = self.execute()
        self.assertEqual(captured["legacy_score"], {"total": 72})
        self.assertEqual(
            result["baseline_resolution"]["selected_snapshot_live_total"],
            78.0,
        )

    def test_multiple_context_snapshots_same_legacy_are_allowed(self):
        self.db.add_snapshot(
            context_hash="ctx_2",
            analyzed_at="2026-08-17T02:00:00Z",
            legacy_total=72,
        )
        result, _ = self.execute()
        self.assertEqual(
            result["baseline_resolution"]["matching_snapshot_count"],
            2,
        )

    def test_multiple_context_snapshots_disagree_fail_closed(self):
        self.db.add_snapshot(
            context_hash="ctx_2",
            analyzed_at="2026-08-17T02:00:00Z",
            legacy_total=73,
        )
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_empty_anchor_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(anchor_capture_record_id="")

    def test_long_anchor_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(anchor_capture_record_id="x" * 257)

    def test_empty_analysis_version_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(analysis_version="")

    def test_empty_scoring_version_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(scoring_version="")

    def test_boolean_scan_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(scan_limit=True)

    def test_low_scan_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(scan_limit=0)

    def test_high_scan_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(scan_limit=501)

    def test_boolean_candidate_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(max_candidates=False)

    def test_low_candidate_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(max_candidates=0)

    def test_high_candidate_limit_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(max_candidates=51)

    def test_missing_gemini_client_rejected_before_baseline(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowProviderUnavailable
        ):
            self.execute(gemini_client=None)

    def test_missing_gemini_generator_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowProviderUnavailable
        ):
            self.execute(gemini_generator=None)

    def test_loader_input_error_maps(self):
        def loader(**_):
            raise browser_capture_inbox.BrowserCaptureInboxInputError("bad")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(capture_loader=loader)

    def test_loader_not_found_maps(self):
        def loader(**_):
            raise browser_capture_inbox.BrowserCaptureInboxNotFoundError("bad")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(capture_loader=loader)

    def test_loader_persistence_maps(self):
        def loader(**_):
            raise browser_capture_inbox.BrowserCaptureInboxPersistenceError("bad")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowLookupError
        ):
            self.execute(capture_loader=loader)

    def test_loader_integrity_maps(self):
        def loader(**_):
            raise browser_capture_inbox.BrowserCaptureInboxIntegrityError("bad")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=loader)

    def test_loader_non_mapping_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: [])

    def test_loader_version_mismatch_rejected(self):
        value = loaded_capture()
        value["version"] = "wrong"
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_loader_scope_mismatch_rejected(self):
        value = loaded_capture(record_id="other")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_loader_missing_policy_rejected(self):
        value = loaded_capture()
        value.pop("policy")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_loader_trust_boundary_rejected(self):
        value = loaded_capture()
        value["policy"]["record_is_untrusted"] = False
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_loader_integrity_boundary_rejected(self):
        value = loaded_capture()
        value["policy"]["integrity_rechecked_on_load"] = False
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_loader_live_effect_rejected(self):
        value = loaded_capture()
        value["policy"]["affects_live_merit"] = True
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_non_web_anchor_fails_closed(self):
        value = loaded_capture(platform="youtube", surface="video")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_non_article_surface_fails_closed(self):
        value = loaded_capture(platform="web", surface="post")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_payload_scope_mismatch_rejected(self):
        value = loaded_capture()
        value["capture"]["payload"]["platform"] = "youtube"
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_missing_title_fails_closed(self):
        value = loaded_capture(title="")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_missing_body_fails_closed(self):
        value = loaded_capture(body="")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(capture_loader=lambda **_: value)

    def test_empty_normalized_url_fails_closed(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute(url_normalizer=lambda _: "")

    def test_content_hash_failure_is_integrity_error(self):
        def fail(*_, **__):
            raise ValueError("hash")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(content_hash_resolver=fail)

    def test_empty_content_hash_is_integrity_error(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute(content_hash_resolver=lambda *_, **__: "")

    def test_missing_connection_factory_rejected(self):
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowInputError
        ):
            self.execute(connection_factory=None)

    def test_connection_factory_failure_maps_lookup(self):
        def fail():
            raise sqlite3.OperationalError("down")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowLookupError
        ):
            self.execute(connection_factory=fail)

    def test_no_media_item_fails_closed(self):
        self.db.close()
        self.db = HistoryDb()
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_duplicate_media_identity_is_integrity_error(self):
        self.db.add_media(media_id="media_2")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_non_article_media_fails_closed(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media(mode="video")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_no_exact_snapshot_fails_closed(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_old_analysis_version_not_used(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(analysis_version="old")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_old_scoring_version_not_used(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(scoring_version="old")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_different_content_hash_not_used(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(snapshot_content_hash="different")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ):
            self.execute()

    def test_invalid_response_json_rejected(self):
        snapshot = {
            "response_json": "{",
            "merit_score": 70,
            "score_calculation_json": "{}",
        }
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            runtime._snapshot_legacy_total(snapshot)

    def test_missing_response_debug_rejected(self):
        snapshot = {
            "response_json": json.dumps({"merit_score": 70}),
            "merit_score": 70,
            "score_calculation_json": "{}",
        }
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            runtime._snapshot_legacy_total(snapshot)

    def test_missing_release_metadata_rejected(self):
        snapshot = {
            "response_json": json.dumps({"merit_score": 70, "debug": {}}),
            "merit_score": 70,
            "score_calculation_json": "{}",
        }
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            runtime._snapshot_legacy_total(snapshot)

    def test_release_version_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(release_version="wrong")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_boolean_legacy_total_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(legacy_total=True)
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_legacy_total_out_of_range_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(legacy_total=101)
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_non_boolean_effect_flag_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(release_patch={"score_effect_applied": "false"})
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_applied_status_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(applied=True, release_status="legacy_fallback")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_fallback_status_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(applied=False, release_status="applied")
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_fallback_live_total_change_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(legacy_total=70, live_total=71, applied=False)
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_snapshot_total_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(snapshot_merit=71)
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_response_total_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(response_merit=71)
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_applied_calculation_legacy_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(
            applied=True,
            legacy_total=70,
            live_total=76,
            score_calculation={
                "legacy_total_before_certified_corroboration": 69,
                "final_total": 76,
            },
        )
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_applied_calculation_final_mismatch_rejected(self):
        self.db.close()
        self.db = HistoryDb()
        self.db.add_media()
        self.db.add_snapshot(
            applied=True,
            legacy_total=70,
            live_total=76,
            score_calculation={
                "legacy_total_before_certified_corroboration": 70,
                "final_total": 75,
            },
        )
        with self.assertRaises(
            runtime.MultimodalInboxHistoryAutoShadowIntegrityError
        ):
            self.execute()

    def test_auto_input_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowInputError("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowInputError):
            self.execute(auto_shadow_runner=runner)

    def test_auto_discovery_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowDiscoveryError("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowExecutionError):
            self.execute(auto_shadow_runner=runner)

    def test_auto_selection_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowSelectionError("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowExecutionError):
            self.execute(auto_shadow_runner=runner)

    def test_auto_provider_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowProviderUnavailable("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowProviderUnavailable):
            self.execute(auto_shadow_runner=runner)

    def test_auto_execution_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowExecutionError("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowExecutionError):
            self.execute(auto_shadow_runner=runner)

    def test_auto_integrity_error_maps(self):
        def runner(**_):
            raise inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowIntegrityError("x")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=runner)

    def test_auto_result_non_mapping_rejected(self):
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: [])

    def test_auto_result_version_rejected(self):
        value = valid_auto_result()
        value["version"] = "wrong"
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_status_rejected(self):
        value = valid_auto_result()
        value["status"] = "nope"
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_anchor_rejected(self):
        value = valid_auto_result("other")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_claim_required(self):
        value = valid_auto_result()
        value["claim_id"] = ""
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_policy_required(self):
        value = valid_auto_result()
        value.pop("policy")
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_required_true_enforced(self):
        value = valid_auto_result()
        value["policy"]["downstream_exact_common_claim_required"] = False
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)

    def test_auto_result_forbidden_live_effect_enforced(self):
        value = valid_auto_result()
        value["policy"]["affects_live_merit"] = True
        with self.assertRaises(runtime.MultimodalInboxHistoryAutoShadowIntegrityError):
            self.execute(auto_shadow_runner=lambda **_: value)


class HistoryAutoShadowRouteTests(unittest.TestCase):
    def build_app(
        self,
        *,
        enabled=True,
        require_admin=lambda _: None,
        gemini_client_factory=lambda: object(),
        request_client_key_resolver=lambda _: "client-route",
        gemini_generator=lambda **_: None,
    ):
        app = FastAPI()
        app.include_router(
            inbox_history_auto_shadow_admin.build_router(
                enabled=enabled,
                require_admin=require_admin,
                connection_factory=lambda: None,
                analysis_version=ANALYSIS_VERSION,
                scoring_version=SCORING_VERSION,
                gemini_client_factory=gemini_client_factory,
                request_client_key_resolver=request_client_key_resolver,
                gemini_generator=gemini_generator,
            )
        )
        return app

    def payload(self):
        return {
            "anchor_capture_record_id": ANCHOR_ID,
            "target_claim_id": "",
            "scan_limit": 100,
            "max_candidates": 12,
        }

    def test_request_model_forbids_legacy_score(self):
        with self.assertRaises(ValidationError):
            inbox_history_auto_shadow_admin.MultimodalInboxHistoryAutoShadowRequest(
                **self.payload(),
                legacy_score={"total": 50},
            )

    def test_request_model_forbids_candidate_id(self):
        with self.assertRaises(ValidationError):
            inbox_history_auto_shadow_admin.MultimodalInboxHistoryAutoShadowRequest(
                **self.payload(),
                candidate_capture_record_id="peer",
            )

    def test_request_model_forbids_subject_id(self):
        with self.assertRaises(ValidationError):
            inbox_history_auto_shadow_admin.MultimodalInboxHistoryAutoShadowRequest(
                **self.payload(),
                subject_entity_id="entity",
            )

    def test_route_path_exists(self):
        app = self.build_app()
        paths = {route.path for route in app.routes}
        self.assertIn(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            paths,
        )

    def test_disabled_route_is_404(self):
        client = TestClient(self.build_app(enabled=False))
        response = client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 404)

    def test_disabled_route_checks_flag_before_admin(self):
        calls = []
        def admin(_):
            calls.append(True)
        client = TestClient(
            self.build_app(enabled=False, require_admin=admin)
        )
        client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(calls, [])

    def test_enabled_route_requires_admin(self):
        def admin(_):
            raise HTTPExceptionForTest(401)
        # Use a normal FastAPI HTTPException without importing it into product code.
        from fastapi import HTTPException
        def real_admin(_):
            raise HTTPException(status_code=401, detail="admin")
        client = TestClient(
            self.build_app(require_admin=real_admin)
        )
        response = client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_client_factory_is_503(self):
        client = TestClient(
            self.build_app(gemini_client_factory=None)
        )
        response = client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 503)

    def test_none_client_is_503(self):
        client = TestClient(
            self.build_app(gemini_client_factory=lambda: None)
        )
        response = client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 503)

    def test_missing_generator_is_503(self):
        client = TestClient(
            self.build_app(gemini_generator=None)
        )
        response = client.post(
            "/admin/intelligence/multimodal-inbox-auto-shadow-history",
            json=self.payload(),
        )
        self.assertEqual(response.status_code, 503)

    def test_route_injects_current_versions(self):
        captured = {}
        def runner(**kwargs):
            captured.update(kwargs)
            result = valid_auto_result()
            return {
                "version": runtime.MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION,
                "status": "completed_shadow",
                "claim_id": "claim_1",
                "anchor_capture_record_id": ANCHOR_ID,
                "selected_candidate_capture_record_id": "bci_peer",
                "selected_subject_entity_id": "entity_1",
                "baseline_resolution": {},
                "automatic_selection": {},
                "orchestration": result,
                "policy": {},
            }
        with patch.object(
            inbox_history_auto_shadow_admin
            .inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=runner,
        ):
            client = TestClient(self.build_app())
            response = client.post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["analysis_version"], ANALYSIS_VERSION)
        self.assertEqual(captured["scoring_version"], SCORING_VERSION)

    def test_route_maps_input_error_422(self):
        error = runtime.MultimodalInboxHistoryAutoShadowInputError("x")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 422)

    def test_route_maps_baseline_unavailable_409(self):
        error = runtime.MultimodalInboxHistoryAutoShadowBaselineUnavailable("x")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 409)

    def test_route_maps_lookup_error_503(self):
        error = runtime.MultimodalInboxHistoryAutoShadowLookupError("x")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 503)

    def test_route_maps_provider_error_503(self):
        error = runtime.MultimodalInboxHistoryAutoShadowProviderUnavailable("x")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 503)

    def test_route_maps_execution_error_409(self):
        error = runtime.MultimodalInboxHistoryAutoShadowExecutionError("x")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 409)

    def test_route_maps_integrity_error_500_generically(self):
        error = runtime.MultimodalInboxHistoryAutoShadowIntegrityError("secret")
        with patch.object(
            inbox_history_auto_shadow_admin.inbox_history_auto_shadow_orchestration,
            "execute_multimodal_inbox_history_auto_shadow",
            side_effect=error,
        ):
            response = TestClient(self.build_app()).post(
                "/admin/intelligence/multimodal-inbox-auto-shadow-history",
                json=self.payload(),
            )
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)


class HTTPExceptionForTest(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
