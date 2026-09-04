from evals.golden_v1.evaluators import evaluate_check
from evals.golden_v1.facts import normalize_text


def test_required_alternative_and_missing_fact():
    check = {"evaluator": "required_facts", "path": "", "facts": [{"id": "contract", "any_phrases": ["four year", "four-year contract"]}]}
    assert evaluate_check("A FOUR-year\n contract", check, 1)["status"] == "PASS"
    result = evaluate_check("two seasons", check, 1)
    assert result["status"] == "FAIL"
    assert result["details"]["facts"][0]["fact_id"] == "contract"


def test_forbidden_fact_and_nfkc_whitespace():
    check = {"evaluator": "forbidden_facts", "path": "", "facts": [{"id": "fee", "phrases": ["€40 million"]}]}
    assert evaluate_check("Fee: €40   million", check, 1)["status"] == "FAIL"
    assert normalize_text("Ａ  B\nC") == "a b c"


def test_duplicate_summary_bullets():
    check = {"evaluator": "structure", "path": "tldr", "list": True, "unique_normalized": True}
    assert evaluate_check({"tldr": ["News here", " NEWS  HERE "]}, check, 1)["status"] == "FAIL"
