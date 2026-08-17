from __future__ import annotations

import hashlib
import json

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping

from .golden_capture import (
    GoldenCaptureError,
    capture_entry,
    clean,
    entity_payload,
    iso,
    platform_url,
)
from .multimodal_golden_cases import (
    CORPUS_POLICY,
    DEFAULT_LIMITS,
    HARD_THRESHOLDS,
    QUALITY_TARGETS,
    MULTIMODAL_GOLDEN_DATASET_ID,
    MULTIMODAL_GOLDEN_SET_VERSION,
    frozen_case_specs,
)


class MultimodalGoldenDatasetError(RuntimeError):
    pass


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _entity(value, sport):
    try:
        return entity_payload(value, sport=sport)
    except GoldenCaptureError as error:
        raise MultimodalGoldenDatasetError(str(error)) from error


def _entry(platform, text, base, hours, slug, index, role="candidate", url=""):
    return capture_entry(
        platform=platform,
        text=text,
        observed_at=iso(base, hours),
        slug=slug,
        index=index,
        role=role,
        url=url,
    )


def _full_pipeline(anchor_platform, accept, reject):
    return {
        "required_accept_labels": list(accept),
        "required_reject_labels": list(reject),
        "expected_story_count": 1,
        "expected_merit_baseline_mode": (
            "legacy_merit" if anchor_platform == "web" else "not_applicable"
        ),
        "synthetic_merit_baseline_used": False,
        "affects_live_merit": False,
    }


def _standard_case(spec: Mapping[str, Any], index: int) -> Dict[str, Any]:
    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=index * 5)
    slug = clean(spec["case_id"])
    anchor_platform = clean(spec["anchor_platform"])
    related_platforms = list(spec["related_platforms"])
    anchor_url = platform_url(anchor_platform, slug, index * 10)
    entity = _entity(spec["entity"], spec["sport"])

    captures = {
        "anchor": _entry(anchor_platform, spec["anchor"], base, 0, slug, index * 10, "anchor", anchor_url),
        "related_primary": _entry(related_platforms[0], spec["related"][0], base, 1, slug, index * 10 + 1),
        "related_secondary": _entry(related_platforms[1], spec["related"][1], base, 2, slug, index * 10 + 2),
        "hard_negative_same_subject": _entry("x", spec["hard_negative"], base, 3, slug, index * 10 + 3),
        "unrelated_no_signal": _entry("web", spec["unrelated"], base, 4, slug, index * 10 + 4),
        "same_url_duplicate": _entry(
            anchor_platform,
            clean(spec["anchor"]) + " Duplicate page snapshot.",
            base,
            5,
            slug,
            index * 10 + 5,
            url=anchor_url,
        ),
    }

    return {
        "case_id": slug,
        "sport": clean(spec["sport"]),
        "scenario_basis": "historical_real_world_scenario",
        "scenario_note": (
            "Frozen, original paraphrase of a historical sports scenario; "
            "publisher wording is not copied."
        ),
        "entities": [entity],
        "captures": captures,
        "expectations": {
            "discovery_status": "candidates_available",
            "required_shortlist_labels": [
                "related_primary",
                "related_secondary",
                "hard_negative_same_subject",
            ],
            "forbidden_shortlist_labels": [
                "unrelated_no_signal",
                "same_url_duplicate",
            ],
            "selection_status": "cluster_selected",
            "expected_subject_entity_id": entity["id"],
            "required_member_labels": [
                "related_primary",
                "related_secondary",
                "hard_negative_same_subject",
            ],
            "required_rejected_labels": [],
            "required_identical_content_labels": [],
            "full_pipeline": _full_pipeline(
                anchor_platform,
                ["related_primary", "related_secondary"],
                ["hard_negative_same_subject"],
            ),
        },
    }


