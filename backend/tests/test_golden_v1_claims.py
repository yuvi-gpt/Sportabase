import pytest

from evals.golden_v1.claims import check_canonical_claim, check_canonical_entities


BASE = {"version": "canonical-claim-contract-v1", "subject_key": "football|player|one", "event_type": "transfer", "state": "completed", "negated": False, "roles": {"destination": "football|club|north"}, "facets": {}}


def test_exact_normalized_claim():
    passed, details = check_canonical_claim(dict(BASE), {"claim": dict(BASE), "match": "exact_normalized"})
    assert passed
    assert details["actual_core_fingerprint"] == details["expected_core_fingerprint"]


def test_core_equivalent_and_specific_compatibility():
    richer = {**BASE, "roles": {**BASE["roles"], "origin": "football|club|south"}}
    assert check_canonical_claim(richer, {"claim": BASE, "match": "core_compatible"})[0]
    assert not check_canonical_claim(richer, {"claim": BASE, "match": "specific_compatible"})[0]


def test_material_conflict():
    left = {**BASE, "roles": {**BASE["roles"], "origin": "football|club|east"}}
    right = {**BASE, "roles": {**BASE["roles"], "origin": "football|club|west"}}
    assert check_canonical_claim(left, {"claim": right, "match": "material_conflict"})[0]


def test_canonical_entities_required_forbidden_and_verified_distinction():
    rows = [{"canonical_key": "football|player|one", "role": "subject", "entity_type": "player", "sport_key": "football", "resolution_status": "candidate"}]
    passed, _ = check_canonical_entities(rows, {"required_keys": ["football|player|one"], "forbidden_keys": ["football|player|two"], "required_entities": [{"canonical_key": "football|player|one", "role": "subject", "entity_type": "player", "sport_key": "football"}]})
    assert passed
    assert not check_canonical_entities(rows, {"required_entities": [{"canonical_key": "football|player|one", "verified": True}]})[0]


@pytest.mark.parametrize("candidate", [
    [42],
    [{"canonical_key": "football|player|one"}, 42],
    "not-a-list",
])
def test_malformed_canonical_entity_candidate_fails(candidate):
    passed, details = check_canonical_entities(
        candidate,
        {"forbidden_keys": ["football|player|forbidden"]},
    )
    assert not passed
    assert details["reason"].startswith("candidate")


def test_clean_forbidden_only_entity_expectation():
    expectation = {"forbidden_keys": ["football|player|forbidden"]}
    assert check_canonical_entities([], expectation)[0]
    assert check_canonical_entities(
        [{"canonical_key": "football|player|allowed"}], expectation
    )[0]
    assert not check_canonical_entities(
        [{"canonical_key": "football|player|forbidden"}], expectation
    )[0]
