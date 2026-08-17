from __future__ import annotations

import math

from typing import Any, Dict, Mapping

from app.services import analysis_cache
from app.services import article_rules
from app.services import browser_capture_inbox
from app.services import content_resolution
from app.services import inbox_candidate_discovery
from app.services import inbox_candidate_shadow_orchestration
from app.services import inbox_history_auto_shadow_orchestration
from app.services import inbox_no_merit_auto_shadow_orchestration


MULTIMODAL_INBOX_STORY_CLUSTER_VERSION = (
    "multimodal-inbox-story-cluster-v1"
)

MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION = (
    "multimodal-inbox-cluster-selection-v1"
)


class MultimodalInboxStoryClusterError(RuntimeError):
    pass


class MultimodalInboxStoryClusterInputError(
    MultimodalInboxStoryClusterError
):
    pass


class MultimodalInboxStoryClusterNotReady(
    MultimodalInboxStoryClusterError
):
    pass


class MultimodalInboxStoryClusterLookupError(
    MultimodalInboxStoryClusterError
):
    pass


class MultimodalInboxStoryClusterProviderUnavailable(
    MultimodalInboxStoryClusterError
):
    pass


class MultimodalInboxStoryClusterExecutionError(
    MultimodalInboxStoryClusterError
):
    pass


class MultimodalInboxStoryClusterIntegrityError(
    MultimodalInboxStoryClusterError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _bounded_int(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise MultimodalInboxStoryClusterInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxStoryClusterInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise MultimodalInboxStoryClusterInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _finite_score(value: Any) -> float:
    if isinstance(value, bool):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate score must be numeric."
        )

    try:
        score = float(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate score must be numeric."
        ) from error

    if (
        not math.isfinite(score)
        or score < 0.0
        or score > 1.0
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate score must be finite and bounded."
        )

    return score


def _load_anchor(
    *,
    anchor_capture_record_id: str,
    connection_factory,
    capture_loader,
) -> Dict[str, Any]:
    try:
        loaded = capture_loader(
            capture_record_id=(
                anchor_capture_record_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    except browser_capture_inbox.BrowserCaptureInboxInputError as error:
        raise MultimodalInboxStoryClusterInputError(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxNotFoundError as error:
        raise MultimodalInboxStoryClusterNotReady(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxPersistenceError as error:
        raise MultimodalInboxStoryClusterLookupError(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxIntegrityError as error:
        raise MultimodalInboxStoryClusterIntegrityError(
            str(error)
        ) from error

    if not isinstance(loaded, Mapping):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Stored anchor capture is invalid."
        )

    result = dict(loaded)

    if (
        _clean(result.get("version"))
        != browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION
        or _clean(result.get("capture_record_id"))
        != anchor_capture_record_id
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Stored anchor capture identity/version changed."
        )

    policy = result.get("policy")

    if (
        not isinstance(policy, Mapping)
        or policy.get("record_is_untrusted") is not True
        or policy.get("integrity_rechecked_on_load") is not True
        or policy.get("load_is_read_only") is not True
        or bool(policy.get("affects_live_merit"))
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Stored anchor capture safety policy changed."
        )

    return result


def _validate_discovery(
    value: Any,
    *,
    anchor_capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox discovery result is invalid."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != (
            inbox_candidate_discovery
            .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        )
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox discovery version changed."
        )

    if (
        _clean(result.get("anchor_capture_record_id"))
        != anchor_capture_record_id
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox discovery changed anchor scope."
        )

    status = _clean(
        result.get("status")
    ).lower()

    if status == "no_candidates":
        raise MultimodalInboxStoryClusterNotReady(
            "No current inbox candidates are available for clustering."
        )

    if status != "candidates_available":
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox discovery status is invalid."
        )

    candidates = result.get("pair_candidates")

    if not isinstance(candidates, list):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox discovery candidate list is invalid."
        )

    policy = result.get("policy")

    required_true = (
        "read_only_discovery",
        "inbox_records_remain_untrusted",
        "anchor_capture_text_is_not_a_verified_claim",
        "entity_matching_is_exact_alias_or_canonical_name_only",
        "entity_candidates_do_not_verify_subject",
        "deterministic_score_is_ranking_only",
        "semantic_same_claim_is_candidate_only",
        "semantic_stance_does_not_establish_truth",
        "semantic_dependency_does_not_establish_independence",
        "candidate_discovery_does_not_establish_corroboration",
    )

    for field in required_true:
        if (
            not isinstance(policy, Mapping)
            or policy.get(field) is not True
        ):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox discovery safety boundary missing: "
                + field
            )

    for field in (
        "creates_story",
        "creates_claim",
        "creates_observation",
        "creates_evidence",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    ):
        if (
            isinstance(policy, Mapping)
            and bool(policy.get(field))
        ):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox discovery enabled forbidden field: "
                + field
            )

    return result


