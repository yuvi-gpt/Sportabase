from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from app.knowledge.entities import (
    ENTITY_TYPES,
    normalize_entity_alias,
)


ENTITY_MENTION_RESOLUTION_VERSION = (
    "entity-mention-resolution-v1"
)

_MAX_QUERY_TOKENS = 48
_MAX_ALIAS_TOKENS = 6
_MAX_QUERY_TERMS = 512


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _normalized_types(entity_types: Iterable[str] | None) -> tuple[str, ...]:
    if entity_types is None:
        return ()

    values = []
    for value in entity_types:
        normalized = _clean(value, 64).casefold()
        if not normalized:
            continue
        if normalized not in ENTITY_TYPES:
            raise ValueError(
                "Entity mention resolution type is unsupported: "
                + normalized
            )
        if normalized not in values:
            values.append(normalized)

    return tuple(values)


def _query_terms(normalized_text: str) -> tuple[str, ...]:
    tokens = [
        token
        for token in normalized_text.split()
        if token
    ][:_MAX_QUERY_TOKENS]

    terms: set[str] = set()
    token_count = len(tokens)

    for start in range(token_count):
        upper = min(
            token_count,
            start + _MAX_ALIAS_TOKENS,
        )
        for end in range(start + 1, upper + 1):
            term = " ".join(tokens[start:end])
            if len(term) >= 2:
                terms.add(term)
            if len(terms) >= _MAX_QUERY_TERMS:
                return tuple(sorted(terms))

    return tuple(sorted(terms))


def _occurrences(normalized_text: str, alias: str) -> list[tuple[int, int]]:
    padded_text = " " + normalized_text + " "
    needle = " " + alias + " "
    spans: list[tuple[int, int]] = []
    offset = 0

    while True:
        index = padded_text.find(needle, offset)
        if index < 0:
            break

        start = index
        end = index + len(alias)
        spans.append((start, end))
        offset = index + 1

    return spans


def _overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(
        start < occupied_end and occupied_start < end
        for occupied_start, occupied_end in occupied
    )


