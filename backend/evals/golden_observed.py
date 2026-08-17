from __future__ import annotations

import hashlib
import json

from typing import Any, Dict, Mapping

from .golden_capture import clean
from .golden_dataset import build_golden_cases
from .multimodal_golden_cases import MULTIMODAL_GOLDEN_DATASET_ID


MULTIMODAL_GOLDEN_OBSERVED_VERSION = "multimodal-golden-observed-v1"
MULTIMODAL_GOLDEN_EVAL_VERSION = "multimodal-golden-eval-v1"


class MultimodalGoldenObservedError(RuntimeError):
    pass


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def observed_template() -> Dict[str, Any]:
    values = []
    for case in build_golden_cases():
        full = case["expectations"]["full_pipeline"]
        if full.get("expected_status") == "not_ready":
            values.append({
                "case_id": case["case_id"],
                "status": "not_ready",
            })
            continue

        values.append({
            "case_id": case["case_id"],
            "status": "completed",
            "accepted_member_labels": list(full["required_accept_labels"]),
            "rejected_member_labels": list(full["required_reject_labels"]),
            "story_count": int(full["expected_story_count"]),
            "merit_baseline_mode": full["expected_merit_baseline_mode"],
            "synthetic_merit_baseline_used": False,
            "affects_live_merit": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "independence_inferred_from_identical_content": False,
        })

    return {
        "version": MULTIMODAL_GOLDEN_OBSERVED_VERSION,
        "dataset_id": MULTIMODAL_GOLDEN_DATASET_ID,
        "cases": values,
    }


def evaluate_observed_artifact(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(artifact, Mapping):
        raise MultimodalGoldenObservedError("Observed golden artifact must be an object.")
    if clean(artifact.get("version")) != MULTIMODAL_GOLDEN_OBSERVED_VERSION:
        raise MultimodalGoldenObservedError("Observed golden artifact version mismatch.")
    if clean(artifact.get("dataset_id")) != MULTIMODAL_GOLDEN_DATASET_ID:
        raise MultimodalGoldenObservedError("Observed golden dataset ID mismatch.")

    raw_cases = artifact.get("cases")
    if not isinstance(raw_cases, list):
        raise MultimodalGoldenObservedError("Observed golden cases must be a list.")

    observed_by_id: Dict[str, Mapping[str, Any]] = {}
    for raw in raw_cases:
        if not isinstance(raw, Mapping):
            raise MultimodalGoldenObservedError("Observed case must be an object.")
        case_id = clean(raw.get("case_id"))
        if not case_id or case_id in observed_by_id:
            raise MultimodalGoldenObservedError(
                "Observed case IDs must be unique and nonempty."
            )
        observed_by_id[case_id] = raw

    cases = build_golden_cases()
    known_ids = {case["case_id"] for case in cases}
    results = []

    for case in cases:
        case_id = case["case_id"]
        observed = observed_by_id.get(case_id)
        failures = []
        if observed is None:
            failures.append("missing_case")
            results.append({
                "case_id": case_id,
                "status": "fail",
                "failures": failures,
            })
            continue

        full = case["expectations"]["full_pipeline"]
        expected_status = clean(full.get("expected_status")) or "completed"
        actual_status = clean(observed.get("status"))
        if actual_status != expected_status:
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
            if clean(observed.get("merit_baseline_mode")) != full["expected_merit_baseline_mode"]:
                failures.append("merit_baseline_mode")
            if bool(observed.get("synthetic_merit_baseline_used")):
                failures.append("synthetic_merit_baseline")
            if bool(observed.get("affects_live_merit")):
                failures.append("live_merit_effect")
            for field in (
                "establishes_truth",
                "establishes_authority",
                "establishes_independence",
            ):
                if bool(observed.get(field)):
                    failures.append(field)
            if (
                full.get("independence_must_not_be_inferred_from_identical_labels")
                and bool(observed.get("independence_inferred_from_identical_content"))
            ):
                failures.append("identical_content_independence")

        results.append({
            "case_id": case_id,
            "status": "pass" if not failures else "fail",
            "failures": failures,
        })

    unknown = sorted(set(observed_by_id) - known_ids)
    failures = [row["case_id"] for row in results if row["status"] == "fail"]
    if unknown:
        failures.append("unknown_cases")

    pass_count = sum(row["status"] == "pass" for row in results)
    report = {
        "version": MULTIMODAL_GOLDEN_EVAL_VERSION,
        "status": "pass" if not failures else "fail",
        "mode": "observed_full_pipeline",
        "dataset_id": MULTIMODAL_GOLDEN_DATASET_ID,
        "case_count": len(results),
        "case_pass_rate": round(pass_count / len(results), 6) if results else 1.0,
        "case_failures": failures,
        "unknown_case_ids": unknown,
        "cases": results,
        "policy": {
            "observed_results_are_scored_not_trusted": True,
            "golden_labels_do_not_establish_truth": True,
            "golden_labels_do_not_establish_authority": True,
            "golden_labels_do_not_establish_independence": True,
            "synthetic_merit_baseline_forbidden": True,
            "live_merit_effect_allowed": False,
        },
    }
    report["report_digest"] = _digest({
        key: value for key, value in report.items() if key != "report_digest"
    })
    return report
