from __future__ import annotations

import json
import math
import re
from typing import Any, Mapping

from app.intelligence.claims.identity import normalize_canonical_claim

from .errors import CaseValidationError, CorpusError, ExpectationValidationError
from .serialization import reject_non_finite

GOLDEN_SET_VERSION = "sportabase-golden-set-v1"
CASE_SCHEMA_VERSION = "golden-case-v1"
EVALUATION_VERSION = "sportabase-golden-eval-v1"
MODES = {"article", "video", "intelligence"}
REVIEW_STATUSES = {"draft", "approved", "needs_review"}
PROVENANCE_TYPES = {"synthetic", "original_paraphrase", "licensed", "public_domain"}
EVALUATORS = {
    "exact", "allowed_values", "forbidden_values", "required_subset",
    "forbidden_subset", "numeric_range", "structure", "required_facts",
    "forbidden_facts", "canonical_claim", "canonical_entities", "language",
}
CASE_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
MAX_COLLECTION = 1000
MAX_ALLOWED_VALUES = 8


def _unique(values: list[Any], label: str, error_type=CaseValidationError) -> None:
    try:
        rendered = [
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            for value in values
        ]
    except (TypeError, ValueError) as error:
        raise error_type(label + " must contain valid JSON values.") from error
    if len(set(rendered)) != len(rendered):
        raise error_type(label + " contains duplicate values.")


def validate_manifest(value: Any) -> dict:
    if not isinstance(value, dict):
        raise CorpusError("Manifest must be a JSON object.")
    if set(value) != {"golden_set_version", "case_schema_version", "cases"}:
        raise CorpusError("Manifest contains missing or unknown fields.")
    if value["golden_set_version"] != GOLDEN_SET_VERSION:
        raise CorpusError("Unsupported golden set version.")
    if value["case_schema_version"] != CASE_SCHEMA_VERSION:
        raise CorpusError("Unsupported manifest case schema version.")
    if not isinstance(value["cases"], list) or not value["cases"]:
        raise CorpusError("Manifest cases must be a non-empty list.")
    if len(value["cases"]) > MAX_COLLECTION:
        raise CorpusError("Manifest contains too many cases.")
    for entry in value["cases"]:
        if not isinstance(entry, dict) or set(entry) != {"case_id", "path"}:
            raise CorpusError("Each manifest case requires only case_id and path.")
        if not CASE_ID_RE.fullmatch(str(entry["case_id"])):
            raise CorpusError("Invalid manifest case ID.")
        if not isinstance(entry["path"], str) or not entry["path"]:
            raise CorpusError("Manifest case path is required.")
    case_ids = [item["case_id"] for item in value["cases"]]
    paths = [item["path"] for item in value["cases"]]
    if len(set(case_ids)) != len(case_ids):
        raise CorpusError("Manifest case IDs contain duplicate values.")
    if len(set(paths)) != len(paths):
        raise CorpusError("Manifest paths contain duplicate values.")
    return value


def _validate_facts(check: Mapping[str, Any], key: str) -> None:
    facts = check.get(key)
    if not isinstance(facts, list) or not facts:
        raise ExpectationValidationError(key + " must be a non-empty list.")
    phrase_key = "any_phrases" if key == "facts" and check["evaluator"] == "required_facts" else "phrases"
    ids = []
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {"id", phrase_key}:
            raise ExpectationValidationError("Invalid fact annotation.")
        phrases = fact[phrase_key]
        if not isinstance(phrases, list) or not phrases or not all(isinstance(p, str) and p.strip() for p in phrases):
            raise ExpectationValidationError("Fact phrases must be non-empty strings.")
        _unique(phrases, "Fact phrases", ExpectationValidationError)
        if not isinstance(fact["id"], str) or not fact["id"].strip():
            raise ExpectationValidationError("Fact IDs must be non-empty strings.")
        ids.append(fact["id"])
    _unique(ids, "Fact IDs", ExpectationValidationError)