def _special_case(spec: Mapping[str, Any], index: int) -> Dict[str, Any]:
    kind = clean(spec["kind"])
    slug = clean(spec["case_id"])
    sport = clean(spec["sport"])
    base = datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc) + timedelta(days=index * 3)

    if kind == "multilingual":
        entity = _entity(spec["entity"], sport)
        captures = {
            "anchor": _entry("web", spec["anchor"], base, 0, slug, index * 10, "anchor"),
            "spanish_related": _entry("x", spec["related"][0], base, 1, slug, index * 10 + 1),
            "french_related": _entry("instagram", spec["related"][1], base, 2, slug, index * 10 + 2),
            "hard_negative_same_subject": _entry("reddit", spec["hard_negative"], base, 3, slug, index * 10 + 3),
            "unrelated_no_signal": _entry("web", spec["unrelated"], base, 4, slug, index * 10 + 4),
        }
        expectations = {
            "discovery_status": "candidates_available",
            "required_shortlist_labels": ["spanish_related", "french_related", "hard_negative_same_subject"],
            "forbidden_shortlist_labels": ["unrelated_no_signal"],
            "selection_status": "cluster_selected",
            "expected_subject_entity_id": entity["id"],
            "required_member_labels": ["spanish_related", "french_related", "hard_negative_same_subject"],
            "required_rejected_labels": [],
            "required_identical_content_labels": [],
            "full_pipeline": _full_pipeline(
                "web",
                ["spanish_related", "french_related"],
                ["hard_negative_same_subject"],
            ),
        }
        note = "Hamilton-to-Ferrari scenario with original Spanish and French paraphrases."
        entities = [entity]

    elif kind == "identical_content":
        entity = _entity(spec["entity"], sport)
        captures = {
            "anchor": _entry("web", spec["anchor"], base, 0, slug, index * 10, "anchor"),
            "identical_copy": _entry("x", spec["anchor"], base, 0.25, slug, index * 10 + 1),
            "related_secondary": _entry("youtube", spec["related"], base, 1, slug, index * 10 + 2),
            "hard_negative_same_subject": _entry("reddit", spec["hard_negative"], base, 2, slug, index * 10 + 3),
            "unrelated_no_signal": _entry("web", spec["unrelated"], base, 3, slug, index * 10 + 4),
        }
        full = _full_pipeline(
            "web",
            ["identical_copy", "related_secondary"],
            ["hard_negative_same_subject"],
        )
        full["independence_must_not_be_inferred_from_identical_labels"] = ["identical_copy"]
        expectations = {
            "discovery_status": "candidates_available",
            "required_shortlist_labels": ["identical_copy", "related_secondary", "hard_negative_same_subject"],
            "forbidden_shortlist_labels": ["unrelated_no_signal"],
            "selection_status": "cluster_selected",
            "expected_subject_entity_id": entity["id"],
            "required_member_labels": ["identical_copy", "related_secondary", "hard_negative_same_subject"],
            "required_rejected_labels": [],
            "required_identical_content_labels": [],
            "full_pipeline": full,
        }
        note = (
            "Sainz-to-Williams scenario with separately captured URLs carrying "
            "identical semantic text; dependency must never be inferred from text identity alone."
        )
        entities = [entity]

    elif kind == "ambiguous_subject":
        entities = [_entity(value, sport) for value in spec["entities"]]
        captures = {
            "anchor": _entry("web", spec["anchor"], base, 0, slug, index * 10, "anchor"),
            "candidate_a": _entry("x", spec["candidate_a"], base, 1, slug, index * 10 + 1),
            "candidate_b": _entry("youtube", spec["candidate_b"], base, 2, slug, index * 10 + 2),
            "unrelated_no_signal": _entry("web", spec["unrelated"], base, 3, slug, index * 10 + 3),
        }
        expectations = {
            "discovery_status": "candidates_available",
            "required_shortlist_labels": ["candidate_a", "candidate_b"],
            "forbidden_shortlist_labels": ["unrelated_no_signal"],
            "selection_status": "not_ready_ambiguous",
            "expected_subject_entity_id": "",
            "required_member_labels": [],
            "required_rejected_labels": [],
            "required_identical_content_labels": [],
            "full_pipeline": {"expected_status": "not_ready"},
        }
        note = "Liverpool transition scenario deliberately creates two exact subject partitions."

    elif kind == "multiple_shared_entities":
        entities = [_entity(value, sport) for value in spec["entities"]]
        captures = {
            "anchor": _entry("web", spec["anchor"], base, 0, slug, index * 10, "anchor"),
            "double_shared": _entry("x", spec["double_shared"], base, 1, slug, index * 10 + 1),
            "single_shared": _entry("reddit", spec["single_shared"], base, 2, slug, index * 10 + 2),
            "unrelated_no_signal": _entry("web", spec["unrelated"], base, 3, slug, index * 10 + 3),
        }
        expectations = {
            "discovery_status": "candidates_available",
            "required_shortlist_labels": ["double_shared", "single_shared"],
            "forbidden_shortlist_labels": ["unrelated_no_signal"],
            "selection_status": "cluster_selected",
            "expected_subject_entity_id": entities[0]["id"],
            "required_member_labels": ["single_shared"],
            "required_rejected_labels": ["double_shared"],
            "required_identical_content_labels": [],
            "full_pipeline": _full_pipeline("web", ["single_shared"], []),
        }
        note = (
            "One candidate shares two catalog entities and must be rejected while "
            "a single-entity partition remains usable."
        )

    elif kind == "no_signal":
        entity = _entity(spec["entity"], sport)
        entities = [entity]
        captures = {
            "anchor": _entry("web", spec["anchor"], base, 0, slug, index * 10, "anchor"),
            "unrelated_one": _entry("web", spec["unrelated"][0], base, 1, slug, index * 10 + 1),
            "unrelated_two": _entry("reddit", spec["unrelated"][1], base, 2, slug, index * 10 + 2),
        }
        expectations = {
            "discovery_status": "no_candidates",
            "required_shortlist_labels": [],
            "forbidden_shortlist_labels": ["unrelated_one", "unrelated_two"],
            "selection_status": "not_ready_no_candidates",
            "expected_subject_entity_id": "",
            "required_member_labels": [],
            "required_rejected_labels": [],
            "required_identical_content_labels": [],
            "full_pipeline": {"expected_status": "not_ready"},
        }
        note = "Only unrelated captures are present; discovery and routing must fail closed."

    else:
        raise MultimodalGoldenDatasetError("Unsupported special golden case kind: " + kind)

    return {
        "case_id": slug,
        "sport": sport,
        "scenario_basis": "historical_real_world_scenario",
        "scenario_note": note,
        "entities": entities,
        "captures": captures,
        "expectations": expectations,
    }


