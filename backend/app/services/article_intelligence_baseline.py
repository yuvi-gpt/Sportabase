import hashlib

from typing import Any, Dict

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)


ARTICLE_INTELLIGENCE_BASELINE_VERSION = (
    "article-intelligence-baseline-v1"
)


ARTICLE_PRIMARY_CLAIM_TYPES = {
    "official_announcement",
    "transfer_official",
    "transfer_report",
    "transfer_rumor",
    "injury_confirmed",
    "injury_rumor",
    "lineup_confirmed",
    "lineup_predicted",
    "squad_news",
    "discipline_legal",
    "managerial_news",
    "contract_news",
    "fixture_schedule",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def build_article_primary_claim_seed(
    *,
    media_item_id: str,
    title: str,
    url: str,
    article_type: str,
    observed_at: str,
    normalize_url,
) -> Dict[str, Any]:
    media_id = _clean(
        media_item_id
    )

    canonical_text = _clean(
        title
    )

    normalized_type = _key(
        article_type
    )

    normalized_observed_at = _clean(
        observed_at
    )

    if not media_id:
        raise ValueError(
            "Article intelligence media "
            "item ID is required."
        )

    if not canonical_text:
        raise ValueError(
            "Article intelligence title "
            "is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Article intelligence observed "
            "time is required."
        )

    if (
        normalized_type
        not in ARTICLE_PRIMARY_CLAIM_TYPES
    ):
        return {
            "version": (
                ARTICLE_INTELLIGENCE_BASELINE_VERSION
            ),
            "status": "not_claim_bearing",
            "reason": (
                "article_type_not_claim_seeded"
            ),
            "article_type": (
                normalized_type
            ),
        }

    normalized_url = _clean(
        normalize_url(
            url
        )
    )

    if not normalized_url:
        raise ValueError(
            "Article intelligence URL "
            "could not be normalized."
        )

    text_hash = hashlib.sha256(
        canonical_text
        .casefold()
        .encode(
            "utf-8"
        )
    ).hexdigest()

    canonical_key = (
        "article-primary|"
        + media_id
        + "|"
        + text_hash
    )

    subject_key = (
        "article-media|"
        + media_id
    )

    return {
        "version": (
            ARTICLE_INTELLIGENCE_BASELINE_VERSION
        ),
        "status": "claim_seed_ready",
        "media_item_id": media_id,
        "canonical_key": (
            canonical_key
        ),
        "subject_key": subject_key,
        "canonical_text": (
            canonical_text
        ),
        "claim_type": (
            "headline_assertion"
        ),
        "article_type": (
            normalized_type
        ),
        "canonical_url": (
            normalized_url
        ),
        "observed_at": (
            normalized_observed_at
        ),
        "policy": {
            (
                "headline_is_recorded_as_"
                "reported_claim"
            ): True,
            (
                "headline_does_not_"
                "establish_truth"
            ): True,
            (
                "claim_identity_is_"
                "deterministic"
            ): True,
        },
    }


def bind_article_media_source(
    *,
    media_item_id: str,
    source_id: str,
    connection_factory,
) -> Dict[str, Any]:
    normalized_media_item_id = _clean(
        media_item_id
    )
    normalized_source_id = _clean(
        source_id
    )

    if not normalized_media_item_id:
        raise ValueError(
            "Article intelligence media "
            "item ID is required."
        )

    if not normalized_source_id:
        raise ValueError(
            "Article intelligence source "
            "ID is required."
        )

    conn = connection_factory()

    try:
        existing = conn.execute(
            """
            SELECT source_id
            FROM media_items
            WHERE id = ?
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchone()

        if existing is None:
            raise ValueError(
                "Article intelligence media "
                "item does not exist."
            )

        existing_source_id = _clean(
            existing["source_id"]
        )

        if (
            existing_source_id
            and existing_source_id
            != normalized_source_id
        ):
            raise ValueError(
                "Article intelligence media "
                "item is already assigned to "
                "a different source."
            )

        conn.execute(
            """
            UPDATE media_items
            SET source_id = ?
            WHERE id = ?
              AND (
                source_id IS NULL
                OR source_id = ?
              )
            """,
            (
                normalized_source_id,
                normalized_media_item_id,
                normalized_source_id,
            ),
        )

        row = conn.execute(
            """
            SELECT *
            FROM media_items
            WHERE id = ?
            """,
            (
                normalized_media_item_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Article intelligence media "
            "source binding failed."
        )

    return dict(
        row
    )


def persist_article_publisher_media_baseline(
    *,
    media_item_id: str,
    url: str,
    observed_at: str,
    normalize_url,
    connection_factory,
    source_upserter=(
        upsert_intelligence_source
    ),
    media_source_binder=(
        bind_article_media_source
    ),
) -> Dict[str, Any]:
    canonical_url = _clean(
        normalize_url(
            url
        )
    )
    normalized_observed_at = _clean(
        observed_at
    )

    if not canonical_url:
        raise ValueError(
            "Article intelligence URL "
            "could not be normalized."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Article intelligence observed "
            "time is required."
        )

    domain_resolver = (
        lambda value: (
            source_domain_for_url(
                value,
                normalize_url=(
                    normalize_url
                ),
            )
        )
    )

    source = source_upserter(
        url=canonical_url,
        display_name=(
            domain_resolver(
                canonical_url
            )
        ),
        source_type="publisher",
        seen_at=(
            normalized_observed_at
        ),
        metadata={
            "seeded_by": (
                ARTICLE_INTELLIGENCE_BASELINE_VERSION
            ),
        },
        domain_resolver=(
            domain_resolver
        ),
        connection_factory=(
            connection_factory
        ),
    )

    media_item = media_source_binder(
        media_item_id=media_item_id,
        source_id=(
            source["id"]
        ),
        connection_factory=(
            connection_factory
        ),
    )

    return {
        "status": (
            "source_media_baseline_persisted"
        ),
        "canonical_url": canonical_url,
        "source": source,
        "media_item": media_item,
    }


def persist_article_primary_claim_seed(
    *,
    seed: Dict[str, Any],
    type_confidence: float,
    normalize_url,
    connection_factory,
    provenance=None,
    source_upserter=(
        upsert_intelligence_source
    ),
    media_source_binder=(
        bind_article_media_source
    ),
    claim_upserter=(
        upsert_intelligence_claim
    ),
    observation_recorder=(
        record_source_observation
    ),
    claim_link_recorder=(
        record_claim_link
    ),
) -> Dict[str, Any]:
    if not isinstance(
        seed,
        dict,
    ):
        raise ValueError(
            "Article intelligence seed "
            "must be a dictionary."
        )

    if (
        seed.get(
            "status"
        )
        != "claim_seed_ready"
    ):
        raise ValueError(
            "Article intelligence seed "
            "is not ready."
        )

    canonical_url = _clean(
        seed.get(
            "canonical_url"
        )
    )

    observed_at = _clean(
        seed.get(
            "observed_at"
        )
    )

    if provenance is None:
        provenance = (
            persist_article_publisher_media_baseline(
                media_item_id=(
                    seed[
                        "media_item_id"
                    ]
                ),
                url=canonical_url,
                observed_at=observed_at,
                normalize_url=(
                    normalize_url
                ),
                connection_factory=(
                    connection_factory
                ),
                source_upserter=(
                    source_upserter
                ),
                media_source_binder=(
                    media_source_binder
                ),
            )
        )

    if not isinstance(
        provenance,
        dict,
    ):
        raise ValueError(
            "Article publisher/media "
            "baseline is invalid."
        )

    source = provenance.get(
        "source"
    )
    media_item = provenance.get(
        "media_item"
    )

    if not isinstance(
        source,
        dict,
    ) or not _clean(
        source.get(
            "id"
        )
    ):
        raise ValueError(
            "Article publisher baseline "
            "source is unavailable."
        )

    if not isinstance(
        media_item,
        dict,
    ) or _clean(
        media_item.get(
            "id"
        )
    ) != _clean(
        seed.get(
            "media_item_id"
        )
    ):
        raise ValueError(
            "Article publisher baseline "
            "media item is unavailable."
        )

    claim = claim_upserter(
        canonical_key=(
            seed[
                "canonical_key"
            ]
        ),
        subject_key=(
            seed[
                "subject_key"
            ]
        ),
        canonical_text=(
            seed[
                "canonical_text"
            ]
        ),
        claim_type=(
            seed[
                "claim_type"
            ]
        ),
        seen_at=observed_at,
        metadata={
            "seed_basis": (
                "article_headline"
            ),
            "article_type": (
                seed[
                    "article_type"
                ]
            ),
            "truth_established": False,
        },
        id_resolver=(
            claim_id_for_canonical_key
        ),
        connection_factory=(
            connection_factory
        ),
    )

    observation = (
        observation_recorder(
            source_id=(
                source["id"]
            ),
            media_item_id=(
                seed[
                    "media_item_id"
                ]
            ),
            subject_key=(
                seed[
                    "subject_key"
                ]
            ),
            observation_type=(
                "article_headline_report"
            ),
            status="reported",
            claim_summary=(
                seed[
                    "canonical_text"
                ]
            ),
            provenance_url=(
                canonical_url
            ),
            confidence=None,
            observed_at=(
                observed_at
            ),
            metadata={
                "article_type": (
                    seed[
                        "article_type"
                    ]
                ),
                "type_confidence": (
                    float(
                        type_confidence
                    )
                ),
                "truth_established": (
                    False
                ),
            },
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    observation_row = (
        observation[
            "observation"
        ]
    )

    link = claim_link_recorder(
        claim_id=(
            claim["id"]
        ),
        source_observation_id=(
            observation_row[
                "id"
            ]
        ),
        relationship_type="reports",
        confidence=None,
        observed_at=(
            observed_at
        ),
        metadata={
            "relationship_basis": (
                "publisher_reports_claim"
            ),
            "truth_established": False,
        },
        connection_factory=(
            connection_factory
        ),
    )

    return {
        "version": (
            ARTICLE_INTELLIGENCE_BASELINE_VERSION
        ),
        "status": "baseline_persisted",
        "media_item": media_item,
        "claim": claim,
        "source": source,
        "observation": (
            observation_row
        ),
        "claim_link": (
            link["link"]
        ),
        "story": None,
        "policy": {
            (
                "report_link_does_not_"
                "establish_support_or_truth"
            ): True,
            (
                "current_source_does_not_"
                "establish_independence"
            ): True,
            (
                "story_link_requires_"
                "canonical_claim_identity"
            ): True,
            "provider_call_performed": False,
        },
    }


def persist_article_intelligence_baseline(
    *,
    media_item_id: str,
    observed_at: str,
    title: str,
    url: str,
    article_type: str,
    type_confidence: float,
    normalize_url,
    connection_factory,
    provenance_persister=(
        persist_article_publisher_media_baseline
    ),
    seed_persister=(
        persist_article_primary_claim_seed
    ),
) -> Dict[str, Any]:
    provenance = provenance_persister(
        media_item_id=media_item_id,
        url=url,
        observed_at=observed_at,
        normalize_url=normalize_url,
        connection_factory=(
            connection_factory
        ),
    )

    seed = build_article_primary_claim_seed(
        media_item_id=media_item_id,
        title=title,
        url=url,
        article_type=article_type,
        observed_at=observed_at,
        normalize_url=normalize_url,
    )

    if (
        seed.get(
            "status"
        )
        != "claim_seed_ready"
    ):
        return {
            "version": (
                ARTICLE_INTELLIGENCE_BASELINE_VERSION
            ),
            "status": (
                "source_media_baseline_persisted"
            ),
            "article_type": (
                seed.get(
                    "article_type",
                    "",
                )
            ),
            "source": provenance[
                "source"
            ],
            "media_item": provenance[
                "media_item"
            ],
            "claim": None,
            "observation": None,
            "claim_link": None,
            "story": None,
            "claim_baseline": {
                "status": "skipped",
                "reason": (
                    seed.get(
                        "reason"
                    )
                    or (
                        "claim_seed_"
                        "unavailable"
                    )
                ),
            },
            "policy": {
                (
                    "claim_policy_does_not_"
                    "gate_source_provenance"
                ): True,
                (
                    "current_source_does_not_"
                    "establish_independence"
                ): True,
                "truth_established": False,
                "provider_call_performed": False,
            },
        }

    return seed_persister(
        seed=seed,
        type_confidence=type_confidence,
        normalize_url=normalize_url,
        connection_factory=(
            connection_factory
        ),
        provenance=provenance,
    )


__all__ = [
    "ARTICLE_INTELLIGENCE_BASELINE_VERSION",
    "ARTICLE_PRIMARY_CLAIM_TYPES",
    "bind_article_media_source",
    "build_article_primary_claim_seed",
    "persist_article_intelligence_baseline",
    "persist_article_publisher_media_baseline",
    "persist_article_primary_claim_seed",
]