def validate_check(check: Any) -> dict:
    if not isinstance(check, dict):
        raise ExpectationValidationError("Expected checks must be objects.")
    evaluator = check.get("evaluator", check.get("type"))
    if evaluator not in EVALUATORS:
        raise ExpectationValidationError("Unknown evaluator: " + str(evaluator))
    if not isinstance(check.get("path", ""), str):
        raise ExpectationValidationError("Check path must be a string.")
    if check.get("severity", "required") not in {"required", "soft"}:
        raise ExpectationValidationError("Check severity must be required or soft.")
    common = {"evaluator", "path", "severity", "dimension"}
    fields = {
        "exact": {"value"},
        "allowed_values": {"values"},
        "forbidden_values": {"values"},
        "required_subset": {"values"},
        "forbidden_subset": {"values"},
        "numeric_range": {"min", "max"},
        "structure": {"list", "min_items", "max_items", "non_empty_strings", "max_item_length", "max_total_length", "required_keys", "unique_normalized"},
        "required_facts": {"facts"},
        "forbidden_facts": {"facts"},
        "canonical_claim": {"claim", "match"},
        "canonical_entities": {"required_keys", "forbidden_keys", "required_entities"},
        "language": {"primary", "mixed", "confidence_min", "confidence_max", "required_localized_keys", "forbidden_fallback_terms"},
    }
    if set(check) - common - fields[evaluator]:
        raise ExpectationValidationError("Unknown fields for evaluator: " + evaluator)
    if "dimension" in check and (not isinstance(check["dimension"], str) or not check["dimension"].strip()):
        raise ExpectationValidationError("Check dimension must be a non-empty string.")
    if evaluator == "exact" and "value" not in check:
        raise ExpectationValidationError("Exact evaluator requires value.")
    if evaluator in {"allowed_values", "forbidden_values"}:
        values = check.get("values")
        if not isinstance(values, list) or not values:
            raise ExpectationValidationError(evaluator + " values must be a non-empty list.")
        if evaluator == "allowed_values" and len(values) > MAX_ALLOWED_VALUES:
            raise ExpectationValidationError("Allowed values are excessively broad.")
        _unique(values, evaluator, ExpectationValidationError)
    if evaluator in {"required_subset", "forbidden_subset"}:
        values = check.get("values")
        if not isinstance(values, list) or not values:
            raise ExpectationValidationError(evaluator + " values must be a non-empty list.")
        _unique(values, evaluator, ExpectationValidationError)
    if evaluator == "numeric_range":
        minimum, maximum = check.get("min"), check.get("max")
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool) or not isinstance(maximum, (int, float)) or isinstance(maximum, bool):
            raise ExpectationValidationError("Numeric range requires numeric min and max.")
        if not math.isfinite(float(minimum)) or not math.isfinite(float(maximum)) or minimum > maximum:
            raise ExpectationValidationError("Invalid numeric range.")
    if evaluator == "structure":
        for key in ("list", "non_empty_strings", "unique_normalized"):
            if key in check and not isinstance(check[key], bool):
                raise ExpectationValidationError(key + " must be boolean.")
        for key in ("min_items", "max_items", "max_item_length", "max_total_length"):
            if key in check and (not isinstance(check[key], int) or isinstance(check[key], bool) or check[key] < 0):
                raise ExpectationValidationError(key + " must be a non-negative integer.")
        if check.get("min_items", 0) > check.get("max_items", MAX_COLLECTION):
            raise ExpectationValidationError("Invalid structure item range.")
        if "required_keys" in check:
            keys = check["required_keys"]
            if not isinstance(keys, list) or not all(isinstance(key, str) and key for key in keys):
                raise ExpectationValidationError("Structure required_keys must be a string list.")
            _unique(keys, "Structure required_keys", ExpectationValidationError)
    if evaluator in {"required_facts", "forbidden_facts"}:
        _validate_facts(check, "facts")
    if evaluator == "canonical_claim":
        if not isinstance(check.get("claim"), dict) or check.get("match", "exact_normalized") not in {"exact_normalized", "core_compatible", "specific_compatible", "material_conflict"}:
            raise ExpectationValidationError("Invalid canonical claim expectation.")
        try:
            normalize_canonical_claim(check["claim"])
        except (TypeError, ValueError) as error:
            raise ExpectationValidationError("Invalid canonical claim expectation: " + str(error)) from error
    if evaluator == "canonical_entities":
        for key in ("required_keys", "forbidden_keys", "required_entities"):
            if key in check and not isinstance(check[key], list):
                raise ExpectationValidationError("Canonical entity collections must be lists.")
        for key in ("required_keys", "forbidden_keys"):
            values = check.get(key, [])
            if not all(isinstance(value, str) and value.strip() for value in values):
                raise ExpectationValidationError(key + " must contain non-empty strings.")
            _unique(values, key, ExpectationValidationError)
        if set(check.get("required_keys", [])) & set(check.get("forbidden_keys", [])):
            raise ExpectationValidationError("Canonical entity keys are contradictory.")
        for entity in check.get("required_entities", []):
            allowed = {"canonical_key", "role", "entity_type", "sport_key", "verified"}
            if not isinstance(entity, dict) or set(entity) - allowed or not isinstance(entity.get("canonical_key"), str) or not entity["canonical_key"].strip():
                raise ExpectationValidationError("Invalid canonical entity expectation.")
            for key in ("role", "entity_type", "sport_key"):
                if key in entity and (not isinstance(entity[key], str) or not entity[key].strip()):
                    raise ExpectationValidationError("Invalid canonical entity " + key + ".")
            if "verified" in entity and not isinstance(entity["verified"], bool):
                raise ExpectationValidationError("Canonical entity verified must be boolean.")
    if evaluator == "language":
        if "primary" in check and (not isinstance(check["primary"], str) or not check["primary"].strip()):
            raise ExpectationValidationError("Language primary must be a non-empty string.")
        if "mixed" in check and not isinstance(check["mixed"], bool):
            raise ExpectationValidationError("Language mixed must be boolean.")
        minimum, maximum = check.get("confidence_min", 0), check.get("confidence_max", 1)
        for value in (minimum, maximum):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                raise ExpectationValidationError("Language confidence bounds must be finite numbers.")
        if not 0 <= minimum <= maximum <= 1:
            raise ExpectationValidationError("Invalid language confidence range.")
        for key in ("required_localized_keys", "forbidden_fallback_terms"):
            if key in check:
                values = check[key]
                if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
                    raise ExpectationValidationError(key + " must be a string list.")
                _unique(values, key, ExpectationValidationError)
    return check