def build_golden_cases() -> list[Dict[str, Any]]:
    result = []
    for index, spec in enumerate(frozen_case_specs(), 1):
        result.append(
            _special_case(spec, index)
            if "kind" in spec
            else _standard_case(spec, index)
        )
    validate_golden_cases(result)
    return result


def validate_golden_cases(cases: Iterable[Mapping[str, Any]]) -> None:
    values = list(cases)
    if len(values) < 20:
        raise MultimodalGoldenDatasetError("Golden corpus must contain at least 20 cases.")

    seen = set()
    sports = set()
    platforms = set()

    for case in values:
        case_id = clean(case.get("case_id"))
        if not case_id or case_id in seen:
            raise MultimodalGoldenDatasetError("Golden case IDs must be unique and nonempty.")
        seen.add(case_id)
        sports.add(clean(case.get("sport")))

        captures = case.get("captures")
        if not isinstance(captures, Mapping) or "anchor" not in captures:
            raise MultimodalGoldenDatasetError("Golden case must contain an anchor capture.")

        labels = set(captures) - {"anchor"}
        for wrapped in captures.values():
            if not isinstance(wrapped, Mapping) or not isinstance(wrapped.get("capture"), Mapping):
                raise MultimodalGoldenDatasetError("Golden capture entry is invalid.")
            platforms.add(clean(wrapped["capture"].get("payload", {}).get("platform")))

        expectations = case.get("expectations")
        if not isinstance(expectations, Mapping):
            raise MultimodalGoldenDatasetError("Golden expectations are missing.")
        for field in (
            "required_shortlist_labels",
            "forbidden_shortlist_labels",
            "required_member_labels",
            "required_rejected_labels",
            "required_identical_content_labels",
        ):
            expected_labels = expectations.get(field, [])
            if not isinstance(expected_labels, list) or not set(expected_labels).issubset(labels):
                raise MultimodalGoldenDatasetError(
                    "Golden expectation references unknown labels: " + field
                )

    if sports != {"football", "f1"}:
        raise MultimodalGoldenDatasetError("Golden corpus must cover football and F1.")

    required_platforms = {
        "web", "x", "instagram", "tiktok", "reddit", "facebook", "youtube"
    }
    if not required_platforms.issubset(platforms):
        raise MultimodalGoldenDatasetError("Golden corpus platform coverage is incomplete.")


def golden_dataset_descriptor() -> Dict[str, Any]:
    cases = build_golden_cases()
    descriptor = {
        "version": MULTIMODAL_GOLDEN_SET_VERSION,
        "dataset_id": MULTIMODAL_GOLDEN_DATASET_ID,
        "corpus_policy": deepcopy(CORPUS_POLICY),
        "default_limits": deepcopy(DEFAULT_LIMITS),
        "hard_thresholds": deepcopy(HARD_THRESHOLDS),
        "quality_targets": deepcopy(QUALITY_TARGETS),
        "case_count": len(cases),
        "capture_count": sum(len(case["captures"]) for case in cases),
        "sports": sorted({case["sport"] for case in cases}),
        "platforms": sorted({
            wrapped["capture"]["payload"]["platform"]
            for case in cases
            for wrapped in case["captures"].values()
        }),
    }
    descriptor["dataset_digest"] = _digest({
        "version": MULTIMODAL_GOLDEN_SET_VERSION,
        "cases": cases,
    })
    return descriptor
