import hashlib
import json

from typing import (
    Any,
    Dict,
    Optional,
)


from app.analysis.adjudication_history import (
    load_latest_adjudication_state_revision,
)

from app.analysis.trusted_validation import (
    TRUSTED_VALIDATION_MIN_CONFIDENCE,
    VALIDATION_REFERENCE_BASIS_BY_FIELD,
)

from app.intelligence.claims import (
    record_claim_link,
)

from app.intelligence.evidence import (
    record_evidence,
)


MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION = (
    "machine-verified-contradiction-semantics-verifier-v1"
)

MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE = (
    "machine_verified_contradiction_semantics_reference"
)

MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_REFERENCE_PREFIX = (
    "machine-verified-contradiction-semantics:"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )


def _metadata(
    value: Any,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(
                value or "{}"
            )
        )
    except Exception:
        return {}

    return (
        parsed
        if isinstance(
            parsed,
            dict,
        )
        else {}
    )


def _confidence(
    value: Any,
) -> Optional[float]:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not (
        0.0
        <= result
        <= 1.0
    ):
        return None

    return result


def _fail(
    status: str,
    *,
    claim_id: str,
    revision_id: str = "",
    machine_stance_values=None,
) -> Dict[str, Any]:
    return {
        "version": (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        ),
        "status": status,
        "claim_id": (
            claim_id
        ),
        "revision_id": (
            revision_id
        ),
        "candidate": None,
        "machine_stance_values": sorted(
            {
                _key(
                    value
                )
                for value
                in (
                    machine_stance_values
                    or []
                )
                if _key(
                    value
                )
            }
        ),
        "policy": {
            "fails_closed_without_machine_verified_stance": True,
            "model_assisted_stance_is_not_accepted": True,
            "verified_semantic_evidence_is_required": True,
            "verified_semantic_claim_link_is_required": True,
            "contradiction_semantics_do_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }


def _load_verified_semantic_evidence(
    *,
    claim_id: str,
    evidence_id: str,
    expected_basis_class: str,
    connection_factory,
) -> Optional[
    Dict[str, Any]
]:
    conn = connection_factory()

    try:
        evidence_row = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (
                evidence_id,
            ),
        ).fetchone()

        link_rows = conn.execute(
            """
            SELECT *
            FROM claim_links
            WHERE claim_id = ?
              AND evidence_id = ?
              AND relationship_type = ?
            ORDER BY id
            """,
            (
                claim_id,
                evidence_id,
                "verifies_semantics",
            ),
        ).fetchall()

    finally:
        conn.close()

    if evidence_row is None:
        return None

    if not link_rows:
        return None

    evidence = dict(
        evidence_row
    )

    if (
        _key(
            evidence.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        return None

    if (
        _key(
            evidence.get(
                "evidence_type"
            )
        )
        != "machine_verified_semantic_reference"
    ):
        return None

    evidence_metadata = _metadata(
        evidence.get(
            "metadata_json"
        )
    )

    if (
        evidence_metadata.get(
            "machine_verified"
        )
        is not True
    ):
        return None

    if (
        evidence_metadata.get(
            "semantic_reference_only"
        )
        is not True
    ):
        return None

    if (
        evidence_metadata.get(
            "claim_truth_established"
        )
        is not False
    ):
        return None

    verified_fields = {
        _key(
            value
        )
        for value
        in evidence_metadata.get(
            "verified_fields",
            [],
        )
        if _key(
            value
        )
    }

    if "stance" not in verified_fields:
        return None

    basis_classes = {
        _key(
            value
        )
        for value
        in evidence_metadata.get(
            "basis_classes",
            [],
        )
        if _key(
            value
        )
    }

    if (
        _key(
            expected_basis_class
        )
        not in basis_classes
    ):
        return None

    valid_links = []

    for raw_link in link_rows:
        link = dict(
            raw_link
        )

        confidence = _confidence(
            link.get(
                "confidence"
            )
        )

        if (
            confidence is None
            or confidence
            < TRUSTED_VALIDATION_MIN_CONFIDENCE
        ):
            continue

        link_metadata = _metadata(
            link.get(
                "metadata_json"
            )
        )

        if (
            link_metadata.get(
                "machine_verified"
            )
            is not True
        ):
            continue

        if (
            link_metadata.get(
                "semantic_reference_only"
            )
            is not True
        ):
            continue

        if (
            link_metadata.get(
                "claim_truth_established"
            )
            is not False
        ):
            continue

        valid_links.append(
            link
        )

    if not valid_links:
        return None

    return {
        "evidence": evidence,
        "claim_links": (
            valid_links
        ),
    }


def build_machine_verified_contradiction_semantics_candidate(
    *,
    claim_id: str,
    connection_factory,
    revision_loader=(
        load_latest_adjudication_state_revision
    ),
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Contradiction semantic verifier "
            "claim ID is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Contradiction semantic verifier "
            "requires database access."
        )

    revision = revision_loader(
        claim_id=(
            normalized_claim_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        revision,
        dict,
    ):
        return _fail(
            "adjudication_revision_unavailable",
            claim_id=(
                normalized_claim_id
            ),
        )

    if (
        _clean(
            revision.get(
                "claim_id"
            )
        )
        != normalized_claim_id
    ):
        return _fail(
            "adjudication_claim_mismatch",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                _clean(
                    revision.get(
                        "revision_id"
                    )
                )
            ),
        )

    revision_id = _clean(
        revision.get(
            "revision_id"
        )
    )

    adjudication = revision.get(
        "adjudication"
    )

    if not isinstance(
        adjudication,
        dict,
    ):
        return _fail(
            "adjudication_lineage_unavailable",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
        )

    evaluator_runs = adjudication.get(
        "evaluators",
        [],
    )

    if not isinstance(
        evaluator_runs,
        list,
    ):
        return _fail(
            "adjudication_evaluators_invalid",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
        )

    machine_stance = []

    for run in evaluator_runs:
        if not isinstance(
            run,
            dict,
        ):
            continue

        if (
            _key(
                run.get(
                    "derivation_mode"
                )
            )
            != "machine_verified"
        ):
            continue

        run_id = _clean(
            run.get(
                "run_id"
            )
        )

        judgments = run.get(
            "judgments",
            [],
        )

        if not isinstance(
            judgments,
            list,
        ):
            continue

        for judgment in judgments:
            if not isinstance(
                judgment,
                dict,
            ):
                continue

            if (
                _key(
                    judgment.get(
                        "field"
                    )
                )
                != "stance"
            ):
                continue

            value = _key(
                judgment.get(
                    "value"
                )
            )

            if not value:
                continue

            machine_stance.append(
                {
                    "run_id": (
                        run_id
                    ),
                    "judgment_id": (
                        _clean(
                            judgment.get(
                                "id"
                            )
                        )
                    ),
                    "value": value,
                    "confidence": (
                        _confidence(
                            judgment.get(
                                "confidence"
                            )
                        )
                    ),
                    "basis_class": (
                        _key(
                            judgment.get(
                                "basis_class"
                            )
                        )
                    ),
                    "evidence_ids": sorted(
                        {
                            _clean(
                                evidence_id
                            )
                            for evidence_id
                            in judgment.get(
                                "evidence_ids",
                                [],
                            )
                            if _clean(
                                evidence_id
                            )
                        }
                    ),
                }
            )

    if not machine_stance:
        return _fail(
            "no_machine_verified_stance",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
        )

    stance_values = {
        row[
            "value"
        ]
        for row
        in machine_stance
    }

    if (
        "contradicts"
        not in stance_values
    ):
        return _fail(
            "no_machine_verified_contradiction_semantics",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
            machine_stance_values=(
                stance_values
            ),
        )

    if (
        stance_values
        != {
            "contradicts"
        }
    ):
        return _fail(
            "conflicting_machine_verified_stance",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
            machine_stance_values=(
                stance_values
            ),
        )

    allowed_basis = {
        _key(
            value
        )
        for value
        in (
            VALIDATION_REFERENCE_BASIS_BY_FIELD[
                "stance"
            ]
        )
    }

    verified_rows = []
    verified_evidence_ids = set()
    verified_link_ids = set()

    for row in machine_stance:
        confidence = row[
            "confidence"
        ]

        if (
            confidence is None
            or confidence
            < TRUSTED_VALIDATION_MIN_CONFIDENCE
        ):
            return _fail(
                "machine_verified_stance_confidence_invalid",
                claim_id=(
                    normalized_claim_id
                ),
                revision_id=(
                    revision_id
                ),
                machine_stance_values=(
                    stance_values
                ),
            )

        basis_class = row[
            "basis_class"
        ]

        if (
            basis_class
            not in allowed_basis
        ):
            return _fail(
                "machine_verified_stance_basis_invalid",
                claim_id=(
                    normalized_claim_id
                ),
                revision_id=(
                    revision_id
                ),
                machine_stance_values=(
                    stance_values
                ),
            )

        evidence_ids = row[
            "evidence_ids"
        ]

        if not evidence_ids:
            return _fail(
                "machine_verified_stance_evidence_missing",
                claim_id=(
                    normalized_claim_id
                ),
                revision_id=(
                    revision_id
                ),
                machine_stance_values=(
                    stance_values
                ),
            )

        for evidence_id in evidence_ids:
            context = (
                _load_verified_semantic_evidence(
                    claim_id=(
                        normalized_claim_id
                    ),
                    evidence_id=(
                        evidence_id
                    ),
                    expected_basis_class=(
                        basis_class
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

            if context is None:
                return _fail(
                    "machine_verified_semantic_evidence_invalid",
                    claim_id=(
                        normalized_claim_id
                    ),
                    revision_id=(
                        revision_id
                    ),
                    machine_stance_values=(
                        stance_values
                    ),
                )

            verified_evidence_ids.add(
                evidence_id
            )

            for link in context[
                "claim_links"
            ]:
                link_id = _clean(
                    link.get(
                        "id"
                    )
                )

                if link_id:
                    verified_link_ids.add(
                        link_id
                    )

        verified_rows.append(
            row
        )

    minimum_confidence = min(
        row[
            "confidence"
        ]
        for row
        in verified_rows
        if row[
            "confidence"
        ]
        is not None
    )

    observed_at = _clean(
        revision.get(
            "as_of"
        )
    )

    if not observed_at:
        return _fail(
            "adjudication_as_of_missing",
            claim_id=(
                normalized_claim_id
            ),
            revision_id=(
                revision_id
            ),
            machine_stance_values=(
                stance_values
            ),
        )

    return {
        "version": (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        ),
        "status": (
            "verified_machine_contradiction_semantics"
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "revision_id": (
            revision_id
        ),
        "candidate": {
            "claim_id": (
                normalized_claim_id
            ),
            "revision_id": (
                revision_id
            ),
            "observed_at": (
                observed_at
            ),
            "stance": (
                "contradicts"
            ),
            "confidence": (
                minimum_confidence
            ),
            "basis_classes": sorted(
                {
                    row[
                        "basis_class"
                    ]
                    for row
                    in verified_rows
                }
            ),
            "machine_run_ids": sorted(
                {
                    row[
                        "run_id"
                    ]
                    for row
                    in verified_rows
                    if row[
                        "run_id"
                    ]
                }
            ),
            "machine_judgment_ids": sorted(
                {
                    row[
                        "judgment_id"
                    ]
                    for row
                    in verified_rows
                    if row[
                        "judgment_id"
                    ]
                }
            ),
            "semantic_evidence_ids": sorted(
                verified_evidence_ids
            ),
            "semantic_claim_link_ids": sorted(
                verified_link_ids
            ),
        },
        "machine_stance_values": [
            "contradicts"
        ],
        "policy": {
            "machine_verified_stance_required": True,
            "model_assisted_stance_is_not_accepted": True,
            "verified_semantic_evidence_is_required": True,
            "verified_semantic_claim_link_is_required": True,
            "contradiction_semantics_verified": True,
            "contradiction_semantics_are_source_semantics": True,
            "claim_truth_established": False,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }


def persist_machine_verified_contradiction_semantics_verification(
    *,
    claim_id: str,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=(
        build_machine_verified_contradiction_semantics_candidate
    ),
    evidence_recorder=(
        record_evidence
    ),
    claim_link_recorder=(
        record_claim_link
    ),
) -> Dict[str, Any]:
    candidate_result = (
        candidate_builder(
            claim_id=(
                claim_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if not isinstance(
        candidate_result,
        dict,
    ):
        raise ValueError(
            "Contradiction semantic candidate "
            "returned invalid data."
        )

    if (
        _clean(
            candidate_result.get(
                "version"
            )
        )
        != (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        )
    ):
        raise ValueError(
            "Contradiction semantic candidate "
            "version is unsupported."
        )

    if (
        candidate_result.get(
            "status"
        )
        != (
            "verified_machine_contradiction_semantics"
        )
    ):
        return {
            "version": (
                MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
            ),
            "status": (
                candidate_result.get(
                    "status"
                )
            ),
            "persisted": False,
            "candidate": (
                candidate_result
            ),
            "evidence": None,
            "claim_link": None,
            "policy": {
                "fails_closed_without_verified_machine_semantics": True,
                "claim_truth_established": False,
                "does_not_change_live_merit": True,
            },
        }

    candidate = (
        candidate_result[
            "candidate"
        ]
    )

    identity = {
        "claim_id": (
            candidate[
                "claim_id"
            ]
        ),
        "revision_id": (
            candidate[
                "revision_id"
            ]
        ),
        "stance": (
            candidate[
                "stance"
            ]
        ),
        "basis_classes": (
            candidate[
                "basis_classes"
            ]
        ),
        "machine_run_ids": (
            candidate[
                "machine_run_ids"
            ]
        ),
        "machine_judgment_ids": (
            candidate[
                "machine_judgment_ids"
            ]
        ),
        "semantic_evidence_ids": (
            candidate[
                "semantic_evidence_ids"
            ]
        ),
        "semantic_claim_link_ids": (
            candidate[
                "semantic_claim_link_ids"
            ]
        ),
    }

    reference_hash = hashlib.sha256(
        _canonical_json(
            identity
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    evidence = evidence_recorder(
        evidence_type=(
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE
        ),
        subject_key=(
            "merit-negative-semantic-evidence|"
            + candidate[
                "claim_id"
            ]
        ),
        observed_at=(
            candidate[
                "observed_at"
            ]
        ),
        reference_key=(
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_REFERENCE_PREFIX
            + reference_hash
        ),
        verification_status=(
            "verified"
        ),
        recorded_at=(
            recorded_at
        ),
        metadata={
            "verifier_version": (
                MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
            ),
            "verification_scope": (
                "machine_verified_stance_semantics_only"
            ),
            "claim_id": (
                candidate[
                    "claim_id"
                ]
            ),
            "revision_id": (
                candidate[
                    "revision_id"
                ]
            ),
            "stance": (
                "contradicts"
            ),
            "confidence": (
                candidate[
                    "confidence"
                ]
            ),
            "basis_classes": (
                candidate[
                    "basis_classes"
                ]
            ),
            "machine_run_ids": (
                candidate[
                    "machine_run_ids"
                ]
            ),
            "machine_judgment_ids": (
                candidate[
                    "machine_judgment_ids"
                ]
            ),
            "semantic_evidence_ids": (
                candidate[
                    "semantic_evidence_ids"
                ]
            ),
            "semantic_claim_link_ids": (
                candidate[
                    "semantic_claim_link_ids"
                ]
            ),
            "contradiction_semantics_verified": True,
            "contradiction_semantics_are_source_semantics": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
        connection_factory=(
            connection_factory
        ),
    )[
        "evidence"
    ]

    link = claim_link_recorder(
        claim_id=(
            candidate[
                "claim_id"
            ]
        ),
        evidence_id=(
            evidence[
                "id"
            ]
        ),
        relationship_type=(
            "verifies_semantics"
        ),
        confidence=(
            candidate[
                "confidence"
            ]
        ),
        observed_at=(
            candidate[
                "observed_at"
            ]
        ),
        recorded_at=(
            recorded_at
        ),
        metadata={
            "negative_merit_semantic_gate": True,
            "machine_verified": True,
            "semantic_reference_only": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
        connection_factory=(
            connection_factory
        ),
    )[
        "link"
    ]

    return {
        "version": (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        ),
        "status": (
            "persisted_verified_machine_contradiction_semantics"
        ),
        "persisted": True,
        "candidate": (
            candidate_result
        ),
        "evidence": (
            evidence
        ),
        "claim_link": (
            link
        ),
        "policy": {
            "semantic_verification_is_machine_verified": True,
            "semantic_verification_is_claim_linked": True,
            "contradiction_semantics_verified": True,
            "contradiction_semantics_are_source_semantics": True,
            "claim_truth_established": False,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }
