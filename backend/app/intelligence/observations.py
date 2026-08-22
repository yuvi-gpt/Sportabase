"""Compatibility facade for persisted intelligence observations.

Article-headline observations receive deterministic, candidate-only entity
resolution metadata when the canonical entity store already contains exact
aliases. Resolution is fail-open and never writes verified participant links.
"""

from __future__ import annotations

import importlib as _importlib
from typing import Any, Dict, Optional

from app.intelligence.claim_entity_context import (
    build_claim_entity_context,
)
from app.intelligence.entity_resolution_runtime import (
    resolve_entity_mentions,
)


_implementation = _importlib.import_module(
    "app.intelligence.records.observations"
)


ENTITY_OBSERVATION_INTEGRATION_VERSION = (
    "entity-observation-integration-v1"
)


def _entity_resolution_metadata(
    *,
    subject_key: str,
    observation_type: str,
    claim_summary: str,
    metadata: Optional[Dict[str, Any]],
    connection_factory,
) -> Optional[Dict[str, Any]]:
    payload = dict(metadata or {})

    if (
        str(observation_type or "").strip().casefold()
        != "article_headline_report"
        or not str(claim_summary or "").strip()
        or connection_factory is None
    ):
        return payload

    try:
        resolution = resolve_entity_mentions(
            text=claim_summary,
            connection_factory=connection_factory,
        )
    except Exception:
        return payload

    if resolution.get("status") not in {
        "resolved",
        "partial_ambiguity",
        "ambiguous",
    }:
        return payload

    payload["entity_resolution"] = {
        **resolution,
        "integration_version": (
            ENTITY_OBSERVATION_INTEGRATION_VERSION
        ),
    }

    try:
        claim_context = build_claim_entity_context(
            claim_text=claim_summary,
            subject_key=subject_key,
            connection_factory=connection_factory,
        )
    except Exception:
        return payload

    if claim_context.get("status") in {
        "ready",
        "partial_ambiguity",
    }:
        payload["claim_entity_context"] = claim_context

    return payload


def record_source_observation(
    *,
    source_id: str,
    subject_key: str,
    observation_type: str,
    observed_at: str,
    status: str = "unresolved",
    claim_summary: str = "",
    provenance_url: str = "",
    confidence: Optional[float] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    normalize_url=None,
    connection_factory=None,
):
    enriched_metadata = _entity_resolution_metadata(
        subject_key=subject_key,
        observation_type=observation_type,
        claim_summary=claim_summary,
        metadata=metadata,
        connection_factory=connection_factory,
    )

    return _implementation.record_source_observation(
        source_id=source_id,
        subject_key=subject_key,
        observation_type=observation_type,
        observed_at=observed_at,
        status=status,
        claim_summary=claim_summary,
        provenance_url=provenance_url,
        confidence=confidence,
        media_item_id=media_item_id,
        story_id=story_id,
        recorded_at=recorded_at,
        metadata=enriched_metadata,
        normalize_url=normalize_url,
        connection_factory=connection_factory,
    )


record_reporter_observation = (
    _implementation.record_reporter_observation
)


def __getattr__(name):
    return getattr(_implementation, name)


def __dir__():
    return sorted(
        set(globals()) | set(dir(_implementation))
    )


__all__ = [
    "ENTITY_OBSERVATION_INTEGRATION_VERSION",
    "record_source_observation",
    "record_reporter_observation",
]
