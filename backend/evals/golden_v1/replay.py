from __future__ import annotations

import json
from typing import Any

from app.services.article_rules import normalize_ai_article_classification
from app.services.article_analysis import normalize_article_bullets
from app.services.video_support import (
    apply_video_extraction_confidence_policy,
    sanitize_video_model_payload,
    validate_video_analysis_consistency,
)

from .errors import ReplayError
from .loader import JSON_ARTIFACT_LIMIT, LoadedCase, read_case_json_artifact, read_json, safe_path

ARTICLE_CONTRACT = "article-single-pass-v1"
VIDEO_CONTRACT = "video-output-v1"


def _raw_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("text"), str):
        return value["text"]
    raise ReplayError("Provider artifact requires a string or a text field.")


def _json_object_from_text(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReplayError("Malformed provider JSON output.") from error
    if not isinstance(value, dict):
        raise ReplayError("Provider output must decode to an object.")
    return value


def replay_case(case: LoadedCase, *, candidate_root=None) -> Any:
    replay = case.data["replay"]
    if candidate_root is not None and replay["kind"] == "final_output":
        root = candidate_root.resolve()
        artifact_path = safe_path(
            root,
            case.data["case_id"] + "/candidate.json",
            label="External candidate artifact",
        )
        artifact = read_json(artifact_path, JSON_ARTIFACT_LIMIT)
    else:
        artifact = read_case_json_artifact(case, replay["artifact"])
    if replay["kind"] == "final_output":
        return artifact

    contract = replay["normalization_contract"]
    payload = _json_object_from_text(_raw_text(artifact))
    if contract == ARTICLE_CONTRACT:
        maximum = int(case.data["input"].get("max_bullets", 3))
        classification = normalize_ai_article_classification(payload)
        return {
            **payload,
            **classification,
            "bullets": normalize_article_bullets(payload.get("bullets", []), maximum),
        }
    if contract == VIDEO_CONTRACT:
        sanitized = sanitize_video_model_payload(payload)
        policy = apply_video_extraction_confidence_policy(
            sanitized,
            case.data["input"].get("transcript_metadata"),
        )
        return validate_video_analysis_consistency(policy["data"])
    raise ReplayError("Unknown normalization contract: " + str(contract))