def resolve_entity_mentions(
    *,
    text: str,
    connection_factory,
    entity_types: Iterable[str] | None = None,
    sport_key: str = "",
    max_entities: int = 24,
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Entity mention resolution requires database access."
        )

    raw_text = _clean(text)
    normalized_text = normalize_entity_alias(raw_text)
    normalized_sport = _clean(sport_key, 64).casefold()
    normalized_entity_types = _normalized_types(entity_types)

    try:
        entity_limit = int(max_entities)
    except (TypeError, ValueError) as exc:
        raise ValueError("Entity mention limit must be an integer.") from exc

    if entity_limit < 1 or entity_limit > 100:
        raise ValueError("Entity mention limit must be between 1 and 100.")

    if not normalized_text:
        return {
            "version": ENTITY_MENTION_RESOLUTION_VERSION,
            "status": "no_match",
            "resolved": [],
            "ambiguous": [],
            "counts": {
                "resolved": 0,
                "ambiguous": 0,
            },
            "policy": {
                "exact_alias_only": True,
                "ambiguity_fails_closed": True,
                "no_fuzzy_guessing": True,
                "candidate_only": True,
                "establishes_identity": False,
                "affects_live_merit": False,
            },
        }

    terms = _query_terms(normalized_text)
    if not terms:
        return {
            "version": ENTITY_MENTION_RESOLUTION_VERSION,
            "status": "no_match",
            "resolved": [],
            "ambiguous": [],
            "counts": {
                "resolved": 0,
                "ambiguous": 0,
            },
            "policy": {
                "exact_alias_only": True,
                "ambiguity_fails_closed": True,
                "no_fuzzy_guessing": True,
                "candidate_only": True,
                "establishes_identity": False,
                "affects_live_merit": False,
            },
        }

    placeholders = ",".join("?" for _ in terms)
    conditions = [
        f"a.normalized_alias IN ({placeholders})",
    ]
    parameters: list[Any] = list(terms)

    if normalized_sport:
        conditions.append("e.sport_key = ?")
        parameters.append(normalized_sport)

    if normalized_entity_types:
        type_placeholders = ",".join(
            "?" for _ in normalized_entity_types
        )
        conditions.append(
            f"e.entity_type IN ({type_placeholders})"
        )
        parameters.extend(normalized_entity_types)

    query = """
        SELECT
            a.normalized_alias,
            a.alias_text,
            a.alias_type,
            e.id AS entity_id,
            e.entity_key,
            e.entity_type,
            e.sport_key,
            e.canonical_name
        FROM entity_aliases AS a
        JOIN canonical_entities AS e
          ON e.id = a.entity_id
        WHERE
    """ + " AND ".join(conditions) + """
        ORDER BY
            LENGTH(a.normalized_alias) DESC,
            a.normalized_alias,
            e.entity_type,
            e.sport_key,
            e.canonical_name,
            e.id
    """

    conn = connection_factory()
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                query,
                tuple(parameters),
            ).fetchall()
        ]
    finally:
        conn.close()

    by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        alias = _clean(row.get("normalized_alias"), 256)
        if alias:
            by_alias[alias].append(row)

    occupied: list[tuple[int, int]] = []
    resolved_by_entity: dict[str, dict[str, Any]] = {}
    ambiguous: list[dict[str, Any]] = []

    for alias in sorted(
        by_alias,
        key=lambda value: (-len(value), value),
    ):
        spans = [
            span
            for span in _occurrences(normalized_text, alias)
            if not _overlaps(span, occupied)
        ]
        if not spans:
            continue

        rows_for_alias = by_alias[alias]
        unique_entities: dict[str, dict[str, Any]] = {}
        for row in rows_for_alias:
            unique_entities[str(row["entity_id"])] = row

        if len(unique_entities) != 1:
            ambiguous.append({
                "matched_alias": alias,
                "candidate_count": len(unique_entities),
                "candidates": [
                    {
                        "entity_id": entity_id,
                        "entity_type": _clean(row.get("entity_type"), 64),
                        "sport_key": _clean(row.get("sport_key"), 64),
                        "canonical_name": _clean(row.get("canonical_name"), 256),
                    }
                    for entity_id, row in sorted(
                        unique_entities.items(),
                        key=lambda item: (
                            _clean(item[1].get("entity_type"), 64),
                            _clean(item[1].get("sport_key"), 64),
                            _clean(item[1].get("canonical_name"), 256).casefold(),
                            item[0],
                        ),
                    )
                ],
            })
            occupied.extend(spans)
            continue

        entity_id, row = next(iter(unique_entities.items()))
        existing = resolved_by_entity.get(entity_id)
        if existing is None:
            resolved_by_entity[entity_id] = {
                "entity_id": entity_id,
                "entity_key": _clean(row.get("entity_key"), 256),
                "entity_type": _clean(row.get("entity_type"), 64),
                "sport_key": _clean(row.get("sport_key"), 64),
                "canonical_name": _clean(row.get("canonical_name"), 256),
                "matched_alias": alias,
                "alias_text": _clean(row.get("alias_text"), 256),
                "alias_type": _clean(row.get("alias_type"), 64),
            }
            occupied.extend(spans)

        if len(resolved_by_entity) >= entity_limit:
            break

    resolved = sorted(
        resolved_by_entity.values(),
        key=lambda row: (
            row["entity_type"],
            row["sport_key"],
            row["canonical_name"].casefold(),
            row["entity_id"],
        ),
    )

    if resolved and ambiguous:
        status = "partial_ambiguity"
    elif resolved:
        status = "resolved"
    elif ambiguous:
        status = "ambiguous"
    else:
        status = "no_match"

    return {
        "version": ENTITY_MENTION_RESOLUTION_VERSION,
        "status": status,
        "resolved": resolved,
        "ambiguous": ambiguous,
        "counts": {
            "resolved": len(resolved),
            "ambiguous": len(ambiguous),
        },
        "query": {
            "sport_key": normalized_sport,
            "entity_types": list(normalized_entity_types),
        },
        "policy": {
            "exact_alias_only": True,
            "ambiguity_fails_closed": True,
            "longest_alias_first": True,
            "no_fuzzy_guessing": True,
            "candidate_only": True,
            "establishes_identity": False,
            "verified_binding_required_for_authority": True,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "ENTITY_MENTION_RESOLUTION_VERSION",
    "resolve_entity_mentions",
]
