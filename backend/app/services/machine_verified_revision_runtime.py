import hashlib
import json

from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from app.analysis.adjudication import (
    AUTO_GOLD_BASIS_BY_FIELD,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)

from app.analysis.trusted_validation import (
    TRUSTED_VALIDATION_MIN_CONFIDENCE,
    VALIDATION_REFERENCE_BASIS_BY_FIELD,
    validation_partition_for_claim,
)

from app.intelligence.adjudication_history import (
    AUTOMATED_ADJUDICATION_HISTORY_VERSION,
    load_latest_adjudication_state_revision,
    re_adjudicate_claim,
)

from app.intelligence.claims import (
    record_claim_link,
)

from app.intelligence.evidence import (
    evidence_key_for_record,
    record_evidence,
)


MACHINE_VERIFIED_REVISION_RUNTIME_VERSION = (
    "machine-verified-revision-runtime-v1"
)


MACHINE_VERIFIER_SPECS = {
    "canonical_resolution": {
        "evaluator_id": (
            "canonical-resolution-verifier-v1"
        ),
        "evaluator_family": (
            "canonical_resolution_verifier"
        ),
    },

    "direct_authority_record": {
        "evaluator_id": (
            "direct-authority-record-verifier-v1"
        ),
        "evaluator_family": (
            "direct_authority_record_verifier"
        ),
    },

    "structured_fact": {
        "evaluator_id": (
            "structured-fact-verifier-v1"
        ),
        "evaluator_family": (
            "structured_fact_verifier"
        ),
    },

    "deterministic_rule": {
        "evaluator_id": (
            "deterministic-rule-verifier-v1"
        ),
        "evaluator_family": (
            "deterministic_rule_verifier"
        ),
    },

    "provenance_graph": {
        "evaluator_id": (
            "provenance-graph-verifier-v1"
        ),
        "evaluator_family": (
            "provenance_graph_verifier"
        ),
    },
}


FORBIDDEN_CALLER_TRUST_KEYS = {
    "training_eligible",
    "evaluator_id",
    "evaluator_family",
    "derivation_mode",
    "reference_trusted",
}


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
        separators=(",", ":"),
        allow_nan=False,
    )


