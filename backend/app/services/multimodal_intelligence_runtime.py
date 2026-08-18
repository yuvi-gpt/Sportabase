from __future__ import annotations

import copy
from contextlib import ExitStack
from typing import Any, Dict, Mapping, Optional, Sequence
from urllib.parse import urlparse

from app.analysis import observation_semantics as observation_semantics_analysis
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import browser_ingestion
from app.services import media_execution
from app.services import multimodal_adjudication_intake
from app.services import multimodal_adjudication_runtime
from app.services import multimodal_corroboration_runtime
from app.services import multimodal_intelligence_bridge
from app.services import multimodal_structured_shadow_caller
from app.services import multimodal_live_merit_shadow
from app.services import observation_semantics
from app.services import semantic_execution
from app.services import structured_claim_fusion
from app.services import verified_persistence_execution


MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION = (
    "multimodal-intelligence-runtime-v1"
)

MERIT_BASELINE_MODE_LEGACY = "legacy_merit"
MERIT_BASELINE_MODE_NOT_APPLICABLE = "not_applicable"
NO_MERIT_BASELINE_SHADOW_VERSION = (
    "multimodal-no-merit-baseline-v1"
)


class MultimodalIntelligenceRuntimeError(RuntimeError):
    pass


class MultimodalPipelineInputError(
    MultimodalIntelligenceRuntimeError
):
    pass


class MultimodalPipelineIntegrityError(
    MultimodalIntelligenceRuntimeError
):
    pass