def _candidate_policy(candidate: Mapping[str, Any]):
    policy = candidate.get("policy")

    required_true = (
        "candidate_only",
        "same_story_not_established",
        "same_claim_not_established",
        "subject_not_verified",
        "independence_not_established",
        "corroboration_not_established",
    )

    for field in required_true:
        if (
            not isinstance(policy, Mapping)
            or policy.get(field) is not True
        ):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox candidate safety boundary missing: "
                + field
            )

    if (
        isinstance(policy, Mapping)
        and bool(policy.get("affects_live_merit"))
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate unexpectedly affects Live Merit."
        )


def _shared_entity_ids(
    candidate: Mapping[str, Any],
):
    signals = candidate.get("signals")

    if not isinstance(signals, Mapping):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate signals are missing."
        )

    value = signals.get("shared_entity_ids")

    if not isinstance(value, list):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Inbox candidate shared entity IDs are invalid."
        )

    ids = []
    seen = set()

    for raw in value:
        entity_id = _clean(raw)

        if not entity_id:
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox candidate contains an empty shared entity ID."
            )

        if entity_id in seen:
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox candidate contains duplicate shared entity IDs."
            )

        seen.add(entity_id)
        ids.append(entity_id)

    return sorted(ids)


def _cluster_selection(
    discovery: Mapping[str, Any],
) -> Dict[str, Any]:
    candidates = discovery.get("pair_candidates", [])
    groups: Dict[str, list] = {}
    rejected = []
    seen_ids = set()

    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox discovery candidate is invalid."
            )

        candidate = dict(raw)
        candidate_id = _clean(
            candidate.get("capture_record_id")
        )

        if not candidate_id:
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox discovery candidate ID is missing."
            )

        if candidate_id in seen_ids:
            raise MultimodalInboxStoryClusterIntegrityError(
                "Inbox discovery returned duplicate candidate IDs."
            )

        seen_ids.add(candidate_id)
        _candidate_policy(candidate)
        score = _finite_score(
            candidate.get("candidate_score")
        )
        shared_ids = _shared_entity_ids(candidate)

        if len(shared_ids) != 1:
            rejected.append({
                "capture_record_id": candidate_id,
                "reason": (
                    "no_shared_exact_entity"
                    if not shared_ids
                    else "multiple_shared_exact_entities"
                ),
                "shared_entity_count": len(shared_ids),
                "candidate_score": score,
            })
            continue

        member = {
            "capture_record_id": candidate_id,
            "subject_entity_id": shared_ids[0],
            "candidate_score": score,
            "candidate_reasons": (
                list(candidate.get("candidate_reasons", []))
                if isinstance(
                    candidate.get("candidate_reasons", []),
                    list,
                )
                else []
            ),
            "shared_entity_ids": shared_ids,
            "identical_normalized_content": bool(
                candidate.get("signals", {}).get(
                    "identical_normalized_content"
                )
            ),
        }

        groups.setdefault(
            shared_ids[0],
            [],
        ).append(member)

    if not groups:
        raise MultimodalInboxStoryClusterNotReady(
            "No inbox candidate has exactly one shared exact entity."
        )

    if len(groups) != 1:
        raise MultimodalInboxStoryClusterNotReady(
            "Automatic story clustering is subject-ambiguous; multiple exact subject partitions are present."
        )

    subject_entity_id = next(iter(groups))
    members = groups[subject_entity_id]
    members.sort(
        key=lambda row: (
            -float(row["candidate_score"]),
            row["capture_record_id"],
        )
    )

    return {
        "version": MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION,
        "status": "cluster_selected",
        "subject_entity_id": subject_entity_id,
        "members": members,
        "member_count": len(members),
        "rejected_candidates": rejected,
        "rejected_candidate_count": len(rejected),
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


def select_multisource_inbox_cluster(
    *,
    anchor_capture_record_id: str,
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    discovery_runner=(
        inbox_candidate_discovery
        .discover_multimodal_inbox_candidates
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(anchor_capture_record_id)

    if not anchor_id:
        raise MultimodalInboxStoryClusterInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxStoryClusterInputError(
            "Anchor capture record ID is too long."
        )

    scan_limit = _bounded_int(
        scan_limit,
        label="Inbox scan limit",
        minimum=1,
        maximum=500,
    )
    max_candidates = _bounded_int(
        max_candidates,
        label="Candidate limit",
        minimum=1,
        maximum=50,
    )

    if connection_factory is None:
        raise MultimodalInboxStoryClusterInputError(
            "Connection factory is required."
        )

    try:
        discovery_raw = discovery_runner(
            anchor_capture_record_id=anchor_id,
            connection_factory=connection_factory,
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            semantic_assessments=0,
            gemini_client=None,
            gemini_client_key="anonymous",
            gemini_generator=None,
        )
    except inbox_candidate_discovery.InboxCandidateDiscoveryInputError as error:
        raise MultimodalInboxStoryClusterInputError(
            str(error)
        ) from error
    except inbox_candidate_discovery.InboxCandidateDiscoveryNotFoundError as error:
        raise MultimodalInboxStoryClusterNotReady(
            str(error)
        ) from error
    except inbox_candidate_discovery.InboxCandidateDiscoveryLookupError as error:
        raise MultimodalInboxStoryClusterLookupError(
            str(error)
        ) from error
    except inbox_candidate_discovery.InboxCandidateDiscoveryIntegrityError as error:
        raise MultimodalInboxStoryClusterIntegrityError(
            str(error)
        ) from error

    discovery = _validate_discovery(
        discovery_raw,
        anchor_capture_record_id=anchor_id,
    )
    selection = _cluster_selection(discovery)

    return {
        "version": MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION,
        "status": "cluster_selected",
        "anchor_capture_record_id": anchor_id,
        "subject_entity_id": selection["subject_entity_id"],
        "members": selection["members"],
        "member_count": selection["member_count"],
        "rejected_candidates": selection["rejected_candidates"],
        "rejected_candidate_count": selection[
            "rejected_candidate_count"
        ],
        "policy": dict(selection["policy"]),
    }


def _baseline_resolution(
    *,
    anchor: Mapping[str, Any],
    anchor_capture_record_id: str,
    analysis_version: str,
    scoring_version: str,
    connection_factory,
) -> Dict[str, Any]:
    platform = _clean(anchor.get("platform")).lower()
    surface = _clean(
        anchor.get("platform_surface")
    ).lower()

    if platform == "web" and surface == "article":
        current_analysis_version = _clean(analysis_version)
        current_scoring_version = _clean(scoring_version)

        if not current_analysis_version:
            raise MultimodalInboxStoryClusterInputError(
                "Current analysis version is required for article clustering."
            )

        if not current_scoring_version:
            raise MultimodalInboxStoryClusterInputError(
                "Current scoring version is required for article clustering."
            )

        try:
            descriptor = (
                inbox_history_auto_shadow_orchestration
                ._article_descriptor(
                    anchor,
                    content_hash_resolver=(
                        analysis_cache.analysis_content_hash
                    ),
                    clean_html=article_rules.clean_html,
                    url_normalizer=(
                        content_resolution.normalized_analysis_url
                    ),
                )
            )
            resolved = (
                inbox_history_auto_shadow_orchestration
                ._resolve_baseline(
                    descriptor=descriptor,
                    analysis_version=(
                        current_analysis_version
                    ),
                    scoring_version=(
                        current_scoring_version
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )
        except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowBaselineUnavailable as error:
            raise MultimodalInboxStoryClusterNotReady(
                str(error)
            ) from error
        except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowLookupError as error:
            raise MultimodalInboxStoryClusterLookupError(
                str(error)
            ) from error
        except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowInputError as error:
            raise MultimodalInboxStoryClusterInputError(
                str(error)
            ) from error
        except inbox_history_auto_shadow_orchestration.MultimodalInboxHistoryAutoShadowIntegrityError as error:
            raise MultimodalInboxStoryClusterIntegrityError(
                str(error)
            ) from error

        return {
            "execution_mode": "article_history_merit",
            "merit_baseline_mode": "legacy_merit",
            "legacy_score": resolved["legacy_score"],
            "baseline": resolved["baseline"],
        }

    if (
        platform
        in inbox_no_merit_auto_shadow_orchestration
        .SUPPORTED_NON_ARTICLE_PLATFORMS
    ):
        return {
            "execution_mode": "non_article_no_merit",
            "merit_baseline_mode": "not_applicable",
            "legacy_score": None,
            "baseline": {
                "mode": "not_applicable",
                "reason": (
                    "no_legacy_merit_baseline_for_non_article"
                ),
                "platform": platform,
                "surface": surface,
                "legacy_score": None,
                "synthetic_merit_baseline_used": False,
            },
        }

    raise MultimodalInboxStoryClusterInputError(
        "Automatic story clustering does not support this anchor platform/surface."
    )


def _validate_member_shadow(
    value: Any,
    *,
    anchor_capture_record_id: str,
    candidate_capture_record_id: str,
    subject_entity_id: str,
    merit_baseline_mode: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Cluster member shadow result is invalid."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        )
        or _clean(result.get("status")).lower()
        != "completed_shadow"
        or _clean(result.get("anchor_capture_record_id"))
        != anchor_capture_record_id
        or _clean(result.get("candidate_capture_record_id"))
        != candidate_capture_record_id
        or _clean(result.get("subject_entity_id"))
        != subject_entity_id
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Cluster member shadow scope/version changed."
        )

    claim_id = _clean(result.get("claim_id"))

    if not claim_id:
        raise MultimodalInboxStoryClusterIntegrityError(
            "Cluster member shadow did not expose a claim ID."
        )

    policy = result.get("policy")

    required_true = (
        "candidate_must_be_currently_discovered",
        "discovery_gate_is_read_only",
        "subject_entity_must_be_shared_exact_candidate",
        "subject_descriptor_loaded_server_side",
        "downstream_exact_common_claim_required",
        "binding_ids_generated_server_side",
        "shadow_adapter_reverifies_bindings",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if (
            not isinstance(policy, Mapping)
            or policy.get(field) is not True
        ):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Cluster member safety boundary missing: "
                + field
            )

    if (
        policy.get("merit_baseline_mode")
        != merit_baseline_mode
        or bool(policy.get("synthetic_merit_baseline_used"))
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Cluster member Merit baseline state changed."
        )

    expected_merit = merit_baseline_mode == "legacy_merit"

    if (
        bool(policy.get("merit_baseline_available"))
        != expected_merit
        or bool(policy.get("merit_shadow_evaluated"))
        != expected_merit
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Cluster member Merit evaluation state changed."
        )

    for field in (
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(policy.get(field)):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Cluster member enabled forbidden field: "
                + field
            )

    return result


def execute_multisource_inbox_story_cluster_shadow(
    *,
    anchor_capture_record_id: str,
    analysis_version: str,
    scoring_version: str,
    target_claim_id: str = "",
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    capture_loader=(
        browser_capture_inbox.load_browser_capture_record
    ),
    selection_runner=select_multisource_inbox_cluster,
    candidate_shadow_runner=(
        inbox_candidate_shadow_orchestration
        .execute_multimodal_inbox_candidate_shadow
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(anchor_capture_record_id)

    if not anchor_id:
        raise MultimodalInboxStoryClusterInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxStoryClusterInputError(
            "Anchor capture record ID is too long."
        )

    scan_limit = _bounded_int(
        scan_limit,
        label="Inbox scan limit",
        minimum=1,
        maximum=500,
    )
    max_candidates = _bounded_int(
        max_candidates,
        label="Candidate limit",
        minimum=1,
        maximum=50,
    )

    if connection_factory is None:
        raise MultimodalInboxStoryClusterInputError(
            "Connection factory is required."
        )

    if gemini_client is None:
        raise MultimodalInboxStoryClusterProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalInboxStoryClusterProviderUnavailable(
            "Gemini generator is unavailable."
        )

    anchor = _load_anchor(
        anchor_capture_record_id=anchor_id,
        connection_factory=connection_factory,
        capture_loader=capture_loader,
    )
    baseline = _baseline_resolution(
        anchor=anchor,
        anchor_capture_record_id=anchor_id,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        connection_factory=connection_factory,
    )

    try:
        selection_raw = selection_runner(
            anchor_capture_record_id=anchor_id,
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            connection_factory=connection_factory,
        )
    except MultimodalInboxStoryClusterError:
        raise
    except Exception as error:
        raise MultimodalInboxStoryClusterExecutionError(
            "Story-cluster selection failed."
        ) from error

    if not isinstance(selection_raw, Mapping):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Story-cluster selection result is invalid."
        )

    selection = dict(selection_raw)

    if (
        _clean(selection.get("version"))
        != MULTIMODAL_INBOX_CLUSTER_SELECTION_VERSION
        or _clean(selection.get("status")).lower()
        != "cluster_selected"
        or _clean(selection.get("anchor_capture_record_id"))
        != anchor_id
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Story-cluster selection scope/version changed."
        )

    subject_entity_id = _clean(
        selection.get("subject_entity_id")
    )
    members = selection.get("members")

    if (
        not subject_entity_id
        or not isinstance(members, list)
        or not members
    ):
        raise MultimodalInboxStoryClusterIntegrityError(
            "Story-cluster selection is incomplete."
        )

    completed = []
    rejected = []

    for member in members:
        if not isinstance(member, Mapping):
            raise MultimodalInboxStoryClusterIntegrityError(
                "Story-cluster member is invalid."
            )

        candidate_id = _clean(
            member.get("capture_record_id")
        )

        if not candidate_id:
            raise MultimodalInboxStoryClusterIntegrityError(
                "Story-cluster member ID is missing."
            )

        try:
            raw = candidate_shadow_runner(
                anchor_capture_record_id=anchor_id,
                candidate_capture_record_id=candidate_id,
                subject_entity_id=subject_entity_id,
                legacy_score=baseline["legacy_score"],
                merit_baseline_mode=(
                    baseline["merit_baseline_mode"]
                ),
                target_claim_id=_clean(target_claim_id),
                scan_limit=scan_limit,
                max_candidates=max_candidates,
                connection_factory=connection_factory,
                gemini_client=gemini_client,
                gemini_client_key=(
                    _clean(gemini_client_key)
                    or "anonymous"
                ),
                gemini_generator=gemini_generator,
            )
        except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowClaimSelectionError as error:
            rejected.append({
                "capture_record_id": candidate_id,
                "reason": "downstream_no_exact_common_claim",
                "error": str(error)[:240],
            })
            continue
        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowDiscoveryError,
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError,
        ) as error:
            raise MultimodalInboxStoryClusterNotReady(
                str(error)
            ) from error
        except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowProviderUnavailable as error:
            raise MultimodalInboxStoryClusterProviderUnavailable(
                str(error)
            ) from error
        except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowExecutionError as error:
            raise MultimodalInboxStoryClusterExecutionError(
                str(error)
            ) from error
        except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowInputError as error:
            raise MultimodalInboxStoryClusterInputError(
                str(error)
            ) from error
        except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowIntegrityError as error:
            raise MultimodalInboxStoryClusterIntegrityError(
                str(error)
            ) from error

        shadow = _validate_member_shadow(
            raw,
            anchor_capture_record_id=anchor_id,
            candidate_capture_record_id=candidate_id,
            subject_entity_id=subject_entity_id,
            merit_baseline_mode=(
                baseline["merit_baseline_mode"]
            ),
        )

        completed.append({
            "capture_record_id": candidate_id,
            "claim_id": shadow["claim_id"],
            "candidate_score": _finite_score(
                member.get("candidate_score")
            ),
            "candidate_reasons": list(
                member.get("candidate_reasons", [])
            )
            if isinstance(
                member.get("candidate_reasons", []),
                list,
            )
            else [],
            "orchestration": shadow,
        })

    if not completed:
        raise MultimodalInboxStoryClusterNotReady(
            "No story-cluster member passed the downstream exact-common-claim gate."
        )

    grouped: Dict[str, list] = {}

    for member in completed:
        grouped.setdefault(
            member["claim_id"],
            [],
        ).append(
            member["capture_record_id"]
        )

    claim_ids = sorted(grouped)
    claim_groups = [
        {
            "claim_id": claim_id,
            "member_capture_record_ids": sorted(
                grouped[claim_id]
            ),
            "member_count": len(grouped[claim_id]),
        }
        for claim_id in claim_ids
    ]
    completed_ids = [
        member["capture_record_id"]
        for member in completed
    ]

    return {
        "version": MULTIMODAL_INBOX_STORY_CLUSTER_VERSION,
        "status": "completed_shadow",
        "anchor_capture_record_id": anchor_id,
        "execution_mode": baseline["execution_mode"],
        "claim_id": (
            claim_ids[0]
            if len(claim_ids) == 1
            else ""
        ),
        "claim_ids": claim_ids,
        "claim_groups": claim_groups,
        "selected_subject_entity_id": subject_entity_id,
        "selected_candidate_capture_record_id": (
            completed_ids[0]
            if len(completed_ids) == 1
            else ""
        ),
        "selected_candidate_capture_record_ids": completed_ids,
        "cluster_selection": selection,
        "completed_members": completed,
        "rejected_members": rejected,
        "baseline_resolution": baseline["baseline"],
        "policy": {
            "cluster_is_routing_candidate_only": True,
            "cluster_selection_is_read_only": True,
            "same_story_not_established_by_cluster": True,
            "same_claim_not_established_by_cluster": True,
            "claim_groups_formed_only_from_downstream_exact_claim_ids": True,
            "each_completed_member_passed_exact_common_claim_gate": True,
            "each_member_revalidated_by_candidate_gate": True,
            "candidate_scores_are_ranking_only": True,
            "cluster_does_not_write_story_records_directly": True,
            "cluster_does_not_link_story_media_directly": True,
            "cluster_level_corroboration_not_established": True,
            "cluster_level_independence_not_established": True,
            "cluster_merit_aggregation_performed": False,
            "merit_baseline_mode": baseline["merit_baseline_mode"],
            "merit_baseline_available": (
                baseline["merit_baseline_mode"]
                == "legacy_merit"
            ),
            "merit_shadow_evaluated_per_completed_member": (
                baseline["merit_baseline_mode"]
                == "legacy_merit"
            ),
            "synthetic_merit_baseline_used": False,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
