import copy
import json
from pathlib import Path

import pytest

from evals.golden_v1.errors import CaseValidationError, ExpectationValidationError
from evals.golden_v1.schema import validate_case, validate_check


CASE = Path(__file__).parents[1] / "evals/golden_v1/corpus/article/article.transfer.official.synthetic-001/case.json"


def sample(): return json.loads(CASE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("field", "value"), [("mode", "audio"), ("case_version", "future")])
def test_invalid_case_contract(field, value):
    case = sample(); case[field] = value
    with pytest.raises(CaseValidationError): validate_case(case)


def test_invalid_review_and_provenance():
    for field, value in (("review_status", "trusted"), ("provenance_type", "internet")):
        case = sample(); case["annotation"][field] = value
        with pytest.raises(CaseValidationError): validate_case(case)


def test_duplicate_and_contradictory_values():
    with pytest.raises(CaseValidationError, match="duplicate"):
        validate_check({"evaluator": "allowed_values", "path": "x", "values": ["a", "a"]})
    case = sample(); case["expected"]["checks"] = [{"evaluator": "allowed_values", "path": "x", "values": ["a"]}, {"evaluator": "forbidden_values", "path": "x", "values": ["a"]}]
    with pytest.raises(CaseValidationError, match="Contradictory"): validate_case(case)


@pytest.mark.parametrize("check", [{"evaluator": "numeric_range", "path": "x", "min": 2, "max": 1}, {"evaluator": "mystery", "path": "x"}, {"evaluator": "allowed_values", "path": "x", "values": []}])
def test_invalid_checks(check):
    with pytest.raises(CaseValidationError): validate_check(check)


def test_non_finite_rejected():
    case = sample(); case["input"]["number"] = float("nan")
    with pytest.raises(ValueError, match="Non-finite"): validate_case(case)


@pytest.mark.parametrize("check", [
    {"evaluator": "numeric_range", "path": "x", "min": True, "max": 1},
    {"evaluator": "structure", "path": "x", "min_items": -1},
    {"evaluator": "structure", "path": "x", "unknown": 1},
    {"evaluator": "structure", "path": "x", "min_items": 3, "max_items": 2},
    {"evaluator": "language", "path": "x", "confidence_min": 0.8, "confidence_max": 0.2},
    {"evaluator": "canonical_claim", "path": "x", "claim": {}, "match": "exact_normalized"},
    {"evaluator": "canonical_entities", "path": "x", "required_entities": [{"role": "subject"}]},
    {"evaluator": "made_up_evaluator", "path": "x"},
])
def test_malformed_expectations_are_distinct(check):
    with pytest.raises(ExpectationValidationError):
        validate_check(check)


def test_language_and_entity_expectation_shapes():
    with pytest.raises(ExpectationValidationError):
        validate_check({"evaluator": "language", "path": "x", "mixed": "yes"})
    with pytest.raises(ExpectationValidationError):
        validate_check({"evaluator": "canonical_entities", "path": "x", "required_keys": [""]})


@pytest.mark.parametrize("values", [
    [{"a": 1}, {"a": 1}],
    [[1, 2], [1, 2]],
])
def test_duplicate_structured_expectations_are_rejected(values):
    with pytest.raises(ExpectationValidationError, match="duplicate"):
        validate_check({"evaluator": "required_subset", "path": "x", "values": values})


def test_bool_and_number_are_not_duplicate_expectations():
    validate_check({"evaluator": "required_subset", "path": "x", "values": [True, 1]})
