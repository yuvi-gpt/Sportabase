from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import tempfile

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


from app.analysis.negative_merit import (
    build_negative_merit_shadow,
)

from app.analysis.negative_merit_calibration_dataset import (
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION,
    build_negative_merit_calibration_dataset,
)

from app.analysis.trusted_validation import (
    VALIDATION_REFERENCE_BASIS_BY_FIELD,
)

from app.analysis.verification.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
)

from app.analysis.verification.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
    build_direct_stakeholder_contradiction_candidate,
    persist_direct_stakeholder_contradiction_verification,
)

from app.analysis.verification.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
    build_machine_verified_contradiction_semantics_candidate,
    persist_machine_verified_contradiction_semantics_verification,
)

from app.analysis.verification import (
    machine_verified_revision_runtime as machine_revision_runtime,
)

from app.intelligence.entity_bindings import (
    VERIFIED_ENTITY_MATCH_VERSION,
)

from app.services.content_resolution import (
    extract_article_content,
    fetch_safe_article_html,
    normalized_analysis_url,
)

from evals.negative_merit_real_world_candidate_batch import (
    CASES,
    _clean as candidate_clean,
    _search_text,
    validate_candidate_batch,
)


REAL_WORLD_TWO_GATE_CALIBRATION_VERSION = (
    "negative-merit-real-world-two-gate-calibration-v1"
)

REAL_WORLD_TWO_GATE_EVAL_VERSION = (
    "negative-merit-real-world-two-gate-eval-v1"
)

PROVISIONAL_PENALTY_CAP = 15
PROVISIONAL_PENALTY_FLOOR = 5


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

    if hostname.startswith(
        "uk."
    ):
        hostname = hostname[
            3:
        ]

    return hostname


def _source_id(
    url: str,
) -> str:
    return _sha256(
        "evaluation-source|"
        + _domain(
            url
        )
    )


def _stable_id(
    prefix: str,
    value: Any,
) -> str:
    return _sha256(
        prefix
        + "|"
        + _canonical_json(
            value
        )
    )


def _parse_time(
    value: str,
) -> datetime:
    text = _clean(
        value
    )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    parsed = datetime.fromisoformat(
        text
    )

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            "Timestamp must include timezone."
        )

    return parsed


def _find_term(
    text: str,
    terms,
) -> str:
    haystack = _search_text(
        text
    )

    for term in terms:
        if (
            _search_text(
                term
            )
            in haystack
        ):
            return term

    return ""


def select_provisional_penalty(
    *,
    two_gate_scores,
    control_scores,
) -> Dict[str, Any]:
    negative = [
        float(
            value
        )
        for value
        in two_gate_scores
    ]

    controls = [
        float(
            value
        )
        for value
        in control_scores
    ]

    if (
        len(
            negative
        )
        < 3
        or len(
            controls
        )
        < 3
    ):
        return {
            "status": (
                "insufficient_case_count"
            ),
            "provisional_adjustment": None,
            "release_authorized": False,
        }

    negative_median = float(
        statistics.median(
            negative
        )
    )

    control_median = float(
        statistics.median(
            controls
        )
    )

    separation = (
        control_median
        - negative_median
    )

    if separation <= 0:
        return {
            "status": (
                "no_positive_median_separation"
            ),
            "two_gate_median": (
                negative_median
            ),
            "control_median": (
                control_median
            ),
            "median_separation": (
                separation
            ),
            "provisional_adjustment": None,
            "release_authorized": False,
        }

    magnitude = int(
        math.ceil(
            separation
            / 2.0
        )
    )

    magnitude = min(
        PROVISIONAL_PENALTY_CAP,
        max(
            PROVISIONAL_PENALTY_FLOOR,
            magnitude,
        ),
    )

    adjustment = float(
        -magnitude
    )

    return {
        "status": (
            "provisional_penalty_selected"
        ),
        "selection_rule": (
            "negative_half_of_median_"
            "two_gate_control_separation_"
            "rounded_up_and_capped"
        ),
        "two_gate_median": (
            negative_median
        ),
        "control_median": (
            control_median
        ),
        "median_separation": (
            separation
        ),
        "cap": (
            PROVISIONAL_PENALTY_CAP
        ),
        "floor": (
            PROVISIONAL_PENALTY_FLOOR
        ),
        "provisional_adjustment": (
            adjustment
        ),
        "release_authorized": False,
        "requires_separate_release_certificate": True,
    }


def _connection_factory(
    path: Path,
):
    def factory():
        conn = sqlite3.connect(
            path
        )

        conn.row_factory = (
            sqlite3.Row
        )

        return conn

    return factory