def validate_case(value: Any) -> dict:
    if not isinstance(value, dict):
        raise CaseValidationError("Case must be a JSON object.")
    required = {"case_version", "case_id", "mode", "description", "language", "tags", "input", "replay", "expected", "annotation"}
    if set(value) != required:
        raise CaseValidationError("Case contains missing or unknown top-level fields.")
    reject_non_finite(value)
    if value["case_version"] != CASE_SCHEMA_VERSION:
        raise CaseValidationError("Unsupported case version.")
    if not CASE_ID_RE.fullmatch(str(value["case_id"])):
        raise CaseValidationError("Invalid case ID.")
    if value["mode"] not in MODES:
        raise CaseValidationError("Invalid case mode.")
    if not isinstance(value["description"], str) or not value["description"].strip():
        raise CaseValidationError("Case description is required.")
    if not isinstance(value["language"], dict):
        raise CaseValidationError("Case language must be an object.")
    tags = value["tags"]
    if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
        raise CaseValidationError("Case tags must be non-empty strings.")
    _unique(tags, "Case tags")
    if not isinstance(value["input"], dict):
        raise CaseValidationError("Case input must be an object.")
    replay = value["replay"]
    if not isinstance(replay, dict) or replay.get("kind") not in {"final_output", "provider_raw"}:
        raise CaseValidationError("Invalid replay declaration.")
    required_replay = {"kind", "artifact"} if replay.get("kind") == "final_output" else {"kind", "artifact", "provider", "model", "task", "prompt_contract_version", "normalization_contract"}
    if set(replay) != required_replay or not all(isinstance(replay.get(key), str) and replay[key].strip() for key in required_replay - {"kind"}):
        raise CaseValidationError("Replay metadata is incomplete or contains unknown fields.")
    annotation = value["annotation"]
    annotation_fields = {"annotation_version", "review_status", "notes", "ambiguity", "accepted_alternatives", "provenance_type"}
    if not isinstance(annotation, dict) or set(annotation) != annotation_fields:
        raise CaseValidationError("Invalid annotation object.")
    if not isinstance(annotation["annotation_version"], int) or annotation["annotation_version"] < 1:
        raise CaseValidationError("Annotation version must be a positive integer.")
    if annotation["review_status"] not in REVIEW_STATUSES:
        raise CaseValidationError("Invalid review status.")
    if annotation["provenance_type"] not in PROVENANCE_TYPES:
        raise CaseValidationError("Unknown provenance type.")
    for key in ("ambiguity", "accepted_alternatives"):
        if not isinstance(annotation[key], list):
            raise CaseValidationError(key + " must be a list.")
    expected = value["expected"]
    if not isinstance(expected, dict) or set(expected) - {"checks", "human_review_required", "review_focus"}:
        raise ExpectationValidationError("Invalid expected object.")
    if not isinstance(expected.get("checks"), list) or not expected["checks"]:
        raise ExpectationValidationError("Expected checks must be non-empty.")
    if "human_review_required" in expected and not isinstance(expected["human_review_required"], bool):
        raise ExpectationValidationError("human_review_required must be boolean.")
    if "review_focus" in expected and not isinstance(expected["review_focus"], str):
        raise ExpectationValidationError("review_focus must be a string.")
    for check in expected["checks"]:
        validate_check(check)
    _validate_contradictions(expected["checks"])
    return value


def _validate_contradictions(checks: list[dict]) -> None:
    by_path: dict[str, dict[str, set[str]]] = {}
    for check in checks:
        if check["evaluator"] in {"required_subset", "forbidden_subset", "allowed_values", "forbidden_values"}:
            by_path.setdefault(check.get("path", ""), {})[check["evaluator"]] = {repr(v) for v in check["values"]}
    for path, groups in by_path.items():
        for positive, negative in (("required_subset", "forbidden_subset"), ("allowed_values", "forbidden_values")):
            if groups.get(positive, set()) & groups.get(negative, set()):
                raise ExpectationValidationError("Contradictory expectations at path: " + path)