def _stable_id(
    value: Any,
    *,
    prefix: str,
) -> str:
    return hashlib.sha256(
        (
            prefix
            + _canonical_json(
                value
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _timestamp(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )

    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed


def _canonical_timestamp(
    value: Any,
    *,
    label: str,
) -> str:
    return _timestamp(
        value,
        label=label,
    ).isoformat()


def _confidence(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Machine verification confidence "
            "must be numeric."
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Machine verification confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Machine verification confidence "
            "must be between 0 and 1."
        )

    return result


def _load_claim(
    *,
    claim_id: str,
    connection_factory,
) -> Dict[str, Any]:
    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (
                claim_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        raise ValueError(
            "Machine verification claim "
            "does not exist."
        )

    return dict(
        row
    )


def _expected_evidence_id(
    *,
    subject_key: str,
    observed_at: str,
    canonical_url: str,
    reference_key: str,
    normalize_url,
) -> str:
    evidence_key = (
        evidence_key_for_record(
            evidence_type=(
                "machine_verified_semantic_reference"
            ),
            subject_key=subject_key,
            observed_at=observed_at,
            canonical_url=canonical_url,
            reference_key=reference_key,
            verification_status="verified",
            normalize_url=normalize_url,
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


def _build_machine_runs(
    *,
    claim_id: str,
    evidence_id: str,
    partition: str,
    field_verifications: List[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    by_basis = {}

    for raw in field_verifications:
        field = _key(
            raw[
                "field"
            ]
        )

        value = _clean(
            raw[
                "value"
            ]
        )

        confidence = _confidence(
            raw[
                "confidence"
            ]
        )

        basis_class = _key(
            raw[
                "basis_class"
            ]
        )

        spec = (
            MACHINE_VERIFIER_SPECS[
                basis_class
            ]
        )

        training_eligible = bool(
            partition
            == "calibration"
            and basis_class
            in (
                AUTO_GOLD_BASIS_BY_FIELD.get(
                    field,
                    set(),
                )
            )
        )

        identity = {
            "claim_id": claim_id,
            "evidence_id": evidence_id,
            "field": field,
            "value": value,
            "confidence": confidence,
            "basis_class": (
                basis_class
            ),
            "evaluator_id": (
                spec[
                    "evaluator_id"
                ]
            ),
            "evaluator_family": (
                spec[
                    "evaluator_family"
                ]
            ),
        }

        judgment = {
            "id": _stable_id(
                identity,
                prefix=(
                    "machine-verified-judgment|"
                ),
            ),
            "field": field,
            "value": value,
            "confidence": confidence,
            "evaluator_id": (
                spec[
                    "evaluator_id"
                ]
            ),
            "evaluator_family": (
                spec[
                    "evaluator_family"
                ]
            ),
            "basis_class": (
                basis_class
            ),
            "evidence_ids": [
                evidence_id
            ],
            "training_eligible": (
                training_eligible
            ),
        }

        by_basis.setdefault(
            basis_class,
            [],
        ).append(
            judgment
        )

    runs = []

    for basis_class in sorted(
        by_basis
    ):
        spec = (
            MACHINE_VERIFIER_SPECS[
                basis_class
            ]
        )

        judgments = sorted(
            by_basis[
                basis_class
            ],
            key=lambda row: (
                row[
                    "field"
                ],
                row[
                    "id"
                ],
            ),
        )

        run_identity = {
            "claim_id": claim_id,
            "evidence_id": evidence_id,
            "basis_class": (
                basis_class
            ),
            "judgment_ids": [
                judgment[
                    "id"
                ]
                for judgment
                in judgments
            ],
        }

        runs.append(
            {
                "run_id": _stable_id(
                    run_identity,
                    prefix=(
                        "machine-verified-run|"
                    ),
                ),
                "evaluator_id": (
                    spec[
                        "evaluator_id"
                    ]
                ),
                "evaluator_family": (
                    spec[
                        "evaluator_family"
                    ]
                ),
                "derivation_mode": (
                    "machine_verified"
                ),
                "judgments": (
                    judgments
                ),
            }
        )

    return runs


def persist_machine_verified_reference_revision(
    *,
    claim_id: str,
    verification_evidence: Dict[
        str,
        Any,
    ],
    field_verifications: List[
        Dict[str, Any]
    ],
    normalize_url,
    connection_factory,
    recorded_at: Optional[str] = None,
    latest_loader=(
        load_latest_adjudication_state_revision
    ),
    evidence_recorder=(
        record_evidence
    ),
    claim_link_recorder=(
        record_claim_link
    ),
    history_writer=(
        re_adjudicate_claim
    ),
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Machine verification claim ID "
            "is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Machine verification requires "
            "database access."
        )

    if normalize_url is None:
        raise ValueError(
            "Machine verification requires "
            "URL normalization."
        )

    if not isinstance(
        verification_evidence,
        dict,
    ):
        raise ValueError(
            "Machine verification evidence "
            "must be a dictionary."
        )

    if (
        not isinstance(
            field_verifications,
            list,
        )
        or not field_verifications
    ):
        raise ValueError(
            "Machine verification requires "
            "at least one field verification."
        )

    claim = _load_claim(
        claim_id=(
            normalized_claim_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    subject_key = _clean(
        claim.get(
            "subject_key"
        )
    )

    if not subject_key:
        raise ValueError(
            "Machine verification claim "
            "subject key is missing."
        )

    latest = latest_loader(
        claim_id=(
            normalized_claim_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        latest,
        dict,
    ):
        raise ValueError(
            "Machine verification requires "
            "an existing baseline revision."
        )

    latest_claim_id = _clean(
        latest.get(
            "claim_id"
        )
    )

    if (
        latest_claim_id
        != normalized_claim_id
    ):
        raise ValueError(
            "Latest adjudication revision "
            "belongs to another claim."
        )

    latest_adjudication = (
        latest.get(
            "adjudication"
        )
    )

    if not isinstance(
        latest_adjudication,
        dict,
    ):
        raise ValueError(
            "Latest adjudication revision "
            "is missing adjudication lineage."
        )

    previous_runs = (
        latest_adjudication.get(
            "evaluators"
        )
    )

    if not isinstance(
        previous_runs,
        list,
    ):
        raise ValueError(
            "Latest adjudication evaluator "
            "history must be a list."
        )

    observed_at = (
        _canonical_timestamp(
            verification_evidence.get(
                "observed_at"
            ),
            label=(
                "Machine verification observed_at"
            ),
        )
    )

    canonical_url = _clean(
        verification_evidence.get(
            "canonical_url"
        )
    )

    reference_key = _clean(
        verification_evidence.get(
            "reference_key"
        )
    )

    if (
        not canonical_url
        and not reference_key
    ):
        raise ValueError(
            "Machine verification evidence "
            "requires a canonical URL "
            "or reference key."
        )

    claim_summary = _clean(
        verification_evidence.get(
            "claim_summary"
        )
        or claim.get(
            "canonical_text"
        )
    )

    published_at = (
        _clean(
            verification_evidence.get(
                "published_at"
            )
        )
        or None
    )

    raw_metadata = (
        verification_evidence.get(
            "metadata",
            {},
        )
    )

    if not isinstance(
        raw_metadata,
        dict,
    ):
        raise ValueError(
            "Machine verification evidence "
            "metadata must be a dictionary."
        )

    normalized_verifications = []
    seen_fields = set()

    for raw in field_verifications:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Machine field verification "
                "must be a dictionary."
            )

        forbidden = (
            set(
                raw.keys()
            )
            & FORBIDDEN_CALLER_TRUST_KEYS
        )

        if forbidden:
            raise ValueError(
                "Machine verification caller "
                "cannot supply trust-control fields."
            )

        field = _key(
            raw.get(
                "field"
            )
        )

        if (
            field
            not in MULTI_EVALUATOR_FIELDS
        ):
            raise ValueError(
                "Machine verification field "
                "is unsupported."
            )

        if field in seen_fields:
            raise ValueError(
                "Machine verification may provide "
                "at most one value per field."
            )

        seen_fields.add(
            field
        )

        value = _clean(
            raw.get(
                "value"
            )
        )

        if not value:
            raise ValueError(
                "Machine verification value "
                "is required."
            )

        confidence = _confidence(
            raw.get(
                "confidence"
            )
        )

        if (
            confidence
            < TRUSTED_VALIDATION_MIN_CONFIDENCE
        ):
            raise ValueError(
                "Machine verification confidence "
                "is below the trusted validation "
                "minimum."
            )

        basis_class = _key(
            raw.get(
                "basis_class"
            )
        )

        if (
            basis_class
            not in MACHINE_VERIFIER_SPECS
        ):
            raise ValueError(
                "Machine verification basis "
                "is not executable."
            )

        if (
            basis_class
            not in (
                VALIDATION_REFERENCE_BASIS_BY_FIELD[
                    field
                ]
            )
        ):
            raise ValueError(
                "Machine verification basis "
                "is not allowed for this field."
            )

        normalized_verifications.append(
            {
                "field": field,
                "value": value,
                "confidence": confidence,
                "basis_class": (
                    basis_class
                ),
            }
        )

    normalized_verifications = sorted(
        normalized_verifications,
        key=lambda row: (
            row[
                "field"
            ]
        ),
    )

    partition = (
        validation_partition_for_claim(
            normalized_claim_id
        )
    )

    expected_evidence_id = (
        _expected_evidence_id(
            subject_key=subject_key,
            observed_at=observed_at,
            canonical_url=canonical_url,
            reference_key=reference_key,
            normalize_url=normalize_url,
        )
    )

    machine_runs = (
        _build_machine_runs(
            claim_id=(
                normalized_claim_id
            ),
            evidence_id=(
                expected_evidence_id
            ),
            partition=partition,
            field_verifications=(
                normalized_verifications
            ),
        )
    )

    machine_run_ids = {
        _clean(
            run.get(
                "run_id"
            )
        )
        for run in machine_runs
    }

    previous_run_ids = {
        _clean(
            run.get(
                "run_id"
            )
        )
        for run in previous_runs
        if (
            isinstance(
                run,
                dict,
            )
            and _clean(
                run.get(
                    "run_id"
                )
            )
        )
    }

    overlap = (
        machine_run_ids
        & previous_run_ids
    )

    already_present = bool(
        machine_run_ids
        and machine_run_ids.issubset(
            previous_run_ids
        )
    )

    if (
        overlap
        and not already_present
    ):
        raise ValueError(
            "Machine verification history "
            "contains a partial run collision."
        )

    latest_time = _timestamp(
        latest.get(
            "as_of"
        ),
        label=(
            "Latest adjudication as_of"
        ),
    )

    verification_time = _timestamp(
        observed_at,
        label=(
            "Machine verification observed_at"
        ),
    )

    exact_leaf_replay = bool(
        already_present
        and latest.get(
            "trigger"
        )
        == {
            "type": "evidence_verified",
            "evidence_ids": [
                expected_evidence_id
            ],
        }
        and verification_time
        == latest_time
    )

    if (
        not already_present
        and not (
            verification_time
            > latest_time
        )
    ):
        raise ValueError(
            "Machine verification must be "
            "later than the current baseline."
        )

    evidence = evidence_recorder(
        evidence_type=(
            "machine_verified_semantic_reference"
        ),
        subject_key=subject_key,
        observed_at=observed_at,
        claim_summary=claim_summary,
        canonical_url=canonical_url,
        reference_key=reference_key,
        verification_status="verified",
        published_at=published_at,
        recorded_at=recorded_at,
        metadata={
            **raw_metadata,
            "machine_verified": True,
            "verification_runtime_version": (
                MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
            ),
            "validation_partition": (
                partition
            ),
            "verified_fields": [
                row[
                    "field"
                ]
                for row
                in normalized_verifications
            ],
            "basis_classes": sorted(
                {
                    row[
                        "basis_class"
                    ]
                    for row
                    in normalized_verifications
                }
            ),
            "semantic_reference_only": True,
            "claim_truth_established": False,
        },
        normalize_url=normalize_url,
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        evidence,
        dict,
    ):
        raise ValueError(
            "Machine verification evidence "
            "persistence returned invalid data."
        )

    evidence_row = evidence.get(
        "evidence"
    )

    if not isinstance(
        evidence_row,
        dict,
    ):
        raise ValueError(
            "Machine verification evidence "
            "row is missing."
        )

    evidence_id = _clean(
        evidence_row.get(
            "id"
        )
    )

    if (
        evidence_id
        != expected_evidence_id
    ):
        raise ValueError(
            "Machine verification evidence "
            "identity is inconsistent."
        )

    if (
        _key(
            evidence_row.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        raise ValueError(
            "Machine verification evidence "
            "was not persisted as verified."
        )

    minimum_confidence = min(
        row[
            "confidence"
        ]
        for row
        in normalized_verifications
    )

    link = claim_link_recorder(
        claim_id=(
            normalized_claim_id
        ),
        evidence_id=(
            evidence_id
        ),
        relationship_type=(
            "verifies_semantics"
        ),
        confidence=(
            minimum_confidence
        ),
        observed_at=(
            observed_at
        ),
        recorded_at=(
            recorded_at
        ),
        metadata={
            "semantic_reference_only": True,
            "claim_truth_established": False,
            "validation_partition": (
                partition
            ),
            "machine_verified": True,
        },
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        link,
        dict,
    ):
        raise ValueError(
            "Machine verification claim link "
            "persistence returned invalid data."
        )

    link_row = link.get(
        "link"
    )

    if not isinstance(
        link_row,
        dict,
    ):
        raise ValueError(
            "Machine verification claim link "
            "row is missing."
        )

    if (
        _clean(
            link_row.get(
                "evidence_id"
            )
        )
        != evidence_id
    ):
        raise ValueError(
            "Machine verification claim link "
            "does not reference the verified evidence."
        )

    if already_present:
        if exact_leaf_replay:
            history = history_writer(
                claim_id=(
                    normalized_claim_id
                ),
                evaluator_runs=(
                    previous_runs
                ),
                as_of=(
                    observed_at
                ),
                trigger_type=(
                    "evidence_verified"
                ),
                trigger_evidence_ids=[
                    evidence_id
                ],
                recorded_at=(
                    recorded_at
                ),
                connection_factory=(
                    connection_factory
                ),
            )

            revision = history.get(
                "revision"
            )

            return {
                "version": (
                    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
                ),
                "status": (
                    history.get(
                        "status"
                    )
                ),
                "claim_id": (
                    normalized_claim_id
                ),
                "partition": partition,
                "evidence": (
                    evidence_row
                ),
                "claim_link": (
                    link_row
                ),
                "machine_evaluator_runs": (
                    machine_runs
                ),
                "revision": revision,
                "policy": {
                    "machine_verified_only": True,
                    "training_eligibility_is_runtime_derived": True,
                    "holdout_never_becomes_training_data": True,
                    "verified_evidence_is_required": True,
                    "verified_evidence_must_be_claim_linked": True,
                    "semantic_verification_does_not_establish_claim_truth": True,
                    "exact_replay_is_idempotent": True,
                    "does_not_change_live_merit": True,
                },
            }

        return {
            "version": (
                MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
            ),
            "status": (
                "verification_already_present"
            ),
            "claim_id": (
                normalized_claim_id
            ),
            "partition": partition,
            "evidence": (
                evidence_row
            ),
            "claim_link": (
                link_row
            ),
            "machine_evaluator_runs": (
                machine_runs
            ),
            "revision": latest,
            "policy": {
                "machine_verified_only": True,
                "training_eligibility_is_runtime_derived": True,
                "holdout_never_becomes_training_data": True,
                "verified_evidence_is_required": True,
                "verified_evidence_must_be_claim_linked": True,
                "semantic_verification_does_not_establish_claim_truth": True,
                "later_history_is_not_rewound": True,
                "does_not_change_live_merit": True,
            },
        }

    combined_runs = [
        *previous_runs,
        *machine_runs,
    ]

    history = history_writer(
        claim_id=(
            normalized_claim_id
        ),
        evaluator_runs=(
            combined_runs
        ),
        as_of=(
            observed_at
        ),
        trigger_type=(
            "evidence_verified"
        ),
        trigger_evidence_ids=[
            evidence_id
        ],
        recorded_at=(
            recorded_at
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        history,
        dict,
    ):
        raise ValueError(
            "Machine verification adjudication "
            "history returned invalid data."
        )

    if (
        _clean(
            history.get(
                "version"
            )
        )
        != AUTOMATED_ADJUDICATION_HISTORY_VERSION
    ):
        raise ValueError(
            "Machine verification adjudication "
            "history version is unsupported."
        )

    revision = history.get(
        "revision"
    )

    if not isinstance(
        revision,
        dict,
    ):
        raise ValueError(
            "Machine verification revision "
            "is missing."
        )

    if (
        revision.get(
            "trigger"
        )
        != {
            "type": "evidence_verified",
            "evidence_ids": [
                evidence_id
            ],
        }
    ):
        raise ValueError(
            "Machine verification revision "
            "trigger lineage is invalid."
        )

    return {
        "version": (
            MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
        ),
        "status": (
            history.get(
                "status"
            )
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "partition": partition,
        "evidence": evidence_row,
        "claim_link": link_row,
        "machine_evaluator_runs": (
            machine_runs
        ),
        "revision": revision,
        "policy": {
            "machine_verified_only": True,
            "caller_cannot_supply_trust_controls": True,
            "training_eligibility_is_runtime_derived": True,
            "calibration_training_requires_existing_auto_gold_basis": True,
            "holdout_never_becomes_training_data": True,
            "verified_evidence_is_required": True,
            "verified_evidence_must_be_claim_linked": True,
            "semantic_verification_does_not_establish_claim_truth": True,
            "model_baseline_is_preserved_for_calibration": True,
            "append_only_history": True,
            "does_not_change_live_merit": True,
        },
    }