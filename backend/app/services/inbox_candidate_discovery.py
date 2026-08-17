from __future__ import annotations

import math
import re
import sqlite3

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from app.intelligence import entities
from app.services import browser_capture_inbox
from app.services import browser_ingestion
from app.services import content_normalization
from app.services import corroboration_semantics


MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION = (
    "multimodal-inbox-candidate-discovery-v1"
)


class InboxCandidateDiscoveryError(RuntimeError):
    pass


class InboxCandidateDiscoveryInputError(
    InboxCandidateDiscoveryError
):
    pass


class InboxCandidateDiscoveryNotFoundError(
    InboxCandidateDiscoveryError
):
    pass


class InboxCandidateDiscoveryLookupError(
    InboxCandidateDiscoveryError
):
    pass


class InboxCandidateDiscoveryIntegrityError(
    InboxCandidateDiscoveryError
):
    pass


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "for", "from", "has", "have", "had", "he", "her",
    "his", "in", "into", "is", "it", "its", "of", "on", "or", "she",
    "that", "the", "their", "they", "this", "to", "was", "were", "will",
    "with", "you", "your",
}


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _bounded_int(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise InboxCandidateDiscoveryInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise InboxCandidateDiscoveryInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise InboxCandidateDiscoveryInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _connect(connection_factory):
    if connection_factory is None:
        raise InboxCandidateDiscoveryLookupError(
            "Inbox discovery requires database access."
        )

    try:
        conn = connection_factory()
    except Exception as error:
        raise InboxCandidateDiscoveryLookupError(
            "Inbox discovery database is unavailable."
        ) from error

    if conn is None:
        raise InboxCandidateDiscoveryLookupError(
            "Inbox discovery database is unavailable."
        )

    return conn


def _parse_time(value: Any):
    text = _clean(value)

    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(timezone.utc)


def _candidate_record_ids(
    *,
    anchor_capture_record_id: str,
    scan_limit: int,
    connection_factory,
):
    conn = _connect(
        connection_factory
    )

    try:
        rows = conn.execute(
            """
            SELECT id
            FROM browser_capture_inbox
            WHERE id != ?
            ORDER BY
              last_received_at DESC,
              id ASC
            LIMIT ?
            """,
            (
                anchor_capture_record_id,
                scan_limit,
            ),
        ).fetchall()
    except sqlite3.Error as error:
        raise InboxCandidateDiscoveryLookupError(
            "Inbox discovery scan failed."
        ) from error
    finally:
        conn.close()

    return [
        _clean(row["id"])
        for row in rows
        if _clean(row["id"])
    ]


def _entity_catalog(connection_factory):
    conn = _connect(
        connection_factory
    )

    try:
        rows = conn.execute(
            """
            SELECT
              e.id AS entity_id,
              e.entity_key,
              e.entity_type,
              e.sport_key,
              e.canonical_name,
              a.alias_text,
              a.alias_type
            FROM canonical_entities AS e
            LEFT JOIN entity_aliases AS a
              ON a.entity_id = e.id
            ORDER BY
              e.entity_type,
              e.sport_key,
              e.canonical_name,
              e.id,
              a.alias_type,
              a.id
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise InboxCandidateDiscoveryLookupError(
            "Canonical entity catalog lookup failed."
        ) from error
    finally:
        conn.close()

    grouped: Dict[str, Dict[str, Any]] = {}

    for raw_row in rows:
        row = dict(raw_row)
        entity_id = _clean(
            row.get("entity_id")
        )

        if not entity_id:
            continue

        candidate = grouped.setdefault(
            entity_id,
            {
                "id": entity_id,
                "entity_key": _clean(
                    row.get("entity_key")
                ),
                "entity_type": _clean(
                    row.get("entity_type")
                ),
                "sport_key": _clean(
                    row.get("sport_key")
                ),
                "canonical_name": _clean(
                    row.get("canonical_name")
                ),
                "aliases": [],
            },
        )

        alias_text = _clean(
            row.get("alias_text")
        )

        if alias_text:
            candidate["aliases"].append({
                "text": alias_text,
                "type": _clean(
                    row.get("alias_type")
                ),
            })

    return list(grouped.values())


def _load_record(
    *,
    capture_record_id: str,
    connection_factory,
    capture_loader,
    anchor: bool,
):
    try:
        return capture_loader(
            capture_record_id=(
                capture_record_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    except (
        browser_capture_inbox
        .BrowserCaptureInboxNotFoundError
    ) as error:
        if anchor:
            raise InboxCandidateDiscoveryNotFoundError(
                "Anchor inbox capture does not exist."
            ) from error

        raise
    except (
        browser_capture_inbox
        .BrowserCaptureInboxIntegrityError
    ) as error:
        if anchor:
            raise InboxCandidateDiscoveryIntegrityError(
                "Anchor inbox capture failed integrity validation."
            ) from error

        raise
    except (
        browser_capture_inbox
        .BrowserCaptureInboxPersistenceError
    ) as error:
        raise InboxCandidateDiscoveryLookupError(
            "Inbox capture lookup failed."
        ) from error
    except (
        browser_capture_inbox
        .BrowserCaptureInboxInputError
    ) as error:
        raise InboxCandidateDiscoveryInputError(
            str(error)
        ) from error


def _normalized_item(
    loaded: Mapping[str, Any],
):
    capture = loaded.get("capture")

    if not isinstance(capture, Mapping):
        raise InboxCandidateDiscoveryIntegrityError(
            "Stored inbox record is missing its capture payload."
        )

    try:
        return browser_ingestion.normalize_browser_capture(
            capture
        )
    except (TypeError, ValueError) as error:
        raise InboxCandidateDiscoveryIntegrityError(
            "Stored inbox capture no longer normalizes safely."
        ) from error


def _text_descriptor(item) -> Dict[str, Any]:
    parts = []
    seen = set()
    title = ""

    for component in item.text_components:
        text = _clean(
            component.text
        )

        if not text:
            continue

        normalized = text.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)

        if (
            not title
            and component.role == "title"
        ):
            title = text

        parts.append(text)

    combined = _clean(
        " ".join(parts)
    )

    if not combined:
        raise InboxCandidateDiscoveryIntegrityError(
            "Inbox capture contains no normalized text for discovery."
        )

    normalized_text = (
        entities.normalize_entity_alias(
            combined
        )
    )

    tokens = {
        token
        for token in normalized_text.split()
        if (
            len(token) >= 3
            and token not in _STOPWORDS
        )
    }

    fingerprint = (
        content_normalization
        .normalized_item_fingerprint(
            item
        )
    )

    if not fingerprint:
        raise InboxCandidateDiscoveryIntegrityError(
            "Inbox capture normalized fingerprint is empty."
        )

    return {
        "title": title,
        "text": combined,
        "semantic_text": combined[:6000],
        "normalized_text": normalized_text,
        "tokens": tokens,
        "fingerprint": fingerprint,
    }


def _entity_mentions(
    descriptor: Mapping[str, Any],
    catalog,
):
    normalized_text = _clean(
        descriptor.get("normalized_text")
    )
    padded = " " + normalized_text + " "
    results = []

    for entity in catalog:
        aliases = [
            {
                "text": _clean(
                    entity.get("canonical_name")
                ),
                "type": "canonical_name",
            }
        ]

        aliases.extend(
            entity.get("aliases")
            if isinstance(
                entity.get("aliases"),
                list,
            )
            else []
        )

        matching = []
        seen_aliases = set()

        for alias in aliases:
            if not isinstance(alias, Mapping):
                continue

            alias_text = _clean(
                alias.get("text")
            )
            normalized_alias = (
                entities.normalize_entity_alias(
                    alias_text
                )
            )

            if not normalized_alias:
                continue

            dedupe_key = normalized_alias

            if dedupe_key in seen_aliases:
                continue

            seen_aliases.add(
                dedupe_key
            )

            needle = (
                " "
                + normalized_alias
                + " "
            )

            if needle not in padded:
                continue

            matching.append({
                "alias_text": alias_text,
                "alias_type": _clean(
                    alias.get("type")
                ) or "canonical_name",
                "normalized_alias": (
                    normalized_alias
                ),
                "mention_count": (
                    padded.count(needle)
                ),
            })

        if not matching:
            continue

        results.append({
            "id": _clean(
                entity.get("id")
            ),
            "entity_key": _clean(
                entity.get("entity_key")
            ),
            "entity_type": _clean(
                entity.get("entity_type")
            ),
            "sport_key": _clean(
                entity.get("sport_key")
            ),
            "canonical_name": _clean(
                entity.get("canonical_name")
            ),
            "matching_mentions": matching,
            "policy": {
                "exact_text_candidate_only": True,
                "alias_match_does_not_verify_subject": True,
                "alias_match_does_not_establish_authority": True,
            },
        })

    results.sort(
        key=lambda row: (
            -sum(
                int(item["mention_count"])
                for item in row[
                    "matching_mentions"
                ]
            ),
            row["canonical_name"].casefold(),
            row["id"],
        )
    )

    return results


def _time_score(
    left: Any,
    right: Any,
):
    left_time = _parse_time(left)
    right_time = _parse_time(right)

    if left_time is None or right_time is None:
        return 0.0, None

    hours = abs(
        (
            left_time - right_time
        ).total_seconds()
    ) / 3600.0

    score = 1.0 / (
        1.0 + (hours / 24.0)
    )

    return score, hours


def _pair_score(
    *,
    anchor_descriptor,
    candidate_descriptor,
    anchor_entities,
    candidate_entities,
    anchor_observed_at,
    candidate_observed_at,
):
    left_tokens = set(
        anchor_descriptor["tokens"]
    )
    right_tokens = set(
        candidate_descriptor["tokens"]
    )

    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens

    jaccard = (
        len(overlap) / len(union)
        if union
        else 0.0
    )

    smaller = min(
        len(left_tokens),
        len(right_tokens),
    )

    containment = (
        len(overlap) / smaller
        if smaller
        else 0.0
    )

    lexical_score = (
        (0.55 * jaccard)
        + (0.45 * containment)
    )

    left_entity_ids = {
        row["id"]
        for row in anchor_entities
    }
    right_entity_ids = {
        row["id"]
        for row in candidate_entities
    }

    shared_entity_ids = (
        left_entity_ids
        & right_entity_ids
    )

    entity_denominator = min(
        len(left_entity_ids),
        len(right_entity_ids),
    )

    entity_score = (
        len(shared_entity_ids)
        / entity_denominator
        if entity_denominator
        else 0.0
    )

    time_score, time_hours = (
        _time_score(
            anchor_observed_at,
            candidate_observed_at,
        )
    )

    score = (
        (0.70 * lexical_score)
        + (0.20 * entity_score)
        + (0.10 * time_score)
    )

    if not math.isfinite(score):
        score = 0.0

    return {
        "candidate_score": round(
            max(0.0, min(1.0, score)),
            6,
        ),
        "lexical_score": round(
            lexical_score,
            6,
        ),
        "entity_score": round(
            entity_score,
            6,
        ),
        "time_score": round(
            time_score,
            6,
        ),
        "time_distance_hours": (
            round(time_hours, 3)
            if time_hours is not None
            else None
        ),
        "shared_token_count": len(
            overlap
        ),
        "shared_tokens": sorted(
            overlap
        )[:24],
        "shared_entity_ids": sorted(
            shared_entity_ids
        ),
    }


def _semantic_result(
    *,
    anchor_capture_record_id: str,
    anchor_descriptor,
    candidate,
    client,
    client_key: str,
    generator,
    semantic_assessor,
):
    if (
        client is None
        or not callable(generator)
    ):
        return {
            "status": "unavailable",
            "reason": "semantic_provider_unavailable",
            "assessment": None,
        }

    claim = {
        "id": (
            "inbox-anchor:"
            + anchor_capture_record_id
        ),
        "canonical_text": (
            anchor_descriptor[
                "semantic_text"
            ]
        ),
    }

    semantic_candidate = {
        "resolution_status": "resolved",
        "extracted_title": candidate[
            "_descriptor"
        ]["title"],
        "final_url": candidate[
            "canonical_url"
        ],
        "text": candidate[
            "_descriptor"
        ]["semantic_text"],
    }

    try:
        result = semantic_assessor(
            claim=claim,
            candidate=semantic_candidate,
            client=client,
            client_key=(
                _clean(client_key)
                or "anonymous"
            ),
            generator=generator,
        )
    except Exception as error:
        return {
            "status": "assessment_failed",
            "reason": "semantic_assessor_failure",
            "error_type": type(error).__name__,
            "error": str(error)[:240],
            "assessment": None,
        }

    if not isinstance(result, Mapping):
        raise InboxCandidateDiscoveryIntegrityError(
            "Semantic candidate assessor returned an invalid result."
        )

    assessment = result.get(
        "assessment"
    )

    if isinstance(assessment, Mapping):
        if assessment.get(
            "independence_established"
        ) is True:
            raise InboxCandidateDiscoveryIntegrityError(
                "Candidate semantics attempted to establish independence."
            )

    return dict(result)


def _public_candidate(candidate):
    return {
        key: value
        for key, value in candidate.items()
        if not key.startswith("_")
    }


def discover_multimodal_inbox_candidates(
    *,
    anchor_capture_record_id: str,
    connection_factory,
    scan_limit: int = 100,
    max_candidates: int = 12,
    semantic_assessments: int = 4,
    gemini_client=None,
    gemini_client_key: str = "anonymous",
    gemini_generator=None,
    capture_loader=(
        browser_capture_inbox
        .load_browser_capture_record
    ),
    semantic_assessor=(
        corroboration_semantics
        .assess_candidate_semantics_with_gemini
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )

    if not anchor_id:
        raise InboxCandidateDiscoveryInputError(
            "Anchor capture record ID is required."
        )

    scan_limit = _bounded_int(
        scan_limit,
        label="Inbox scan limit",
        minimum=1,
        maximum=500,
    )

    max_candidates = _bounded_int(
        max_candidates,
        label="Candidate limit",
        minimum=1,
        maximum=50,
    )

    semantic_assessments = _bounded_int(
        semantic_assessments,
        label="Semantic assessment limit",
        minimum=0,
        maximum=20,
    )

    anchor_loaded = _load_record(
        capture_record_id=anchor_id,
        connection_factory=connection_factory,
        capture_loader=capture_loader,
        anchor=True,
    )

    anchor_item = _normalized_item(
        anchor_loaded
    )
    anchor_descriptor = _text_descriptor(
        anchor_item
    )

    catalog = _entity_catalog(
        connection_factory
    )

    anchor_entities = _entity_mentions(
        anchor_descriptor,
        catalog,
    )

    candidate_ids = _candidate_record_ids(
        anchor_capture_record_id=anchor_id,
        scan_limit=scan_limit,
        connection_factory=connection_factory,
    )

    candidates = []
    load_failures = []
    same_url_excluded = 0
    no_signal_excluded = 0

    for candidate_id in candidate_ids:
        try:
            loaded = _load_record(
                capture_record_id=candidate_id,
                connection_factory=connection_factory,
                capture_loader=capture_loader,
                anchor=False,
            )
            item = _normalized_item(
                loaded
            )
            descriptor = _text_descriptor(
                item
            )
        except (
            browser_capture_inbox
            .BrowserCaptureInboxNotFoundError,
            browser_capture_inbox
            .BrowserCaptureInboxIntegrityError,
            InboxCandidateDiscoveryIntegrityError,
        ) as error:
            load_failures.append({
                "capture_record_id": candidate_id,
                "error_type": type(error).__name__,
                "error": str(error)[:240],
            })
            continue

        canonical_url = _clean(
            loaded.get("canonical_url")
        )

        if (
            canonical_url
            and canonical_url
            == _clean(
                anchor_loaded.get(
                    "canonical_url"
                )
            )
        ):
            same_url_excluded += 1
            continue

        entity_mentions = _entity_mentions(
            descriptor,
            catalog,
        )

        scoring = _pair_score(
            anchor_descriptor=(
                anchor_descriptor
            ),
            candidate_descriptor=descriptor,
            anchor_entities=anchor_entities,
            candidate_entities=entity_mentions,
            anchor_observed_at=(
                anchor_loaded.get(
                    "observed_at"
                )
            ),
            candidate_observed_at=(
                loaded.get(
                    "observed_at"
                )
            ),
        )

        if (
            scoring["shared_token_count"] < 2
            and not scoring[
                "shared_entity_ids"
            ]
        ):
            no_signal_excluded += 1
            continue

        reasons = []

        if scoring[
            "shared_token_count"
        ]:
            reasons.append(
                "shared_text_tokens"
            )

        if scoring[
            "shared_entity_ids"
        ]:
            reasons.append(
                "shared_exact_entity_candidates"
            )

        if scoring[
            "time_distance_hours"
        ] is not None:
            reasons.append(
                "temporal_proximity"
            )

        identical_content = (
            descriptor["fingerprint"]
            == anchor_descriptor[
                "fingerprint"
            ]
        )

        if identical_content:
            reasons.append(
                "identical_normalized_content"
            )

        candidates.append({
            "capture_record_id": candidate_id,
            "canonical_url": canonical_url,
            "platform": _clean(
                loaded.get("platform")
            ),
            "platform_surface": _clean(
                loaded.get(
                    "platform_surface"
                )
            ),
            "observed_at": _clean(
                loaded.get("observed_at")
            ),
            "title": descriptor["title"],
            "candidate_score": scoring[
                "candidate_score"
            ],
            "signals": {
                "lexical_score": scoring[
                    "lexical_score"
                ],
                "entity_score": scoring[
                    "entity_score"
                ],
                "time_score": scoring[
                    "time_score"
                ],
                "time_distance_hours": (
                    scoring[
                        "time_distance_hours"
                    ]
                ),
                "shared_token_count": (
                    scoring[
                        "shared_token_count"
                    ]
                ),
                "shared_tokens": scoring[
                    "shared_tokens"
                ],
                "shared_entity_ids": (
                    scoring[
                        "shared_entity_ids"
                    ]
                ),
                "identical_normalized_content": (
                    identical_content
                ),
            },
            "entity_candidates": (
                entity_mentions
            ),
            "candidate_reasons": reasons,
            "semantic": {
                "status": "not_assessed",
                "assessment": None,
            },
            "policy": {
                "candidate_only": True,
                "same_story_not_established": True,
                "same_claim_not_established": True,
                "subject_not_verified": True,
                "independence_not_established": True,
                "corroboration_not_established": True,
                "affects_live_merit": False,
            },
            "_descriptor": descriptor,
        })

    candidates.sort(
        key=lambda row: (
            -float(
                row["candidate_score"]
            ),
            row["capture_record_id"],
        )
    )

    candidates = candidates[
        :max_candidates
    ]

    semantic_attempts = min(
        semantic_assessments,
        len(candidates),
    )

    assessed = 0
    semantic_failures = 0
    semantic_unavailable = 0
    semantic_same_claim = 0
    semantic_related_claim = 0

    for index, candidate in enumerate(
        candidates
    ):
        if index >= semantic_attempts:
            continue

        semantic = _semantic_result(
            anchor_capture_record_id=anchor_id,
            anchor_descriptor=anchor_descriptor,
            candidate=candidate,
            client=gemini_client,
            client_key=gemini_client_key,
            generator=gemini_generator,
            semantic_assessor=semantic_assessor,
        )

        candidate["semantic"] = semantic

        status = _clean(
            semantic.get("status")
        )

        if status == "assessed":
            assessed += 1
            assessment = semantic.get(
                "assessment"
            )

            if isinstance(
                assessment,
                Mapping,
            ):
                relevance = _clean(
                    assessment.get(
                        "claim_relevance"
                    )
                )

                if relevance == "same_claim":
                    semantic_same_claim += 1
                elif relevance == "related_claim":
                    semantic_related_claim += 1

        elif status == "unavailable":
            semantic_unavailable += 1
        else:
            semantic_failures += 1

    public_candidates = [
        _public_candidate(row)
        for row in candidates
    ]

    status = (
        "candidates_available"
        if public_candidates
        else "no_candidates"
    )

    return {
        "version": (
            MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        ),
        "status": status,
        "anchor_capture_record_id": anchor_id,
        "anchor": {
            "canonical_url": _clean(
                anchor_loaded.get(
                    "canonical_url"
                )
            ),
            "platform": _clean(
                anchor_loaded.get("platform")
            ),
            "platform_surface": _clean(
                anchor_loaded.get(
                    "platform_surface"
                )
            ),
            "observed_at": _clean(
                anchor_loaded.get(
                    "observed_at"
                )
            ),
            "title": anchor_descriptor[
                "title"
            ],
            "entity_candidates": (
                anchor_entities
            ),
        },
        "pair_candidates": public_candidates,
        "load_failures": load_failures,
        "counts": {
            "scan_limit": scan_limit,
            "record_ids_scanned": len(
                candidate_ids
            ),
            "candidate_load_failures": len(
                load_failures
            ),
            "same_url_excluded": (
                same_url_excluded
            ),
            "no_signal_excluded": (
                no_signal_excluded
            ),
            "ranked_candidates": len(
                public_candidates
            ),
            "semantic_attempts": (
                semantic_attempts
            ),
            "semantic_assessed": assessed,
            "semantic_failures": (
                semantic_failures
            ),
            "semantic_unavailable": (
                semantic_unavailable
            ),
            "semantic_same_claim_candidates": (
                semantic_same_claim
            ),
            "semantic_related_claim_candidates": (
                semantic_related_claim
            ),
            "independence_established": 0,
            "corroboration_established": 0,
            "live_merit_effects": 0,
        },
        "policy": {
            "read_only_discovery": True,
            "inbox_records_remain_untrusted": True,
            "anchor_capture_text_is_not_a_verified_claim": True,
            "entity_matching_is_exact_alias_or_canonical_name_only": True,
            "entity_candidates_do_not_verify_subject": True,
            "deterministic_score_is_ranking_only": True,
            "semantic_same_claim_is_candidate_only": True,
            "semantic_stance_does_not_establish_truth": True,
            "semantic_dependency_does_not_establish_independence": True,
            "candidate_discovery_does_not_establish_corroboration": True,
            "manual_or_later_verified_selection_required": True,
            "creates_entity": False,
            "creates_alias": False,
            "creates_source": False,
            "creates_media_item": False,
            "creates_story": False,
            "creates_claim": False,
            "creates_observation": False,
            "creates_evidence": False,
            "creates_verified_binding": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
