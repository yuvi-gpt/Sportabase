from __future__ import annotations

import hashlib
import json
import tempfile

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Mapping

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence import entities as entity_runtime
from app.services import browser_capture_inbox
from app.services import inbox_candidate_discovery
from app.services import inbox_story_cluster_orchestration

from .golden_capture import clean
from .golden_dataset import build_golden_cases, golden_dataset_descriptor
from .multimodal_golden_cases import DEFAULT_LIMITS, HARD_THRESHOLDS, QUALITY_TARGETS


MULTIMODAL_GOLDEN_EVAL_VERSION = "multimodal-golden-eval-v1"


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _factory(db_path: Path):
    return lambda: connect_database(db_path)


def _initialize(db_path: Path) -> None:
    conn = connect_database(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _insert_entities(case: Mapping[str, Any], connection_factory) -> None:
    conn = connection_factory()
    try:
        for entity in case["entities"]:
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id, entity_key, entity_type, sport_key,
                  canonical_name, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity["id"],
                    entity["entity_key"],
                    entity["entity_type"],
                    entity["sport_key"],
                    entity["canonical_name"],
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:00:00Z",
                    _json({"evaluation_only": True}),
                ),
            )
            for index, alias in enumerate(entity.get("aliases", []), 1):
                conn.execute(
                    """
                    INSERT INTO entity_aliases (
                      id, entity_id, alias_text, normalized_alias,
                      alias_type, first_seen_at, last_seen_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"golden_alias_{entity['id']}_{index}",
                        entity["id"],
                        alias,
                        entity_runtime.normalize_entity_alias(alias),
                        "common_name",
                        "2024-01-01T00:00:00Z",
                        "2024-01-01T00:00:00Z",
                        _json({"evaluation_only": True}),
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def _store_captures(case: Mapping[str, Any], connection_factory):
    label_to_id: Dict[str, str] = {}
    id_to_label: Dict[str, str] = {}
    for label, wrapped in case["captures"].items():
        capture = wrapped["capture"]
        observed = clean(capture.get("observed_at"))
        stored = browser_capture_inbox.store_browser_capture(
            raw_capture=capture,
            connection_factory=connection_factory,
            now_provider=lambda value=observed: value,
        )
        capture_id = stored["capture_record_id"]
        label_to_id[label] = capture_id
        id_to_label[capture_id] = label
    return label_to_id, id_to_label


def _labels(values, id_to_label) -> list[str]:
    result = []
    for value in values:
        label = id_to_label.get(clean(value), "")
        if label:
            result.append(label)
    return result


def _safe_discovery(result: Mapping[str, Any]) -> bool:
    policy = result.get("policy")
    counts = result.get("counts")
    if not isinstance(policy, Mapping) or not isinstance(counts, Mapping):
        return False

    required_true = (
        "read_only_discovery",
        "inbox_records_remain_untrusted",
        "anchor_capture_text_is_not_a_verified_claim",
        "entity_matching_is_exact_alias_or_canonical_name_only",
        "entity_candidates_do_not_verify_subject",
        "deterministic_score_is_ranking_only",
        "candidate_discovery_does_not_establish_corroboration",
    )
    forbidden = (
        "creates_story",
        "creates_claim",
        "creates_observation",
        "creates_evidence",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    )
    return (
        all(policy.get(field) is True for field in required_true)
        and not any(bool(policy.get(field)) for field in forbidden)
        and int(counts.get("independence_established") or 0) == 0
        and int(counts.get("corroboration_established") or 0) == 0
        and int(counts.get("live_merit_effects") or 0) == 0
    )


def _safe_selection(result: Mapping[str, Any]) -> bool:
    policy = result.get("policy")
    if not isinstance(policy, Mapping):
        return False
    required_true = (
        "cluster_is_routing_candidate_only",
        "cluster_selection_is_read_only",
        "cluster_requires_one_unambiguous_subject_partition",
        "cluster_member_requires_exactly_one_shared_entity",
        "candidate_score_is_ranking_only",
        "same_story_not_established_by_cluster",
        "same_claim_not_established_by_cluster",
        "subject_not_verified_by_cluster",
        "independence_not_established_by_cluster",
        "corroboration_not_established_by_cluster",
    )
    return (
        all(policy.get(field) is True for field in required_true)
        and not bool(policy.get("creates_story"))
        and not bool(policy.get("affects_live_merit"))
    )


def _not_ready_status(error: Exception) -> str:
    message = str(error).lower()
    if "subject-ambiguous" in message or "multiple exact subject partitions" in message:
        return "not_ready_ambiguous"
    if "no current inbox candidates" in message:
        return "not_ready_no_candidates"
    if "no inbox candidate has exactly one shared exact entity" in message:
        return "not_ready_no_partition"
    return "not_ready_other"


def _case_failures(expectations, discovery_status, shortlist, selection_status,
                   subject_entity_id, members, rejected, safety):
    failures = []
    shortlist_set = set(shortlist)
    if discovery_status != expectations["discovery_status"]:
        failures.append("discovery_status")
    if not set(expectations["required_shortlist_labels"]).issubset(shortlist_set):
        failures.append("required_shortlist_recall")
    if shortlist_set & set(expectations["forbidden_shortlist_labels"]):
        failures.append("forbidden_shortlist_leakage")
    if selection_status != expectations["selection_status"]:
        failures.append("selection_status")

    expected_subject = clean(expectations.get("expected_subject_entity_id"))
    if expected_subject and subject_entity_id != expected_subject:
        failures.append("subject_partition")
    if not expected_subject and subject_entity_id:
        failures.append("unexpected_subject_partition")
    if not set(expectations["required_member_labels"]).issubset(set(members)):
        failures.append("required_member_recall")
    if not set(expectations["required_rejected_labels"]).issubset(set(rejected)):
        failures.append("required_rejected_recall")
    if not safety:
        failures.append("safety_policy")
    return failures


def evaluate_golden_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sportabase-golden-") as tmp:
        db_path = Path(tmp) / "golden.db"
        _initialize(db_path)
        factory = _factory(db_path)
        _insert_entities(case, factory)
        label_to_id, id_to_label = _store_captures(case, factory)
        anchor_id = label_to_id["anchor"]

        discovery = inbox_candidate_discovery.discover_multimodal_inbox_candidates(
            anchor_capture_record_id=anchor_id,
            connection_factory=factory,
            scan_limit=int(DEFAULT_LIMITS["scan_limit"]),
            max_candidates=int(DEFAULT_LIMITS["max_candidates"]),
            semantic_assessments=0,
            gemini_client=None,
            gemini_client_key="golden-eval",
            gemini_generator=None,
        )
        candidate_rows = discovery.get("pair_candidates", [])
        shortlist = _labels(
            [row.get("capture_record_id") for row in candidate_rows],
            id_to_label,
        )
        ranks = {label: index + 1 for index, label in enumerate(shortlist)}
        identical = _labels(
            [
                row.get("capture_record_id")
                for row in candidate_rows
                if bool(row.get("signals", {}).get("identical_normalized_content"))
            ],
            id_to_label,
        )

        selection_status = ""
        subject_entity_id = ""
        members: list[str] = []
        rejected: list[str] = []
        selection_safety = True
        try:
            selection = inbox_story_cluster_orchestration.select_multisource_inbox_cluster(
                anchor_capture_record_id=anchor_id,
                scan_limit=int(DEFAULT_LIMITS["scan_limit"]),
                max_candidates=int(DEFAULT_LIMITS["max_candidates"]),
                connection_factory=factory,
            )
            selection_status = clean(selection.get("status"))
            subject_entity_id = clean(selection.get("subject_entity_id"))
            members = _labels(
                [row.get("capture_record_id") for row in selection.get("members", [])],
                id_to_label,
            )
            rejected = _labels(
                [row.get("capture_record_id") for row in selection.get("rejected_candidates", [])],
                id_to_label,
            )
            selection_safety = _safe_selection(selection)
        except inbox_story_cluster_orchestration.MultimodalInboxStoryClusterNotReady as error:
            selection_status = _not_ready_status(error)

        safety = _safe_discovery(discovery) and selection_safety
        expectations = case["expectations"]
        failures = _case_failures(
            expectations,
            clean(discovery.get("status")),
            shortlist,
            selection_status,
            subject_entity_id,
            members,
            rejected,
            safety,
        )

        return {
            "case_id": case["case_id"],
            "sport": case["sport"],
            "status": "pass" if not failures else "fail",
            "failures": failures,
            "discovery_status": clean(discovery.get("status")),
            "shortlist_labels": shortlist,
            "required_label_ranks": {
                label: ranks.get(label)
                for label in expectations["required_shortlist_labels"]
            },
            "identical_content_labels": identical,
            "selection_status": selection_status,
            "subject_entity_id": subject_entity_id,
            "member_labels": members,
            "rejected_labels": rejected,
            "safety_policy_pass": safety,
            "counts": deepcopy(discovery.get("counts", {})),
        }


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator <= 0 else round(numerator / denominator, 6)


def _metrics(cases, results) -> Dict[str, float]:
    by_id = {case["case_id"]: case for case in cases}
    totals = {
        "required_shortlist": [0, 0],
        "forbidden": [0, 0],
        "selection": [0, 0],
        "subject": [0, 0],
        "member": [0, 0],
        "rejected": [0, 0],
        "safety": [0, 0],
    }
    case_passes = 0

    for result in results:
        case = by_id[result["case_id"]]
        exp = case["expectations"]
        shortlist = set(result["shortlist_labels"])
        members = set(result["member_labels"])
        rejected = set(result["rejected_labels"])
        case_passes += result["status"] == "pass"

        required = set(exp["required_shortlist_labels"])
        forbidden = set(exp["forbidden_shortlist_labels"])
        totals["required_shortlist"][0] += len(required & shortlist)
        totals["required_shortlist"][1] += len(required)
        totals["forbidden"][0] += len(forbidden & shortlist)
        totals["forbidden"][1] += len(forbidden)
        totals["selection"][0] += result["selection_status"] == exp["selection_status"]
        totals["selection"][1] += 1

        expected_subject = clean(exp.get("expected_subject_entity_id"))
        if expected_subject:
            totals["subject"][0] += result["subject_entity_id"] == expected_subject
            totals["subject"][1] += 1

        required_members = set(exp["required_member_labels"])
        totals["member"][0] += len(required_members & members)
        totals["member"][1] += len(required_members)
        required_rejected = set(exp["required_rejected_labels"])
        totals["rejected"][0] += len(required_rejected & rejected)
        totals["rejected"][1] += len(required_rejected)
        totals["safety"][0] += bool(result["safety_policy_pass"])
        totals["safety"][1] += 1

    return {
        "case_pass_rate": _ratio(case_passes, len(results)),
        "required_shortlist_recall": _ratio(*totals["required_shortlist"]),
        "forbidden_shortlist_leakage": (
            _ratio(*totals["forbidden"])
            if totals["forbidden"][1]
            else 0.0
        ),
        "selection_status_accuracy": _ratio(*totals["selection"]),
        "subject_partition_accuracy": _ratio(*totals["subject"]),
        "required_member_recall": _ratio(*totals["member"]),
        "required_rejected_recall": _ratio(*totals["rejected"]),
        "safety_policy_pass_rate": _ratio(*totals["safety"]),
    }


def _threshold_failures(metrics: Mapping[str, Any]) -> list[str]:
    failures = []
    for metric, expected in HARD_THRESHOLDS.items():
        actual = float(metrics.get(metric, 0.0))
        if metric == "forbidden_shortlist_leakage":
            if actual > float(expected):
                failures.append(metric)
        elif actual < float(expected):
            failures.append(metric)
    return failures


def evaluate_deterministic_golden_set() -> Dict[str, Any]:
    cases = build_golden_cases()
    results = [evaluate_golden_case(case) for case in cases]
    metrics = _metrics(cases, results)
    threshold_failures = _threshold_failures(metrics)
    case_failures = [row["case_id"] for row in results if row["status"] != "pass"]
    report = {
        "version": MULTIMODAL_GOLDEN_EVAL_VERSION,
        "status": "pass" if not threshold_failures else "fail",
        "dataset": golden_dataset_descriptor(),
        "mode": "deterministic_offline",
        "network_fetches": 0,
        "gemini_calls": 0,
        "real_database_used": False,
        "temporary_database_per_case": True,
        "metrics": metrics,
        "hard_thresholds": deepcopy(HARD_THRESHOLDS),
        "quality_targets": deepcopy(QUALITY_TARGETS),
        "threshold_failures": threshold_failures,
        "quality_case_failures": case_failures,
        "cases": results,
        "policy": {
            "ranking_is_not_truth_confidence": True,
            "golden_labels_do_not_establish_authority": True,
            "golden_labels_do_not_establish_independence": True,
            "default_run_does_not_call_gemini": True,
            "default_run_does_not_touch_real_db": True,
            "live_merit_effect_allowed": False,
        },
    }
    report["report_digest"] = _digest({
        key: value for key, value in report.items() if key != "report_digest"
    })
    return report
