from __future__ import annotations

import math
from typing import Any, Callable

from .claims import check_canonical_claim, check_canonical_entities
from .facts import duplicate_normalized_items, forbidden_fact_results, normalize_text, required_fact_results


def json_value_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/integer coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_value_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_value_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def _contains_json_value(collection: list[Any], wanted: Any) -> bool:
    return any(json_value_equal(item, wanted) for item in collection)


def value_at(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for component in path.split("."):
        if isinstance(current, dict) and component in current:
            current = current[component]
        else:
            raise KeyError(path)
    return current


def _structure(candidate: Any, check: dict) -> tuple[bool, dict]:
    failures = []
    if check.get("list") and not isinstance(candidate, list):
        return False, {"failures": ["expected list"]}
    if isinstance(candidate, list):
        if len(candidate) < check.get("min_items", 0): failures.append("too few items")
        if len(candidate) > check.get("max_items", 1000): failures.append("too many items")
        if check.get("non_empty_strings") and any(not isinstance(v, str) or not v.strip() for v in candidate): failures.append("items must be non-empty strings")
        if "max_item_length" in check and any(len(str(v)) > check["max_item_length"] for v in candidate): failures.append("item exceeds maximum length")
        if "max_total_length" in check and sum(len(str(v)) for v in candidate) > check["max_total_length"]: failures.append("total length exceeds maximum")
        if check.get("unique_normalized") and duplicate_normalized_items(candidate): failures.append("duplicate normalized items")
    if "required_keys" in check:
        if not isinstance(candidate, dict): failures.append("expected object")
        else:
            missing = sorted(set(check["required_keys"]) - set(candidate))
            if missing: failures.append("missing keys: " + ", ".join(missing))
    return not failures, {"failures": failures}


def _language(candidate: Any, check: dict) -> tuple[bool, dict]:
    if not isinstance(candidate, dict): return False, {"failures": ["language value is not an object"]}
    failures = []
    if "primary" in check and candidate.get("detected_language") != check["primary"]: failures.append("primary language mismatch")
    if "mixed" in check and candidate.get("mixed_language") is not check["mixed"]: failures.append("mixed-language flag mismatch")
    if "confidence_min" in check or "confidence_max" in check:
        value = candidate.get("language_confidence")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or not check.get("confidence_min", 0) <= value <= check.get("confidence_max", 1): failures.append("language confidence outside range")
    missing = sorted(set(check.get("required_localized_keys", [])) - set(candidate.get("ui_labels", {})))
    if missing: failures.append("missing localized keys: " + ", ".join(missing))
    text = normalize_text(candidate)
    leaked = [term for term in check.get("forbidden_fallback_terms", []) if normalize_text(term) in text]
    if leaked: failures.append("forbidden fallback terms: " + ", ".join(leaked))
    return not failures, {"failures": failures}


def evaluate_check(candidate_root: Any, check: dict, index: int) -> dict:
    path = check.get("path", "")
    result = {"check_id": f"{index:03d}", "evaluator": check["evaluator"], "path": path, "severity": check.get("severity", "required"), "dimension": check.get("dimension", check["evaluator"])}
    evaluator = check.get("evaluator")
    if evaluator not in REGISTRY:
        result.update({"status": "INVALID_CASE", "details": {"error": "Unknown evaluator: " + str(evaluator)}})
        return result
    try:
        candidate = value_at(candidate_root, path)
        details: dict[str, Any] = {}
        if evaluator == "exact":
            passed = candidate == check.get("value"); details = {"actual": candidate, "expected": check.get("value")}
        elif evaluator == "allowed_values":
            passed = candidate in check["values"]; details = {"actual": candidate, "expected": check["values"]}
        elif evaluator == "forbidden_values": passed = candidate not in check["values"]
        elif evaluator == "required_subset":
            passed = isinstance(candidate, list) and all(
                _contains_json_value(candidate, wanted)
                for wanted in check["values"]
            )
        elif evaluator == "forbidden_subset":
            passed = isinstance(candidate, list) and not any(
                _contains_json_value(candidate, forbidden)
                for forbidden in check["values"]
            )
        elif evaluator == "numeric_range": passed = isinstance(candidate, (int, float)) and not isinstance(candidate, bool) and math.isfinite(float(candidate)) and check["min"] <= candidate <= check["max"]
        elif evaluator == "structure": passed, details = _structure(candidate, check)
        elif evaluator == "required_facts":
            facts = required_fact_results(candidate, check["facts"]); passed = all(row["passed"] for row in facts); details = {"facts": facts}
        elif evaluator == "forbidden_facts":
            facts = forbidden_fact_results(candidate, check["facts"]); passed = all(row["passed"] for row in facts); details = {"facts": facts}
        elif evaluator == "canonical_claim": passed, details = check_canonical_claim(candidate, check)
        elif evaluator == "canonical_entities": passed, details = check_canonical_entities(candidate, check)
        elif evaluator == "language": passed, details = _language(candidate, check)
        result.update({"status": "PASS" if passed else ("WARN" if result["severity"] == "soft" else "FAIL"), "details": details})
    except (KeyError, TypeError, ValueError) as error:
        result.update({"status": "FAIL", "details": {"error": type(error).__name__ + ": " + str(error)}})
    return result


REGISTRY: dict[str, Callable[..., dict]] = {name: evaluate_check for name in (
    "exact", "allowed_values", "forbidden_values", "required_subset", "forbidden_subset", "numeric_range", "structure", "required_facts", "forbidden_facts", "canonical_claim", "canonical_entities", "language"
)}
