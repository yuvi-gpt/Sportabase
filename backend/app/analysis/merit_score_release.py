import hashlib
import json
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from app.analysis.merit import MERIT_CORROBORATION_SHADOW_MAX_BOOST
from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_EVALUATION_CASE_VERSION,
    MERIT_CORROBORATION_EVALUATION_VERSION,
    evaluate_merit_corroboration_cases,
)
from app.services.direct_stakeholder_independence_verifier import (
    DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
)


MERIT_SCORE_RELEASE_CERTIFICATE_VERSION = "merit-score-release-certificate-v1"
MERIT_SCORE_RELEASE_CASE_VERSION = "merit-score-release-case-v1"
MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS = (
    "verified_independent_corroboration",
    "recorded_dependency_no_boost",
    "same_publisher_no_diversity",
)

_FORBIDDEN_HUMAN_KEYS = {
    "reviewer",
    "review_status",
    "reviewed_at",
    "human_review",
    "human_reviewer",
    "manual_approval",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _key(value: Any) -> str:
    return _clean(value).lower()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _assert_no_human_review_keys(value: Any, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _key(key)
            if normalized in _FORBIDDEN_HUMAN_KEYS:
                raise ValueError(
                    f"Machine score-release data cannot contain human-review key {path}.{key}."
                )
            _assert_no_human_review_keys(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_no_human_review_keys(nested, path=f"{path}[{index}]")


def _claim_row(case: Dict[str, Any]) -> Dict[str, Any]:
    state = case.get("corroboration_state")
    if not isinstance(state, dict):
        raise ValueError("Score-release corroboration_state must be a dictionary.")
    rows = [
        row
        for row in state.get("claims", [])
        if isinstance(row, dict) and _clean(row.get("claim_id")) == _clean(case.get("claim_id"))
    ]
    if len(rows) != 1:
        raise ValueError("Score-release case requires exactly one target corroboration claim.")
    return rows[0]


def _validate_capture(capture: Any) -> Dict[str, Any]:
    if not isinstance(capture, dict):
        raise ValueError("Score-release source capture must be a dictionary.")
    url = _clean(capture.get("url"))
    digest = _key(capture.get("content_sha256"))
    source_id = _clean(capture.get("source_id"))
    if not url or urlparse(url).scheme.lower() != "https":
        raise ValueError("Score-release source capture must use HTTPS.")
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("Score-release source capture requires a SHA256 content hash.")
    if not source_id:
        raise ValueError("Score-release source capture requires source identity.")
    return {
        "url": url,
        "content_sha256": digest,
        "source_id": source_id,
    }


def _number(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric.") from exc


def _validate_case(raw_case: Any) -> Dict[str, Any]:
    if not isinstance(raw_case, dict):
        raise ValueError("Each Merit score-release case must be a dictionary.")
    _assert_no_human_review_keys(raw_case)

    if _clean(raw_case.get("version")) != MERIT_SCORE_RELEASE_CASE_VERSION:
        raise ValueError("Unsupported Merit score-release case version.")
    if raw_case.get("origin") != "real_world":
        raise ValueError("Merit score-release cases must be real_world.")
    if raw_case.get("machine_verified") is not True:
        raise ValueError("Merit score-release cases must be machine_verified.")

    case_id = _clean(raw_case.get("id"))
    claim_id = _clean(raw_case.get("claim_id"))
    scenario = _key(raw_case.get("scenario"))
    if not case_id or not claim_id:
        raise ValueError("Merit score-release case and claim IDs are required.")
    if scenario not in MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS:
        raise ValueError("Unsupported Merit score-release scenario.")

    captures = [_validate_capture(row) for row in raw_case.get("source_captures", [])]
    if not captures:
        raise ValueError("Merit score-release case requires captured real-world sources.")

    legacy = raw_case.get("legacy_score")
    expectations = raw_case.get("expectations")
    lineage = raw_case.get("lineage")
    if not isinstance(legacy, dict) or not isinstance(expectations, dict) or not isinstance(lineage, dict):
        raise ValueError("Score-release case legacy_score, expectations, and lineage are required dictionaries.")

    claim = _claim_row(raw_case)
    supporting_source_ids = sorted(
        {_clean(value) for value in claim.get("supporting_source_ids", []) if _clean(value)}
    )

    adjustment = _number(expectations.get("adjustment"), label="Expected adjustment")
    live_total = _number(expectations.get("live_total"), label="Expected live total")
    shadow_total = _number(expectations.get("shadow_total"), label="Expected shadow total")
    legacy_total = _number(legacy.get("total"), label="Legacy total")

    if abs(live_total - legacy_total) > 1e-9:
        raise ValueError("Score-release case cannot change the legacy live total during certification.")

    if scenario == "verified_independent_corroboration":
        if (
            _key(claim.get("status")) != "corroboration_established"
            or claim.get("corroboration_established") is not True
            or claim.get("independent_support_established") is not True
            or claim.get("contested") is True
            or len(supporting_source_ids) < 2
        ):
            raise ValueError("Positive score-release case lacks verified uncontested independent corroboration.")
        if _clean(expectations.get("signal")) != "verified_corroboration":
            raise ValueError("Positive score-release case requires verified_corroboration signal.")
        if abs(adjustment - MERIT_CORROBORATION_SHADOW_MAX_BOOST) > 1e-9:
            raise ValueError("Positive score-release case must use the fixed corroboration boost.")
        if abs(shadow_total - min(100.0, legacy_total + adjustment)) > 1e-9:
            raise ValueError("Positive score-release shadow total is inconsistent.")
        if _clean(lineage.get("independence_verifier_version")) != DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION:
            raise ValueError("Positive score-release case lacks the approved independence verifier lineage.")
        for key in ("independence_assertion_id", "independence_evidence_id"):
            if not _clean(lineage.get(key)):
                raise ValueError(f"Positive score-release case lacks {key}.")

    elif scenario == "recorded_dependency_no_boost":
        if _key(claim.get("status")) != "recorded_support_dependency_present":
            raise ValueError("Dependency control must derive recorded_support_dependency_present.")
        if adjustment != 0.0 or shadow_total != legacy_total:
            raise ValueError("Recorded dependency control must receive zero score adjustment.")
        if _clean(expectations.get("signal")) != "support_dependency_present":
            raise ValueError("Dependency control requires support_dependency_present signal.")
        for key in ("dependency_id", "dependency_evidence_id"):
            if not _clean(lineage.get(key)):
                raise ValueError(f"Dependency control lacks {key}.")

    elif scenario == "same_publisher_no_diversity":
        if _key(claim.get("status")) != "support_source_diversity_not_established":
            raise ValueError("Same-publisher control must derive support_source_diversity_not_established.")
        if len(captures) < 2 or len(supporting_source_ids) != 1:
            raise ValueError("Same-publisher control requires multiple pages collapsing to one source identity.")
        if adjustment != 0.0 or shadow_total != legacy_total:
            raise ValueError("Same-publisher control must receive zero score adjustment.")
        if _clean(expectations.get("signal")) != "no_verified_corroboration_boost":
            raise ValueError("Same-publisher control requires no_verified_corroboration_boost signal.")

    evaluation_case = {
        "version": MERIT_CORROBORATION_EVALUATION_CASE_VERSION,
        "id": case_id,
        "claim_id": claim_id,
        "legacy_score": legacy,
        "corroboration_state": raw_case["corroboration_state"],
        "expectations": {
            "signal": _clean(expectations.get("signal")),
            "adjustment": adjustment,
            "live_total": live_total,
            "shadow_total": shadow_total,
        },
    }

    return {
        "case": raw_case,
        "evaluation_case": evaluation_case,
        "scenario": scenario,
    }


def build_merit_score_release_certificate(*, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(cases, list) or not cases:
        raise ValueError("Merit score release requires real-world machine-verified cases.")

    validated = [_validate_case(case) for case in cases]
    ids = [_clean(row["case"].get("id")) for row in validated]
    if len(ids) != len(set(ids)):
        raise ValueError("Merit score-release case IDs must be unique.")

    scenarios = [row["scenario"] for row in validated]
    scenario_counts = {scenario: scenarios.count(scenario) for scenario in MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS}
    scenario_complete = all(count >= 1 for count in scenario_counts.values())

    evaluation = evaluate_merit_corroboration_cases(
        cases=[row["evaluation_case"] for row in validated]
    )
    evaluation_passed = (
        evaluation.get("version") == MERIT_CORROBORATION_EVALUATION_VERSION
        and evaluation.get("status") == "passed"
        and evaluation.get("metrics", {}).get("expectations_failed") == 0
        and evaluation.get("metrics", {}).get("safety_violations") == 0
        and evaluation.get("metrics", {}).get("unverified_positive_adjustments") == 0
        and evaluation.get("metrics", {}).get("contested_positive_adjustments") == 0
        and evaluation.get("metrics", {}).get("negative_adjustments") == 0
    )

    authorized = bool(scenario_complete and evaluation_passed)
    blockers = []
    if not scenario_complete:
        blockers.append("required_real_world_score_scenarios_missing")
    if not evaluation_passed:
        blockers.append("merit_corroboration_evaluation_failed")

    payload = {
        "version": MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
        "status": "authorized" if authorized else "blocked",
        "live_enablement_authorized": authorized,
        "blockers": blockers,
        "scenario_counts": scenario_counts,
        "case_count": len(validated),
        "cases": [row["case"] for row in validated],
        "evaluation": evaluation,
        "policy": {
            "real_world_cases_required": True,
            "machine_verification_required": True,
            "human_review_not_part_of_release_path": True,
            "model_output_is_not_release_truth": True,
            "positive_effect_requires_verified_independence": True,
            "dependency_control_must_not_boost": True,
            "same_publisher_control_must_not_boost": True,
            "certificate_does_not_itself_activate_live_merit": True,
        },
    }
    payload["certificate_sha256"] = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def validate_merit_score_release_certificate(certificate: Any) -> Dict[str, Any]:
    if not isinstance(certificate, dict):
        raise ValueError("Merit score-release certificate must be a dictionary.")
    _assert_no_human_review_keys(certificate)
    if _clean(certificate.get("version")) != MERIT_SCORE_RELEASE_CERTIFICATE_VERSION:
        raise ValueError("Unsupported Merit score-release certificate version.")

    rebuilt = build_merit_score_release_certificate(cases=certificate.get("cases"))
    if _canonical_json(rebuilt) != _canonical_json(certificate):
        raise ValueError("Merit score-release certificate content or identity has been tampered with.")
    return rebuilt
