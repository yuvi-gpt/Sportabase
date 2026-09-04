from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


def normalize_text(value: Any) -> str:
    return re.sub(
        r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))
    ).strip().casefold()


def searchable_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(searchable_text(value[key]) for key in sorted(value))
    if isinstance(value, (list, tuple)):
        return " ".join(searchable_text(item) for item in value)
    return normalize_text(value)


def required_fact_results(candidate: Any, facts: Iterable[dict]) -> list[dict]:
    text = searchable_text(candidate)
    results = []
    for fact in facts:
        phrases = [normalize_text(item) for item in fact["any_phrases"]]
        matched = next((phrase for phrase in phrases if phrase in text), "")
        results.append({
            "fact_id": fact["id"],
            "passed": bool(matched),
            "matched_phrase": matched,
            "message": (
                "required fact matched"
                if matched else "missing required fact: " + fact["id"]
            ),
        })
    return results


def forbidden_fact_results(candidate: Any, facts: Iterable[dict]) -> list[dict]:
    text = searchable_text(candidate)
    results = []
    for fact in facts:
        phrases = [normalize_text(item) for item in fact["phrases"]]
        matched = next((phrase for phrase in phrases if phrase in text), "")
        results.append({
            "fact_id": fact["id"],
            "passed": not bool(matched),
            "matched_phrase": matched,
            "message": (
                "forbidden fact absent"
                if not matched else "forbidden fact found: " + fact["id"]
            ),
        })
    return results


def duplicate_normalized_items(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if normalized in seen:
            duplicates.add(normalized)
        seen.add(normalized)
    return sorted(duplicates)
