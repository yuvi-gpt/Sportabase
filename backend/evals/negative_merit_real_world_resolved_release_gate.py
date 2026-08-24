from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import statistics
import tempfile

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


from app.analysis.canonical_outcome import (
    CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION,
    compare_canonical_claim_to_outcome,
)
from app.analysis.negative_merit import (
    build_negative_merit_shadow,
)
from app.analysis.negative_merit_calibration_dataset import (
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION,
    build_negative_merit_calibration_dataset,
)
from app.db.connection import (
    connect_database,
)
from app.db.schema import (
    SCHEMA,
)
from app.intelligence.adjudication_history import (
    re_adjudicate_claim,
)
from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)
from app.intelligence.entities import (
    upsert_canonical_entity,
)
from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)
from app.intelligence.evidence import (
    record_evidence,
)
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)
from app.services.article_rules import (
    detect_article_type,
    merit_score,
)
from app.services.canonical_outcome_resolution_verifier import (
    CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE,
    CANONICAL_OUTCOME_PROOF_KIND,
    CANONICAL_OUTCOME_PROOF_RELATIONSHIP,
    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
    persist_canonical_outcome_resolution_verified_revision,
)
from app.services.content_resolution import (
    extract_article_content,
    fetch_safe_article_html,
    normalized_analysis_url,
)
from app.services.direct_stakeholder_contradiction_verifier import (
    persist_direct_stakeholder_contradiction_verification,
)
from app.services.machine_verified_contradiction_semantics_verifier import (
    persist_machine_verified_contradiction_semantics_verification,
)

from evals.negative_merit_real_world_candidate_batch import (
    CASES as TWO_GATE_CASE_DEFINITIONS,
    validate_candidate_batch,
)
from evals.negative_merit_real_world_two_gate_calibration import (
    _control_observations,
    _evaluate_two_gate_case,
    select_provisional_penalty,
)


RESOLVED_RELEASE_GATE_VERSION = (
    "negative-merit-real-world-resolved-release-gate-v1"
)

RESOLVED_CASE_VERSION = (
    "negative-merit-real-world-resolved-case-v1"
)

TEMPORAL_CONTROL_VERSION = (
    "negative-merit-temporal-false-positive-control-v1"
)


PIASTRI_CLAIM_URL = (
    "https://media.alpinecars.com/35821/?lang=eng"
)

PIASTRI_OUTCOME_URL = (
    "https://media.alpinecars.com/"
    "pierre-gasly-completes-2023-bwt-alpine-f1-team-driver-line-up/"
    "?lang=eng"
)

CUCURELLA_DENIAL_URL = (
    "https://www.brightonandhovealbion.com/"
    "media-article/Club-statement%3A-Marc-Cucurella"
)

CUCURELLA_COMPLETION_URL = (
    "https://www.brightonandhovealbion.com/"
    "media-article/Marc-Cucurella-makes-record-move-to-Chelsea"
)


PIASTRI_SUBJECT = (
    "motorsport|driver|oscar-piastri"
)

ALPINE_ENTITY_KEY = (
    "motorsport|team|alpine-f1-team"
)


PIASTRI_CANONICAL_CLAIM = {
    "subject_key": PIASTRI_SUBJECT,
    "event_type": "tenure",
    "state": "appointed",
    "negated": False,
    "roles": {
        "organization": (
            ALPINE_ENTITY_KEY
        ),
    },
    "facets": {
        "role": (
            "formula_1_race_driver"
        ),
        "effective_period": (
            "2023-season"
        ),
    },
}


