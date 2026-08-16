from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from app.intelligence import claims as claim_intelligence
from app.intelligence import dependencies as dependency_intelligence
from app.intelligence import evidence as evidence_intelligence
from app.intelligence import observations as observation_intelligence
from app.models import content
from app.models import intelligence_bridge as bridge_models

VERIFIED_PERSISTENCE_EXECUTION_VERSION = "verified-persistence-execution-v1"

_DEPENDENCY_RELATIONSHIP_MAP = {
    "quote_of": "attributed_to",
    "repost_of": "derived_from",
    "crosspost_of": "derived_from",
    "derives_from": "derived_from",
}


class VerifiedPersistenceError(RuntimeError):
    pass


class ProposalBlockedError(VerifiedPersistenceError):
    pass


class BindingVerificationError(VerifiedPersistenceError):
    pass


class IntegrityVerificationError(VerifiedPersistenceError):
    pass


class _SharedTransactionConnection:
    """Expose one SQLite connection while suppressing helper commit/close calls."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, *args, **kwargs):
        return self._connection.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._connection.executemany(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._connection.cursor(*args, **kwargs)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(self._connection, name)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _identity_url(value: Any) -> str:
    return _clean(value)


def _require_ready(
    proposal: bridge_models.PersistenceProposal,
    expected_operation: str,
) -> Dict[str, Any]:
    if proposal.operation != expected_operation:
        raise IntegrityVerificationError(
            f"Expected {expected_operation!r}, got {proposal.operation!r}."
        )

    if proposal.readiness != "ready":
        reasons = ", ".join(proposal.blocked_reasons) or "unspecified"
        raise ProposalBlockedError(
            f"{expected_operation} proposal is not ready: {reasons}"
        )

    kwargs = dict(proposal.kwargs)

    if not kwargs:
        raise IntegrityVerificationError(
            f"{expected_operation} proposal has no arguments."
        )

    return kwargs


def _row_by_id(
    conn,
    table: str,
    row_id: str,
):
    allowed = {
        "intelligence_sources",
        "media_items",
        "intelligence_stories",
        "source_observations",
        "reporter_observations",
        "intelligence_reporters",
        "intelligence_claims",
        "evidence_records",
        "claim_links",
        "observation_dependencies",
    }

    if table not in allowed:
        raise ValueError(
            "Unsafe table name."
        )

    normalized_id = _clean(
        row_id
    )

    if not normalized_id:
        raise BindingVerificationError(
            f"{table} binding ID is empty."
        )

    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?",
        (
            normalized_id,
        ),
    ).fetchone()

    if row is None:
        raise BindingVerificationError(
            f"{table} row does not exist: {normalized_id}"
        )

    return row


def _verify_subject(
    conn,
    subject_key: str,
):
    normalized = _clean(
        subject_key
    )

    if not normalized:
        raise BindingVerificationError(
            "Persistence subject is unresolved."
        )

    row = conn.execute(
        """
        SELECT *
        FROM canonical_entities
        WHERE entity_key = ?
        """,
        (
            normalized,
        ),
    ).fetchone()

    if row is None:
        raise BindingVerificationError(
            "Subject entity row does not exist: "
            + normalized
        )

    return row


def _expected_evidence_id(
    kwargs: Mapping[str, Any],
) -> str:
    import hashlib

    evidence_key = (
        evidence_intelligence
        .evidence_key_for_record(
            evidence_type=(
                kwargs["evidence_type"]
            ),
            subject_key=(
                kwargs["subject_key"]
            ),
            observed_at=(
                kwargs["observed_at"]
            ),
            canonical_url=(
                kwargs.get(
                    "canonical_url",
                    "",
                )
            ),
            reference_key=(
                kwargs.get(
                    "reference_key",
                    "",
                )
            ),
            verification_status=(
                kwargs.get(
                    "verification_status",
                    "unverified",
                )
            ),
            normalize_url=(
                _identity_url
            ),
        )
    )

    return hashlib.sha256(
        (
            "evidence|"
            + evidence_key
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _validate_candidate(
    plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    candidate: (
        bridge_models
        .CandidateBridgeRecord
    ),
    bindings: (
        bridge_models
        .BridgeBindings
    ),
) -> Dict[
    str,
    Dict[str, Any],
]:
    for key in (
        "training_eligible",
        "establishes_truth",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(
            candidate.policy.get(key)
        ):
            raise (
                IntegrityVerificationError(
                    "Candidate policy may not enable "
                    + key
                    + "."
                )
            )

    claim = _require_ready(
        candidate.claim,
        "upsert_intelligence_claim",
    )

    evidence = _require_ready(
        candidate.evidence,
        "record_evidence",
    )

    claim_link = _require_ready(
        candidate.claim_link,
        "record_claim_link",
    )

    observation = _require_ready(
        candidate.source_observation,
        "record_source_observation",
    )

    subject_key = _clean(
        plan.subject_key
    )

    for label, kwargs in (
        (
            "claim",
            claim,
        ),
        (
            "evidence",
            evidence,
        ),
        (
            "observation",
            observation,
        ),
    ):
        if (
            _clean(
                kwargs.get(
                    "subject_key"
                )
            )
            != subject_key
        ):
            raise (
                IntegrityVerificationError(
                    label
                    + " subject does not match "
                    + "the bridge plan."
                )
            )

    expected_claim_id = (
        claim_intelligence
        .claim_id_for_canonical_key(
            claim[
                "canonical_key"
            ]
        )
    )

    if (
        candidate
        .claim
        .deterministic_id
        != expected_claim_id
    ):
        raise (
            IntegrityVerificationError(
                "Claim identity mismatch."
            )
        )

    expected_evidence_id = (
        _expected_evidence_id(
            evidence
        )
    )

    if (
        candidate
        .evidence
        .deterministic_id
        != expected_evidence_id
    ):
        raise (
            IntegrityVerificationError(
                "Evidence identity mismatch."
            )
        )

    if (
        _clean(
            evidence.get(
                "verification_status"
            )
        ).lower()
        != "unverified"
    ):
        raise (
            IntegrityVerificationError(
                "Multimodal evidence "
                "must remain unverified."
            )
        )

    evidence_metadata = (
        evidence.get(
            "metadata"
        )
        or {}
    )

    for key in (
        "training_eligible",
        "establishes_truth",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(
            evidence_metadata.get(key)
        ):
            raise (
                IntegrityVerificationError(
                    "Evidence metadata may not enable "
                    + key
                    + "."
                )
            )

    if (
        _clean(
            claim_link.get(
                "claim_id"
            )
        )
        != expected_claim_id
        or _clean(
            claim_link.get(
                "evidence_id"
            )
        )
        != expected_evidence_id
    ):
        raise (
            IntegrityVerificationError(
                "Claim/evidence link targets "
                "do not match the candidate."
            )
        )

    if (
        _clean(
            claim_link.get(
                "relationship_type"
            )
        ).lower()
        != "aligned_to"
    ):
        raise (
            IntegrityVerificationError(
                "Semantic claim link "
                "must remain aligned_to."
            )
        )

    if (
        claim_link.get(
            "confidence"
        )
        is not None
    ):
        raise (
            IntegrityVerificationError(
                "Semantic claim-link confidence "
                "must remain unset."
            )
        )

    expected_link_id = (
        claim_intelligence
        .claim_link_id_for_record(
            claim_id=(
                expected_claim_id
            ),
            relationship_type=(
                "aligned_to"
            ),
            observed_at=(
                claim_link[
                    "observed_at"
                ]
            ),
            confidence=None,
            evidence_id=(
                expected_evidence_id
            ),
        )
    )

    if (
        candidate
        .claim_link
        .deterministic_id
        != expected_link_id
    ):
        raise (
            IntegrityVerificationError(
                "Claim/evidence link "
                "identity mismatch."
            )
        )

    if (
        observation.get(
            "confidence"
        )
        is not None
    ):
        raise (
            IntegrityVerificationError(
                "Model confidence may not become "
                "observation confidence."
            )
        )

    if (
        _clean(
            observation.get(
                "status"
            )
        ).lower()
        != "unresolved"
    ):
        raise (
            IntegrityVerificationError(
                "Multimodal source observation "
                "must begin unresolved."
            )
        )

    source_id = _clean(
        observation.get(
            "source_id"
        )
    )

    if (
        not bindings
        .source_record_verified
        or not source_id
        or source_id
        != _clean(
            bindings.source_id
        )
    ):
        raise (
            BindingVerificationError(
                "Observation source does not match "
                "the verified source binding."
            )
        )

    media_id = _clean(
        observation.get(
            "media_item_id"
        )
    )

    bound_media = _clean(
        bindings.media_item_id
    )

    if media_id:
        if (
            not bindings
            .media_item_record_verified
            or media_id
            != bound_media
        ):
            raise (
                BindingVerificationError(
                    "Media proposal does not match "
                    "the verified media binding."
                )
            )

    elif (
        bindings
        .media_item_record_verified
        and bound_media
    ):
        raise (
            BindingVerificationError(
                "Verified media binding was "
                "omitted from the proposal."
            )
        )

    story_id = _clean(
        observation.get(
            "story_id"
        )
    )

    bound_story = _clean(
        bindings.story_id
    )

    if story_id:
        if (
            not bindings
            .story_record_verified
            or story_id
            != bound_story
        ):
            raise (
                BindingVerificationError(
                    "Story proposal does not match "
                    "the verified story binding."
                )
            )

    elif (
        bindings
        .story_record_verified
        and bound_story
    ):
        raise (
            BindingVerificationError(
                "Verified story binding was "
                "omitted from the proposal."
            )
        )

    return {
        "claim": claim,
        "evidence": evidence,
        "claim_link": claim_link,
        "observation": observation,
    }


def _neutral_observation_kwargs(
    kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    result: Dict[
        str,
        Any,
    ] = {
        "source_id": _clean(
            kwargs[
                "source_id"
            ]
        ),
        "subject_key": _clean(
            kwargs[
                "subject_key"
            ]
        ),
        "observation_type": (
            _clean(
                kwargs[
                    "observation_type"
                ]
            ).lower()
        ),
        "observed_at": _clean(
            kwargs[
                "observed_at"
            ]
        ),
        "status": "unresolved",
        # Intentionally candidate-neutral:
        # multiple semantic claims extracted
        # from one captured post must not
        # fabricate independent observations.
        "claim_summary": "",
        "provenance_url": _clean(
            kwargs.get(
                "provenance_url"
            )
        ),
        "confidence": None,
        "metadata": {
            "persistence_runtime_version": (
                VERIFIED_PERSISTENCE_EXECUTION_VERSION
            ),
            "semantic_candidates_present": True,
            "source_confidence_inferred": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }

    if _clean(
        kwargs.get(
            "media_item_id"
        )
    ):
        result[
            "media_item_id"
        ] = _clean(
            kwargs[
                "media_item_id"
            ]
        )

    if _clean(
        kwargs.get(
            "story_id"
        )
    ):
        result[
            "story_id"
        ] = _clean(
            kwargs[
                "story_id"
            ]
        )

    return result


def _observation_identity_key(
    kwargs: Mapping[str, Any],
) -> tuple:
    return (
        _clean(
            kwargs.get(
                "source_id"
            )
        ),
        _clean(
            kwargs.get(
                "subject_key"
            )
        ),
        _clean(
            kwargs.get(
                "observation_type"
            )
        ).lower(),
        _clean(
            kwargs.get(
                "observed_at"
            )
        ),
        "unresolved",
        _clean(
            kwargs.get(
                "provenance_url"
            )
        ),
        None,
        _clean(
            kwargs.get(
                "media_item_id"
            )
        ),
        _clean(
            kwargs.get(
                "story_id"
            )
        ),
    )


def _dependency_relationships(
    plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    relationships: Sequence[
        content.ContentRelationship
    ],
):
    by_id = {
        relationship.relationship_id:
        relationship
        for relationship
        in relationships
    }

    output = []

    constraint_ids = {
        item.relationship_id
        for item
        in plan.dependency_constraints
    }

    for constraint in (
        plan.dependency_constraints
    ):
        relationship = by_id.get(
            constraint.relationship_id
        )

        if relationship is None:
            raise (
                IntegrityVerificationError(
                    "Dependency relationship missing: "
                    + constraint.relationship_id
                )
            )

        if (
            relationship.source_item_id
            != plan.item_id
        ):
            raise (
                IntegrityVerificationError(
                    "Dependency relationship "
                    "does not originate from this item."
                )
            )

        expected = (
            _DEPENDENCY_RELATIONSHIP_MAP
            .get(
                relationship
                .relationship_type
            )
        )

        if (
            expected
            != constraint
            .persistence_relationship_type
        ):
            raise (
                IntegrityVerificationError(
                    "Dependency relationship "
                    "mapping mismatch."
                )
            )

        output.append(
            relationship
        )

    extra = [
        relationship.relationship_id
        for relationship
        in relationships
        if (
            relationship.source_item_id
            == plan.item_id
            and relationship.relationship_type
            in _DEPENDENCY_RELATIONSHIP_MAP
            and relationship.relationship_id
            not in constraint_ids
        )
    ]

    if extra:
        raise (
            IntegrityVerificationError(
                "Bridge plan omitted explicit "
                "dependency relationships: "
                + ", ".join(extra)
            )
        )

    return output


def _verified_upstream_target(
    conn,
    relationship: (
        content
        .ContentRelationship
    ),
    bindings: (
        bridge_models
        .BridgeBindings
    ),
):
    raw = (
        bindings
        .upstream_targets_by_item_id
        .get(
            relationship.target_item_id,
            {},
        )
    )

    if (
        not isinstance(
            raw,
            Mapping,
        )
        or not bool(
            raw.get(
                "record_verified"
            )
        )
    ):
        raise (
            BindingVerificationError(
                "Explicit dependency upstream "
                "target is not verified."
            )
        )

    field_to_table = {
        "upstream_source_observation_id":
            "source_observations",
        "upstream_reporter_observation_id":
            "reporter_observations",
        "upstream_source_id":
            "intelligence_sources",
        "upstream_reporter_id":
            "intelligence_reporters",
    }

    active = [
        (
            field,
            _clean(
                raw.get(field)
            ),
        )
        for field
        in field_to_table
        if _clean(
            raw.get(field)
        )
    ]

    if len(active) != 1:
        raise (
            BindingVerificationError(
                "Dependency requires exactly "
                "one verified upstream target."
            )
        )

    field, row_id = active[0]

    _row_by_id(
        conn,
        field_to_table[field],
        row_id,
    )

    return (
        field,
        row_id,
    )


def _verify_database_bindings(
    conn,
    *,
    plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    candidate_inputs,
    bindings: (
        bridge_models
        .BridgeBindings
    ),
    relationships,
):
    _verify_subject(
        conn,
        plan.subject_key,
    )

    if (
        not bindings
        .source_record_verified
        or not _clean(
            bindings.source_id
        )
    ):
        raise (
            BindingVerificationError(
                "Verified source binding "
                "is required."
            )
        )

    source = _row_by_id(
        conn,
        "intelligence_sources",
        bindings.source_id,
    )

    if (
        bindings
        .media_item_record_verified
    ):
        media = _row_by_id(
            conn,
            "media_items",
            bindings.media_item_id,
        )

        media_source = _clean(
            media[
                "source_id"
            ]
        )

        if (
            media_source
            and media_source
            != _clean(
                source["id"]
            )
        ):
            raise (
                BindingVerificationError(
                    "Bound media item belongs "
                    "to a different source."
                )
            )

    if (
        bindings
        .story_record_verified
    ):
        _row_by_id(
            conn,
            "intelligence_stories",
            bindings.story_id,
        )

    if (
        bindings
        .media_item_record_verified
        and bindings
        .story_record_verified
    ):
        link = conn.execute(
            """
            SELECT 1
            FROM story_media_links
            WHERE story_id = ?
              AND media_item_id = ?
            """,
            (
                _clean(
                    bindings.story_id
                ),
                _clean(
                    bindings.media_item_id
                ),
            ),
        ).fetchone()

        if link is None:
            raise (
                BindingVerificationError(
                    "Verified story/media "
                    "bindings are not linked."
                )
            )

    for values in candidate_inputs:
        observation = values[
            "observation"
        ]

        if (
            _clean(
                observation[
                    "source_id"
                ]
            )
            != _clean(
                source["id"]
            )
        ):
            raise (
                BindingVerificationError(
                    "Candidate source binding "
                    "does not match the database row."
                )
            )

    for relationship in relationships:
        _verified_upstream_target(
            conn,
            relationship,
            bindings,
        )


def execute_verified_persistence(
    *,
    plan: (
        bridge_models
        .ItemIntelligenceBridgePlan
    ),
    bindings: (
        bridge_models
        .BridgeBindings
    ),
    connection_factory,
    relationships: Sequence[
        content.ContentRelationship
    ] = (),
) -> Dict[str, Any]:
    if (
        plan.policy.get(
            "dry_run_only"
        )
        is not True
    ):
        raise (
            IntegrityVerificationError(
                "Only #14 dry-run bridge plans "
                "may enter verified persistence."
            )
        )

    for key in (
        "training_eligible",
        "establishes_truth",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(
            plan.policy.get(key)
        ):
            raise (
                IntegrityVerificationError(
                    "Bridge plan may not enable "
                    + key
                    + "."
                )
            )

    if not plan.candidates:
        raise ProposalBlockedError(
            "Bridge plan contains no candidates."
        )

    candidate_inputs = [
        _validate_candidate(
            plan,
            candidate,
            bindings,
        )
        for candidate
        in plan.candidates
    ]

    dependency_relationships = (
        _dependency_relationships(
            plan,
            relationships,
        )
    )

    conn = connection_factory()

    if conn is None:
        raise VerifiedPersistenceError(
            "Connection factory returned "
            "no connection."
        )

    try:
        if getattr(
            conn,
            "in_transaction",
            False,
        ):
            raise (
                VerifiedPersistenceError(
                    "Verified persistence requires "
                    "a fresh connection."
                )
            )

        conn.execute(
            "PRAGMA foreign_keys=ON;"
        )

        fk = conn.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()

        if (
            fk is None
            or int(fk[0]) != 1
        ):
            raise (
                VerifiedPersistenceError(
                    "SQLite foreign key enforcement "
                    "is required."
                )
            )

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        _verify_database_bindings(
            conn,
            plan=plan,
            candidate_inputs=(
                candidate_inputs
            ),
            bindings=bindings,
            relationships=(
                dependency_relationships
            ),
        )

        proxy = (
            _SharedTransactionConnection(
                conn
            )
        )

        def shared_factory():
            return proxy

        claim_ids = set()
        evidence_ids = set()
        claim_evidence_link_ids = set()
        claim_observation_link_ids = set()
        observation_rows = {}
        dependency_ids = set()
        candidate_rows = []

        for (
            candidate,
            values,
        ) in zip(
            plan.candidates,
            candidate_inputs,
        ):
            claim_row = (
                claim_intelligence
                .upsert_intelligence_claim(
                    **values[
                        "claim"
                    ],
                    id_resolver=(
                        claim_intelligence
                        .claim_id_for_canonical_key
                    ),
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

            claim_id = _clean(
                claim_row["id"]
            )

            if (
                claim_id
                != candidate
                .claim
                .deterministic_id
            ):
                raise (
                    IntegrityVerificationError(
                        "Claim read-back "
                        "identity mismatch."
                    )
                )

            evidence_result = (
                evidence_intelligence
                .record_evidence(
                    **values[
                        "evidence"
                    ],
                    normalize_url=(
                        _identity_url
                    ),
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

            evidence_row = dict(
                evidence_result[
                    "evidence"
                ]
            )

            evidence_id = _clean(
                evidence_row[
                    "id"
                ]
            )

            if (
                evidence_id
                != candidate
                .evidence
                .deterministic_id
            ):
                raise (
                    IntegrityVerificationError(
                        "Evidence read-back "
                        "identity mismatch."
                    )
                )

            if (
                _clean(
                    evidence_row[
                        "verification_status"
                    ]
                ).lower()
                != "unverified"
            ):
                raise (
                    IntegrityVerificationError(
                        "Multimodal evidence was "
                        "unexpectedly verified."
                    )
                )

            evidence_link_result = (
                claim_intelligence
                .record_claim_link(
                    **values[
                        "claim_link"
                    ],
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

            evidence_link = dict(
                evidence_link_result[
                    "link"
                ]
            )

            if (
                _clean(
                    evidence_link[
                        "id"
                    ]
                )
                != candidate
                .claim_link
                .deterministic_id
            ):
                raise (
                    IntegrityVerificationError(
                        "Claim/evidence link "
                        "read-back identity mismatch."
                    )
                )

            observation_key = (
                _observation_identity_key(
                    values[
                        "observation"
                    ]
                )
            )

            if (
                observation_key
                not in observation_rows
            ):
                observation_result = (
                    observation_intelligence
                    .record_source_observation(
                        **_neutral_observation_kwargs(
                            values[
                                "observation"
                            ]
                        ),
                        normalize_url=(
                            _identity_url
                        ),
                        connection_factory=(
                            shared_factory
                        ),
                    )
                )

                observation_rows[
                    observation_key
                ] = dict(
                    observation_result[
                        "observation"
                    ]
                )

            observation_id = _clean(
                observation_rows[
                    observation_key
                ][
                    "id"
                ]
            )

            observed_in_result = (
                claim_intelligence
                .record_claim_link(
                    claim_id=(
                        claim_id
                    ),
                    relationship_type=(
                        "observed_in"
                    ),
                    observed_at=(
                        _clean(
                            observation_rows[
                                observation_key
                            ][
                                "observed_at"
                            ]
                        )
                    ),
                    confidence=None,
                    source_observation_id=(
                        observation_id
                    ),
                    metadata={
                        "persistence_runtime_version": (
                            VERIFIED_PERSISTENCE_EXECUTION_VERSION
                        ),
                        "candidate_id": (
                            candidate
                            .candidate_id
                        ),
                        "semantic_candidate_only":
                            True,
                        "establishes_support":
                            False,
                        "establishes_truth":
                            False,
                        "establishes_independence":
                            False,
                        "affects_live_merit":
                            False,
                    },
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

            observed_in_link = dict(
                observed_in_result[
                    "link"
                ]
            )

            claim_ids.add(
                claim_id
            )

            evidence_ids.add(
                evidence_id
            )

            claim_evidence_link_ids.add(
                _clean(
                    evidence_link[
                        "id"
                    ]
                )
            )

            claim_observation_link_ids.add(
                _clean(
                    observed_in_link[
                        "id"
                    ]
                )
            )

            candidate_rows.append({
                "candidate_id": (
                    candidate
                    .candidate_id
                ),
                "claim_id": (
                    claim_id
                ),
                "evidence_id": (
                    evidence_id
                ),
                "source_observation_id": (
                    observation_id
                ),
            })

        observation_ids = sorted({
            _clean(
                row["id"]
            )
            for row
            in observation_rows.values()
        })

        for relationship in (
            dependency_relationships
        ):
            (
                upstream_field,
                upstream_id,
            ) = (
                _verified_upstream_target(
                    conn,
                    relationship,
                    bindings,
                )
            )

            persistence_type = (
                _DEPENDENCY_RELATIONSHIP_MAP[
                    relationship
                    .relationship_type
                ]
            )

            for observation_id in (
                observation_ids
            ):
                observation = _row_by_id(
                    conn,
                    "source_observations",
                    observation_id,
                )

                observed_at = (
                    _clean(
                        relationship
                        .provenance
                        .observed_at
                    )
                    or _clean(
                        observation[
                            "observed_at"
                        ]
                    )
                )

                if not observed_at:
                    raise (
                        IntegrityVerificationError(
                            "Dependency observed_at "
                            "is unavailable."
                        )
                    )

                dependency_result = (
                    dependency_intelligence
                    .record_observation_dependency(
                        relationship_type=(
                            persistence_type
                        ),
                        observed_at=(
                            observed_at
                        ),
                        confidence=None,
                        downstream_source_observation_id=(
                            observation_id
                        ),
                        metadata={
                            "persistence_runtime_version": (
                                VERIFIED_PERSISTENCE_EXECUTION_VERSION
                            ),
                            "content_relationship_id": (
                                relationship
                                .relationship_id
                            ),
                            "content_relationship_type": (
                                relationship
                                .relationship_type
                            ),
                            "source_url": (
                                _clean(
                                    relationship
                                    .provenance
                                    .source_url
                                )
                            ),
                            "extraction_method": (
                                _clean(
                                    relationship
                                    .provenance
                                    .extraction_method
                                )
                            ),
                            "source_content_hash": (
                                _clean(
                                    relationship
                                    .provenance
                                    .content_hash
                                )
                            ),
                            "explicit_dependency_blocks_independence":
                                True,
                            "establishes_independence":
                                False,
                            "establishes_truth":
                                False,
                            "affects_live_merit":
                                False,
                        },
                        connection_factory=(
                            shared_factory
                        ),
                        **{
                            upstream_field:
                                upstream_id
                        },
                    )
                )

                dependency_ids.add(
                    _clean(
                        dependency_result[
                            "dependency"
                        ][
                            "id"
                        ]
                    )
                )

        for table, ids in (
            (
                "intelligence_claims",
                claim_ids,
            ),
            (
                "evidence_records",
                evidence_ids,
            ),
            (
                "source_observations",
                observation_ids,
            ),
            (
                "claim_links",
                claim_evidence_link_ids,
            ),
            (
                "claim_links",
                claim_observation_link_ids,
            ),
            (
                "observation_dependencies",
                dependency_ids,
            ),
        ):
            for row_id in ids:
                _row_by_id(
                    conn,
                    table,
                    row_id,
                )

        conn.commit()

        return {
            "version": (
                VERIFIED_PERSISTENCE_EXECUTION_VERSION
            ),
            "item_id": (
                plan.item_id
            ),
            "candidate_count": (
                len(
                    plan.candidates
                )
            ),
            "candidate_rows": (
                candidate_rows
            ),
            "claim_ids": (
                sorted(
                    claim_ids
                )
            ),
            "evidence_ids": (
                sorted(
                    evidence_ids
                )
            ),
            "source_observation_ids": (
                observation_ids
            ),
            "claim_evidence_link_ids": (
                sorted(
                    claim_evidence_link_ids
                )
            ),
            "claim_observation_link_ids": (
                sorted(
                    claim_observation_link_ids
                )
            ),
            "dependency_ids": (
                sorted(
                    dependency_ids
                )
            ),
            "policy": {
                "evidence_verification":
                    "unverified",
                "establishes_truth":
                    False,
                "establishes_independence":
                    False,
                "adjudication_performed":
                    False,
                "affects_live_merit":
                    False,
            },
        }

    except Exception:
        if getattr(
            conn,
            "in_transaction",
            False,
        ):
            conn.rollback()

        raise

    finally:
        conn.close()
