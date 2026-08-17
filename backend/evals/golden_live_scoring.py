from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from .golden_capture import clean
from .golden_dataset import build_golden_cases
from .golden_live_budget import MultimodalGoldenLiveInputError

DEFAULT_LIVE_CASE_IDS = (
    "football_bellingham_real_madrid_2023",
    "f1_alonso_aston_extension_2024",
)


def selected_cases(case_ids: Sequence[str]) -> list[Dict[str, Any]]:
    normalized = [clean(value) for value in case_ids]
    if not normalized or any(not value for value in normalized):
        raise MultimodalGoldenLiveInputError("Live golden case IDs cannot be empty.")
    if len(set(normalized)) != len(normalized):
        raise MultimodalGoldenLiveInputError("Live golden case IDs must be unique.")
    available = {case["case_id"]: case for case in build_golden_cases()}
    unknown = [case_id for case_id in normalized if case_id not in available]
    if unknown:
        raise MultimodalGoldenLiveInputError(
            "Unknown live golden case IDs: " + ", ".join(unknown)
        )
    return [available[case_id] for case_id in normalized]


def walk_true_flags(value: Any, keys: Iterable[str]) -> set[str]:
    wanted = set(keys)
    found = set()

    def visit(node: Any):
        if isinstance(node, Mapping):
            for key, child in node.items():
                if key in wanted and child is True:
                    found.add(key)
                visit(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(value)
    return found


def labels_from_members(members: Any, *, id_to_label: Mapping[str, str]) -> list[str]:
    if not isinstance(members, list):
        return []
    labels = []
    for raw in members:
        if not isinstance(raw, Mapping):
            continue
        label = clean(id_to_label.get(clean(raw.get("capture_record_id"))))
        if label and label not in labels:
            labels.append(label)
    return labels


def score_case(*, case: Mapping[str, Any], observed: Mapping[str, Any]) -> Dict[str, Any]:
    full = case["expectations"]["full_pipeline"]
    expected_status = clean(full.get("expected_status")) or "completed"
    failures = []
    if clean(observed.get("status")) != expected_status:
        failures.append("status")
    if expected_status == "completed":
        accepted = set(observed.get("accepted_member_labels") or [])
        rejected = set(observed.get("rejected_member_labels") or [])
        if not set(full["required_accept_labels"]).issubset(accepted):
            failures.append("accepted_member_recall")
        if not set(full["required_reject_labels"]).issubset(rejected):
            failures.append("rejected_member_recall")
        if int(observed.get("story_count") or 0) != int(full["expected_story_count"]):
            failures.append("story_count")
        if clean(observed.get("merit_baseline_mode")) != clean(
            full["expected_merit_baseline_mode"]
        ):
            failures.append("merit_baseline_mode")

    hard_fields = (
        "synthetic_merit_baseline_used",
        "affects_live_merit",
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "live_enablement_authorized",
    )
    hard = [field for field in hard_fields if bool(observed.get(field))]
    if bool(observed.get("independence_inferred_from_identical_content")):
        hard.append("identical_content_independence")
    return {
        "case_id": case["case_id"],
        "quality_status": "pass" if not failures else "fail",
        "quality_failures": failures,
        "hard_safety_status": "pass" if not hard else "fail",
        "hard_safety_failures": hard,
    }


def completed_case(
    *,
    case: Mapping[str, Any],
    cluster: Mapping[str, Any],
    graph: Mapping[str, Any],
    id_to_label: Mapping[str, str],
) -> Dict[str, Any]:
    safety_keys = (
        "synthetic_merit_baseline_used",
        "affects_live_merit",
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "live_enablement_authorized",
    )
    true_flags = walk_true_flags({"cluster": cluster, "graph": graph}, safety_keys)
    selection = cluster.get("cluster_selection")
    selected = selection.get("members", []) if isinstance(selection, Mapping) else []
    identical = any(
        isinstance(member, Mapping)
        and bool(member.get("identical_normalized_content"))
        for member in selected
    )
    observed = {
        "case_id": case["case_id"],
        "status": "completed",
        "accepted_member_labels": labels_from_members(
            cluster.get("completed_members"), id_to_label=id_to_label
        ),
        "rejected_member_labels": labels_from_members(
            cluster.get("rejected_members"), id_to_label=id_to_label
        ),
        "story_count": int(graph.get("story_count") or 0),
        "story_ids": list(graph.get("story_ids", []) or []),
        "claim_ids": list(cluster.get("claim_ids", []) or []),
        "merit_baseline_mode": clean(
            (cluster.get("policy") or {}).get("merit_baseline_mode")
        ),
        "synthetic_merit_baseline_used": "synthetic_merit_baseline_used" in true_flags,
        "affects_live_merit": "affects_live_merit" in true_flags,
        "score_effect_applied": "score_effect_applied" in true_flags,
        "establishes_truth": "establishes_truth" in true_flags,
        "establishes_authority": "establishes_authority" in true_flags,
        "establishes_independence": "establishes_independence" in true_flags,
        "live_enablement_authorized": "live_enablement_authorized" in true_flags,
        "independence_inferred_from_identical_content": (
            identical and "establishes_independence" in true_flags
        ),
    }
    observed["score"] = score_case(case=case, observed=observed)
    return observed


def noncompleted_case(*, case: Mapping[str, Any], status: str, error: Exception) -> Dict[str, Any]:
    observed = {
        "case_id": case["case_id"],
        "status": status,
        "error_type": type(error).__name__,
        "error": str(error)[:240],
        "accepted_member_labels": [],
        "rejected_member_labels": [],
        "story_count": 0,
        "merit_baseline_mode": "not_applicable",
        "synthetic_merit_baseline_used": False,
        "affects_live_merit": False,
        "score_effect_applied": False,
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_independence": False,
        "live_enablement_authorized": False,
        "independence_inferred_from_identical_content": False,
    }
    observed["score"] = score_case(case=case, observed=observed)
    return observed
