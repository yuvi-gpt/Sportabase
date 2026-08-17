from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest import mock


BACKEND_DIR = Path(__file__).resolve().parents[1]


from app.services import browser_capture_inbox
from app.services import inbox_candidate_discovery
from app.services import inbox_candidate_shadow_orchestration
from app.services import inbox_story_cluster_orchestration as cluster
from app.services import multimodal_inbox_shadow_orchestration
from app.services import multimodal_shadow_api
from app.services import multimodal_shadow_orchestration


ANCHOR = "anchor-1"
ENTITY = "entity-arsenal"


def loaded_anchor(
    *,
    platform="x",
    surface="post",
):
    return {
        "version": browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION,
        "capture_record_id": ANCHOR,
        "capture": {
            "version": "browser-capture-v1",
            "source_url": "https://x.com/a/status/1",
            "observed_at": "2026-08-17T10:00:00Z",
            "extraction_method": "browser_dom",
            "payload": {
                "platform": platform,
                "surface": surface,
                "container_kind": surface,
                "canonical_url": "https://x.com/a/status/1",
                "body": "Arsenal transfer update",
            },
            "actor": {"handle": "a"},
        },
        "canonical_url": "https://x.com/a/status/1",
        "platform": platform,
        "platform_surface": surface,
        "observed_at": "2026-08-17T10:00:00Z",
        "policy": {
            "record_is_untrusted": True,
            "integrity_rechecked_on_load": True,
            "load_is_read_only": True,
            "affects_live_merit": False,
        },
    }


def candidate(
    candidate_id,
    *,
    entity_id=ENTITY,
    score=0.8,
    identical=False,
    shared_ids=None,
):
    if shared_ids is None:
        shared_ids = [entity_id]

    return {
        "capture_record_id": candidate_id,
        "candidate_score": score,
        "candidate_reasons": [
            "shared_text_tokens",
            "shared_exact_entity_candidates",
        ],
        "signals": {
            "shared_entity_ids": list(shared_ids),
            "identical_normalized_content": identical,
        },
        "policy": {
            "candidate_only": True,
            "same_story_not_established": True,
            "same_claim_not_established": True,
            "subject_not_verified": True,
            "independence_not_established": True,
            "corroboration_not_established": True,
            "affects_live_merit": False,
        },
    }