def _initialize_eval_db(
    path: Path,
) -> None:
    conn = sqlite3.connect(
        path
    )

    try:
        conn.executescript(
            """
            CREATE TABLE intelligence_claims (
              id TEXT PRIMARY KEY,
              subject_key TEXT NOT NULL,
              canonical_text TEXT NOT NULL
            );

            CREATE TABLE source_observations (
              id TEXT PRIMARY KEY,
              subject_key TEXT NOT NULL,
              source_id TEXT NOT NULL,
              observed_at TEXT NOT NULL
            );

            CREATE TABLE claim_links (
              id TEXT PRIMARY KEY,
              claim_id TEXT NOT NULL,
              source_observation_id TEXT,
              evidence_id TEXT,
              relationship_type TEXT NOT NULL,
              confidence REAL,
              observed_at TEXT,
              recorded_at TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE evidence_records (
              id TEXT PRIMARY KEY,
              evidence_type TEXT NOT NULL,
              subject_key TEXT NOT NULL,
              observed_at TEXT NOT NULL,
              canonical_url TEXT,
              reference_key TEXT,
              verification_status TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )

        conn.commit()

    finally:
        conn.close()


def _refetch_frozen_page(
    *,
    capture: Dict[str, Any],
    subject_terms,
    semantic_terms,
) -> Dict[str, Any]:
    frozen_url = normalized_analysis_url(
        _clean(
            capture.get(
                "final_url"
            )
        )
    )

    frozen_hash = _clean(
        capture.get(
            "content_sha256"
        )
    ).lower()

    fetched = fetch_safe_article_html(
        frozen_url,
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

    if final_url != frozen_url:
        raise RuntimeError(
            "Frozen source URL redirected "
            "to a different canonical URL."
        )

    extraction = extract_article_content(
        fetched.get(
            "html",
            "",
        ),
        max_chars=30_000,
        min_chars=120,
    )

    title = candidate_clean(
        extraction.get(
            "title"
        )
    )

    body = candidate_clean(
        extraction.get(
            "text"
        )
    )

    content_hash = _sha256(
        body
    )

    if content_hash != frozen_hash:
        raise RuntimeError(
            "Frozen real-world capture hash "
            "changed since collection."
        )

    combined = (
        title
        + "\n"
        + body
    )

    for subject_term in subject_terms:
        if (
            _search_text(
                subject_term
            )
            not in _search_text(
                combined
            )
        ):
            raise RuntimeError(
                "Frozen source no longer contains "
                "required subject identity."
            )

    matched_semantic_term = (
        _find_term(
            combined,
            semantic_terms,
        )
    )

    if not matched_semantic_term:
        raise RuntimeError(
            "Frozen source does not contain "
            "the deterministic semantic phrase."
        )

    return {
        "url": final_url,
        "title": title,
        "body_sha256": (
            content_hash
        ),
        "matched_semantic_term": (
            matched_semantic_term
        ),
        "character_count": len(
            body
        ),
    }


def _make_recorders(
    *,
    connection_factory,
):
    def evidence_recorder(
        **kwargs,
    ):
        evidence_type = _clean(
            kwargs.get(
                "evidence_type"
            )
        )

        subject_key = _clean(
            kwargs.get(
                "subject_key"
            )
        )

        observed_at = _clean(
            kwargs.get(
                "observed_at"
            )
        )

        canonical_url = _clean(
            kwargs.get(
                "canonical_url"
            )
        )

        reference_key = _clean(
            kwargs.get(
                "reference_key"
            )
        )

        verification_status = _clean(
            kwargs.get(
                "verification_status"
            )
        )

        metadata = kwargs.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValueError(
                "Evaluation evidence metadata "
                "must be a dictionary."
            )

        if (
            evidence_type
            == "machine_verified_semantic_reference"
        ):
            evidence_id = (
                machine_revision_runtime
                ._expected_evidence_id(
                    subject_key=(
                        subject_key
                    ),
                    observed_at=(
                        observed_at
                    ),
                    canonical_url=(
                        canonical_url
                    ),
                    reference_key=(
                        reference_key
                    ),
                    normalize_url=(
                        normalized_analysis_url
                    ),
                )
            )

        else:
            evidence_id = _stable_id(
                "eval-evidence",
                {
                    "evidence_type": (
                        evidence_type
                    ),
                    "subject_key": (
                        subject_key
                    ),
                    "observed_at": (
                        observed_at
                    ),
                    "canonical_url": (
                        canonical_url
                    ),
                    "reference_key": (
                        reference_key
                    ),
                    "metadata": (
                        metadata
                    ),
                },
            )

        row = {
            "id": evidence_id,
            "evidence_type": (
                evidence_type
            ),
            "subject_key": (
                subject_key
            ),
            "observed_at": (
                observed_at
            ),
            "canonical_url": (
                canonical_url
            ),
            "reference_key": (
                reference_key
            ),
            "verification_status": (
                verification_status
            ),
            "metadata_json": json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
            ),
        }

        conn = connection_factory()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_records (
                  id,
                  evidence_type,
                  subject_key,
                  observed_at,
                  canonical_url,
                  reference_key,
                  verification_status,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row[
                        "evidence_type"
                    ],
                    row[
                        "subject_key"
                    ],
                    row[
                        "observed_at"
                    ],
                    row[
                        "canonical_url"
                    ],
                    row[
                        "reference_key"
                    ],
                    row[
                        "verification_status"
                    ],
                    row[
                        "metadata_json"
                    ],
                ),
            )

            conn.commit()

        finally:
            conn.close()

        return {
            "evidence": row,
        }

    def claim_link_recorder(
        **kwargs,
    ):
        metadata = kwargs.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            raise ValueError(
                "Evaluation claim-link metadata "
                "must be a dictionary."
            )

        identity = {
            "claim_id": _clean(
                kwargs.get(
                    "claim_id"
                )
            ),
            "source_observation_id": _clean(
                kwargs.get(
                    "source_observation_id"
                )
            ),
            "evidence_id": _clean(
                kwargs.get(
                    "evidence_id"
                )
            ),
            "relationship_type": _clean(
                kwargs.get(
                    "relationship_type"
                )
            ),
            "observed_at": _clean(
                kwargs.get(
                    "observed_at"
                )
            ),
            "metadata": metadata,
        }

        row = {
            "id": _stable_id(
                "eval-claim-link",
                identity,
            ),
            "claim_id": (
                identity[
                    "claim_id"
                ]
            ),
            "source_observation_id": (
                identity[
                    "source_observation_id"
                ]
                or None
            ),
            "evidence_id": (
                identity[
                    "evidence_id"
                ]
                or None
            ),
            "relationship_type": (
                identity[
                    "relationship_type"
                ]
            ),
            "confidence": float(
                kwargs.get(
                    "confidence",
                    1.0,
                )
            ),
            "observed_at": (
                identity[
                    "observed_at"
                ]
            ),
            "recorded_at": (
                _clean(
                    kwargs.get(
                        "recorded_at"
                    )
                )
                or None
            ),
            "metadata_json": json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
            ),
        }

        conn = connection_factory()

        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO claim_links (
                  id,
                  claim_id,
                  source_observation_id,
                  evidence_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row[
                        "claim_id"
                    ],
                    row[
                        "source_observation_id"
                    ],
                    row[
                        "evidence_id"
                    ],
                    row[
                        "relationship_type"
                    ],
                    row[
                        "confidence"
                    ],
                    row[
                        "observed_at"
                    ],
                    row[
                        "recorded_at"
                    ],
                    row[
                        "metadata_json"
                    ],
                ),
            )

            conn.commit()

        finally:
            conn.close()

        return {
            "link": row,
        }

    return (
        evidence_recorder,
        claim_link_recorder,
    )


def _evaluate_two_gate_case(
    *,
    case: Dict[str, Any],
    definition: Dict[str, Any],
    working_dir: Path,
) -> Dict[str, Any]:
    candidate_id = _clean(
        case.get(
            "candidate_id"
        )
    )

    claimant_capture = case[
        "claimant_capture"
    ]

    authority_capture = case[
        "authority_capture"
    ]

    claimant_page = _refetch_frozen_page(
        capture=(
            claimant_capture
        ),
        subject_terms=(
            definition[
                "claimant_subject_terms"
            ]
        ),
        semantic_terms=(
            definition[
                "claimant_assertion_terms"
            ]
        ),
    )

    authority_page = _refetch_frozen_page(
        capture=(
            authority_capture
        ),
        subject_terms=(
            definition[
                "authority_subject_terms"
            ]
        ),
        semantic_terms=(
            definition[
                "authority_denial_terms"
            ]
        ),
    )

    claimant_time = _parse_time(
        claimant_capture[
            "captured_at"
        ]
    )

    authority_time = _parse_time(
        authority_capture[
            "captured_at"
        ]
    )

    if (
        authority_time
        <= claimant_time
    ):
        raise RuntimeError(
            "Authority capture must follow "
            "claimant capture in evaluation lineage."
        )

    db_path = (
        working_dir
        / (
            candidate_id
            + ".db"
        )
    )

    _initialize_eval_db(
        db_path
    )

    connection_factory = (
        _connection_factory(
            db_path
        )
    )

    claim_id = _stable_id(
        "real-world-two-gate-claim",
        candidate_id,
    )

    subject_key = (
        "real-world-negative|"
        + candidate_id
    )

    authority_source_id = (
        _source_id(
            authority_capture[
                "final_url"
            ]
        )
    )

    claimant_source_id = (
        _source_id(
            claimant_capture[
                "final_url"
            ]
        )
    )

    observation_id = _stable_id(
        "real-world-authority-observation",
        {
            "candidate_id": (
                candidate_id
            ),
            "source_id": (
                authority_source_id
            ),
        },
    )

    contradiction_link_id = (
        _stable_id(
            "real-world-contradiction-link",
            {
                "claim_id": (
                    claim_id
                ),
                "observation_id": (
                    observation_id
                ),
            },
        )
    )

    entity_id = _stable_id(
        "real-world-authority-entity",
        case[
            "authority_entity"
        ],
    )

    entity_key = (
        "club|"
        + _clean(
            case[
                "authority_entity"
            ]
        ).lower().replace(
            " ",
            "-",
        )
    )

    binding_evidence_id = (
        _stable_id(
            "eval-authority-binding-evidence",
            {
                "entity_id": (
                    entity_id
                ),
                "authority_hash": (
                    authority_capture[
                        "content_sha256"
                    ]
                ),
            },
        )
    )

    participant_evidence_id = (
        _stable_id(
            "eval-participant-evidence",
            {
                "claim_id": (
                    claim_id
                ),
                "entity_id": (
                    entity_id
                ),
            },
        )
    )

    conn = connection_factory()

    try:
        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id,
              subject_key,
              canonical_text
            )
            VALUES (?, ?, ?)
            """,
            (
                claim_id,
                subject_key,
                case[
                    "claim_summary"
                ],
            ),
        )

        conn.execute(
            """
            INSERT INTO source_observations (
              id,
              subject_key,
              source_id,
              observed_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                observation_id,
                subject_key,
                authority_source_id,
                authority_capture[
                    "captured_at"
                ],
            ),
        )

        conn.execute(
            """
            INSERT INTO claim_links (
              id,
              claim_id,
              source_observation_id,
              evidence_id,
              relationship_type,
              confidence,
              observed_at,
              metadata_json
            )
            VALUES (?, ?, ?, NULL, 'contradicts', 1.0, ?, ?)
            """,
            (
                contradiction_link_id,
                claim_id,
                observation_id,
                authority_capture[
                    "captured_at"
                ],
                json.dumps(
                    {
                        "evaluation_only": True,
                        "frozen_authority_capture": True,
                        "claim_truth_established": False,
                    },
                    sort_keys=True,
                ),
            ),
        )

        conn.commit()

    finally:
        conn.close()

    def match_loader(
        **kwargs,
    ):
        if (
            _clean(
                kwargs.get(
                    "source_id"
                )
            )
            != authority_source_id
        ):
            raise RuntimeError(
                "Evaluation authority source mismatch."
            )

        if (
            _clean(
                kwargs.get(
                    "claim_id"
                )
            )
            != claim_id
        ):
            raise RuntimeError(
                "Evaluation authority claim mismatch."
            )

        return {
            "version": (
                VERIFIED_ENTITY_MATCH_VERSION
            ),
            "matches": [
                {
                    "entity": {
                        "id": (
                            entity_id
                        ),
                        "entity_key": (
                            entity_key
                        ),
                        "entity_type": (
                            "club"
                        ),
                        "sport_key": (
                            "football"
                        ),
                        "canonical_name": (
                            case[
                                "authority_entity"
                            ]
                        ),
                    },
                    "source_binding": {
                        "id": _stable_id(
                            "eval-source-binding",
                            {
                                "source_id": (
                                    authority_source_id
                                ),
                                "entity_id": (
                                    entity_id
                                ),
                            },
                        ),
                        "binding_type": (
                            "official_site"
                        ),
                        "evidence_id": (
                            binding_evidence_id
                        ),
                        "confidence": 1.0,
                        "recorded_at": (
                            authority_capture[
                                "captured_at"
                            ]
                        ),
                    },
                    "claim_participant": {
                        "id": _stable_id(
                            "eval-claim-participant",
                            {
                                "claim_id": (
                                    claim_id
                                ),
                                "entity_id": (
                                    entity_id
                                ),
                            },
                        ),
                        "participant_role": (
                            "counterparty"
                        ),
                        "evidence_id": (
                            participant_evidence_id
                        ),
                        "confidence": 1.0,
                        "recorded_at": (
                            authority_capture[
                                "captured_at"
                            ]
                        ),
                    },
                }
            ],
        }

    def authority_candidate_builder(
        **kwargs,
    ):
        return (
            build_direct_authority_entity_candidate(
                source_id=(
                    kwargs[
                        "source_id"
                    ]
                ),
                claim_id=(
                    kwargs[
                        "claim_id"
                    ]
                ),
                connection_factory=(
                    kwargs[
                        "connection_factory"
                    ]
                ),
                match_loader=(
                    match_loader
                ),
            )
        )

    direct_authority = (
        authority_candidate_builder(
            source_id=(
                authority_source_id
            ),
            claim_id=(
                claim_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if (
        direct_authority.get(
            "version"
        )
        != (
            DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
        )
        or direct_authority.get(
            "status"
        )
        != (
            "verified_direct_stakeholder"
        )
    ):
        raise RuntimeError(
            "Direct authority verifier failed."
        )

    stakeholder_candidate = (
        build_direct_stakeholder_contradiction_candidate(
            claim_id=(
                claim_id
            ),
            observation_id=(
                observation_id
            ),
            connection_factory=(
                connection_factory
            ),
            authority_candidate_builder=(
                authority_candidate_builder
            ),
        )
    )

    if (
        stakeholder_candidate.get(
            "version"
        )
        != (
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        )
        or stakeholder_candidate.get(
            "status"
        )
        != (
            "verified_direct_stakeholder_"
            "contradiction_lineage"
        )
    ):
        raise RuntimeError(
            "Direct stakeholder contradiction "
            "candidate failed."
        )

    (
        evidence_recorder,
        claim_link_recorder,
    ) = _make_recorders(
        connection_factory=(
            connection_factory
        )
    )

    authority_verification = (
        persist_direct_stakeholder_contradiction_verification(
            claim_id=(
                claim_id
            ),
            observation_id=(
                observation_id
            ),
            connection_factory=(
                connection_factory
            ),
            candidate_builder=(
                lambda **kwargs: (
                    stakeholder_candidate
                )
            ),
            evidence_recorder=(
                evidence_recorder
            ),
        )
    )

    if (
        authority_verification.get(
            "status"
        )
        != (
            "persisted_verified_direct_"
            "stakeholder_contradiction_lineage"
        )
        or authority_verification.get(
            "persisted"
        )
        is not True
    ):
        raise RuntimeError(
            "Direct stakeholder contradiction "
            "verification failed."
        )

    if (
        "direct_authority_record"
        not in (
            VALIDATION_REFERENCE_BASIS_BY_FIELD[
                "stance"
            ]
        )
    ):
        raise RuntimeError(
            "Trusted validation no longer allows "
            "direct-authority records for stance."
        )

    baseline_revision = {
        "revision_id": _stable_id(
            "eval-baseline-revision",
            claim_id,
        ),
        "claim_id": (
            claim_id
        ),
        "as_of": (
            claimant_capture[
                "captured_at"
            ]
        ),
        "trigger": {
            "type": (
                "evaluation_baseline"
            ),
            "evidence_ids": [],
        },
        "adjudication": {
            "evaluators": [],
        },
    }

    def latest_loader(
        **kwargs,
    ):
        return baseline_revision

    def history_writer(
        **kwargs,
    ):
        revision = {
            "revision_id": _stable_id(
                "eval-machine-revision",
                {
                    "claim_id": (
                        kwargs[
                            "claim_id"
                        ]
                    ),
                    "as_of": (
                        kwargs[
                            "as_of"
                        ]
                    ),
                    "evaluator_runs": (
                        kwargs[
                            "evaluator_runs"
                        ]
                    ),
                },
            ),
            "claim_id": (
                kwargs[
                    "claim_id"
                ]
            ),
            "as_of": (
                kwargs[
                    "as_of"
                ]
            ),
            "trigger": {
                "type": (
                    kwargs[
                        "trigger_type"
                    ]
                ),
                "evidence_ids": list(
                    kwargs[
                        "trigger_evidence_ids"
                    ]
                ),
            },
            "adjudication": {
                "evaluators": (
                    kwargs[
                        "evaluator_runs"
                    ]
                ),
            },
        }

        return {
            "version": (
                machine_revision_runtime
                .AUTOMATED_ADJUDICATION_HISTORY_VERSION
            ),
            "status": (
                "persisted_evaluation_revision"
            ),
            "revision": (
                revision
            ),
        }

    machine_revision = (
        machine_revision_runtime
        .persist_machine_verified_reference_revision(
            claim_id=(
                claim_id
            ),
            verification_evidence={
                "observed_at": (
                    authority_capture[
                        "captured_at"
                    ]
                ),
                "canonical_url": (
                    authority_capture[
                        "final_url"
                    ]
                ),
                "reference_key": (
                    "direct-authority-denial|"
                    + candidate_id
                ),
                "claim_summary": (
                    case[
                        "claim_summary"
                    ]
                ),
                "metadata": {
                    "evaluation_version": (
                        REAL_WORLD_TWO_GATE_EVAL_VERSION
                    ),
                    "candidate_id": (
                        candidate_id
                    ),
                    "claimant_content_sha256": (
                        claimant_capture[
                            "content_sha256"
                        ]
                    ),
                    "authority_content_sha256": (
                        authority_capture[
                            "content_sha256"
                        ]
                    ),
                    "matched_claimant_assertion": (
                        claimant_page[
                            "matched_semantic_term"
                        ]
                    ),
                    "matched_authority_denial": (
                        authority_page[
                            "matched_semantic_term"
                        ]
                    ),
                    "deterministic_direct_authority_denial": True,
                    "claim_truth_established": False,
                    "live_merit_changed": False,
                },
            },
            field_verifications=[
                {
                    "field": (
                        "stance"
                    ),
                    "value": (
                        "contradicts"
                    ),
                    "confidence": 1.0,
                    "basis_class": (
                        "direct_authority_record"
                    ),
                }
            ],
            normalize_url=(
                normalized_analysis_url
            ),
            connection_factory=(
                connection_factory
            ),
            latest_loader=(
                latest_loader
            ),
            evidence_recorder=(
                evidence_recorder
            ),
            claim_link_recorder=(
                claim_link_recorder
            ),
            history_writer=(
                history_writer
            ),
        )
    )

    revision = machine_revision.get(
        "revision"
    )

    if not isinstance(
        revision,
        dict,
    ):
        raise RuntimeError(
            "Machine verification revision missing."
        )

    semantic_candidate = (
        build_machine_verified_contradiction_semantics_candidate(
            claim_id=(
                claim_id
            ),
            connection_factory=(
                connection_factory
            ),
            revision_loader=(
                lambda **kwargs: (
                    revision
                )
            ),
        )
    )

    if (
        semantic_candidate.get(
            "version"
        )
        != (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        )
        or semantic_candidate.get(
            "status"
        )
        != (
            "verified_machine_"
            "contradiction_semantics"
        )
    ):
        raise RuntimeError(
            "Machine semantic contradiction "
            "verification failed: "
            + str(
                semantic_candidate.get(
                    "status"
                )
            )
        )

    semantic_verification = (
        persist_machine_verified_contradiction_semantics_verification(
            claim_id=(
                claim_id
            ),
            connection_factory=(
                connection_factory
            ),
            candidate_builder=(
                lambda **kwargs: (
                    semantic_candidate
                )
            ),
            evidence_recorder=(
                evidence_recorder
            ),
            claim_link_recorder=(
                claim_link_recorder
            ),
        )
    )

    if (
        semantic_verification.get(
            "status"
        )
        != (
            "persisted_verified_machine_"
            "contradiction_semantics"
        )
        or semantic_verification.get(
            "persisted"
        )
        is not True
    ):
        raise RuntimeError(
            "Persisted semantic gate failed."
        )

    legacy_score = {
        "total": int(
            case[
                "claimant_current_merit"
            ][
                "total"
            ]
        )
    }

    shadow = build_negative_merit_shadow(
        legacy_score=(
            legacy_score
        ),
        claim_id=(
            claim_id
        ),
        contradiction_verification=(
            authority_verification
        ),
        semantic_verification=(
            semantic_verification
        ),
    )

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
        or shadow[
            "proposed"
        ][
            "eligible_for_penalty_calibration"
        ]
        is not True
    ):
        raise RuntimeError(
            "Negative Merit two-gate shadow "
            "did not become calibration eligible."
        )

    calibration_observation = {
        "version": (
            NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
        ),
        "id": _stable_id(
            "real-world-calibration-observation",
            candidate_id,
        ),
        "claim_id": (
            claim_id
        ),
        "origin": (
            "real_world"
        ),
        "machine_verified": True,
        "observation_class": (
            "two_gate_observation"
        ),
        "observed_at": (
            authority_capture[
                "captured_at"
            ]
        ),
        "resolution_status": (
            "unresolved"
        ),
        "resolution_verification": None,
        "legacy_score": (
            legacy_score
        ),
        "source_captures": [
            {
                "url": (
                    claimant_capture[
                        "final_url"
                    ]
                ),
                "source_id": (
                    claimant_source_id
                ),
                "content_sha256": (
                    claimant_capture[
                        "content_sha256"
                    ]
                ),
                "captured_at": (
                    claimant_capture[
                        "captured_at"
                    ]
                ),
            },
            {
                "url": (
                    authority_capture[
                        "final_url"
                    ]
                ),
                "source_id": (
                    authority_source_id
                ),
                "content_sha256": (
                    authority_capture[
                        "content_sha256"
                    ]
                ),
                "captured_at": (
                    authority_capture[
                        "captured_at"
                    ]
                ),
            },
        ],
        "contradiction_verification": (
            authority_verification
        ),
        "semantic_verification": (
            semantic_verification
        ),
    }

    return {
        "candidate_id": (
            candidate_id
        ),
        "claim_id": (
            claim_id
        ),
        "authority_entity": (
            case[
                "authority_entity"
            ]
        ),
        "claimant_source": (
            claimant_capture[
                "domain"
            ]
        ),
        "authority_source": (
            authority_capture[
                "domain"
            ]
        ),
        "claimant_content_sha256": (
            claimant_capture[
                "content_sha256"
            ]
        ),
        "authority_content_sha256": (
            authority_capture[
                "content_sha256"
            ]
        ),
        "matched_claimant_assertion": (
            claimant_page[
                "matched_semantic_term"
            ]
        ),
        "matched_authority_denial": (
            authority_page[
                "matched_semantic_term"
            ]
        ),
        "direct_authority_status": (
            direct_authority[
                "status"
            ]
        ),
        "direct_stakeholder_status": (
            authority_verification[
                "status"
            ]
        ),
        "machine_revision_status": (
            machine_revision[
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
        "calibration_eligible": (
            shadow[
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        ),
        "legacy_merit_total": (
            legacy_score[
                "total"
            ]
        ),
        "claim_truth_established": False,
        "live_merit_changed": False,
        "calibration_observation": (
            calibration_observation
        ),
    }


def _control_observations(
    *,
    primary_manifest: Dict[str, Any],
    batch_manifest: Dict[str, Any],
):
    rows = [
        {
            "label": (
                "Rangers"
            ),
            "claim_id": (
                primary_manifest[
                    "claim_id"
                ]
            ),
            "url": (
                primary_manifest[
                    "source_url"
                ]
            ),
            "content_sha256": (
                primary_manifest[
                    "body_sha256"
                ]
            ),
            "captured_at": (
                primary_manifest[
                    "captured_at"
                ]
            ),
            "legacy_merit_total": int(
                primary_manifest[
                    "legacy_merit_total"
                ]
            ),
        }
    ]

    for capture in batch_manifest[
        "captures"
    ]:
        rows.append(
            {
                "label": (
                    capture[
                        "label"
                    ]
                ),
                "claim_id": (
                    capture[
                        "claim_id"
                    ]
                ),
                "url": (
                    capture[
                        "source_url"
                    ]
                ),
                "content_sha256": (
                    capture[
                        "body_sha256"
                    ]
                ),
                "captured_at": (
                    capture[
                        "captured_at"
                    ]
                ),
                "legacy_merit_total": int(
                    capture[
                        "legacy_merit_total"
                    ]
                ),
            }
        )

    if len(
        rows
    ) != 3:
        raise RuntimeError(
            "Expected exactly three current "
            "control captures."
        )

    observations = []

    for row in rows:
        observations.append(
            {
                "version": (
                    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
                ),
                "id": _stable_id(
                    "real-world-control-observation",
                    row[
                        "claim_id"
                    ],
                ),
                "claim_id": (
                    row[
                        "claim_id"
                    ]
                ),
                "origin": (
                    "real_world"
                ),
                "machine_verified": True,
                "observation_class": (
                    "no_negative_evidence_control"
                ),
                "observed_at": (
                    row[
                        "captured_at"
                    ]
                ),
                "resolution_status": (
                    "unresolved"
                ),
                "resolution_verification": None,
                "legacy_score": {
                    "total": (
                        row[
                            "legacy_merit_total"
                        ]
                    ),
                },
                "source_captures": [
                    {
                        "url": (
                            row[
                                "url"
                            ]
                        ),
                        "source_id": (
                            _source_id(
                                row[
                                    "url"
                                ]
                            )
                        ),
                        "content_sha256": (
                            row[
                                "content_sha256"
                            ]
                        ),
                        "captured_at": (
                            row[
                                "captured_at"
                            ]
                        ),
                    }
                ],
                "contradiction_verification": None,
                "semantic_verification": None,
            }
        )

    return (
        rows,
        observations,
    )


def validate_two_gate_calibration_report(
    report: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(
            "Calibration report must be a dictionary."
        )

    if (
        report.get(
            "version"
        )
        != (
            REAL_WORLD_TWO_GATE_CALIBRATION_VERSION
        )
    ):
        raise ValueError(
            "Unsupported two-gate calibration version."
        )

    gate_cases = report.get(
        "gate_cases"
    )

    if (
        not isinstance(
            gate_cases,
            list,
        )
        or len(
            gate_cases
        )
        != 3
    ):
        raise ValueError(
            "Two-gate calibration requires "
            "exactly three negative cases."
        )

    for case in gate_cases:
        if (
            case.get(
                "direct_authority_status"
            )
            != "verified_direct_stakeholder"
        ):
            raise ValueError(
                "Direct authority gate is not verified."
            )

        if (
            case.get(
                "direct_stakeholder_status"
            )
            != (
                "persisted_verified_direct_"
                "stakeholder_contradiction_lineage"
            )
        ):
            raise ValueError(
                "Direct stakeholder gate is not persisted."
            )

        if (
            case.get(
                "semantic_status"
            )
            != (
                "persisted_verified_machine_"
                "contradiction_semantics"
            )
        ):
            raise ValueError(
                "Machine semantic gate is not verified."
            )

        if (
            case.get(
                "calibration_eligible"
            )
            is not True
        ):
            raise ValueError(
                "Two-gate case is not calibration eligible."
            )

        if (
            case.get(
                "claim_truth_established"
            )
            is not False
            or case.get(
                "live_merit_changed"
            )
            is not False
        ):
            raise ValueError(
                "Truth/live safety boundary violated."
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

    if dataset.get(
        "case_count"
    ) != 6:
        raise ValueError(
            "Expected six total calibration observations."
        )

    distributions = (
        dataset[
            "score_distribution"
        ]
    )

    if (
        distributions[
            "two_gate_observations"
        ][
            "count"
        ]
        != 3
    ):
        raise ValueError(
            "Expected three two-gate observations."
        )

    if (
        distributions[
            "controls"
        ][
            "count"
        ]
        != 3
    ):
        raise ValueError(
            "Expected three controls."
        )

    if (
        dataset[
            "calibration"
        ][
            "live_negative_merit_authorized"
        ]
        is not False
    ):
        raise ValueError(
            "Calibration dataset cannot authorize live Merit."
        )

    selection = report.get(
        "penalty_selection"
    )

    if not isinstance(
        selection,
        dict,
    ):
        raise ValueError(
            "Penalty selection is missing."
        )

    if (
        selection.get(
            "status"
        )
        != (
            "provisional_penalty_selected"
        )
    ):
        raise ValueError(
            "Provisional penalty was not selected."
        )

    if (
        float(
            selection.get(
                "provisional_adjustment"
            )
        )
        >= 0.0
    ):
        raise ValueError(
            "Provisional adjustment must be negative."
        )

    if (
        selection.get(
            "release_authorized"
        )
        is not False
    ):
        raise ValueError(
            "Calibration report cannot itself "
            "authorize live release."
        )

    policy = report.get(
        "policy"
    )

    if not isinstance(
        policy,
        dict,
    ):
        raise ValueError(
            "Calibration report policy is missing."
        )

    for field in (
        "production_database_written",
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
                "Unsafe calibration policy field: "
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
            "Two-gate calibration report "
            "digest mismatch."
        )

    return {
        "status": "valid",
        "case_count": 6,
        "two_gate_count": 3,
        "control_count": 3,
        "provisional_adjustment": (
            selection[
                "provisional_adjustment"
            ]
        ),
        "manifest_digest": (
            expected_digest
        ),
    }


def build_real_world_two_gate_calibration(
    *,
    candidate_manifest_path: Path,
    primary_control_manifest_path: Path,
    batch_control_manifest_path: Path,
) -> Dict[str, Any]:
    candidate_manifest = json.loads(
        candidate_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    candidate_validation = (
        validate_candidate_batch(
            candidate_manifest
        )
    )

    primary_manifest = json.loads(
        primary_control_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    batch_manifest = json.loads(
        batch_control_manifest_path.read_text(
            encoding="utf-8"
        )
    )

    definitions = {
        definition[
            "candidate_id"
        ]: definition
        for definition
        in CASES
    }

    gate_cases = []
    calibration_observations = []

    with tempfile.TemporaryDirectory(
        prefix=(
            "sportabase-negative-merit-"
            "two-gate-eval-"
        )
    ) as temp_dir:
        working_dir = Path(
            temp_dir
        )

        for case in candidate_manifest[
            "cases"
        ]:
            candidate_id = case[
                "candidate_id"
            ]

            if (
                candidate_id
                not in definitions
            ):
                raise RuntimeError(
                    "Frozen candidate definition missing."
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
                        working_dir
                    ),
                )
            )

            calibration_observations.append(
                evaluated.pop(
                    "calibration_observation"
                )
            )

            gate_cases.append(
                evaluated
            )

    (
        control_rows,
        control_observations,
    ) = _control_observations(
        primary_manifest=(
            primary_manifest
        ),
        batch_manifest=(
            batch_manifest
        ),
    )

    calibration_observations.extend(
        control_observations
    )

    dataset = (
        build_negative_merit_calibration_dataset(
            cases=(
                calibration_observations
            )
        )
    )

    two_gate_scores = [
        int(
            case[
                "legacy_merit_total"
            ]
        )
        for case
        in gate_cases
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
        selection.get(
            "status"
        )
        != (
            "provisional_penalty_selected"
        )
    ):
        raise RuntimeError(
            "Real-world score distributions "
            "did not support a provisional penalty."
        )

    adjustment = float(
        selection[
            "provisional_adjustment"
        ]
    )

    selection[
        "two_gate_scores"
    ] = two_gate_scores

    selection[
        "control_scores"
    ] = control_scores

    selection[
        "two_gate_scores_if_released"
    ] = [
        max(
            0.0,
            min(
                100.0,
                float(
                    score
                )
                + adjustment,
            ),
        )
        for score
        in two_gate_scores
    ]

    core = {
        "version": (
            REAL_WORLD_TWO_GATE_CALIBRATION_VERSION
        ),
        "candidate_manifest_digest": (
            candidate_validation[
                "manifest_digest"
            ]
        ),
        "control_manifest_digests": {
            "primary": (
                primary_manifest[
                    "manifest_digest"
                ]
            ),
            "batch": (
                batch_manifest[
                    "manifest_digest"
                ]
            ),
        },
        "gate_case_count": len(
            gate_cases
        ),
        "control_case_count": len(
            control_rows
        ),
        "gate_cases": (
            gate_cases
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
            "frozen_capture_hashes_reverified": True,
            "production_verifier_logic_used": True,
            "evaluation_entity_bindings_only": True,
            "temporary_evaluation_database_only": True,
            "production_database_written": False,
            "provider_calls": False,
            "claim_truth_established": False,
            "numeric_penalty_live": False,
            "live_negative_merit_authorized": False,
            "separate_release_certificate_required": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "two_gate_contradiction_is_not_permanent_objective_truth": True,
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

    validate_two_gate_calibration_report(
        report
    )

    return report


def main(
    argv=None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the real-world two-gate "
            "Negative Merit calibration."
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
        build_real_world_two_gate_calibration(
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

    dataset = report[
        "calibration_dataset"
    ]

    selection = report[
        "penalty_selection"
    ]

    print()
    print(
        "TWO_GATE_CASES="
        + str(
            report[
                "gate_case_count"
            ]
        )
    )

    print(
        "CONTROL_CASES="
        + str(
            report[
                "control_case_count"
            ]
        )
    )

    print(
        "TWO_GATE_SCORES="
        + json.dumps(
            selection[
                "two_gate_scores"
            ]
        )
    )

    print(
        "CONTROL_SCORES="
        + json.dumps(
            selection[
                "control_scores"
            ]
        )
    )

    print(
        "TWO_GATE_MEDIAN="
        + str(
            selection[
                "two_gate_median"
            ]
        )
    )

    print(
        "CONTROL_MEDIAN="
        + str(
            selection[
                "control_median"
            ]
        )
    )

    print(
        "MEDIAN_SEPARATION="
        + str(
            selection[
                "median_separation"
            ]
        )
    )

    print(
        "PROVISIONAL_NEGATIVE_ADJUSTMENT="
        + str(
            selection[
                "provisional_adjustment"
            ]
        )
    )

    print(
        "TWO_GATE_SCORES_IF_RELEASED="
        + json.dumps(
            selection[
                "two_gate_scores_if_released"
            ]
        )
    )

    print(
        "DATASET_BLOCKERS="
        + json.dumps(
            dataset[
                "calibration"
            ][
                "blockers"
            ]
        )
    )

    for case in report[
        "gate_cases"
    ]:
        print(
            "VERIFIED_TWO_GATE|"
            + case[
                "candidate_id"
            ]
            + "|merit="
            + str(
                case[
                    "legacy_merit_total"
                ]
            )
            + "|authority="
            + case[
                "direct_authority_status"
            ]
            + "|semantic="
            + case[
                "semantic_status"
            ]
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
        "REAL_WORLD_TWO_GATE_CALIBRATION=PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