class MultimodalClaimSelectionError(
    MultimodalIntelligenceRuntimeError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _normalize_merit_baseline(
    *,
    legacy_score: Optional[Mapping[str, Any]],
    merit_baseline_mode: str,
) -> tuple[str, Optional[Dict[str, Any]]]:
    mode = _clean(
        merit_baseline_mode
    ).lower() or MERIT_BASELINE_MODE_LEGACY

    if mode == MERIT_BASELINE_MODE_LEGACY:
        if not isinstance(legacy_score, Mapping):
            raise MultimodalPipelineInputError(
                "Legacy Merit score must be a mapping."
            )
        return mode, copy.deepcopy(dict(legacy_score))

    if mode == MERIT_BASELINE_MODE_NOT_APPLICABLE:
        if legacy_score is not None:
            raise MultimodalPipelineInputError(
                "No-Merit execution must not receive a synthetic legacy score."
            )
        return mode, None

    raise MultimodalPipelineInputError(
        "Unsupported Merit baseline mode."
    )


def _no_merit_shadow_result(
    *,
    claim_id: str,
) -> Dict[str, Any]:
    return {
        "version": NO_MERIT_BASELINE_SHADOW_VERSION,
        "status": "not_applicable",
        "claim_id": claim_id,
        "reason": "no_legacy_merit_baseline",
        "live_score": None,
        "proposed_adjustment": None,
        "proposed_shadow_total": None,
        "shadow_boost_eligible_under_overlay": False,
        "policy": {
            "merit_baseline_available": False,
            "merit_shadow_evaluated": False,
            "shadow_runner_called": False,
            "synthetic_merit_baseline_used": False,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


def _model_payload(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="python"
        )

    if hasattr(value, "dict"):
        return value.dict()

    if isinstance(value, Mapping):
        return dict(value)

    raise MultimodalPipelineIntegrityError(
        "Pipeline model value cannot be serialized."
    )


def _require_bindings(
    raw: bridge_models.BridgeBindings,
    *,
    label: str,
) -> bridge_models.BridgeBindings:
    if not isinstance(
        raw,
        bridge_models.BridgeBindings,
    ):
        raise MultimodalPipelineInputError(
            label
            + " bindings must be BridgeBindings."
        )

    if (
        not _clean(raw.source_id)
        or raw.source_record_verified
        is not True
    ):
        raise MultimodalPipelineInputError(
            label
            + " source binding must be explicitly verified."
        )

    if (
        not _clean(raw.media_item_id)
        or raw.media_item_record_verified
        is not True
    ):
        raise MultimodalPipelineInputError(
            label
            + " media binding must be explicitly verified."
        )

    return raw


def _require_ingestion(
    raw: Any,
    *,
    label: str,
):
    item = getattr(
        raw,
        "item",
        None,
    )
    manifest = getattr(
        raw,
        "artifact_manifest",
        None,
    )

    if not isinstance(
        item,
        content.UnifiedContentItem,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " browser ingestion did not return "
              "a UnifiedContentItem."
        )

    if not isinstance(
        manifest,
        artifact_models.ItemArtifactManifest,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " browser ingestion did not return "
              "an ItemArtifactManifest."
        )

    if manifest.item_id != item.item_id:
        raise MultimodalPipelineIntegrityError(
            label
            + " browser item/manifest IDs do not match."
        )

    content.validate_unified_content_item(
        item
    )
    artifact_models.validate_item_artifact_manifest(
        manifest
    )

    return raw


def _require_semantic_manifest(
    raw: Any,
    *,
    item_id: str,
    label: str,
) -> artifact_models.ItemArtifactManifest:
    if not isinstance(
        raw,
        artifact_models.ItemArtifactManifest,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " semantic execution did not return "
              "an ItemArtifactManifest."
        )

    if raw.item_id != item_id:
        raise MultimodalPipelineIntegrityError(
            label
            + " semantic manifest item ID changed."
        )

    artifact_models.validate_item_artifact_manifest(
        raw
    )

    return raw


def _require_bridge_plan(
    raw: Any,
    *,
    item_id: str,
    label: str,
) -> bridge_models.ItemIntelligenceBridgePlan:
    if not isinstance(
        raw,
        bridge_models.ItemIntelligenceBridgePlan,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " bridge did not return an "
              "ItemIntelligenceBridgePlan."
        )

    if raw.item_id != item_id:
        raise MultimodalPipelineIntegrityError(
            label
            + " bridge plan item ID changed."
        )

    if (
        raw.policy.get(
            "dry_run_only"
        )
        is not True
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " bridge plan escaped dry-run mode."
        )

    for field in (
        "training_eligible",
        "establishes_truth",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(
            raw.policy.get(field)
        ):
            raise MultimodalPipelineIntegrityError(
                label
                + " bridge plan may not enable "
                + field
                + "."
            )

    return raw


def _candidate_ready(
    candidate: bridge_models.CandidateBridgeRecord,
) -> bool:
    proposals = (
        candidate.claim,
        candidate.evidence,
        candidate.claim_link,
        candidate.source_observation,
    )

    return all(
        proposal.readiness == "ready"
        for proposal in proposals
    )


def _ready_candidates_by_claim(
    plan: bridge_models.ItemIntelligenceBridgePlan,
    *,
    label: str,
) -> Dict[
    str,
    bridge_models.CandidateBridgeRecord,
]:
    output = {}

    for candidate in plan.candidates:
        if not _candidate_ready(
            candidate
        ):
            continue

        claim_id = _clean(
            candidate.claim.deterministic_id
        )

        if not claim_id:
            continue

        if claim_id in output:
            raise MultimodalClaimSelectionError(
                label
                + " bridge contains duplicate "
                  "ready deterministic claim IDs."
            )

        output[claim_id] = candidate

    return output


def _select_common_claim(
    *,
    left_plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    right_plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    target_claim_id: str,
):
    left_subject = _clean(
        left_plan.subject_key
    )
    right_subject = _clean(
        right_plan.subject_key
    )

    if (
        not left_subject
        or not right_subject
        or left_subject != right_subject
    ):
        raise MultimodalClaimSelectionError(
            "Both bridge plans must resolve "
            "to the same non-empty subject."
        )

    left = _ready_candidates_by_claim(
        left_plan,
        label="Left",
    )
    right = _ready_candidates_by_claim(
        right_plan,
        label="Right",
    )

    requested = _clean(
        target_claim_id
    )

    if requested:
        if requested not in left:
            raise MultimodalClaimSelectionError(
                "Requested claim is not a ready "
                "left-side bridge candidate."
            )

        if requested not in right:
            raise MultimodalClaimSelectionError(
                "Requested claim is not a ready "
                "right-side bridge candidate."
            )

        selected = requested

    else:
        common = sorted(
            set(left)
            & set(right)
        )

        if not common:
            raise MultimodalClaimSelectionError(
                "The two multimodal items have no "
                "common ready deterministic claim."
            )

        if len(common) != 1:
            raise MultimodalClaimSelectionError(
                "Multiple common ready claims exist; "
                "target_claim_id is required."
            )

        selected = common[0]

    return (
        selected,
        left[selected],
        right[selected],
    )


def _filtered_plan(
    plan: bridge_models.ItemIntelligenceBridgePlan,
    candidate: bridge_models.CandidateBridgeRecord,
) -> bridge_models.ItemIntelligenceBridgePlan:
    data = _model_payload(
        plan
    )
    data["candidates"] = [
        _model_payload(candidate)
    ]

    return (
        bridge_models
        .ItemIntelligenceBridgePlan(
            **data
        )
    )


def _require_persistence_result(
    raw: Any,
    *,
    claim_id: str,
    candidate_id: str,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence result must be a mapping."
        )

    result = dict(raw)

    if (
        _clean(result.get("version"))
        != (
            verified_persistence_execution
            .VERIFIED_PERSISTENCE_EXECUTION_VERSION
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence version is unsupported."
        )

    rows = result.get(
        "candidate_rows"
    )

    if (
        not isinstance(rows, list)
        or len(rows) != 1
        or not isinstance(
            rows[0],
            Mapping,
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence must return exactly "
              "one candidate row."
        )

    row = dict(rows[0])

    if (
        _clean(row.get("candidate_id"))
        != candidate_id
        or _clean(row.get("claim_id"))
        != claim_id
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence candidate/claim binding changed."
        )

    policy = result.get("policy")

    if not isinstance(
        policy,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence policy is required."
        )

    if (
        _clean(
            policy.get(
                "evidence_verification"
            )
        ).lower()
        != "unverified"
        or bool(
            policy.get(
                "establishes_truth"
            )
        )
        or bool(
            policy.get(
                "establishes_independence"
            )
        )
        or bool(
            policy.get(
                "adjudication_performed"
            )
        )
        or bool(
            policy.get(
                "affects_live_merit"
            )
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " persistence safety boundary changed."
        )

    return result


def _artifact_text(
    artifact: artifact_models.ExtractionArtifact,
) -> Sequence[str]:
    kind = _clean(
        artifact.artifact_kind
    ).lower()

    payload = (
        artifact.payload
        if isinstance(
            artifact.payload,
            Mapping,
        )
        else {}
    )

    output = []

    if kind in {
        "text_component",
        "ocr_text",
        "transcript",
    }:
        text = _clean(
            payload.get("text")
        )

        if text:
            output.append(text)

    elif kind == "visual_observations":
        scene = _clean(
            payload.get(
                "scene_summary"
            )
        )

        if scene:
            output.append(scene)

        observations = payload.get(
            "observations",
            [],
        )

        if isinstance(
            observations,
            list,
        ):
            for raw in observations:
                if not isinstance(
                    raw,
                    Mapping,
                ):
                    continue

                text = _clean(
                    raw.get("text")
                )

                if text:
                    output.append(text)

    return output


def _observation_source(
    *,
    item: content.UnifiedContentItem,
    manifest: artifact_models.ItemArtifactManifest,
    candidate: bridge_models.CandidateBridgeRecord,
    label: str,
) -> Dict[str, Any]:
    source_url = _clean(
        item.canonical_url
    )

    if not source_url:
        raise MultimodalPipelineInputError(
            label
            + " item requires a canonical URL "
              "for observation semantics."
        )

    artifact_ids = {
        _clean(
            row.artifact_id
        )
        for row in (
            candidate.source_artifacts
        )
        if _clean(
            row.artifact_id
        )
    }

    artifact_by_id = {
        artifact.artifact_id:
            artifact
        for artifact
        in manifest.artifacts
    }

    pieces = []
    seen = set()

    def add(value: Any):
        text = _clean(value)

        if (
            not text
            or text in seen
        ):
            return

        seen.add(text)
        pieces.append(text)

    components = sorted(
        list(
            item.text_components
        ),
        key=lambda row: (
            (
                row.sequence_index
                is None
            ),
            (
                row.sequence_index
                if row.sequence_index
                is not None
                else 0
            ),
            row.component_id,
        ),
    )

    title = ""

    for component in components:
        if (
            not title
            and component.role
            == "title"
        ):
            title = _clean(
                component.text
            )

        add(
            component.text
        )

    for artifact_id in sorted(
        artifact_ids
    ):
        artifact = artifact_by_id.get(
            artifact_id
        )

        if artifact is None:
            raise MultimodalPipelineIntegrityError(
                label
                + " selected candidate references "
                  "a missing semantic source artifact."
            )

        for text in _artifact_text(
            artifact
        ):
            add(text)

    if not pieces:
        raise MultimodalPipelineInputError(
            label
            + " source has no underlying text, OCR, "
              "transcript, or visual observation text "
              "for claim-relative semantics."
        )

    actor = item.actor

    actor_id = (
        _clean(
            actor.canonical_entity_id
        )
        or _clean(
            actor.platform_actor_id
        )
        or _clean(
            actor.handle
        )
    )

    domain = _clean(
        urlparse(
            source_url
        ).hostname
    ).lower()

    return {
        "url": source_url,
        "final_url": source_url,
        "title": title,
        "extracted_title": title,
        "text": "\n".join(
            pieces
        ),
        "actor_id": actor_id,
        "source_domain": domain,
    }


def _claim_payload(
    *,
    claim_id: str,
    plan: bridge_models.ItemIntelligenceBridgePlan,
    candidate: bridge_models.CandidateBridgeRecord,
) -> Dict[str, Any]:
    return {
        "id": claim_id,
        "claim_id": claim_id,
        "canonical_text": (
            candidate.canonical_text
        ),
        "subject_key": (
            plan.subject_key
        ),
    }


def _require_semantic_assessment(
    raw: Any,
    *,
    claim_id: str,
    source_url: str,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics result "
              "must be a mapping."
        )

    wrapper = dict(raw)

    if (
        _clean(wrapper.get("version"))
        != (
            observation_semantics
            .OBSERVATION_SEMANTIC_GEMINI_VERSION
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics wrapper "
              "version is unsupported."
        )

    if (
        _clean(
            wrapper.get("status")
        ).lower()
        != "assessed"
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation semantics did not "
              "produce an assessed result."
        )

    assessment = wrapper.get(
        "assessment"
    )

    if not isinstance(
        assessment,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics assessment "
              "is unavailable."
        )

    assessment = dict(
        assessment
    )

    if (
        _clean(
            assessment.get("version")
        )
        != (
            observation_semantics_analysis
            .CLAIM_OBSERVATION_SEMANTICS_VERSION
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics assessment "
              "version is unsupported."
        )

    if (
        _clean(
            assessment.get("claim_id")
        )
        != claim_id
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics claim ID changed."
        )

    if (
        _clean(
            assessment.get("source_url")
        )
        != source_url
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation-semantics source URL changed."
        )

    if (
        _clean(
            assessment.get(
                "claim_relevance"
            )
        ).lower()
        != "same_claim"
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " observation semantics are not "
              "for the exact selected claim."
        )

    policy = assessment.get(
        "policy"
    )

    for field in (
        "model_does_not_establish_truth",
        "model_does_not_establish_corroboration",
        "model_does_not_establish_independence",
        "observation_semantics_does_not_change_live_merit",
    ):
        if (
            not isinstance(
                policy,
                Mapping,
            )
            or policy.get(field)
            is not True
        ):
            raise MultimodalPipelineIntegrityError(
                label
                + " observation-semantics safety "
                  "boundary changed: "
                + field
            )

    return {
        "wrapper": wrapper,
        "assessment": assessment,
    }


def _require_intake_result(
    raw: Any,
    *,
    claim_id: str,
    media_item_id: str,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication intake must be a mapping."
        )

    result = dict(raw)

    if (
        _clean(result.get("version"))
        != (
            multimodal_adjudication_intake
            .MULTIMODAL_ADJUDICATION_INTAKE_VERSION
        )
        or _clean(
            result.get("status")
        ).lower()
        != "ready"
        or _clean(
            result.get("claim_id")
        )
        != claim_id
        or _clean(
            result.get("media_item_id")
        )
        != media_item_id
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication intake binding/version "
              "is invalid."
        )

    policy = result.get(
        "policy"
    )

    if not isinstance(
        policy,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication intake policy is required."
        )

    for field in (
        "multimodal_evidence_remains_unverified",
        "model_judgments_are_not_hard_references",
        "verified_authority_requires_database_records",
        "adjudication_not_performed",
        "adjudication_state_not_persisted",
    ):
        if policy.get(field) is not True:
            raise MultimodalPipelineIntegrityError(
                label
                + " adjudication intake safety "
                  "boundary changed: "
                + field
            )

    for field in (
        "establishes_truth",
        "establishes_corroboration",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(
            policy.get(field)
        ):
            raise MultimodalPipelineIntegrityError(
                label
                + " adjudication intake may not "
                  "enable "
                + field
                + "."
            )

    if (
        policy.get(
            "explicit_persistence_scope_applied"
        )
        is not True
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication intake was not "
              "scoped to the exact #15 candidate."
        )

    return result


def _require_adjudication_result(
    raw: Any,
    *,
    claim_id: str,
    media_item_id: str,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication result must be a mapping."
        )

    result = dict(raw)

    if (
        _clean(result.get("version"))
        != (
            multimodal_adjudication_runtime
            .MULTIMODAL_ADJUDICATION_RUNTIME_VERSION
        )
        or _clean(
            result.get("claim_id")
        )
        != claim_id
        or _clean(
            result.get("media_item_id")
        )
        != media_item_id
        or not _clean(
            result.get("revision_id")
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication result binding/version "
              "is invalid."
        )

    policy = result.get(
        "policy"
    )

    if (
        not isinstance(
            policy,
            Mapping,
        )
        or policy.get(
            "multimodal_evidence_remains_unverified"
        )
        is not True
        or policy.get(
            "evidence_verification_unchanged"
        )
        is not True
        or bool(
            policy.get("establishes_truth")
        )
        or bool(
            policy.get(
                "establishes_corroboration"
            )
        )
        or bool(
            policy.get(
                "establishes_independence"
            )
        )
        or bool(
            policy.get(
                "affects_live_merit"
            )
        )
    ):
        raise MultimodalPipelineIntegrityError(
            label
            + " adjudication safety boundary changed."
        )

    return result


def _require_corroboration_result(
    raw: Any,
    *,
    claim_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            "Corroboration result must be a mapping."
        )

    result = dict(raw)

    if (
        _clean(result.get("version"))
        != (
            multimodal_corroboration_runtime
            .MULTIMODAL_CORROBORATION_RUNTIME_VERSION
        )
        or _clean(
            result.get("claim_id")
        )
        != claim_id
    ):
        raise MultimodalPipelineIntegrityError(
            "Corroboration result claim/version "
            "is invalid."
        )

    policy = result.get(
        "policy"
    )

    if (
        not isinstance(
            policy,
            Mapping,
        )
        or policy.get(
            "model_stance_materializes_historical_support_only"
        )
        is not True
        or policy.get(
            "support_edge_does_not_establish_truth"
        )
        is not True
        or policy.get(
            "support_edge_does_not_establish_independence"
        )
        is not True
        or bool(
            policy.get("establishes_truth")
        )
        or bool(
            policy.get(
                "live_merit_evaluated"
            )
        )
        or bool(
            policy.get(
                "affects_live_merit"
            )
        )
    ):
        raise MultimodalPipelineIntegrityError(
            "Corroboration safety boundary changed."
        )

    return result


def _require_shadow_result(
    raw: Any,
    *,
    claim_id: str,
    legacy_score: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise MultimodalPipelineIntegrityError(
            "Live Merit shadow result must "
            "be a mapping."
        )

    result = dict(raw)

    if (
        _clean(result.get("version"))
        != (
            multimodal_live_merit_shadow
            .MULTIMODAL_LIVE_MERIT_SHADOW_VERSION
        )
        or _clean(
            result.get("claim_id")
        )
        != claim_id
    ):
        raise MultimodalPipelineIntegrityError(
            "Live Merit shadow claim/version "
            "is invalid."
        )

    if (
        result.get("live_score")
        != legacy_score
    ):
        raise MultimodalPipelineIntegrityError(
            "Live Merit shadow changed "
            "the legacy live score."
        )

    policy = result.get(
        "policy"
    )

    if (
        not isinstance(
            policy,
            Mapping,
        )
        or policy.get(
            "shadow_only"
        )
        is not True
        or policy.get(
            "existing_merit_overlay_used"
        )
        is not True
        or policy.get(
            "no_live_release_invocation"
        )
        is not True
        or policy.get(
            "no_certificate_consumption"
        )
        is not True
        or bool(
            policy.get(
                "live_enablement_authorized"
            )
        )
        or bool(
            policy.get(
                "score_effect_applied"
            )
        )
        or bool(
            policy.get(
                "establishes_truth"
            )
        )
        or bool(
            policy.get(
                "affects_live_merit"
            )
        )
    ):
        raise MultimodalPipelineIntegrityError(
            "Live Merit shadow safety boundary changed."
        )

    return result


def _item_summary(
    item: content.UnifiedContentItem,
) -> Dict[str, Any]:
    return {
        "item_id": item.item_id,
        "platform": item.platform,
        "container_kind": (
            item.container_kind
        ),
        "canonical_url": (
            item.canonical_url
        ),
        "text_component_count": len(
            item.text_components
        ),
        "media_component_count": len(
            item.media_components
        ),
    }


def _manifest_summary(
    manifest: artifact_models.ItemArtifactManifest,
) -> Dict[str, Any]:
    kinds = sorted({
        artifact.artifact_kind
        for artifact
        in manifest.artifacts
    })

    return {
        "item_id": (
            manifest.item_id
        ),
        "artifact_count": len(
            manifest.artifacts
        ),
        "artifact_kinds": kinds,
        "work_unit_count": len(
            manifest.work_units
        ),
    }


def run_multimodal_intelligence_runtime(
    *,
    left_capture: Mapping[str, Any],
    right_capture: Mapping[str, Any],
    left_bindings: bridge_models.BridgeBindings,
    right_bindings: bridge_models.BridgeBindings,
    legacy_score: Optional[Mapping[str, Any]],
    as_of: str,
    connection_factory,
    semantic_interpreter,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    target_claim_id: str = "",
    left_relationships: Sequence[
        content.ContentRelationship
    ] = (),
    right_relationships: Sequence[
        content.ContentRelationship
    ] = (),
    left_observation_context: Optional[
        Mapping[str, Any]
    ] = None,
    right_observation_context: Optional[
        Mapping[str, Any]
    ] = None,
    recorded_at: Optional[str] = None,
    merit_baseline_mode: str = (
        MERIT_BASELINE_MODE_LEGACY
    ),
    browser_ingestor=(
        browser_ingestion
        .ingest_browser_capture
    ),
    semantic_manifest_runner=(
        semantic_execution
        .execute_semantic_manifest
    ),
    bridge_builder=(
        multimodal_intelligence_bridge
        .build_item_intelligence_bridge
    ),
    persistence_runner=(
        verified_persistence_execution
        .execute_verified_persistence
    ),
    observation_semantic_runner=(
        observation_semantics
        .assess_claim_observation_semantics_with_gemini
    ),
    intake_builder=(
        multimodal_adjudication_intake
        .build_multimodal_adjudication_intake
    ),
    adjudication_runner=(
        multimodal_adjudication_runtime
        .execute_multimodal_adjudication
    ),
    corroboration_runner=(
        multimodal_corroboration_runtime
        .execute_multimodal_corroboration
    ),
    shadow_runner=(
        multimodal_live_merit_shadow
        .evaluate_multimodal_live_merit_shadow
    ),
    workspace_factory=(
        media_execution.MediaWorkspace
    ),
    perception_executor_builder=None,
    left_perception_options: Optional[
        Mapping[str, Any]
    ] = None,
    right_perception_options: Optional[
        Mapping[str, Any]
    ] = None,
    structured_claim_shadow_enabled: bool = False,
    left_structured_claim_outputs: Optional[
        Mapping[str, Any]
    ] = None,
    right_structured_claim_outputs: Optional[
        Mapping[str, Any]
    ] = None,
    structured_claim_allowed_entity_keys: Sequence[
        str
    ] = (),
    structured_claim_allowed_entities: Optional[
        Mapping[str, Any]
    ] = None,
    structured_shadow_sink=None,
    structured_shadow_bridge_builder=None,
) -> Dict[str, Any]:
    """Run the multimodal intelligence path through shadow Merit only.

    This orchestration reuses the existing capture, semantic, bridge,
    persistence, adjudication, corroboration, and shadow-Merit runtimes.
    It never invokes the live Merit release service or consumes a release
    certificate.
    """

    left_binding = _require_bindings(
        left_bindings,
        label="Left",
    )
    right_binding = _require_bindings(
        right_bindings,
        label="Right",
    )

    if (
        _clean(
            left_binding.media_item_id
        )
        == _clean(
            right_binding.media_item_id
        )
    ):
        raise MultimodalPipelineInputError(
            "End-to-end corroboration requires "
            "two distinct verified media items."
        )

    (
        normalized_merit_baseline_mode,
        original_legacy,
    ) = _normalize_merit_baseline(
        legacy_score=legacy_score,
        merit_baseline_mode=(
            merit_baseline_mode
        ),
    )

    if semantic_interpreter is None:
        raise MultimodalPipelineInputError(
            "Semantic interpreter is required."
        )

    if connection_factory is None:
        raise MultimodalPipelineInputError(
            "Connection factory is required."
        )

    left_ingestion = _require_ingestion(
        browser_ingestor(
            left_capture
        ),
        label="Left",
    )

    right_ingestion = _require_ingestion(
        browser_ingestor(
            right_capture
        ),
        label="Right",
    )

    if (
        left_ingestion.item.item_id
        == right_ingestion.item.item_id
    ):
        raise MultimodalPipelineInputError(
            "End-to-end corroboration requires "
            "two distinct content items."
        )

    resolved_structured_claim_allowed_entity_keys = []

    for raw_key in tuple(
        structured_claim_allowed_entity_keys
        or ()
    ):
        entity_key = _clean(
            raw_key
        ).casefold()

        if (
            entity_key
            and entity_key
            not in (
                resolved_structured_claim_allowed_entity_keys
            )
        ):
            (
                resolved_structured_claim_allowed_entity_keys
                .append(
                    entity_key
                )
            )

    if isinstance(
        structured_claim_allowed_entities,
        Mapping,
    ):
        for raw_key in (
            structured_claim_allowed_entities
            .keys()
        ):
            entity_key = _clean(
                raw_key
            ).casefold()

            if (
                entity_key
                and entity_key
                not in (
                    resolved_structured_claim_allowed_entity_keys
                )
            ):
                (
                    resolved_structured_claim_allowed_entity_keys
                    .append(
                        entity_key
                    )
                )

    left_structured_claim_context = None
    right_structured_claim_context = None

    if structured_claim_shadow_enabled and left_structured_claim_outputs is None:
        left_structured_claim_context = (
            structured_claim_fusion
            .structured_claim_fusion_context_for_bindings(
                bindings=left_binding,
                allowed_entity_keys=tuple(
                    resolved_structured_claim_allowed_entity_keys
                ),
                allowed_entities=(
                    structured_claim_allowed_entities
                    if isinstance(
                        structured_claim_allowed_entities,
                        Mapping,
                    )
                    else None
                ),
            )
        )

    if structured_claim_shadow_enabled and right_structured_claim_outputs is None:
        right_structured_claim_context = (
            structured_claim_fusion
            .structured_claim_fusion_context_for_bindings(
                bindings=right_binding,
                allowed_entity_keys=tuple(
                    resolved_structured_claim_allowed_entity_keys
                ),
                allowed_entities=(
                    structured_claim_allowed_entities
                    if isinstance(
                        structured_claim_allowed_entities,
                        Mapping,
                    )
                    else None
                ),
            )
        )

    left_semantic_options = dict(
        left_perception_options
        or {}
    )

    right_semantic_options = dict(
        right_perception_options
        or {}
    )

    if (
        left_structured_claim_context
        is not None
    ):
        left_semantic_options[
            structured_claim_fusion
            .STRUCTURED_CLAIM_CONTEXT_OPTION
        ] = left_structured_claim_context

    if (
        right_structured_claim_context
        is not None
    ):
        right_semantic_options[
            structured_claim_fusion
            .STRUCTURED_CLAIM_CONTEXT_OPTION
        ] = right_structured_claim_context

    # Preflight both media items through semantic execution and the
    # dry-run bridge before either side is persisted.
    with ExitStack() as stack:
        left_workspace = stack.enter_context(
            workspace_factory()
        )
        right_workspace = stack.enter_context(
            workspace_factory()
        )

        left_manifest = (
            _require_semantic_manifest(
                semantic_manifest_runner(
                    left_ingestion
                    .artifact_manifest,
                    workspace=(
                        left_workspace
                    ),
                    interpreter=(
                        semantic_interpreter
                    ),
                    perception_executor_builder=(
                        perception_executor_builder
                    ),
                    perception_options=(
                        left_semantic_options
                    ),
                ),
                item_id=(
                    left_ingestion
                    .item
                    .item_id
                ),
                label="Left",
            )
        )

        right_manifest = (
            _require_semantic_manifest(
                semantic_manifest_runner(
                    right_ingestion
                    .artifact_manifest,
                    workspace=(
                        right_workspace
                    ),
                    interpreter=(
                        semantic_interpreter
                    ),
                    perception_executor_builder=(
                        perception_executor_builder
                    ),
                    perception_options=(
                        right_semantic_options
                    ),
                ),
                item_id=(
                    right_ingestion
                    .item
                    .item_id
                ),
                label="Right",
            )
        )

    if not structured_claim_shadow_enabled:
        left_plan = _require_bridge_plan(
            bridge_builder(
                item=left_ingestion.item,
                manifest=left_manifest,
                bindings=left_binding,
                relationships=tuple(
                    left_relationships
                ),
            ),
            item_id=(
                left_ingestion.item.item_id
            ),
            label="Left",
        )

        right_plan = _require_bridge_plan(
            bridge_builder(
                item=right_ingestion.item,
                manifest=right_manifest,
                bindings=right_binding,
                relationships=tuple(
                    right_relationships
                ),
            ),
            item_id=(
                right_ingestion.item.item_id
            ),
            label="Right",
        )

    else:
        shadow_builder_kwargs = {}

        if (
            structured_shadow_bridge_builder
            is not None
        ):
            shadow_builder_kwargs[
                "shadow_bridge_builder"
            ] = (
                structured_shadow_bridge_builder
            )

        left_shadow_bridge = (
            multimodal_structured_shadow_caller
            .build_runtime_bridge_plan(
                item=left_ingestion.item,
                manifest=left_manifest,
                bindings=left_binding,
                relationships=tuple(
                    left_relationships
                ),
                shadow_enabled=True,
                structured_outputs_by_candidate_id=(
                    left_structured_claim_outputs
                ),
                allowed_entity_keys=tuple(
                    resolved_structured_claim_allowed_entity_keys
                ),
                production_bridge_builder=(
                    bridge_builder
                ),
                **shadow_builder_kwargs,
            )
        )

        right_shadow_bridge = (
            multimodal_structured_shadow_caller
            .build_runtime_bridge_plan(
                item=right_ingestion.item,
                manifest=right_manifest,
                bindings=right_binding,
                relationships=tuple(
                    right_relationships
                ),
                shadow_enabled=True,
                structured_outputs_by_candidate_id=(
                    right_structured_claim_outputs
                ),
                allowed_entity_keys=tuple(
                    resolved_structured_claim_allowed_entity_keys
                ),
                production_bridge_builder=(
                    bridge_builder
                ),
                **shadow_builder_kwargs,
            )
        )

        left_plan = _require_bridge_plan(
            left_shadow_bridge[
                "production_plan"
            ],
            item_id=(
                left_ingestion.item.item_id
            ),
            label="Left",
        )

        right_plan = _require_bridge_plan(
            right_shadow_bridge[
                "production_plan"
            ],
            item_id=(
                right_ingestion.item.item_id
            ),
            label="Right",
        )

        (
            multimodal_structured_shadow_caller
            .emit_structured_shadow_diagnostic(
                sink=structured_shadow_sink,
                side="left",
                report=(
                    left_shadow_bridge[
                        "structured_shadow"
                    ]
                ),
            )
        )

        (
            multimodal_structured_shadow_caller
            .emit_structured_shadow_diagnostic(
                sink=structured_shadow_sink,
                side="right",
                report=(
                    right_shadow_bridge[
                        "structured_shadow"
                    ]
                ),
            )
        )

    (
        claim_id,
        left_candidate,
        right_candidate,
    ) = _select_common_claim(
        left_plan=left_plan,
        right_plan=right_plan,
        target_claim_id=(
            target_claim_id
        ),
    )

    left_selected_plan = (
        _filtered_plan(
            left_plan,
            left_candidate,
        )
    )

    right_selected_plan = (
        _filtered_plan(
            right_plan,
            right_candidate,
        )
    )

    # Existing #15 persistence is atomic per side. The overall #20
    # pipeline is intentionally not described as one cross-stage
    # transaction; downstream stages are independently idempotent.
    left_persistence = (
        _require_persistence_result(
            persistence_runner(
                plan=(
                    left_selected_plan
                ),
                bindings=(
                    left_binding
                ),
                connection_factory=(
                    connection_factory
                ),
                relationships=tuple(
                    left_relationships
                ),
            ),
            claim_id=claim_id,
            candidate_id=(
                left_candidate
                .candidate_id
            ),
            label="Left",
        )
    )

    right_persistence = (
        _require_persistence_result(
            persistence_runner(
                plan=(
                    right_selected_plan
                ),
                bindings=(
                    right_binding
                ),
                connection_factory=(
                    connection_factory
                ),
                relationships=tuple(
                    right_relationships
                ),
            ),
            claim_id=claim_id,
            candidate_id=(
                right_candidate
                .candidate_id
            ),
            label="Right",
        )
    )

    left_source = _observation_source(
        item=left_ingestion.item,
        manifest=left_manifest,
        candidate=left_candidate,
        label="Left",
    )

    right_source = _observation_source(
        item=right_ingestion.item,
        manifest=right_manifest,
        candidate=right_candidate,
        label="Right",
    )

    left_claim = _claim_payload(
        claim_id=claim_id,
        plan=left_selected_plan,
        candidate=left_candidate,
    )

    right_claim = _claim_payload(
        claim_id=claim_id,
        plan=right_selected_plan,
        candidate=right_candidate,
    )

    left_semantics = (
        _require_semantic_assessment(
            observation_semantic_runner(
                claim=left_claim,
                source=left_source,
                context=dict(
                    left_observation_context
                    or {}
                ),
                client=gemini_client,
                client_key=(
                    gemini_client_key
                ),
                generator=gemini_generator,
            ),
            claim_id=claim_id,
            source_url=(
                left_source[
                    "final_url"
                ]
            ),
            label="Left",
        )
    )

    right_semantics = (
        _require_semantic_assessment(
            observation_semantic_runner(
                claim=right_claim,
                source=right_source,
                context=dict(
                    right_observation_context
                    or {}
                ),
                client=gemini_client,
                client_key=(
                    gemini_client_key
                ),
                generator=gemini_generator,
            ),
            claim_id=claim_id,
            source_url=(
                right_source[
                    "final_url"
                ]
            ),
            label="Right",
        )
    )

    left_intake = (
        _require_intake_result(
            intake_builder(
                claim_id=claim_id,
                media_item_id=(
                    left_binding
                    .media_item_id
                ),
                semantic_result=(
                    left_semantics[
                        "assessment"
                    ]
                ),
                aligned_evidence_ids=[
                    left_persistence[
                        "candidate_rows"
                    ][0][
                        "evidence_id"
                    ]
                ],
                source_observation_ids=[
                    left_persistence[
                        "candidate_rows"
                    ][0][
                        "source_observation_id"
                    ]
                ],
                connection_factory=(
                    connection_factory
                ),
            ),
            claim_id=claim_id,
            media_item_id=(
                left_binding
                .media_item_id
            ),
            label="Left",
        )
    )

    right_intake = (
        _require_intake_result(
            intake_builder(
                claim_id=claim_id,
                media_item_id=(
                    right_binding
                    .media_item_id
                ),
                semantic_result=(
                    right_semantics[
                        "assessment"
                    ]
                ),
                aligned_evidence_ids=[
                    right_persistence[
                        "candidate_rows"
                    ][0][
                        "evidence_id"
                    ]
                ],
                source_observation_ids=[
                    right_persistence[
                        "candidate_rows"
                    ][0][
                        "source_observation_id"
                    ]
                ],
                connection_factory=(
                    connection_factory
                ),
            ),
            claim_id=claim_id,
            media_item_id=(
                right_binding
                .media_item_id
            ),
            label="Right",
        )
    )

    left_adjudication = (
        _require_adjudication_result(
            adjudication_runner(
                intake=left_intake,
                as_of=as_of,
                connection_factory=(
                    connection_factory
                ),
                recorded_at=(
                    recorded_at
                ),
            ),
            claim_id=claim_id,
            media_item_id=(
                left_binding
                .media_item_id
            ),
            label="Left",
        )
    )

    right_adjudication = (
        _require_adjudication_result(
            adjudication_runner(
                intake=right_intake,
                as_of=as_of,
                connection_factory=(
                    connection_factory
                ),
                recorded_at=(
                    recorded_at
                ),
            ),
            claim_id=claim_id,
            media_item_id=(
                right_binding
                .media_item_id
            ),
            label="Right",
        )
    )

    corroboration = (
        _require_corroboration_result(
            corroboration_runner(
                claim_id=claim_id,
                left_intake=(
                    left_intake
                ),
                right_intake=(
                    right_intake
                ),
                left_adjudication=(
                    left_adjudication
                ),
                right_adjudication=(
                    right_adjudication
                ),
                connection_factory=(
                    connection_factory
                ),
                recorded_at=(
                    recorded_at
                ),
            ),
            claim_id=claim_id,
        )
    )

    if (
        normalized_merit_baseline_mode
        == MERIT_BASELINE_MODE_LEGACY
    ):
        if original_legacy is None:
            raise MultimodalPipelineIntegrityError(
                "Legacy Merit baseline disappeared before shadow evaluation."
            )

        shadow = _require_shadow_result(
            shadow_runner(
                corroboration_result=(
                    corroboration
                ),
                legacy_score=copy.deepcopy(
                    original_legacy
                ),
            ),
            claim_id=claim_id,
            legacy_score=(
                original_legacy
            ),
        )

        if (
            not isinstance(legacy_score, Mapping)
            or dict(legacy_score) != original_legacy
        ):
            raise MultimodalPipelineIntegrityError(
                "End-to-end runtime mutated the caller legacy score."
            )
    else:
        if legacy_score is not None:
            raise MultimodalPipelineIntegrityError(
                "No-Merit execution acquired an unexpected legacy score."
            )
        shadow = _no_merit_shadow_result(
            claim_id=claim_id
        )

    return {
        "version": (
            MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": claim_id,
        "subject_key": (
            left_selected_plan
            .subject_key
        ),
        "left_item_id": (
            left_ingestion
            .item
            .item_id
        ),
        "right_item_id": (
            right_ingestion
            .item
            .item_id
        ),
        "left_media_item_id": (
            left_binding
            .media_item_id
        ),
        "right_media_item_id": (
            right_binding
            .media_item_id
        ),
        "left_candidate_id": (
            left_candidate
            .candidate_id
        ),
        "right_candidate_id": (
            right_candidate
            .candidate_id
        ),
        "stages": {
            "left": {
                "ingestion": (
                    _item_summary(
                        left_ingestion.item
                    )
                ),
                "semantic_manifest": (
                    _manifest_summary(
                        left_manifest
                    )
                ),
                "persistence": (
                    left_persistence
                ),
                "observation_semantics": (
                    left_semantics[
                        "wrapper"
                    ]
                ),
                "adjudication_intake": (
                    left_intake
                ),
                "adjudication": (
                    left_adjudication
                ),
            },
            "right": {
                "ingestion": (
                    _item_summary(
                        right_ingestion.item
                    )
                ),
                "semantic_manifest": (
                    _manifest_summary(
                        right_manifest
                    )
                ),
                "persistence": (
                    right_persistence
                ),
                "observation_semantics": (
                    right_semantics[
                        "wrapper"
                    ]
                ),
                "adjudication_intake": (
                    right_intake
                ),
                "adjudication": (
                    right_adjudication
                ),
            },
            "corroboration": (
                corroboration
            ),
            "live_merit_shadow": (
                shadow
            ),
        },
        "live_score": copy.deepcopy(
            shadow["live_score"]
        ),
        "shadow": {
            "proposed_adjustment": (
                shadow[
                    "proposed_adjustment"
                ]
            ),
            "proposed_shadow_total": (
                shadow[
                    "proposed_shadow_total"
                ]
            ),
            "boost_eligible": (
                shadow[
                    "shadow_boost_eligible_under_overlay"
                ]
            ),
        },
        "policy": {
            "browser_capture_preflighted_before_persistence":
                True,
            "semantic_execution_preflighted_before_persistence":
                True,
            "exact_common_claim_required":
                True,
            "heuristic_cross_item_claim_matching":
                False,
            "verified_bindings_supplied_by_caller":
                True,
            "verified_bindings_rechecked_downstream":
                True,
            "adjudication_intake_is_candidate_scoped":
                True,
            "model_observation_semantics_are_claim_relative":
                True,
            "multimodal_evidence_remains_unverified":
                True,
            "model_output_does_not_establish_truth":
                True,
            "model_output_does_not_establish_independence":
                True,
            "independence_uses_existing_verifier_only":
                True,
            "stage_persistence_uses_existing_atomic_runtimes":
                True,
            "pipeline_is_cross_stage_atomic":
                False,
            "idempotent_stage_replay_supported":
                True,
            "merit_baseline_mode":
                normalized_merit_baseline_mode,
            "merit_baseline_available":
                (
                    normalized_merit_baseline_mode
                    == MERIT_BASELINE_MODE_LEGACY
                ),
            "merit_shadow_evaluated":
                (
                    normalized_merit_baseline_mode
                    == MERIT_BASELINE_MODE_LEGACY
                ),
            "synthetic_merit_baseline_used":
                False,
            "merit_shadow_only":
                True,
            "live_release_not_called":
                True,
            "release_certificate_not_consumed":
                True,
            "live_enablement_authorized":
                False,
            "score_effect_applied":
                False,
            "establishes_truth":
                False,
            "affects_live_merit":
                False,
        },
    }