def discovery(*members, status="candidates_available"):
    return {
        "version": (
            inbox_candidate_discovery
            .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        ),
        "status": status,
        "anchor_capture_record_id": ANCHOR,
        "pair_candidates": list(members),
        "policy": {
            "read_only_discovery": True,
            "inbox_records_remain_untrusted": True,
            "anchor_capture_text_is_not_a_verified_claim": True,
            "entity_matching_is_exact_alias_or_canonical_name_only": True,
            "entity_candidates_do_not_verify_subject": True,
            "deterministic_score_is_ranking_only": True,
            "semantic_same_claim_is_candidate_only": True,
            "semantic_stance_does_not_establish_truth": True,
            "semantic_dependency_does_not_establish_independence": True,
            "candidate_discovery_does_not_establish_corroboration": True,
            "creates_story": False,
            "creates_claim": False,
            "creates_observation": False,
            "creates_evidence": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


def selection(*members, entity_id=ENTITY):
    return {
        "version": cluster.MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION,
        "status": "cluster_selected",
        "anchor_capture_record_id": ANCHOR,
        "subject_entity_id": entity_id,
        "members": list(members),
        "member_count": len(members),
        "rejected_candidates": [],
        "rejected_candidate_count": 0,
        "policy": {
            "cluster_is_routing_candidate_only": True,
            "cluster_selection_is_read_only": True,
            "cluster_requires_one_unambiguous_subject_partition": True,
            "cluster_member_requires_exactly_one_shared_entity": True,
            "candidate_score_is_ranking_only": True,
            "same_story_not_established_by_cluster": True,
            "same_claim_not_established_by_cluster": True,
            "subject_not_verified_by_cluster": True,
            "independence_not_established_by_cluster": True,
            "corroboration_not_established_by_cluster": True,
            "creates_story": False,
            "affects_live_merit": False,
        },
    }


def member_shadow(
    candidate_id,
    *,
    claim_id="claim-1",
    baseline_mode="not_applicable",
):
    merit = baseline_mode == "legacy_merit"
    return {
        "version": (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": claim_id,
        "anchor_capture_record_id": ANCHOR,
        "candidate_capture_record_id": candidate_id,
        "subject_entity_id": ENTITY,
        "policy": {
            "candidate_must_be_currently_discovered": True,
            "discovery_gate_is_read_only": True,
            "subject_entity_must_be_shared_exact_candidate": True,
            "subject_descriptor_loaded_server_side": True,
            "downstream_exact_common_claim_required": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
            "live_merit_shadow_only": True,
            "merit_baseline_mode": baseline_mode,
            "merit_baseline_available": merit,
            "merit_shadow_evaluated": merit,
            "synthetic_merit_baseline_used": False,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class StoryClusterSelectionTests(unittest.TestCase):
    def run_selection(self, result):
        return cluster.select_multisource_inbox_cluster(
            anchor_capture_record_id=ANCHOR,
            scan_limit=100,
            max_candidates=12,
            connection_factory=lambda: object(),
            discovery_runner=lambda **_kwargs: copy.deepcopy(result),
        )

    def test_versions_are_v1(self):
        self.assertEqual(
            cluster.MULTIMODAL_INBOX_STORY_CLUSTER_VERSION,
            "multimodal-inbox-story-cluster-v1",
        )
        self.assertEqual(
            cluster.MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION,
            "multimodal-inbox-cluster-selection-v1",
        )

    def test_requires_anchor(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterInputError):
            cluster.select_multisource_inbox_cluster(
                anchor_capture_record_id="",
                connection_factory=lambda: object(),
            )

    def test_bounds_are_enforced(self):
        for field, value in (
            ("scan_limit", 0),
            ("scan_limit", 501),
            ("max_candidates", 0),
            ("max_candidates", 51),
        ):
            kwargs = {
                "anchor_capture_record_id": ANCHOR,
                "connection_factory": lambda: object(),
                field: value,
            }
            with self.subTest(field=field, value=value):
                with self.assertRaises(cluster.MultimodalInboxStoryClusterInputError):
                    cluster.select_multisource_inbox_cluster(**kwargs)

    def test_discovery_errors_are_typed(self):
        cases = (
            (
                inbox_candidate_discovery.InboxCandidateDiscoveryInputError("bad"),
                cluster.MultimodalInboxStoryClusterInputError,
            ),
            (
                inbox_candidate_discovery.InboxCandidateDiscoveryNotFoundError("missing"),
                cluster.MultimodalInboxStoryClusterNotReady,
            ),
            (
                inbox_candidate_discovery.InboxCandidateDiscoveryLookupError("db"),
                cluster.MultimodalInboxStoryClusterLookupError,
            ),
            (
                inbox_candidate_discovery.InboxCandidateDiscoveryIntegrityError("unsafe"),
                cluster.MultimodalInboxStoryClusterIntegrityError,
            ),
        )

        for error, expected in cases:
            def runner(**_kwargs):
                raise error

            with self.subTest(error=type(error).__name__):
                with self.assertRaises(expected):
                    cluster.select_multisource_inbox_cluster(
                        anchor_capture_record_id=ANCHOR,
                        connection_factory=lambda: object(),
                        discovery_runner=runner,
                    )

    def test_no_candidates_is_not_ready(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterNotReady):
            self.run_selection(discovery(status="no_candidates"))

    def test_discovery_version_and_anchor_are_strict(self):
        for field, value in (
            ("version", "wrong"),
            ("anchor_capture_record_id", "other"),
            ("status", "weird"),
        ):
            value_map = discovery(candidate("c1"))
            value_map[field] = value
            with self.subTest(field=field):
                with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
                    self.run_selection(value_map)

    def test_discovery_policy_is_strict(self):
        value = discovery(candidate("c1"))
        value["policy"]["read_only_discovery"] = False
        with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
            self.run_selection(value)

    def test_candidate_policy_is_strict(self):
        item = candidate("c1")
        item["policy"]["same_story_not_established"] = False
        with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
            self.run_selection(discovery(item))

    def test_candidate_score_is_strict(self):
        for value in (True, "abc", -0.1, 1.1, float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
                    self.run_selection(discovery(candidate("c1", score=value)))

    def test_duplicate_candidate_ids_fail(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
            self.run_selection(
                discovery(
                    candidate("same", score=0.9),
                    candidate("same", score=0.8),
                )
            )

    def test_zero_shared_entity_is_rejected(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterNotReady):
            self.run_selection(
                discovery(candidate("c1", shared_ids=[]))
            )

    def test_multiple_shared_entities_are_rejected(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterNotReady):
            self.run_selection(
                discovery(
                    candidate(
                        "c1",
                        shared_ids=["entity-a", "entity-b"],
                    )
                )
            )

    def test_multiple_members_same_subject_form_one_cluster(self):
        result = self.run_selection(
            discovery(
                candidate("c1", score=0.7),
                candidate("c2", score=0.9),
                candidate("c3", score=0.8),
            )
        )
        self.assertEqual(result["member_count"], 3)
        self.assertEqual(
            [row["capture_record_id"] for row in result["members"]],
            ["c2", "c3", "c1"],
        )

    def test_ties_are_deterministic_by_id(self):
        result = self.run_selection(
            discovery(
                candidate("c2", score=0.8),
                candidate("c1", score=0.8),
            )
        )
        self.assertEqual(
            [row["capture_record_id"] for row in result["members"]],
            ["c1", "c2"],
        )

    def test_multiple_subject_partitions_fail_closed(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterNotReady):
            self.run_selection(
                discovery(
                    candidate("c1", entity_id="entity-a"),
                    candidate("c2", entity_id="entity-b"),
                )
            )

    def test_identical_content_is_metadata_not_exclusion(self):
        result = self.run_selection(
            discovery(candidate("c1", identical=True))
        )
        self.assertTrue(
            result["members"][0]["identical_normalized_content"]
        )

    def test_cluster_policy_is_routing_only(self):
        result = self.run_selection(
            discovery(candidate("c1"), candidate("c2"))
        )
        policy = result["policy"]
        self.assertTrue(policy["cluster_is_routing_candidate_only"])
        self.assertTrue(policy["cluster_selection_is_read_only"])
        self.assertTrue(policy["same_story_not_established_by_cluster"])
        self.assertTrue(policy["same_claim_not_established_by_cluster"])
        self.assertFalse(policy["creates_story"])
        self.assertFalse(policy["affects_live_merit"])


class StoryClusterExecutionTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def loader(self, **_kwargs):
        return loaded_anchor()

    def selection_runner(self, **_kwargs):
        return selection(
            {
                "capture_record_id": "c1",
                "candidate_score": 0.9,
                "candidate_reasons": [],
            },
            {
                "capture_record_id": "c2",
                "candidate_score": 0.8,
                "candidate_reasons": [],
            },
        )

    def member_runner(self, **kwargs):
        self.calls.append(kwargs)
        return member_shadow(
            kwargs["candidate_capture_record_id"],
            claim_id="claim-1",
            baseline_mode=kwargs["merit_baseline_mode"],
        )

    def execute(self, **overrides):
        kwargs = {
            "anchor_capture_record_id": ANCHOR,
            "analysis_version": "analysis-current",
            "scoring_version": "score-current",
            "connection_factory": lambda: object(),
            "gemini_client": object(),
            "gemini_client_key": "client-1",
            "gemini_generator": lambda **_kwargs: None,
            "capture_loader": self.loader,
            "selection_runner": self.selection_runner,
            "candidate_shadow_runner": self.member_runner,
        }
        kwargs.update(overrides)
        return cluster.execute_multisource_inbox_story_cluster_shadow(
            **kwargs
        )

    def test_non_article_runs_all_cluster_members(self):
        result = self.execute()
        self.assertEqual(result["execution_mode"], "non_article_no_merit")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(
            [call["candidate_capture_record_id"] for call in self.calls],
            ["c1", "c2"],
        )

    def test_non_article_never_receives_merit_score(self):
        self.execute()
        for call in self.calls:
            self.assertIsNone(call["legacy_score"])
            self.assertEqual(call["merit_baseline_mode"], "not_applicable")

    def test_article_uses_persisted_history_baseline(self):
        article = loaded_anchor(platform="web", surface="article")
        article["capture"]["source_url"] = "https://example.com/a"
        article["capture"]["payload"]["canonical_url"] = "https://example.com/a"
        article["capture"]["payload"]["title"] = "Title"
        article["capture"]["payload"]["body"] = "Body"
        article["canonical_url"] = "https://example.com/a"

        with mock.patch.object(
            cluster.inbox_history_auto_shadow_orchestration,
            "_article_descriptor",
            return_value={"canonical_url": "https://example.com/a"},
        ), mock.patch.object(
            cluster.inbox_history_auto_shadow_orchestration,
            "_resolve_baseline",
            return_value={
                "legacy_score": {"total": 64.0},
                "baseline": {"legacy_total": 64.0},
            },
        ):
            result = self.execute(
                capture_loader=lambda **_kwargs: article,
            )

        self.assertEqual(result["execution_mode"], "article_history_merit")
        for call in self.calls:
            self.assertEqual(call["legacy_score"], {"total": 64.0})
            self.assertEqual(call["merit_baseline_mode"], "legacy_merit")

    def test_missing_provider_and_generator_fail(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterProviderUnavailable):
            self.execute(gemini_client=None)
        with self.assertRaises(cluster.MultimodalInboxStoryClusterProviderUnavailable):
            self.execute(gemini_generator=None)

    def test_unsupported_anchor_fails(self):
        with self.assertRaises(cluster.MultimodalInboxStoryClusterInputError):
            self.execute(
                capture_loader=lambda **_kwargs: loaded_anchor(
                    platform="web",
                    surface="page",
                )
            )

    def test_target_claim_is_forwarded_to_every_member(self):
        self.execute(target_claim_id=" claim-9 ")
        self.assertEqual(
            [call["target_claim_id"] for call in self.calls],
            ["claim-9", "claim-9"],
        )

    def test_client_key_is_normalized(self):
        self.execute(gemini_client_key="  client-x  ")
        self.assertEqual(
            [call["gemini_client_key"] for call in self.calls],
            ["client-x", "client-x"],
        )

    def test_exact_claim_mismatch_rejects_only_that_member(self):
        def runner(**kwargs):
            if kwargs["candidate_capture_record_id"] == "c1":
                raise (
                    inbox_candidate_shadow_orchestration
                    .MultimodalInboxCandidateShadowClaimSelectionError(
                        "no common claim"
                    )
                )
            return member_shadow(
                "c2",
                claim_id="claim-2",
            )

        result = self.execute(candidate_shadow_runner=runner)
        self.assertEqual(
            result["selected_candidate_capture_record_ids"],
            ["c2"],
        )
        self.assertEqual(len(result["rejected_members"]), 1)
        self.assertEqual(
            result["rejected_members"][0]["reason"],
            "downstream_no_exact_common_claim",
        )

    def test_all_exact_claim_mismatches_are_not_ready(self):
        def runner(**_kwargs):
            raise (
                inbox_candidate_shadow_orchestration
                .MultimodalInboxCandidateShadowClaimSelectionError(
                    "no common claim"
                )
            )

        with self.assertRaises(cluster.MultimodalInboxStoryClusterNotReady):
            self.execute(candidate_shadow_runner=runner)

    def test_candidate_runtime_errors_are_typed(self):
        cases = (
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowDiscoveryError("race"),
                cluster.MultimodalInboxStoryClusterNotReady,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowBindingError("race"),
                cluster.MultimodalInboxStoryClusterNotReady,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowProviderUnavailable("provider"),
                cluster.MultimodalInboxStoryClusterProviderUnavailable,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowExecutionError("execution"),
                cluster.MultimodalInboxStoryClusterExecutionError,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowInputError("input"),
                cluster.MultimodalInboxStoryClusterInputError,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowIntegrityError("unsafe"),
                cluster.MultimodalInboxStoryClusterIntegrityError,
            ),
        )

        for error, expected in cases:
            def runner(**_kwargs):
                raise error

            with self.subTest(error=type(error).__name__):
                with self.assertRaises(expected):
                    self.execute(candidate_shadow_runner=runner)

    def test_member_scope_is_revalidated(self):
        bad = member_shadow("c1")
        bad["candidate_capture_record_id"] = "other"
        with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
            self.execute(candidate_shadow_runner=lambda **_kwargs: bad)

    def test_member_baseline_mode_is_revalidated(self):
        bad = member_shadow("c1", baseline_mode="legacy_merit")
        with self.assertRaises(cluster.MultimodalInboxStoryClusterIntegrityError):
            self.execute(candidate_shadow_runner=lambda **_kwargs: bad)

    def test_multi_member_same_claim_forms_one_claim_group(self):
        result = self.execute()
        self.assertEqual(result["claim_id"], "claim-1")
        self.assertEqual(result["claim_ids"], ["claim-1"])
        self.assertEqual(len(result["claim_groups"]), 1)
        self.assertEqual(result["claim_groups"][0]["member_count"], 2)

    def test_multiple_exact_claims_are_grouped_without_inventing_primary(self):
        def runner(**kwargs):
            candidate_id = kwargs["candidate_capture_record_id"]
            return member_shadow(
                candidate_id,
                claim_id=(
                    "claim-b" if candidate_id == "c1" else "claim-a"
                ),
            )

        result = self.execute(candidate_shadow_runner=runner)
        self.assertEqual(result["claim_id"], "")
        self.assertEqual(result["claim_ids"], ["claim-a", "claim-b"])
        self.assertEqual(len(result["claim_groups"]), 2)

    def test_single_member_preserves_legacy_compatibility_fields(self):
        result = self.execute(
            selection_runner=lambda **_kwargs: selection(
                {
                    "capture_record_id": "only",
                    "candidate_score": 0.9,
                    "candidate_reasons": [],
                }
            ),
            candidate_shadow_runner=lambda **kwargs: member_shadow(
                kwargs["candidate_capture_record_id"]
            ),
        )
        self.assertEqual(
            result["selected_candidate_capture_record_id"],
            "only",
        )
        self.assertEqual(
            result["selected_candidate_capture_record_ids"],
            ["only"],
        )

    def test_multi_member_does_not_invent_single_selected_peer(self):
        result = self.execute()
        self.assertEqual(result["selected_candidate_capture_record_id"], "")
        self.assertEqual(
            result["selected_candidate_capture_record_ids"],
            ["c1", "c2"],
        )

    def test_cluster_policy_never_establishes_story_or_independence(self):
        policy = self.execute()["policy"]
        self.assertTrue(policy["same_story_not_established_by_cluster"])
        self.assertTrue(policy["cluster_does_not_write_story_records_directly"])
        self.assertTrue(policy["cluster_does_not_link_story_media_directly"])
        self.assertTrue(policy["cluster_level_independence_not_established"])
        self.assertFalse(policy["cluster_merit_aggregation_performed"])
        self.assertFalse(policy["affects_live_merit"])

    def test_non_article_policy_has_no_merit_baseline(self):
        policy = self.execute()["policy"]
        self.assertEqual(policy["merit_baseline_mode"], "not_applicable")
        self.assertFalse(policy["merit_baseline_available"])
        self.assertFalse(policy["merit_shadow_evaluated_per_completed_member"])
        self.assertFalse(policy["synthetic_merit_baseline_used"])

    def test_source_contains_no_direct_story_persistence_sql(self):
        source = Path(cluster.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "INSERT INTO intelligence_stories",
            "UPDATE intelligence_stories",
            "INSERT INTO story_media_links",
            "UPDATE story_media_links",
            "DELETE FROM intelligence_stories",
            "DELETE FROM story_media_links",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class ClaimSelectionPropagationContractTests(unittest.TestCase):
    def test_claim_selection_errors_remain_execution_subclasses(self):
        pairs = (
            (
                multimodal_shadow_api.MultimodalShadowApiClaimSelectionError,
                multimodal_shadow_api.MultimodalShadowApiExecutionError,
            ),
            (
                multimodal_shadow_orchestration.MultimodalShadowOrchestrationClaimSelectionError,
                multimodal_shadow_orchestration.MultimodalShadowOrchestrationExecutionError,
            ),
            (
                multimodal_inbox_shadow_orchestration.MultimodalInboxShadowClaimSelectionError,
                multimodal_inbox_shadow_orchestration.MultimodalInboxShadowExecutionError,
            ),
            (
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowClaimSelectionError,
                inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowExecutionError,
            ),
        )
        for child, parent in pairs:
            with self.subTest(child=child.__name__):
                self.assertTrue(issubclass(child, parent))

    def test_candidate_layer_has_specific_claim_selection_catch(self):
        source = Path(
            inbox_candidate_shadow_orchestration.__file__
        ).read_text(encoding="utf-8")
        self.assertIn(
            "MultimodalInboxShadowClaimSelectionError",
            source,
        )
        self.assertIn(
            "MultimodalInboxCandidateShadowClaimSelectionError",
            source,
        )


if __name__ == "__main__":
    unittest.main()
