from __future__ import annotations

import copy
import inspect
import sys
import unittest

from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis import observation_semantics as observation_semantics_analysis
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import browser_ingestion
from app.services import multimodal_adjudication_intake
from app.services import multimodal_adjudication_runtime
from app.services import multimodal_corroboration_runtime
from app.services import multimodal_intelligence_bridge
from app.services import multimodal_live_merit_shadow
from app.services import observation_semantics
from app.services import semantic_execution
from app.services import verified_persistence_execution
from app.services import multimodal_intelligence_runtime as runtime


CLAIM_ID = "claim-shared"
SUBJECT = "club|arsenal"
AS_OF = "2026-08-16T12:30:00+00:00"
RECORDED_AT = "2026-08-16T12:31:00+00:00"


class DummyWorkspace:
    def __init__(self):
        self.entered = False
        self.closed = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self.closed = True


def binding(side, *, source_verified=True, media_verified=True, media_id=None):
    return bridge_models.BridgeBindings(
        subject_key=SUBJECT,
        source_id=f"source-{side}",
        source_record_verified=source_verified,
        media_item_id=media_id or f"media-{side}",
        media_item_record_verified=media_verified,
    )


def make_item(side, *, item_id=None):
    return content.UnifiedContentItem(
        item_id=item_id or f"item-{side}",
        platform="web",
        container_kind="post",
        canonical_url=f"https://{side}.example/post",
        actor=content.ActorReference(
            platform_actor_id=f"actor-{side}",
            handle=f"@{side}",
        ),
        observed_at="2026-08-16T12:00:00+00:00",
        text_components=[
            content.TextComponent(
                component_id=f"text-{side}",
                role="body",
                text=f"{side} source confirms the same transfer agreement.",
                sequence_index=0,
            ),
        ],
    )


def initial_manifest(side, *, item_id=None):
    return artifact_models.ItemArtifactManifest(
        item_id=item_id or f"item-{side}"
    )


def semantic_manifest(side, *, artifact_id=None, item_id=None):
    return artifact_models.ItemArtifactManifest(
        item_id=item_id or f"item-{side}",
        artifacts=[
            artifact_models.ExtractionArtifact(
                artifact_id=artifact_id or f"artifact-{side}",
                artifact_kind="text_component",
                modality="text",
                source_item_ids=[item_id or f"item-{side}"],
                source_component_ids=[f"text-{side}"],
                content_hash=f"hash-{side}",
                payload={"text": f"{side} semantic source text"},
                provenance=artifact_models.ArtifactProvenance(
                    source_url=f"https://{side}.example/post",
                    observed_at="2026-08-16T12:00:00+00:00",
                    extraction_method="browser_test",
                ),
            ),
        ],
    )


def proposal(operation, *, deterministic_id="", ready=True):
    return bridge_models.PersistenceProposal(
        operation=operation,
        readiness="ready" if ready else "blocked",
        deterministic_id=deterministic_id,
        blocked_reasons=[] if ready else ["test_block"],
        kwargs={"test": True},
    )


