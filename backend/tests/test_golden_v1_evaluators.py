import pytest

from evals.golden_v1.evaluators import evaluate_check


@pytest.mark.parametrize(("check", "candidate", "status"), [
    ({"evaluator": "exact", "path": "x", "value": 2}, {"x": 2}, "PASS"),
    ({"evaluator": "allowed_values", "path": "x", "values": [1, 2]}, {"x": 2}, "PASS"),
    ({"evaluator": "forbidden_values", "path": "x", "values": [3]}, {"x": 2}, "PASS"),
    ({"evaluator": "required_subset", "path": "x", "values": [1]}, {"x": [1, 2]}, "PASS"),
    ({"evaluator": "forbidden_subset", "path": "x", "values": [3]}, {"x": [1, 2]}, "PASS"),
    ({"evaluator": "numeric_range", "path": "x", "min": 2, "max": 3}, {"x": 2}, "PASS"),
    ({"evaluator": "numeric_range", "path": "x", "min": 2, "max": 3}, {"x": 4}, "FAIL"),
])
def test_comparators(check, candidate, status):
    assert evaluate_check(candidate, check, 1)["status"] == status


def test_structure_constraints_and_soft_warning():
    check = {"evaluator": "structure", "path": "x", "list": True, "min_items": 2, "max_items": 3, "non_empty_strings": True, "unique_normalized": True, "severity": "soft"}
    assert evaluate_check({"x": ["Same", " same "]}, check, 1)["status"] == "WARN"


@pytest.mark.parametrize(("evaluator", "values", "candidate", "status"), [
    ("required_subset", [{"a": 1}], [{"a": 1}], "PASS"),
    ("required_subset", [[1, {"b": 2}]], [[1, {"b": 2}]], "PASS"),
    ("required_subset", [{"a": 1}], [{"a": 2}], "FAIL"),
    ("forbidden_subset", [{"a": 1}], [{"a": 1}], "FAIL"),
    ("forbidden_subset", [{"a": 1}], [{"a": 2}], "PASS"),
])
def test_subset_evaluators_support_structured_json(evaluator, values, candidate, status):
    check = {"evaluator": evaluator, "path": "x", "values": values}
    assert evaluate_check({"x": candidate}, check, 1)["status"] == status


def test_subset_equality_distinguishes_bool_from_number():
    required = {"evaluator": "required_subset", "path": "x", "values": [True]}
    forbidden = {"evaluator": "forbidden_subset", "path": "x", "values": [True]}
    assert evaluate_check({"x": [1]}, required, 1)["status"] == "FAIL"
    assert evaluate_check({"x": [1]}, forbidden, 1)["status"] == "PASS"