PIASTRI_CANONICAL_OUTCOME = {
    "subject_key": PIASTRI_SUBJECT,
    "event_type": "tenure",
    "state": "appointed",
    "negated": True,
    "roles": {
        "organization": (
            ALPINE_ENTITY_KEY
        ),
    },
    "facets": {
        "role": (
            "formula_1_race_driver"
        ),
        "effective_period": (
            "2023-season"
        ),
    },
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def _digest(
    value: Any,
) -> str:
    return _sha256(
        _canonical_json(
            value
        )
    )


def _domain(
    value: str,
) -> str:
    hostname = (
        urlparse(
            value
        ).hostname
        or ""
    ).lower()

    if hostname.startswith(
        "www."
    ):
        hostname = hostname[
            4:
        ]

    return hostname


def _contains_all(
    text: str,
    terms,
) -> bool:
    haystack = (
        _clean(
            text
        ).casefold()
    )

    return all(
        _clean(
            term
        ).casefold()
        in haystack
        for term
        in terms
    )


def _raw_semantic_text(
    raw_html: str,
) -> str:
    value = html.unescape(
        str(
            raw_html
            or ""
        )
    )

    value = value.replace(
        "\\u0026",
        "&",
    )

    value = value.replace(
        "\\u2019",
        "'",
    )

    value = value.replace(
        "\\u2018",
        "'",
    )

    value = value.replace(
        "\\u201c",
        '"',
    )

    value = value.replace(
        "\\u201d",
        '"',
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    return _clean(
        value
    )


def _capture(
    *,
    url: str,
    expected_domain: str,
    required_terms,
) -> Dict[str, Any]:
    requested = normalized_analysis_url(
        url
    )

    fetched = fetch_safe_article_html(
        requested,
        max_bytes=1_500_000,
        timeout_seconds=15.0,
        max_redirects=4,
    )

    final_url = normalized_analysis_url(
        _clean(
            fetched.get(
                "final_url"
            )
        )
    )

    if (
        _domain(
            final_url
        )
        != expected_domain
    ):
        raise RuntimeError(
            "Unexpected source domain for "
            + requested
        )

    raw_html = str(
        fetched.get(
            "html",
            "",
        )
        or ""
    )

    extraction = extract_article_content(
        raw_html,
        max_chars=30_000,
        min_chars=120,
    )

    title = _clean(
        extraction.get(
            "title"
        )
    )

    body = _clean(
        extraction.get(
            "text"
        )
    )

    combined = (
        title
        + "\n"
        + body
    )

    if len(
        body
    ) < 120:
        raise RuntimeError(
            "Captured article body is too short."
        )

    semantic_source = (
        "article_extraction"
    )

    hash_scope = (
        "extracted_body"
    )

    hash_value = body

    if not _contains_all(
        combined,
        required_terms,
    ):
        raw_semantics = (
            _raw_semantic_text(
                raw_html
            )
        )

        if not _contains_all(
            raw_semantics,
            required_terms,
        ):
            raise RuntimeError(
                "Captured source does not contain "
                "required frozen semantics in either "
                "article extraction or server HTML: "
                + json.dumps(
                    list(
                        required_terms
                    )
                )
            )

        semantic_source = (
            "raw_server_html_fallback"
        )

        hash_scope = (
            "raw_server_html"
        )

        hash_value = raw_html

    captured_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    return {
        "url": final_url,
        "title": title,
        "content_sha256": (
            _sha256(
                hash_value
            )
        ),
        "content_hash_scope": (
            hash_scope
        ),
        "semantic_verification_source": (
            semantic_source
        ),
        "captured_at": captured_at,
        "character_count": len(
            body
        ),
        "paragraph_count": int(
            extraction.get(
                "paragraph_count",
                0,
            )
            or 0
        ),
        "_body": body,
    }


def _domain_resolver(
    value,
):
    return source_domain_for_url(
        value,
        normalize_url=(
            normalized_analysis_url
        ),
    )


def _connection_factory(
    path: Path,
):
    def factory():
        return connect_database(
            path
        )

    return factory


def _initialize_db(
    path: Path,
):
    conn = connect_database(
        path
    )

    try:
        conn.executescript(
            SCHEMA
        )

        conn.commit()

    finally:
        conn.close()


def _seed_baseline(
    *,
    claim,
    connection_factory,
):
    evidence = record_evidence(
        evidence_type=(
            "model_assisted_snapshot"
        ),
        subject_key=(
            claim[
                "subject_key"
            ]
        ),
        observed_at=(
            "2022-08-02T12:01:00+00:00"
        ),
        reference_key=(
            "piastri-tenure-baseline:"
            + claim[
                "id"
            ]
        ),
        verification_status=(
            "unverified"
        ),
        recorded_at=(
            "2022-08-02T12:02:00+00:00"
        ),
        normalize_url=(
            normalized_analysis_url
        ),
        connection_factory=(
            connection_factory
        ),
    )[
        "evidence"
    ]

    record_claim_link(
        claim_id=(
            claim[
                "id"
            ]
        ),
        evidence_id=(
            evidence[
                "id"
            ]
        ),
        relationship_type=(
            "baseline_semantics"
        ),
        confidence=0.90,
        observed_at=(
            "2022-08-02T12:01:00+00:00"
        ),
        recorded_at=(
            "2022-08-02T12:02:30+00:00"
        ),
        connection_factory=(
            connection_factory
        ),
    )

    values = {
        "source_role": (
            "publisher"
        ),
        "authority_class": (
            "none"
        ),
        "reliability_class": (
            "unknown"
        ),
        "provenance_class": (
            "attributed_reporting"
        ),
        "stance": "neutral",
        "independence_status": (
            "unknown"
        ),
    }

    judgments = []

    for field, value in (
        values.items()
    ):
        judgments.append(
            {
                "id": (
                    "piastri-baseline-"
                    + field
                ),
                "field": field,
                "value": value,
                "confidence": 0.90,
                "evaluator_id": (
                    "semantic-model-v1"
                ),
                "evaluator_family": (
                    "observation_semantic_model"
                ),
                "basis_class": (
                    "model_inference"
                ),
                "evidence_ids": [
                    evidence[
                        "id"
                    ]
                ],
                "training_eligible": False,
            }
        )

    return re_adjudicate_claim(
        claim_id=(
            claim[
                "id"
            ]
        ),
        evaluator_runs=[
            {
                "run_id": (
                    "piastri-baseline-run"
                ),
                "evaluator_id": (
                    "semantic-model-v1"
                ),
                "evaluator_family": (
                    "observation_semantic_model"
                ),
                "derivation_mode": (
                    "model_assisted"
                ),
                "judgments": judgments,
            }
        ],
        as_of=(
            "2022-08-02T12:05:00+00:00"
        ),
        trigger_type=(
            "evidence_added"
        ),
        trigger_evidence_ids=[
            evidence[
                "id"
            ]
        ],
        recorded_at=(
            "2022-08-02T12:06:00+00:00"
        ),
        connection_factory=(
            connection_factory
        ),
    )[
        "revision"
    ]


def _build_resolved_piastri_case(
    *,
    claim_capture,
    outcome_capture,
    working_dir: Path,
):
    db_path = (
        working_dir
        / "piastri-resolved.db"
    )

    _initialize_db(
        db_path
    )

    connection_factory = (
        _connection_factory(
            db_path
        )
    )

    source = upsert_intelligence_source(
        url=(
            outcome_capture[
                "url"
            ]
        ),
        display_name=(
            "BWT Alpine F1 Team"
        ),
        source_type=(
            "publisher"
        ),
        seen_at=(
            "2022-08-02T12:00:00+00:00"
        ),
        domain_resolver=(
            _domain_resolver
        ),
        connection_factory=(
            connection_factory
        ),
    )

    claim = upsert_intelligence_claim(
        canonical_key=(
            "article-primary|"
            "piastri-alpine-2023|"
            "tenure"
        ),
        subject_key=(
            PIASTRI_SUBJECT
        ),
        canonical_text=(
            "Oscar Piastri will be promoted "
            "to an Alpine Formula 1 race seat "
            "for the 2023 season."
        ),
        claim_type=(
            "headline_assertion"
        ),
        metadata={
            "canonical_claim_candidate": (
                PIASTRI_CANONICAL_CLAIM
            ),
            "real_world_resolved_eval": True,
            "claim_truth_established": False,
        },
        seen_at=(
            "2022-08-02T12:00:00+00:00"
        ),
        id_resolver=(
            claim_id_for_canonical_key
        ),
        connection_factory=(
            connection_factory
        ),
    )

    _seed_baseline(
        claim=claim,
        connection_factory=(
            connection_factory
        ),
    )

    entity = upsert_canonical_entity(
        entity_key=(
            ALPINE_ENTITY_KEY
        ),
        entity_type="team",
        canonical_name=(
            "BWT Alpine F1 Team"
        ),
        sport_key=(
            "formula_1"
        ),
        seen_at=(
            "2022-08-02T12:07:00+00:00"
        ),
        connection_factory=(
            connection_factory
        ),
    )[
        "entity"
    ]

    source_binding_evidence = (
        record_evidence(
            evidence_type=(
                "source_entity_reference"
            ),
            subject_key=(
                "source-entity|"
                + source[
                    "id"
                ]
                + "|"
                + entity[
                    "id"
                ]
            ),
            observed_at=(
                "2022-08-02T12:07:00+00:00"
            ),
            reference_key=(
                "alpine-official-site:"
                + entity[
                    "id"
                ]
            ),
            verification_status=(
                "verified"
            ),
            recorded_at=(
                "2022-08-02T12:08:00+00:00"
            ),
            metadata={
                "machine_verified": True,
                "claim_truth_established": False,
            },
            normalize_url=(
                normalized_analysis_url
            ),
            connection_factory=(
                connection_factory
            ),
        )[
            "evidence"
        ]
    )

    record_verified_source_entity_binding(
        source_id=(
            source[
                "id"
            ]
        ),
        entity_id=(
            entity[
                "id"
            ]
        ),
        binding_type=(
            "official_site"
        ),
        evidence_id=(
            source_binding_evidence[
                "id"
            ]
        ),
        confidence=0.99,
        observed_at=(
            "2022-08-02T12:07:00+00:00"
        ),
        recorded_at=(
            "2022-08-02T12:08:30+00:00"
        ),
        connection_factory=(
            connection_factory
        ),
    )

    outcome_proof = record_evidence(
        evidence_type=(
            CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE
        ),
        subject_key=(
            claim[
                "subject_key"
            ]
        ),
        observed_at=(
            "2022-10-07T12:00:00+00:00"
        ),
        canonical_url=(
            outcome_capture[
                "url"
            ]
        ),
        reference_key=(
            "piastri-alpine-2023-outcome:"
            + claim[
                "id"
            ]
        ),
        verification_status=(
            "verified"
        ),
        recorded_at=(
            "2022-10-07T12:01:00+00:00"
        ),
        metadata={
            "proof_kind": (
                CANONICAL_OUTCOME_PROOF_KIND
            ),
            "source_id": (
                source[
                    "id"
                ]
            ),
            "claim_id": (
                claim[
                    "id"
                ]
            ),
            "entity_id": (
                entity[
                    "id"
                ]
            ),
            "outcome_candidate": (
                PIASTRI_CANONICAL_OUTCOME
            ),
            "content_sha256": (
                outcome_capture[
                    "content_sha256"
                ]
            ),
            "claim_truth_established": False,
        },
        normalize_url=(
            normalized_analysis_url
        ),
        connection_factory=(
            connection_factory
        ),
    )[
        "evidence"
    ]

    record_verified_claim_entity_participant(
        claim_id=(
            claim[
                "id"
            ]
        ),
        entity_id=(
            entity[
                "id"
            ]
        ),
        participant_role=(
            "counterparty"
        ),
        evidence_id=(
            outcome_proof[
                "id"
            ]
        ),
        confidence=0.99,
        observed_at=(
            "2022-10-07T12:00:00+00:00"
        ),
        recorded_at=(
            "2022-10-07T12:02:00+00:00"
        ),
        connection_factory=(
            connection_factory
        ),
    )

    outcome_observation = (
        record_source_observation(
            source_id=(
                source[
                    "id"
                ]
            ),
            subject_key=(
                claim[
                    "subject_key"
                ]
            ),
            observation_type=(
                "official_statement"
            ),
            observed_at=(
                "2022-10-07T12:03:00+00:00"
            ),
            status="captured",
            claim_summary=(
                "Alpine's official 2023 driver-line-up "
                "announcement identifies Pierre Gasly "
                "alongside Esteban Ocon for the "
                "2023 Formula 1 season."
            ),
            provenance_url=(
                outcome_capture[
                    "url"
                ]
            ),
            confidence=0.99,
            recorded_at=(
                "2022-10-07T12:03:30+00:00"
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            connection_factory=(
                connection_factory
            ),
        )[
            "observation"
        ]
    )

    record_claim_link(
        claim_id=(
            claim[
                "id"
            ]
        ),
        source_observation_id=(
            outcome_observation[
                "id"
            ]
        ),
        relationship_type=(
            "contradicts"
        ),
        confidence=0.99,
        observed_at=(
            "2022-10-07T12:03:00+00:00"
        ),
        recorded_at=(
            "2022-10-07T12:04:00+00:00"
        ),
        metadata={
            "machine_verifiable": True,
            "claim_truth_established": False,
        },
        connection_factory=(
            connection_factory
        ),
    )

    record_claim_link(
        claim_id=(
            claim[
                "id"
            ]
        ),
        evidence_id=(
            outcome_proof[
                "id"
            ]
        ),
        relationship_type=(
            CANONICAL_OUTCOME_PROOF_RELATIONSHIP
        ),
        confidence=1.0,
        observed_at=(
            "2022-10-07T12:00:00+00:00"
        ),
        recorded_at=(
            "2022-10-07T12:05:00+00:00"
        ),
        metadata={
            "machine_verifiable": True,
            "claim_truth_established": False,
        },
        connection_factory=(
            connection_factory
        ),
    )

    direct_verification = (
        persist_direct_stakeholder_contradiction_verification(
            claim_id=(
                claim[
                    "id"
                ]
            ),
            observation_id=(
                outcome_observation[
                    "id"
                ]
            ),
            connection_factory=(
                connection_factory
            ),
            recorded_at=(
                "2022-10-07T12:09:00+00:00"
            ),
        )
    )

    if (
        direct_verification.get(
            "persisted"
        )
        is not True
    ):
        raise RuntimeError(
            "Piastri direct-authority "
            "contradiction verification failed: "
            + str(
                direct_verification.get(
                    "status"
                )
            )
        )

    resolution_verification = (
        persist_canonical_outcome_resolution_verified_revision(
            source_id=(
                source[
                    "id"
                ]
            ),
            claim_id=(
                claim[
                    "id"
                ]
            ),
            proof_evidence_id=(
                outcome_proof[
                    "id"
                ]
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            connection_factory=(
                connection_factory
            ),
            recorded_at=(
                "2022-10-07T12:10:00+00:00"
            ),
        )
    )

    if (
        resolution_verification.get(
            "status"
        )
        != (
            "persisted_verified_"
            "canonical_outcome_resolution"
        )
        or resolution_verification.get(
            "persisted"
        )
        is not True
    ):
        raise RuntimeError(
            "Piastri canonical resolution failed: "
            + str(
                resolution_verification.get(
                    "status"
                )
            )
        )

    semantic_verification = (
        persist_machine_verified_contradiction_semantics_verification(
            claim_id=(
                claim[
                    "id"
                ]
            ),
            connection_factory=(
                connection_factory
            ),
            recorded_at=(
                "2022-10-07T12:11:00+00:00"
            ),
        )
    )

    if (
        semantic_verification.get(
            "persisted"
        )
        is not True
    ):
        raise RuntimeError(
            "Piastri machine-semantic "
            "verification failed: "
            + str(
                semantic_verification.get(
                    "status"
                )
            )
        )

    type_info = detect_article_type(
        claim_capture[
            "title"
        ],
        claim_capture[
            "_body"
        ],
        claim_capture[
            "url"
        ],
    )

    score = merit_score(
        claim_capture[
            "title"
        ],
        claim_capture[
            "_body"
        ],
        claim_capture[
            "url"
        ],
        type_info,
    )

    legacy_score = {
        "total": int(
            score[
                "total"
            ]
        ),
    }

    shadow = build_negative_merit_shadow(
        legacy_score=(
            legacy_score
        ),
        claim_id=(
            claim[
                "id"
            ]
        ),
        contradiction_verification=(
            direct_verification
        ),
        semantic_verification=(
            semantic_verification
        ),
    )

    proposed = shadow[
        "proposed"
    ]

    gates = shadow[
        "evidence_gates"
    ]

    if (
        gates[
            "direct_authority_contradiction_lineage"
        ]
        is not True
        or gates[
            "machine_verified_contradiction_semantics"
        ]
        is not True
        or proposed[
            "eligible_for_penalty_calibration"
        ]
        is not True
    ):
        raise RuntimeError(
            "Piastri resolved case did not "
            "satisfy both negative gates."
        )

    claim_source_capture = {
        "url": (
            claim_capture[
                "url"
            ]
        ),
        "source_id": (
            source[
                "id"
            ]
        ),
        "content_sha256": (
            claim_capture[
                "content_sha256"
            ]
        ),
        "captured_at": (
            claim_capture[
                "captured_at"
            ]
        ),
    }

    outcome_source_capture = {
        "url": (
            outcome_capture[
                "url"
            ]
        ),
        "source_id": (
            source[
                "id"
            ]
        ),
        "content_sha256": (
            outcome_capture[
                "content_sha256"
            ]
        ),
        "captured_at": (
            outcome_capture[
                "captured_at"
            ]
        ),
    }

    observation = {
        "version": (
            NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
        ),
        "id": _sha256(
            "resolved-piastri-alpine-2023"
        ),
        "claim_id": (
            claim[
                "id"
            ]
        ),
        "origin": "real_world",
        "machine_verified": True,
        "observation_class": (
            "resolved_against_claim_observation"
        ),
        "observed_at": (
            outcome_capture[
                "captured_at"
            ]
        ),
        "resolution_status": (
            "resolved_against_claim"
        ),
        "resolution_verification": (
            resolution_verification
        ),
        "legacy_score": (
            legacy_score
        ),
        "source_captures": [
            claim_source_capture,
            outcome_source_capture,
        ],
        "contradiction_verification": (
            direct_verification
        ),
        "semantic_verification": (
            semantic_verification
        ),
    }

    return {
        "version": (
            RESOLVED_CASE_VERSION
        ),
        "case_id": (
            "piastri-alpine-2023-"
            "resolved-against-claim"
        ),
        "claim_id": (
            claim[
                "id"
            ]
        ),
        "subject": (
            "Oscar Piastri"
        ),
        "claim_source": {
            key: value
            for key, value
            in claim_capture.items()
            if key != "_body"
        },
        "outcome_source": {
            key: value
            for key, value
            in outcome_capture.items()
            if key != "_body"
        },
        "canonical_contract_version": (
            CANONICAL_TENURE_OUTCOME_CONTRACT_VERSION
        ),
        "canonical_claim": (
            PIASTRI_CANONICAL_CLAIM
        ),
        "canonical_outcome": (
            PIASTRI_CANONICAL_OUTCOME
        ),
        "current_legacy_merit": (
            int(
                score[
                    "total"
                ]
            )
        ),
        "current_article_type": (
            _clean(
                type_info.get(
                    "primary_type"
                )
            )
        ),
        "direct_contradiction_status": (
            direct_verification[
                "status"
            ]
        ),
        "canonical_resolution_status": (
            resolution_verification[
                "status"
            ]
        ),
        "semantic_status": (
            semantic_verification[
                "status"
            ]
        ),
        "negative_merit_signal": (
            shadow[
                "signal"
            ]
        ),
        "calibration_eligible": True,
        "claim_truth_established": False,
        "live_merit_changed": False,
        "_calibration_observation": (
            observation
        ),
    }


def build_temporal_false_positive_control(
    *,
    denial_capture,
    completion_capture,
):
    claim = {
        "subject_key": (
            "football|player|marc-cucurella"
        ),
        "event_type": "transfer",
        "state": "agreed",
        "negated": False,
        "roles": {
            "destination": (
                "football|club|chelsea"
            ),
            "origin": (
                "football|club|brighton"
            ),
        },
        "facets": {
            "effective_period": (
                "2022-summer"
            ),
            "transfer_kind": (
                "permanent"
            ),
        },
    }

    denial = {
        **claim,
        "state": "failed",
    }

    completion = {
        **claim,
        "state": "completed",
    }

    denial_result = (
        compare_canonical_claim_to_outcome(
            claim_candidate=claim,
            outcome_candidate=denial,
            claim_observed_at=(
                "2022-08-03T18:00:00+00:00"
            ),
            outcome_observed_at=(
                "2022-08-03T20:00:00+00:00"
            ),
        )
    )

    completion_result = (
        compare_canonical_claim_to_outcome(
            claim_candidate=claim,
            outcome_candidate=completion,
            claim_observed_at=(
                "2022-08-03T18:00:00+00:00"
            ),
            outcome_observed_at=(
                "2022-08-05T12:00:00+00:00"
            ),
        )
    )

    if (
        denial_result[
            "direction"
        ]
        != "indeterminate"
        or denial_result[
            "status"
        ]
        != (
            "state_transition_not_decisive"
        )
    ):
        raise RuntimeError(
            "Agreement followed by denial was "
            "incorrectly treated as proven falsehood."
        )

    if (
        completion_result[
            "direction"
        ]
        == "against_claim"
    ):
        raise RuntimeError(
            "Later completion was incorrectly "
            "treated as evidence against the claim."
        )

    return {
        "version": (
            TEMPORAL_CONTROL_VERSION
        ),
        "subject": (
            "Marc Cucurella"
        ),
        "reported_state": (
            "agreed"
        ),
        "direct_club_denial": {
            key: value
            for key, value
            in denial_capture.items()
            if key != "_body"
        },
        "later_official_completion": {
            key: value
            for key, value
            in completion_capture.items()
            if key != "_body"
        },
        "denial_comparison": (
            denial_result
        ),
        "completion_comparison": (
            completion_result
        ),
        "penalty_authorized": False,
        "claim_truth_established": False,
        "safety_rule": (
            "club_denial_does_not_make_"
            "agreement_claim_permanently_false"
        ),
    }


def validate_resolved_release_gate_report(
    report,
):
    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(
            "Resolved release gate report "
            "must be a dictionary."
        )

    if (
        report.get(
            "version"
        )
        != RESOLVED_RELEASE_GATE_VERSION
    ):
        raise ValueError(
            "Unsupported resolved gate version."
        )

    resolved = report.get(
        "resolved_case"
    )

    if not isinstance(
        resolved,
        dict,
    ):
        raise ValueError(
            "Resolved case is missing."
        )

    if (
        resolved.get(
            "canonical_resolution_status"
        )
        != (
            "persisted_verified_"
            "canonical_outcome_resolution"
        )
        or resolved.get(
            "calibration_eligible"
        )
        is not True
    ):
        raise ValueError(
            "Resolved case is not verifier-certified."
        )

    dataset = report.get(
        "calibration_dataset"
    )

    if not isinstance(
        dataset,
        dict,
    ):
        raise ValueError(
            "Calibration dataset is missing."
        )

    calibration = dataset.get(
        "calibration",
        {},
    )

    if (
        calibration.get(
            "resolved_against_claim_case_count"
        )
        != 1
    ):
        raise ValueError(
            "Exactly one real resolved case "
            "is required at this gate."
        )

    if (
        calibration.get(
            "blockers"
        )
        != [
            "numeric_penalty_not_calibrated"
        ]
    ):
        raise ValueError(
            "Resolved-label blocker was "
            "not cleared cleanly."
        )

    selection = report.get(
        "penalty_selection"
    )

    if (
        not isinstance(
            selection,
            dict,
        )
        or float(
            selection.get(
                "provisional_adjustment"
            )
        )
        != -15.0
    ):
        raise ValueError(
            "Provisional -15 calibration "
            "did not remain stable."
        )

    temporal = report.get(
        "temporal_false_positive_control"
    )

    if (
        not isinstance(
            temporal,
            dict,
        )
        or temporal[
            "denial_comparison"
        ][
            "direction"
        ]
        != "indeterminate"
        or temporal.get(
            "penalty_authorized"
        )
        is not False
    ):
        raise ValueError(
            "Temporal false-positive safety "
            "control failed."
        )

    policy = report.get(
        "policy"
    )

    if not isinstance(
        policy,
        dict,
    ):
        raise ValueError(
            "Resolved gate policy missing."
        )

    for field in (
        "production_database_written",
        "provider_call_performed",
        "claim_truth_established",
        "live_negative_merit_authorized",
    ):
        if (
            policy.get(
                field
            )
            is not False
        ):
            raise ValueError(
                "Unsafe resolved-gate policy: "
                + field
            )

    core = {
        key: value
        for key, value
        in report.items()
        if key
        != "manifest_digest"
    }

    expected_digest = _digest(
        core
    )

    if (
        report.get(
            "manifest_digest"
        )
        != expected_digest
    ):
        raise ValueError(
            "Resolved release gate report "
            "digest mismatch."
        )

    return {
        "status": "valid",
        "resolved_case_count": 1,
        "calibration_case_count": (
            dataset[
                "case_count"
            ]
        ),
        "provisional_adjustment": -15.0,
        "remaining_blockers": (
            calibration[
                "blockers"
            ]
        ),
        "manifest_digest": (
            expected_digest
        ),
    }


def build_resolved_release_gate(
    *,
    candidate_manifest_path: Path,
    primary_control_manifest_path: Path,
    batch_control_manifest_path: Path,
):
    print(
        "CAPTURING_RESOLVED_CASE="
        "PIASTRI_ALPINE_2023"
    )

    piastri_claim_capture = _capture(
        url=(
            PIASTRI_CLAIM_URL
        ),
        expected_domain=(
            "media.alpinecars.com"
        ),
        required_terms=['Oscar Piastri', 'race driver', '2023', 'Esteban Ocon'],
    )

    piastri_outcome_capture = _capture(
        url=(
            PIASTRI_OUTCOME_URL
        ),
        expected_domain=(
            "media.alpinecars.com"
        ),
        required_terms=['Pierre Gasly', 'Esteban Ocon', '2023', 'BWT Alpine F1 Team'],
    )

    print(
        "PIASTRI_CLAIM_SHA256="
        + piastri_claim_capture[
            "content_sha256"
        ]
    )

    print(
        "PIASTRI_OUTCOME_SHA256="
        + piastri_outcome_capture[
            "content_sha256"
        ]
    )

    print(
        "CAPTURING_TEMPORAL_CONTROL="
        "CUCURELLA_2022"
    )

    cucurella_denial_capture = _capture(
        url=(
            CUCURELLA_DENIAL_URL
        ),
        expected_domain=(
            "brightonandhovealbion.com"
        ),
        required_terms=['Marc Cucurella', 'no agreement has been reached', 'sell Marc Cucurella'],
    )

    cucurella_completion_capture = (
        _capture(
            url=(
                CUCURELLA_COMPLETION_URL
            ),
            expected_domain=(
                "brightonandhovealbion.com"
            ),
            required_terms=['Marc Cucurella', 'completed a move to Chelsea', 'record transfer fee'],
        )
    )

    temporal_control = (
        build_temporal_false_positive_control(
            denial_capture=(
                cucurella_denial_capture
            ),
            completion_capture=(
                cucurella_completion_capture
            ),
        )
    )

    candidate_manifest = json.loads(
        candidate_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    validate_candidate_batch(
        candidate_manifest
    )

    primary_control_manifest = (
        json.loads(
            primary_control_manifest_path.read_text(
                encoding="utf-8"
            )
        )
    )

    batch_control_manifest = (
        json.loads(
            batch_control_manifest_path.read_text(
                encoding="utf-8"
            )
        )
    )

    definitions = {
        definition[
            "candidate_id"
        ]: definition
        for definition
        in TWO_GATE_CASE_DEFINITIONS
    }

    with tempfile.TemporaryDirectory(
        prefix=(
            "sportabase-resolved-"
            "negative-gate-"
        )
    ) as temp_dir:
        working_dir = Path(
            temp_dir
        )

        resolved_case = (
            _build_resolved_piastri_case(
                claim_capture=(
                    piastri_claim_capture
                ),
                outcome_capture=(
                    piastri_outcome_capture
                ),
                working_dir=(
                    working_dir
                ),
            )
        )

        resolved_observation = (
            resolved_case.pop(
                "_calibration_observation"
            )
        )

        two_gate_observations = []
        two_gate_summaries = []

        two_gate_dir = (
            working_dir
            / "two-gate"
        )

        two_gate_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for case in candidate_manifest[
            "cases"
        ]:
            candidate_id = (
                case[
                    "candidate_id"
                ]
            )

            evaluated = (
                _evaluate_two_gate_case(
                    case=case,
                    definition=(
                        definitions[
                            candidate_id
                        ]
                    ),
                    working_dir=(
                        two_gate_dir
                    ),
                )
            )

            two_gate_observations.append(
                evaluated.pop(
                    "calibration_observation"
                )
            )

            two_gate_summaries.append(
                evaluated
            )

    (
        control_rows,
        control_observations,
    ) = _control_observations(
        primary_manifest=(
            primary_control_manifest
        ),
        batch_manifest=(
            batch_control_manifest
        ),
    )

    calibration_cases = [
        resolved_observation,
        *two_gate_observations,
        *control_observations,
    ]

    dataset = (
        build_negative_merit_calibration_dataset(
            cases=(
                calibration_cases
            )
        )
    )

    if (
        dataset[
            "case_count"
        ]
        != 7
    ):
        raise RuntimeError(
            "Expected seven real-world "
            "calibration observations."
        )

    calibration = dataset[
        "calibration"
    ]

    if (
        calibration[
            "resolved_against_claim_case_count"
        ]
        != 1
    ):
        raise RuntimeError(
            "Resolved case was not admitted "
            "to the calibration dataset."
        )

    if (
        calibration[
            "blockers"
        ]
        != [
            "numeric_penalty_not_calibrated"
        ]
    ):
        raise RuntimeError(
            "Resolved-label blocker did not clear: "
            + json.dumps(
                calibration[
                    "blockers"
                ]
            )
        )

    two_gate_scores = [
        int(
            row[
                "legacy_merit_total"
            ]
        )
        for row
        in two_gate_summaries
    ]

    control_scores = [
        int(
            row[
                "legacy_merit_total"
            ]
        )
        for row
        in control_rows
    ]

    selection = (
        select_provisional_penalty(
            two_gate_scores=(
                two_gate_scores
            ),
            control_scores=(
                control_scores
            ),
        )
    )

    if (
        float(
            selection[
                "provisional_adjustment"
            ]
        )
        != -15.0
    ):
        raise RuntimeError(
            "Provisional penalty changed "
            "after resolved-case admission."
        )

    selection[
        "two_gate_scores"
    ] = two_gate_scores

    selection[
        "control_scores"
    ] = control_scores

    core = {
        "version": (
            RESOLVED_RELEASE_GATE_VERSION
        ),
        "resolved_case": (
            resolved_case
        ),
        "temporal_false_positive_control": (
            temporal_control
        ),
        "two_gate_cases": (
            two_gate_summaries
        ),
        "controls": (
            control_rows
        ),
        "calibration_dataset": (
            dataset
        ),
        "penalty_selection": (
            selection
        ),
        "policy": {
            "real_world_sources_only": True,
            "production_verifier_logic_used": True,
            "temporary_evaluation_database_only": True,
            "production_database_written": False,
            "provider_call_performed": False,
            "claim_truth_established": False,
            "numeric_penalty_live": False,
            "live_negative_merit_authorized": False,
            "resolved_case_is_temporal_not_permanent_truth": True,
            "club_denial_alone_never_authorizes_negative_merit": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "separate_release_certificate_still_required": True,
        },
    }

    report = {
        **core,
        "manifest_digest": (
            _digest(
                core
            )
        ),
    }

    validate_resolved_release_gate_report(
        report
    )

    return report


def main(
    argv=None,
):
    parser = argparse.ArgumentParser(
        description=(
            "Certify the real-world "
            "resolved Negative Merit release gate."
        )
    )

    parser.add_argument(
        "--candidates",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--control-primary",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--control-batch",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args(
        argv
    )

    report = (
        build_resolved_release_gate(
            candidate_manifest_path=(
                args.candidates
            ),
            primary_control_manifest_path=(
                args.control_primary
            ),
            batch_control_manifest_path=(
                args.control_batch
            ),
        )
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    calibration = report[
        "calibration_dataset"
    ][
        "calibration"
    ]

    resolved = report[
        "resolved_case"
    ]

    temporal = report[
        "temporal_false_positive_control"
    ]

    print()
    print(
        "RESOLVED_CASES="
        + str(
            calibration[
                "resolved_against_claim_case_count"
            ]
        )
    )

    print(
        "TOTAL_CALIBRATION_CASES="
        + str(
            report[
                "calibration_dataset"
            ][
                "case_count"
            ]
        )
    )

    print(
        "RESOLVED_CASE="
        + resolved[
            "case_id"
        ]
    )

    print(
        "RESOLVED_CASE_LEGACY_MERIT="
        + str(
            resolved[
                "current_legacy_merit"
            ]
        )
    )

    print(
        "RESOLUTION_STATUS="
        + resolved[
            "canonical_resolution_status"
        ]
    )

    print(
        "TEMPORAL_DENIAL_DIRECTION="
        + temporal[
            "denial_comparison"
        ][
            "direction"
        ]
    )

    print(
        "TEMPORAL_FALSE_POSITIVE_CONTROLS=1"
    )

    print(
        "CALIBRATION_BLOCKERS="
        + json.dumps(
            calibration[
                "blockers"
            ]
        )
    )

    print(
        "PROVISIONAL_NEGATIVE_ADJUSTMENT="
        + str(
            report[
                "penalty_selection"
            ][
                "provisional_adjustment"
            ]
        )
    )

    print(
        "LIVE_NEGATIVE_MERIT_AUTHORIZED=False"
    )

    print(
        "MANIFEST_DIGEST="
        + report[
            "manifest_digest"
        ]
    )

    print(
        "RESOLVED_NEGATIVE_MERIT_GATE=PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