def candidate(
    side,
    *,
    claim_id=CLAIM_ID,
    candidate_id=None,
    ready=True,
    source_artifact_id=None,
):
    return bridge_models.CandidateBridgeRecord(
        candidate_id=candidate_id or f"candidate-{side}",
        canonical_text="Arsenal and the counterparty have agreed the transfer.",
        interpretation_confidence=0.94,
        source_artifacts=[
            bridge_models.BridgeArtifactProvenance(
                artifact_id=source_artifact_id or f"artifact-{side}",
                artifact_kind="text_component",
                modality="text",
                content_hash=f"hash-{side}",
                source_item_ids=[f"item-{side}"],
                source_component_ids=[f"text-{side}"],
                source_url=f"https://{side}.example/post",
                observed_at="2026-08-16T12:00:00+00:00",
                extraction_method="browser_test",
            )
        ],
        claim=proposal(
            "upsert_intelligence_claim",
            deterministic_id=claim_id,
            ready=ready,
        ),
        evidence=proposal(
            "record_evidence",
            deterministic_id=f"evidence-{side}",
            ready=ready,
        ),
        claim_link=proposal(
            "record_claim_link",
            deterministic_id=f"link-{side}",
            ready=ready,
        ),
        source_observation=proposal(
            "record_source_observation",
            ready=ready,
        ),
        policy={
            "training_eligible": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    )


def plan(side, *, rows=None, subject=SUBJECT):
    return bridge_models.ItemIntelligenceBridgePlan(
        item_id=f"item-{side}",
        subject_key=subject,
        subject_resolution_status="explicit_binding",
        candidates=list(rows) if rows is not None else [candidate(side)],
        independence_status="unknown",
        policy={
            "bridge_runtime_version": (
                multimodal_intelligence_bridge
                .MULTIMODAL_INTELLIGENCE_BRIDGE_RUNTIME_VERSION
            ),
            "dry_run_only": True,
            "training_eligible": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    )


def semantic_assessment(claim_id, source_url, *, relevance="same_claim"):
    return {
        "version": (
            observation_semantics_analysis
            .CLAIM_OBSERVATION_SEMANTICS_VERSION
        ),
        "claim_id": claim_id,
        "source_url": source_url,
        "claim_relevance": relevance,
        "field_judgments": [],
        "policy": {
            "model_does_not_establish_truth": True,
            "model_does_not_establish_corroboration": True,
            "model_does_not_establish_independence": True,
            "observation_semantics_does_not_change_live_merit": True,
        },
    }


def semantic_wrapper(claim_id, source_url, *, status="assessed", assessment=None):
    return {
        "version": observation_semantics.OBSERVATION_SEMANTIC_GEMINI_VERSION,
        "status": status,
        "claim_id": claim_id,
        "source_url": source_url,
        "assessment": (
            semantic_assessment(claim_id, source_url)
            if assessment is None and status == "assessed"
            else assessment
        ),
    }


def intake_result(claim_id, media_id):
    return {
        "version": multimodal_adjudication_intake.MULTIMODAL_ADJUDICATION_INTAKE_VERSION,
        "status": "ready",
        "claim_id": claim_id,
        "media_item_id": media_id,
        "aligned_evidence_ids": [f"evidence-{media_id}"],
        "policy": {
            "multimodal_evidence_remains_unverified": True,
            "model_judgments_are_not_hard_references": True,
            "verified_authority_requires_database_records": True,
            "adjudication_not_performed": True,
            "adjudication_state_not_persisted": True,
            "explicit_persistence_scope_applied": True,
            "establishes_truth": False,
            "establishes_corroboration": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


def adjudication_result(claim_id, media_id):
    return {
        "version": multimodal_adjudication_runtime.MULTIMODAL_ADJUDICATION_RUNTIME_VERSION,
        "status": "persisted",
        "claim_id": claim_id,
        "media_item_id": media_id,
        "revision_id": f"revision-{media_id}",
        "adjudication": {},
        "revision": {"revision_id": f"revision-{media_id}"},
        "policy": {
            "multimodal_evidence_remains_unverified": True,
            "evidence_verification_unchanged": True,
            "establishes_truth": False,
            "establishes_corroboration": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


def corroboration_result(claim_id=CLAIM_ID):
    return {
        "version": multimodal_corroboration_runtime.MULTIMODAL_CORROBORATION_RUNTIME_VERSION,
        "status": "verified_direct_stakeholder_corroboration",
        "claim_id": claim_id,
        "corroboration_established": True,
        "independent_support_established": True,
        "contested": False,
        "corroboration_state": {},
        "policy": {
            "model_stance_materializes_historical_support_only": True,
            "support_edge_does_not_establish_truth": True,
            "support_edge_does_not_establish_independence": True,
            "establishes_truth": False,
            "live_merit_evaluated": False,
            "affects_live_merit": False,
        },
    }


def legacy_score(total=64.0):
    return {
        "total": total,
        "components": {"corroboration": 4.0},
        "label": "test",
    }


def shadow_result(claim_id=CLAIM_ID, *, score=None, adjustment=6.0):
    score = copy.deepcopy(score or legacy_score())
    return {
        "version": multimodal_live_merit_shadow.MULTIMODAL_LIVE_MERIT_SHADOW_VERSION,
        "status": "evaluated_shadow",
        "claim_id": claim_id,
        "live_score": score,
        "proposed_adjustment": adjustment,
        "proposed_shadow_total": min(100.0, float(score["total"]) + adjustment),
        "shadow_boost_eligible_under_overlay": adjustment == 6.0,
        "policy": {
            "shadow_only": True,
            "existing_merit_overlay_used": True,
            "no_live_release_invocation": True,
            "no_certificate_consumption": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


class Harness:
    def __init__(self):
        self.calls = []
        self.items = {"left": make_item("left"), "right": make_item("right")}
        self.browser_manifests = {
            "left": initial_manifest("left"),
            "right": initial_manifest("right"),
        }
        self.semantic_manifests = {
            "left": semantic_manifest("left"),
            "right": semantic_manifest("right"),
        }
        self.plans = {"left": plan("left"), "right": plan("right")}
        self.workspaces = []

    def side(self, item_id):
        if item_id == "item-left":
            return "left"
        if item_id == "item-right":
            return "right"
        raise AssertionError(f"Unexpected item ID: {item_id}")

    def browser(self, capture):
        side = capture["side"]
        self.calls.append(("browser", side))
        return browser_ingestion.BrowserIngestionResult(
            item=self.items[side],
            processing_plan=object(),
            artifact_manifest=self.browser_manifests[side],
        )

    def semantic(self, manifest, *, workspace, interpreter,
                 perception_executor_builder=None, perception_options=None):
        side = self.side(manifest.item_id)
        self.calls.append((
            "semantic", side, workspace, interpreter,
            perception_executor_builder, dict(perception_options or {}),
        ))
        return self.semantic_manifests[side]

    def bridge(self, *, item, manifest, bindings, relationships=()):
        side = self.side(item.item_id)
        self.calls.append((
            "bridge", side, manifest.item_id, bindings.media_item_id,
            tuple(relationships),
        ))
        return self.plans[side]

    def persist(self, *, plan, bindings, connection_factory, relationships=()):
        side = self.side(plan.item_id)
        row = plan.candidates[0]
        self.calls.append((
            "persist", side, len(plan.candidates),
            row.claim.deterministic_id, bindings.media_item_id,
            connection_factory, tuple(relationships),
        ))
        return {
            "version": verified_persistence_execution.VERIFIED_PERSISTENCE_EXECUTION_VERSION,
            "item_id": plan.item_id,
            "candidate_count": 1,
            "candidate_rows": [{
                "candidate_id": row.candidate_id,
                "claim_id": row.claim.deterministic_id,
                "evidence_id": f"evidence-{side}",
                "source_observation_id": f"observation-{side}",
            }],
            "policy": {
                "evidence_verification": "unverified",
                "establishes_truth": False,
                "establishes_independence": False,
                "adjudication_performed": False,
                "affects_live_merit": False,
            },
        }

    def observe(self, *, claim, source, context, client, client_key, generator):
        side = "left" if "left.example" in source["final_url"] else "right"
        self.calls.append((
            "observe", side, claim["id"], source["final_url"],
            dict(context), client, client_key, generator,
        ))
        return semantic_wrapper(claim["id"], source["final_url"])

    def intake(self, *, claim_id, media_item_id, semantic_result,
               aligned_evidence_ids=None, source_observation_ids=None,
               connection_factory):
        self.calls.append((
            "intake", media_item_id, claim_id, semantic_result["claim_id"],
            tuple(aligned_evidence_ids or []),
            tuple(source_observation_ids or []),
            connection_factory,
        ))
        return intake_result(claim_id, media_item_id)

    def adjudicate(self, *, intake, as_of, connection_factory, recorded_at=None):
        self.calls.append((
            "adjudicate", intake["media_item_id"], as_of,
            recorded_at, connection_factory,
        ))
        return adjudication_result(intake["claim_id"], intake["media_item_id"])

    def corroborate(self, *, claim_id, left_intake, right_intake,
                    left_adjudication, right_adjudication,
                    connection_factory, recorded_at=None):
        self.calls.append((
            "corroborate", claim_id,
            left_intake["media_item_id"], right_intake["media_item_id"],
            left_adjudication["revision_id"], right_adjudication["revision_id"],
            recorded_at, connection_factory,
        ))
        return corroboration_result(claim_id)

    def shadow(self, *, corroboration_result, legacy_score):
        self.calls.append((
            "shadow", corroboration_result["claim_id"],
            copy.deepcopy(legacy_score),
        ))
        return shadow_result(
            corroboration_result["claim_id"],
            score=legacy_score,
        )

    def workspace(self):
        value = DummyWorkspace()
        self.workspaces.append(value)
        return value

    def kwargs(self):
        return {
            "left_capture": {"side": "left"},
            "right_capture": {"side": "right"},
            "left_bindings": binding("left"),
            "right_bindings": binding("right"),
            "legacy_score": legacy_score(),
            "as_of": AS_OF,
            "recorded_at": RECORDED_AT,
            "connection_factory": object(),
            "semantic_interpreter": object(),
            "gemini_client": object(),
            "gemini_client_key": "client-key",
            "gemini_generator": object(),
            "browser_ingestor": self.browser,
            "semantic_manifest_runner": self.semantic,
            "bridge_builder": self.bridge,
            "persistence_runner": self.persist,
            "observation_semantic_runner": self.observe,
            "intake_builder": self.intake,
            "adjudication_runner": self.adjudicate,
            "corroboration_runner": self.corroborate,
            "shadow_runner": self.shadow,
            "workspace_factory": self.workspace,
        }


class MultimodalIntelligenceRuntimeTests(unittest.TestCase):
    def run_success(self, harness=None, **overrides):
        harness = harness or Harness()
        values = harness.kwargs()
        values.update(overrides)
        return harness, runtime.run_multimodal_intelligence_runtime(**values)

    def test_version_constant(self):
        self.assertEqual(
            runtime.MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION,
            "multimodal-intelligence-runtime-v1",
        )

    def test_successful_pipeline_completes_shadow(self):
        _, result = self.run_success()
        self.assertEqual(result["status"], "completed_shadow")
        self.assertEqual(result["claim_id"], CLAIM_ID)
        self.assertEqual(result["shadow"]["proposed_adjustment"], 6.0)

    def test_pipeline_live_score_is_legacy_score(self):
        score = legacy_score(71.0)
        _, result = self.run_success(legacy_score=score)
        self.assertEqual(result["live_score"], score)
        self.assertEqual(score, legacy_score(71.0))

    def test_final_policy_is_shadow_only(self):
        _, result = self.run_success()
        p = result["policy"]
        self.assertTrue(p["merit_shadow_only"])
        self.assertTrue(p["live_release_not_called"])
        self.assertTrue(p["release_certificate_not_consumed"])
        self.assertFalse(p["live_enablement_authorized"])
        self.assertFalse(p["score_effect_applied"])
        self.assertFalse(p["establishes_truth"])
        self.assertFalse(p["affects_live_merit"])

    def test_pipeline_does_not_claim_cross_stage_atomicity(self):
        _, result = self.run_success()
        self.assertFalse(result["policy"]["pipeline_is_cross_stage_atomic"])
        self.assertTrue(
            result["policy"]["stage_persistence_uses_existing_atomic_runtimes"]
        )

    def test_preflights_both_semantic_sides_before_persistence(self):
        harness, _ = self.run_success()
        names = [row[0] for row in harness.calls]
        first_persist = names.index("persist")
        self.assertEqual(names[:first_persist].count("semantic"), 2)
        self.assertEqual(names[:first_persist].count("bridge"), 2)

    def test_workspaces_are_closed_after_semantic_preflight(self):
        harness, _ = self.run_success()
        self.assertEqual(len(harness.workspaces), 2)
        self.assertTrue(all(row.entered for row in harness.workspaces))
        self.assertTrue(all(row.closed for row in harness.workspaces))

    def test_exact_common_claim_is_auto_selected(self):
        _, result = self.run_success()
        self.assertEqual(result["claim_id"], CLAIM_ID)

    def test_explicit_target_claim_is_supported(self):
        _, result = self.run_success(target_claim_id=CLAIM_ID)
        self.assertEqual(result["claim_id"], CLAIM_ID)

    def test_no_common_claim_fails_before_persistence(self):
        harness = Harness()
        harness.plans["right"] = plan(
            "right", rows=[candidate("right", claim_id="claim-other")]
        )
        with self.assertRaises(runtime.MultimodalClaimSelectionError):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())
        self.assertFalse(any(row[0] == "persist" for row in harness.calls))

    def test_multiple_common_claims_require_explicit_target(self):
        harness = Harness()
        for side in ("left", "right"):
            harness.plans[side] = plan(side, rows=[
                candidate(side),
                candidate(
                    side,
                    claim_id="claim-second",
                    candidate_id=f"candidate-second-{side}",
                ),
            ])
        with self.assertRaises(runtime.MultimodalClaimSelectionError):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_explicit_target_missing_left_fails(self):
        harness = Harness()
        values = harness.kwargs()
        values["target_claim_id"] = "claim-missing"
        with self.assertRaises(runtime.MultimodalClaimSelectionError):
            runtime.run_multimodal_intelligence_runtime(**values)

    def test_blocked_candidate_cannot_be_selected(self):
        harness = Harness()
        harness.plans["right"] = plan(
            "right", rows=[candidate("right", ready=False)]
        )
        with self.assertRaises(runtime.MultimodalClaimSelectionError):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_duplicate_ready_claim_ids_fail_closed(self):
        harness = Harness()
        harness.plans["left"] = plan("left", rows=[
            candidate("left", candidate_id="candidate-a"),
            candidate("left", candidate_id="candidate-b"),
        ])
        with self.assertRaises(runtime.MultimodalClaimSelectionError):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_subjects_must_match(self):
        harness = Harness()
        harness.plans["right"] = plan("right", subject="club|chelsea")
        with self.assertRaisesRegex(
            runtime.MultimodalClaimSelectionError,
            "same non-empty subject",
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_same_verified_media_binding_is_rejected_early(self):
        harness = Harness()
        values = harness.kwargs()
        values["right_bindings"] = binding("right", media_id="media-left")
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineInputError,
            "two distinct verified media items",
        ):
            runtime.run_multimodal_intelligence_runtime(**values)
        self.assertEqual(harness.calls, [])

    def test_source_binding_must_be_verified(self):
        harness = Harness()
        values = harness.kwargs()
        values["left_bindings"] = binding("left", source_verified=False)
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineInputError, "source binding"
        ):
            runtime.run_multimodal_intelligence_runtime(**values)

    def test_media_binding_must_be_verified(self):
        harness = Harness()
        values = harness.kwargs()
        values["left_bindings"] = binding("left", media_verified=False)
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineInputError, "media binding"
        ):
            runtime.run_multimodal_intelligence_runtime(**values)

    def test_same_content_item_is_rejected_before_semantic_execution(self):
        harness = Harness()
        harness.items["right"] = harness.items["left"]
        harness.browser_manifests["right"] = initial_manifest(
            "right", item_id="item-left"
        )
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineInputError, "two distinct content items"
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())
        self.assertFalse(any(row[0] == "semantic" for row in harness.calls))

    def test_persistence_receives_one_candidate_per_side(self):
        harness, _ = self.run_success()
        calls = [row for row in harness.calls if row[0] == "persist"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(row[2] == 1 for row in calls))
        self.assertTrue(all(row[3] == CLAIM_ID for row in calls))

    def test_relationships_are_forwarded_to_bridge_and_persistence(self):
        harness = Harness()
        relation = content.ContentRelationship(
            relationship_id="relationship-left",
            source_item_id="item-left",
            target_item_id="upstream-item",
            relationship_type="repost_of",
        )
        self.run_success(harness, left_relationships=[relation])
        b = next(row for row in harness.calls if row[:2] == ("bridge", "left"))
        p = next(row for row in harness.calls if row[:2] == ("persist", "left"))
        self.assertEqual(b[4], (relation,))
        self.assertEqual(p[6], (relation,))

    def test_observation_semantics_use_selected_persisted_claim_id(self):
        harness, _ = self.run_success()
        calls = [row for row in harness.calls if row[0] == "observe"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(row[2] == CLAIM_ID for row in calls))

    def test_observation_context_is_forwarded_per_side(self):
        harness, _ = self.run_success(
            left_observation_context={"known_reliability_class": "established"},
            right_observation_context={"known_reliability_class": "unrated"},
        )
        calls = {row[1]: row for row in harness.calls if row[0] == "observe"}
        self.assertEqual(calls["left"][4]["known_reliability_class"], "established")
        self.assertEqual(calls["right"][4]["known_reliability_class"], "unrated")

    def test_source_text_uses_original_content_and_candidate_artifacts(self):
        harness = Harness()
        captured = {}

        def observe(**kwargs):
            source = kwargs["source"]
            side = "left" if "left.example" in source["final_url"] else "right"
            captured[side] = source
            return semantic_wrapper(kwargs["claim"]["id"], source["final_url"])

        self.run_success(harness, observation_semantic_runner=observe)
        self.assertIn("left source confirms", captured["left"]["text"])
        self.assertIn("left semantic source text", captured["left"]["text"])

    def test_missing_candidate_source_artifact_fails_closed(self):
        harness = Harness()
        harness.plans["left"] = plan(
            "left",
            rows=[candidate("left", source_artifact_id="missing-artifact")],
        )
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "missing semantic source artifact",
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_observation_semantics_unavailable_fails_closed(self):
        harness = Harness()

        def unavailable(**kwargs):
            return semantic_wrapper(
                kwargs["claim"]["id"],
                kwargs["source"]["final_url"],
                status="unavailable",
            )

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "did not produce an assessed result",
        ):
            self.run_success(harness, observation_semantic_runner=unavailable)

    def test_observation_semantics_wrong_claim_fails_closed(self):
        harness = Harness()

        def wrong(**kwargs):
            url = kwargs["source"]["final_url"]
            assessment = semantic_assessment("wrong-claim", url)
            return semantic_wrapper(kwargs["claim"]["id"], url, assessment=assessment)

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError, "claim ID changed"
        ):
            self.run_success(harness, observation_semantic_runner=wrong)

    def test_observation_semantics_wrong_source_url_fails_closed(self):
        harness = Harness()

        def wrong(**kwargs):
            assessment = semantic_assessment(
                kwargs["claim"]["id"], "https://wrong.example/post"
            )
            return semantic_wrapper(
                kwargs["claim"]["id"],
                kwargs["source"]["final_url"],
                assessment=assessment,
            )

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError, "source URL changed"
        ):
            self.run_success(harness, observation_semantic_runner=wrong)

    def test_observation_semantics_related_claim_fails_closed(self):
        harness = Harness()

        def related(**kwargs):
            url = kwargs["source"]["final_url"]
            assessment = semantic_assessment(
                kwargs["claim"]["id"], url, relevance="related_claim"
            )
            return semantic_wrapper(kwargs["claim"]["id"], url, assessment=assessment)

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "not for the exact selected claim",
        ):
            self.run_success(harness, observation_semantic_runner=related)

    def test_observation_semantics_safety_policy_is_required(self):
        harness = Harness()

        def unsafe(**kwargs):
            url = kwargs["source"]["final_url"]
            assessment = semantic_assessment(kwargs["claim"]["id"], url)
            assessment["policy"]["model_does_not_establish_truth"] = False
            return semantic_wrapper(kwargs["claim"]["id"], url, assessment=assessment)

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError, "safety boundary changed"
        ):
            self.run_success(harness, observation_semantic_runner=unsafe)

    def test_persistence_claim_mismatch_fails_closed(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.persist(**kwargs)
            result["candidate_rows"][0]["claim_id"] = "wrong"
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "candidate/claim binding changed",
        ):
            self.run_success(harness, persistence_runner=bad)

    def test_persistence_cannot_mark_evidence_verified(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.persist(**kwargs)
            result["policy"]["evidence_verification"] = "verified"
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "persistence safety boundary changed",
        ):
            self.run_success(harness, persistence_runner=bad)

    def test_intake_is_scoped_to_exact_persistence_rows(self):
        harness, _ = self.run_success()
        calls = [row for row in harness.calls if row[0] == "intake"]
        by_media = {row[1]: row for row in calls}
        self.assertEqual(by_media["media-left"][4], ("evidence-left",))
        self.assertEqual(by_media["media-left"][5], ("observation-left",))
        self.assertEqual(by_media["media-right"][4], ("evidence-right",))
        self.assertEqual(by_media["media-right"][5], ("observation-right",))

    def test_intake_requires_explicit_candidate_scope_marker(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.intake(**kwargs)
            result["policy"]["explicit_persistence_scope_applied"] = False
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "not scoped to the exact #15 candidate",
        ):
            self.run_success(harness, intake_builder=bad)

    def test_intake_media_binding_mismatch_fails_closed(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.intake(**kwargs)
            result["media_item_id"] = "wrong"
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError, "intake binding/version"
        ):
            self.run_success(harness, intake_builder=bad)

    def test_intake_cannot_enable_truth(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.intake(**kwargs)
            result["policy"]["establishes_truth"] = True
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "may not enable establishes_truth",
        ):
            self.run_success(harness, intake_builder=bad)

    def test_adjudication_media_binding_mismatch_fails_closed(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.adjudicate(**kwargs)
            result["media_item_id"] = "wrong"
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "adjudication result binding/version",
        ):
            self.run_success(harness, adjudication_runner=bad)

    def test_adjudication_cannot_affect_live_merit(self):
        harness = Harness()

        def bad(**kwargs):
            result = harness.adjudicate(**kwargs)
            result["policy"]["affects_live_merit"] = True
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "adjudication safety boundary changed",
        ):
            self.run_success(harness, adjudication_runner=bad)

    def test_as_of_and_recorded_at_are_forwarded_to_both_adjudications(self):
        harness, _ = self.run_success()
        calls = [row for row in harness.calls if row[0] == "adjudicate"]
        self.assertTrue(all(row[2] == AS_OF for row in calls))
        self.assertTrue(all(row[3] == RECORDED_AT for row in calls))

    def test_corroboration_receives_two_distinct_media_intakes(self):
        harness, _ = self.run_success()
        call = next(row for row in harness.calls if row[0] == "corroborate")
        self.assertEqual(call[2], "media-left")
        self.assertEqual(call[3], "media-right")

    def test_corroboration_claim_mismatch_fails_closed(self):
        harness = Harness()

        def bad(**_kwargs):
            return corroboration_result("wrong")

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "Corroboration result claim/version",
        ):
            self.run_success(harness, corroboration_runner=bad)

    def test_corroboration_cannot_claim_live_merit_evaluated(self):
        harness = Harness()

        def bad(**kwargs):
            result = corroboration_result(kwargs["claim_id"])
            result["policy"]["live_merit_evaluated"] = True
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "Corroboration safety boundary changed",
        ):
            self.run_success(harness, corroboration_runner=bad)

    def test_shadow_claim_mismatch_fails_closed(self):
        harness = Harness()

        def bad(**kwargs):
            return shadow_result("wrong", score=kwargs["legacy_score"])

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "Live Merit shadow claim/version",
        ):
            self.run_success(harness, shadow_runner=bad)

    def test_shadow_live_score_mutation_fails_closed(self):
        harness = Harness()

        def bad(**kwargs):
            result = shadow_result(
                kwargs["corroboration_result"]["claim_id"],
                score=kwargs["legacy_score"],
            )
            result["live_score"]["total"] += 6
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "changed the legacy live score",
        ):
            self.run_success(harness, shadow_runner=bad)

    def test_shadow_cannot_authorize_live_enablement(self):
        harness = Harness()

        def bad(**kwargs):
            result = shadow_result(
                kwargs["corroboration_result"]["claim_id"],
                score=kwargs["legacy_score"],
            )
            result["policy"]["live_enablement_authorized"] = True
            return result

        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "shadow safety boundary changed",
        ):
            self.run_success(harness, shadow_runner=bad)

    def test_shadow_receives_exact_legacy_score_without_mutation(self):
        harness = Harness()
        score = legacy_score(79.0)
        before = copy.deepcopy(score)
        self.run_success(harness, legacy_score=score)
        call = next(row for row in harness.calls if row[0] == "shadow")
        self.assertEqual(call[2], before)
        self.assertEqual(score, before)

    def test_semantic_manifest_item_id_change_fails_closed(self):
        harness = Harness()
        harness.semantic_manifests["left"] = artifact_models.ItemArtifactManifest(
            item_id="wrong-item"
        )
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "semantic manifest item ID changed",
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_bridge_plan_item_id_change_fails_closed(self):
        harness = Harness()
        value = plan("left")
        data = value.model_dump(mode="python") if hasattr(
            value, "model_dump"
        ) else value.dict()
        data["item_id"] = "wrong-item"
        harness.plans["left"] = bridge_models.ItemIntelligenceBridgePlan(**data)
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError,
            "bridge plan item ID changed",
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_bridge_plan_must_remain_dry_run(self):
        harness = Harness()
        value = harness.plans["left"]
        data = value.model_dump(mode="python") if hasattr(
            value, "model_dump"
        ) else value.dict()
        data["policy"]["dry_run_only"] = False
        harness.plans["left"] = bridge_models.ItemIntelligenceBridgePlan(**data)
        with self.assertRaisesRegex(
            runtime.MultimodalPipelineIntegrityError, "escaped dry-run mode"
        ):
            runtime.run_multimodal_intelligence_runtime(**harness.kwargs())

    def test_perception_options_are_scoped_per_side(self):
        harness, _ = self.run_success(
            left_perception_options={"language": "en"},
            right_perception_options={"language": "fr"},
        )
        calls = {row[1]: row for row in harness.calls if row[0] == "semantic"}
        self.assertEqual(calls["left"][5], {"language": "en"})
        self.assertEqual(calls["right"][5], {"language": "fr"})

    def test_existing_stage_signatures_match_runtime_calls(self):
        harness = Harness()
        browser = mock.create_autospec(
            browser_ingestion.ingest_browser_capture, side_effect=harness.browser
        )
        semantic = mock.create_autospec(
            semantic_execution.execute_semantic_manifest,
            side_effect=harness.semantic,
        )
        bridge = mock.create_autospec(
            multimodal_intelligence_bridge.build_item_intelligence_bridge,
            side_effect=harness.bridge,
        )
        persist = mock.create_autospec(
            verified_persistence_execution.execute_verified_persistence,
            side_effect=harness.persist,
        )
        observe = mock.create_autospec(
            observation_semantics.assess_claim_observation_semantics_with_gemini,
            side_effect=harness.observe,
        )
        intake_builder = mock.create_autospec(
            multimodal_adjudication_intake.build_multimodal_adjudication_intake,
            side_effect=harness.intake,
        )
        adjudicate = mock.create_autospec(
            multimodal_adjudication_runtime.execute_multimodal_adjudication,
            side_effect=harness.adjudicate,
        )
        corroborate = mock.create_autospec(
            multimodal_corroboration_runtime.execute_multimodal_corroboration,
            side_effect=harness.corroborate,
        )
        shadow_runner = mock.create_autospec(
            multimodal_live_merit_shadow.evaluate_multimodal_live_merit_shadow,
            side_effect=harness.shadow,
        )

        _, result = self.run_success(
            harness,
            browser_ingestor=browser,
            semantic_manifest_runner=semantic,
            bridge_builder=bridge,
            persistence_runner=persist,
            observation_semantic_runner=observe,
            intake_builder=intake_builder,
            adjudication_runner=adjudicate,
            corroboration_runner=corroborate,
            shadow_runner=shadow_runner,
        )

        self.assertEqual(result["claim_id"], CLAIM_ID)
        self.assertEqual(browser.call_count, 2)
        self.assertEqual(semantic.call_count, 2)
        self.assertEqual(bridge.call_count, 2)
        self.assertEqual(persist.call_count, 2)
        self.assertEqual(observe.call_count, 2)
        self.assertEqual(intake_builder.call_count, 2)
        self.assertEqual(adjudicate.call_count, 2)
        self.assertEqual(corroborate.call_count, 1)
        self.assertEqual(shadow_runner.call_count, 1)

    def test_default_stage_parameters_exist_on_real_functions(self):
        expected = {
            browser_ingestion.ingest_browser_capture: {"raw_capture"},
            semantic_execution.execute_semantic_manifest: {
                "manifest", "workspace", "interpreter",
            },
            multimodal_intelligence_bridge.build_item_intelligence_bridge: {
                "item", "manifest", "bindings", "relationships",
            },
            verified_persistence_execution.execute_verified_persistence: {
                "plan", "bindings", "connection_factory", "relationships",
            },
            observation_semantics.assess_claim_observation_semantics_with_gemini: {
                "claim", "source", "context", "client", "client_key", "generator",
            },
            multimodal_adjudication_intake.build_multimodal_adjudication_intake: {
                "claim_id", "media_item_id", "semantic_result",
                "aligned_evidence_ids", "source_observation_ids",
                "connection_factory",
            },
            multimodal_adjudication_runtime.execute_multimodal_adjudication: {
                "intake", "as_of", "connection_factory", "recorded_at",
            },
            multimodal_corroboration_runtime.execute_multimodal_corroboration: {
                "claim_id", "left_intake", "right_intake",
                "left_adjudication", "right_adjudication",
                "connection_factory", "recorded_at",
            },
            multimodal_live_merit_shadow.evaluate_multimodal_live_merit_shadow: {
                "corroboration_result", "legacy_score",
            },
        }

        for function, names in expected.items():
            parameters = set(inspect.signature(function).parameters)
            self.assertTrue(
                names.issubset(parameters),
                msg=(
                    function.__name__
                    + " missing "
                    + repr(sorted(names - parameters))
                ),
            )

    def test_runtime_does_not_import_live_release_module(self):
        source = Path(runtime.__file__).read_text(encoding="utf-8")
        self.assertNotIn("live_merit_release", source)
        self.assertNotIn("merit_score_release", source)

    def test_runtime_has_no_direct_sql(self):
        source = Path(runtime.__file__).read_text(encoding="utf-8")
        for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "BEGIN IMMEDIATE"):
            self.assertNotIn(token, source)

    def test_runtime_does_not_call_live_release(self):
        source = Path(runtime.__file__).read_text(encoding="utf-8")
        for token in (
            "apply_certified_live_merit",
            "evaluate_live_merit_release",
            "validate_merit_score_release_certificate",
        ):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
