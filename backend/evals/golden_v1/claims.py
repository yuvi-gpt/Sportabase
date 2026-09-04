from __future__ import annotations

from typing import Any

from app.intelligence.claims.identity import (
    canonical_claim_core_fingerprint,
    canonical_claim_specific_fingerprint,
    compare_canonical_claims,
    normalize_canonical_claim,
)


def check_canonical_claim(candidate: Any, expectation: dict) -> tuple[bool, dict]:
    expected = normalize_canonical_claim(expectation["claim"])
    actual = normalize_canonical_claim(candidate)
    comparison = compare_canonical_claims(actual, expected)
    mode = expectation.get("match", "exact_normalized")
    if mode == "exact_normalized":
        passed = actual == expected
    elif mode == "core_compatible":
        passed = comparison["same_core"] and not comparison["material_conflicts"]
    elif mode == "specific_compatible":
        passed = comparison["same_specific"] and not comparison["material_conflicts"]
    elif mode == "material_conflict":
        passed = comparison["status"] == "material_conflict"
    else:
        raise ValueError("Unsupported canonical claim match mode: " + str(mode))
    return passed, {
        "match": mode,
        "comparison_status": comparison["status"],
        "actual_core_fingerprint": canonical_claim_core_fingerprint(actual),
        "expected_core_fingerprint": canonical_claim_core_fingerprint(expected),
        "actual_specific_fingerprint": canonical_claim_specific_fingerprint(actual),
        "expected_specific_fingerprint": canonical_claim_specific_fingerprint(expected),
        "material_conflicts": comparison["material_conflicts"],
    }


def check_canonical_entities(candidate: Any, expectation: dict) -> tuple[bool, dict]:
    if not isinstance(candidate, list):
        return False, {"reason": "candidate entities are not a list"}
    malformed_rows = [
        index
        for index, row in enumerate(candidate)
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("canonical_key"), str)
            or not row["canonical_key"].strip()
        )
    ]
    if malformed_rows:
        return False, {
            "reason": "candidate entity rows are malformed",
            "malformed_row_indexes": malformed_rows,
        }
    rows = candidate
    keys = {str(row.get("canonical_key", "")) for row in rows}
    required = set(expectation.get("required_keys", []))
    forbidden = set(expectation.get("forbidden_keys", []))
    failures = []
    if required - keys:
        failures.append("missing keys: " + ", ".join(sorted(required - keys)))
    if forbidden & keys:
        failures.append("forbidden keys: " + ", ".join(sorted(forbidden & keys)))
    for wanted in expectation.get("required_entities", []):
        match = next((row for row in rows if row.get("canonical_key") == wanted["canonical_key"]), None)
        if match is None:
            failures.append("missing entity: " + wanted["canonical_key"])
            continue
        for field in ("role", "entity_type", "sport_key"):
            if field in wanted and match.get(field) != wanted[field]:
                failures.append(wanted["canonical_key"] + " wrong " + field)
        if wanted.get("verified") is True and match.get("resolution_status") != "verified":
            failures.append(wanted["canonical_key"] + " is candidate-only, not verified")
    return not failures, {"failures": failures, "candidate_keys": sorted(keys)}
