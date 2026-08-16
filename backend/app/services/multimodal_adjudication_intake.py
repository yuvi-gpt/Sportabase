from __future__ import annotations

import math

from typing import Any, Dict, List, Mapping

from app.analysis import evidence as evidence_analysis
from app.analysis import observation_semantics

MULTIMODAL_ADJUDICATION_INTAKE_VERSION = (
    "multimodal-adjudication-intake-v1"
)

_ALLOWED_MODEL_BASIS = {
    "model_inference",
    "structured_fact",
}

_HARD_PARTICIPANT_ROLES = {
    "subject",
    "actor",
    "counterparty",
    "origin",
    "destination",
    "affected_party",
}

_INSTITUTION_PARTICIPANT_ROLES = {
    "governing_body",
    "competition",
}


class MultimodalAdjudicationIntakeError(RuntimeError):
    pass


class IntakeBindingError(
    MultimodalAdjudicationIntakeError
):
    pass


class IntakeSemanticError(
    MultimodalAdjudicationIntakeError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _row_dict(row) -> Dict[str, Any]:
    return dict(row)


def _rows(
    conn,
    sql: str,
    parameters=(),
) -> List[Dict[str, Any]]:
    return [
        _row_dict(row)
        for row in conn.execute(
            sql,
            parameters,
        ).fetchall()
    ]


def _one(
    conn,
    sql: str,
    parameters=(),
):
    row = conn.execute(
        sql,
        parameters,
    ).fetchone()

    return (
        _row_dict(row)
        if row is not None
        else None
    )


def _require_claim(
    conn,
    claim_id: str,
) -> Dict[str, Any]:
    row = _one(
        conn,
        """
        SELECT *
        FROM intelligence_claims
        WHERE id = ?
        """,
        (
            claim_id,
        ),
    )

    if row is None:
        raise IntakeBindingError(
            "Intake claim does not exist."
        )

    return row


def _require_media(
    conn,
    media_item_id: str,
) -> Dict[str, Any]:
    row = _one(
        conn,
        """
        SELECT *
        FROM media_items
        WHERE id = ?
        """,
        (
            media_item_id,
        ),
    )

    if row is None:
        raise IntakeBindingError(
            "Intake media item does not exist."
        )

    return row


def _claim_links(
    conn,
    claim_id: str,
) -> List[Dict[str, Any]]:
    return _rows(
        conn,
        """
        SELECT *
        FROM claim_links
        WHERE claim_id = ?
        ORDER BY id
        """,
        (
            claim_id,
        ),
    )


def _aligned_evidence_ids(
    links: List[Dict[str, Any]],
) -> List[str]:
    values = {
        _clean(
            row.get(
                "evidence_id"
            )
        )
        for row in links
        if (
            _clean(
                row.get(
                    "relationship_type"
                )
            ).lower()
            == "aligned_to"
            and _clean(
                row.get(
                    "evidence_id"
                )
            )
        )
    }

    return sorted(
        values
    )


def _observed_source_ids(
    links: List[Dict[str, Any]],
) -> List[str]:
    values = {
        _clean(
            row.get(
                "source_observation_id"
            )
        )
        for row in links
        if (
            _clean(
                row.get(
                    "relationship_type"
                )
            ).lower()
            == "observed_in"
            and _clean(
                row.get(
                    "source_observation_id"
                )
            )
        )
    }

    return sorted(
        values
    )


def _fetch_by_ids(
    conn,
    *,
    table: str,
    ids: List[str],
) -> List[Dict[str, Any]]:
    allowed = {
        "source_observations",
        "evidence_records",
    }

    if table not in allowed:
        raise ValueError(
            "Unsupported intake table."
        )

    if not ids:
        return []

    placeholders = ",".join(
        "?"
        for _ in ids
    )

    return _rows(
        conn,
        f"""
        SELECT *
        FROM {table}
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        tuple(
            ids
        ),
    )


def _validate_evidence(
    rows: List[Dict[str, Any]],
    expected_ids: List[str],
    subject_key: str,
):
    found = sorted(
        _clean(
            row.get(
                "id"
            )
        )
        for row in rows
    )

    if found != expected_ids:
        raise IntakeBindingError(
            "Aligned evidence set is incomplete."
        )

    for row in rows:
        if (
            _clean(
                row.get(
                    "subject_key"
                )
            )
            != subject_key
        ):
            raise IntakeBindingError(
                "Aligned evidence subject "
                "does not match the claim."
            )

        if (
            _clean(
                row.get(
                    "evidence_type"
                )
            ).lower()
            == "multimodal_claim_candidate"
            and _clean(
                row.get(
                    "verification_status"
                )
            ).lower()
            != "unverified"
        ):
            raise IntakeBindingError(
                "Multimodal candidate evidence "
                "must remain unverified at intake."
            )


def _validate_observations(
    rows: List[Dict[str, Any]],
    expected_ids: List[str],
    *,
    subject_key: str,
    media_item_id: str,
):
    found = sorted(
        _clean(
            row.get(
                "id"
            )
        )
        for row in rows
    )

    if found != expected_ids:
        raise IntakeBindingError(
            "Observed source set is incomplete."
        )

    for row in rows:
        if (
            _clean(
                row.get(
                    "subject_key"
                )
            )
            != subject_key
        ):
            raise IntakeBindingError(
                "Source observation subject "
                "does not match the claim."
            )

        if (
            _clean(
                row.get(
                    "media_item_id"
                )
            )
            != media_item_id
        ):
            raise IntakeBindingError(
                "Source observation is outside "
                "the requested media item."
            )

        if (
            _clean(
                row.get(
                    "status"
                )
            ).lower()
            != "unresolved"
        ):
            raise IntakeBindingError(
                "Multimodal source observation "
                "must remain unresolved at intake."
            )


def _story_links(
    conn,
    media_item_id: str,
):
    return _rows(
        conn,
        """
        SELECT
          story_id,
          relationship_type,
          confidence
        FROM story_media_links
        WHERE media_item_id = ?
        ORDER BY story_id
        """,
        (
            media_item_id,
        ),
    )


def _dependencies(
    conn,
    observation_ids: List[str],
):
    if not observation_ids:
        return []

    placeholders = ",".join(
        "?"
        for _ in observation_ids
    )

    return _rows(
        conn,
        f"""
        SELECT *
        FROM observation_dependencies
        WHERE downstream_source_observation_id
          IN ({placeholders})
        ORDER BY id
        """,
        tuple(
            observation_ids
        ),
    )


def _independence_assertions(
    conn,
    observation_ids: List[str],
):
    if not observation_ids:
        return []

    placeholders = ",".join(
        "?"
        for _ in observation_ids
    )

    parameters = tuple(
        observation_ids
        + observation_ids
    )

    return _rows(
        conn,
        f"""
        SELECT *
        FROM observation_independence_assertions
        WHERE observation_a_source_observation_id
          IN ({placeholders})
           OR observation_b_source_observation_id
          IN ({placeholders})
        ORDER BY id
        """,
        parameters,
    )


def _verified_authority_matches(
    conn,
    *,
    claim_id: str,
    source_ids: List[str],
) -> List[Dict[str, Any]]:
    if not source_ids:
        return []

    placeholders = ",".join(
        "?"
        for _ in source_ids
    )

    rows = _rows(
        conn,
        f"""
        SELECT
          seb.id AS source_binding_id,
          seb.source_id,
          seb.entity_id,
          seb.binding_type,
          seb.evidence_id
            AS source_binding_evidence_id,
          seb.confidence
            AS source_binding_confidence,
          seb.observed_at
            AS source_binding_observed_at,
          cp.id AS participant_id,
          cp.participant_role,
          cp.evidence_id
            AS participant_evidence_id,
          cp.confidence
            AS participant_confidence,
          cp.observed_at
            AS participant_observed_at
        FROM verified_source_entity_bindings seb
        JOIN verified_claim_entity_participants cp
          ON cp.entity_id = seb.entity_id
        JOIN evidence_records seb_e
          ON seb_e.id = seb.evidence_id
         AND seb_e.verification_status = 'verified'
        JOIN evidence_records cp_e
          ON cp_e.id = cp.evidence_id
         AND cp_e.verification_status = 'verified'
        WHERE seb.source_id
          IN ({placeholders})
          AND cp.claim_id = ?
          AND seb.verification_status = 'verified'
          AND cp.verification_status = 'verified'
        ORDER BY
          seb.source_id,
          seb.entity_id,
          cp.participant_role,
          seb.id,
          cp.id
        """,
        tuple(
            source_ids
            + [
                claim_id
            ]
        ),
    )

    output = []

    for row in rows:
        source_confidence = float(
            row[
                "source_binding_confidence"
            ]
        )

        participant_confidence = float(
            row[
                "participant_confidence"
            ]
        )

        confidence = min(
            source_confidence,
            participant_confidence,
        )

        if (
            not math.isfinite(
                confidence
            )
            or confidence < 0.95
            or confidence > 1.0
        ):
            raise IntakeBindingError(
                "Verified authority match "
                "fell below the hard-reference "
                "confidence floor."
            )

        role = _clean(
            row[
                "participant_role"
            ]
        ).lower()

        if role in (
            _HARD_PARTICIPANT_ROLES
        ):
            source_role = (
                "primary_stakeholder"
            )

            authority_class = (
                "direct"
            )

        elif role in (
            _INSTITUTION_PARTICIPANT_ROLES
        ):
            source_role = (
                "official_institution"
            )

            authority_class = (
                "institutional"
            )

        else:
            continue

        output.append({
            **row,
            "resolved_source_role":
                source_role,
            "resolved_authority_class":
                authority_class,
            "hard_reference_confidence":
                confidence,
        })

    return output


def _semantic_judgments(
    semantic_result: Mapping[
        str,
        Any,
    ],
    *,
    claim_id: str,
    evidence_ids: List[str],
) -> Dict[
    str,
    List[Dict[str, Any]],
]:
    if not isinstance(
        semantic_result,
        Mapping,
    ):
        raise IntakeSemanticError(
            "Observation semantics must "
            "be a mapping."
        )

    if (
        _clean(
            semantic_result.get(
                "version"
            )
        )
        != (
            observation_semantics
            .CLAIM_OBSERVATION_SEMANTICS_VERSION
        )
    ):
        raise IntakeSemanticError(
            "Unsupported observation "
            "semantic version."
        )

    if (
        _clean(
            semantic_result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise IntakeSemanticError(
            "Observation semantics claim "
            "does not match intake."
        )

    if (
        _clean(
            semantic_result.get(
                "claim_relevance"
            )
        ).lower()
        != "same_claim"
    ):
        raise IntakeSemanticError(
            "Only same-claim observation "
            "semantics are adjudication-ready."
        )

    policy = (
        semantic_result.get(
            "policy"
        )
        or {}
    )

    required_true = (
        "model_does_not_establish_truth",
        "model_does_not_establish_corroboration",
        "model_does_not_establish_independence",
        "observation_semantics_does_not_change_live_merit",
    )

    for key in required_true:
        if policy.get(
            key
        ) is not True:
            raise IntakeSemanticError(
                "Observation semantics missing "
                "required policy boundary: "
                + key
            )

    raw_judgments = (
        semantic_result.get(
            "field_judgments"
        )
    )

    if not isinstance(
        raw_judgments,
        list,
    ):
        raise IntakeSemanticError(
            "Observation semantic field "
            "judgments must be a list."
        )

    output: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    seen_ids = set()

    for raw in raw_judgments:
        if not isinstance(
            raw,
            Mapping,
        ):
            raise IntakeSemanticError(
                "Observation semantic judgment "
                "must be a mapping."
            )

        judgment_id = _clean(
            raw.get(
                "id"
            )
        )

        field = _clean(
            raw.get(
                "field"
            )
        ).lower()

        value = _clean(
            raw.get(
                "value"
            )
        )

        basis = _clean(
            raw.get(
                "basis_class"
            )
        ).lower()

        evaluator_id = _clean(
            raw.get(
                "evaluator_id"
            )
        )

        evaluator_family = _clean(
            raw.get(
                "evaluator_family"
            )
        ).lower()

        confidence = raw.get(
            "confidence"
        )

        if (
            not judgment_id
            or judgment_id in seen_ids
        ):
            raise IntakeSemanticError(
                "Observation semantic judgment "
                "IDs must be unique and non-empty."
            )

        seen_ids.add(
            judgment_id
        )

        if (
            field
            not in (
                observation_semantics
                .FIELD_NAMES
            )
        ):
            raise IntakeSemanticError(
                "Observation semantic field "
                "is unsupported."
            )

        if not value:
            raise IntakeSemanticError(
                "Observation semantic judgment "
                "value is required."
            )

        if basis not in (
            _ALLOWED_MODEL_BASIS
        ):
            raise IntakeSemanticError(
                "Model-assisted judgment "
                "cannot claim hard-reference basis."
            )

        if (
            not evaluator_id
            or not evaluator_family
        ):
            raise IntakeSemanticError(
                "Observation semantic evaluator "
                "identity is required."
            )

        if confidence is None:
            normalized_confidence = 0.0

        else:
            if isinstance(
                confidence,
                bool,
            ):
                raise IntakeSemanticError(
                    "Observation semantic "
                    "confidence must be numeric."
                )

            try:
                normalized_confidence = float(
                    confidence
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise IntakeSemanticError(
                    "Observation semantic "
                    "confidence must be numeric."
                ) from exc

            if not (
                0.0
                <= normalized_confidence
                <= 1.0
            ):
                raise IntakeSemanticError(
                    "Observation semantic "
                    "confidence is out of range."
                )

        output.setdefault(
            field,
            [],
        ).append({
            "id": judgment_id,
            "field": field,
            "value": value,
            "confidence":
                normalized_confidence,
            "evaluator_id":
                evaluator_id,
            "evaluator_family":
                evaluator_family,
            "basis_class":
                basis,
            "evidence_ids":
                list(
                    evidence_ids
                ),
            "training_eligible":
                False,
        })

    return output


def _authority_judgments(
    *,
    claim_id: str,
    matches: List[Dict[str, Any]],
) -> Dict[
    str,
    List[Dict[str, Any]],
]:
    output: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for row in matches:
        evidence_ids = sorted({
            _clean(
                row.get(
                    "source_binding_evidence_id"
                )
            ),
            _clean(
                row.get(
                    "participant_evidence_id"
                )
            ),
        } - {
            ""
        })

        confidence = float(
            row[
                "hard_reference_confidence"
            ]
        )

        identity = (
            _clean(
                row[
                    "source_binding_id"
                ]
            )
            + ":"
            + _clean(
                row[
                    "participant_id"
                ]
            )
        )

        for (
            field,
            value,
        ) in (
            (
                "source_role",
                row[
                    "resolved_source_role"
                ],
            ),
            (
                "authority_class",
                row[
                    "resolved_authority_class"
                ],
            ),
        ):
            output.setdefault(
                field,
                [],
            ).append({
                "id": (
                    "verified-authority:"
                    + claim_id
                    + ":"
                    + field
                    + ":"
                    + identity
                ),
                "field": field,
                "value": value,
                "confidence": confidence,
                "evaluator_id": (
                    "verified-source-claim-"
                    "entity-match"
                ),
                "evaluator_family": (
                    "verified_authority_record"
                ),
                "basis_class": (
                    "direct_authority_record"
                ),
                "evidence_ids":
                    evidence_ids,
                "training_eligible":
                    True,
            })

    return output


def _merge_judgments(
    *groups: Mapping[
        str,
        List[Dict[str, Any]],
    ],
) -> Dict[
    str,
    List[Dict[str, Any]],
]:
    output: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for group in groups:
        for (
            field,
            judgments,
        ) in group.items():
            output.setdefault(
                field,
                []
            ).extend(
                judgments
            )

    for field in output:
        output[
            field
        ] = sorted(
            output[
                field
            ],
            key=lambda row: (
                row[
                    "evaluator_family"
                ],
                row[
                    "evaluator_id"
                ],
                row[
                    "id"
                ],
            ),
        )

    return output


def build_multimodal_adjudication_intake(
    *,
    claim_id: str,
    media_item_id: str,
    semantic_result: Mapping[
        str,
        Any,
    ],
    connection_factory,
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    normalized_media_item_id = (
        _clean(
            media_item_id
        )
    )

    if not normalized_claim_id:
        raise ValueError(
            "Adjudication intake claim ID "
            "is required."
        )

    if not normalized_media_item_id:
        raise ValueError(
            "Adjudication intake media "
            "item ID is required."
        )

    conn = connection_factory()

    if conn is None:
        raise (
            MultimodalAdjudicationIntakeError(
                "Connection factory returned "
                "no connection."
            )
        )

    try:
        claim = _require_claim(
            conn,
            normalized_claim_id,
        )

        _require_media(
            conn,
            normalized_media_item_id,
        )

        subject_key = _clean(
            claim.get(
                "subject_key"
            )
        )

        if not subject_key:
            raise IntakeBindingError(
                "Persisted claim subject "
                "is unavailable."
            )

        links = _claim_links(
            conn,
            normalized_claim_id,
        )

        evidence_ids = (
            _aligned_evidence_ids(
                links
            )
        )

        observation_ids = (
            _observed_source_ids(
                links
            )
        )

        if not evidence_ids:
            raise IntakeBindingError(
                "Claim has no aligned "
                "multimodal evidence."
            )

        if not observation_ids:
            raise IntakeBindingError(
                "Claim has no observed-in "
                "source observation."
            )

        evidence_rows = (
            _fetch_by_ids(
                conn,
                table=(
                    "evidence_records"
                ),
                ids=evidence_ids,
            )
        )

        observation_rows = (
            _fetch_by_ids(
                conn,
                table=(
                    "source_observations"
                ),
                ids=observation_ids,
            )
        )

        _validate_evidence(
            evidence_rows,
            evidence_ids,
            subject_key,
        )

        _validate_observations(
            observation_rows,
            observation_ids,
            subject_key=subject_key,
            media_item_id=(
                normalized_media_item_id
            ),
        )

        semantic_source_url = (
            _clean(
                semantic_result.get(
                    "source_url"
                )
            )
            if isinstance(
                semantic_result,
                Mapping,
            )
            else ""
        )

        observation_urls = {
            _clean(
                row.get(
                    "provenance_url"
                )
            )
            for row
            in observation_rows
            if _clean(
                row.get(
                    "provenance_url"
                )
            )
        }

        if (
            not semantic_source_url
            or semantic_source_url
            not in observation_urls
        ):
            raise IntakeSemanticError(
                "Observation semantics source URL "
                "does not match the persisted "
                "source observation."
            )

        dependencies = (
            _dependencies(
                conn,
                observation_ids,
            )
        )

        independence = (
            _independence_assertions(
                conn,
                observation_ids,
            )
        )

        source_ids = sorted({
            _clean(
                row.get(
                    "source_id"
                )
            )
            for row
            in observation_rows
            if _clean(
                row.get(
                    "source_id"
                )
            )
        })

        authority_matches = (
            _verified_authority_matches(
                conn,
                claim_id=(
                    normalized_claim_id
                ),
                source_ids=(
                    source_ids
                ),
            )
        )

        story_links = (
            _story_links(
                conn,
                normalized_media_item_id,
            )
        )

        evidence_bundle = (
            evidence_analysis
            .build_evidence_analysis_bundle(
                media_item_id=(
                    normalized_media_item_id
                ),
                story_links=story_links,
                source_observations=(
                    observation_rows
                ),
                reporter_observations=[],
                evidence_records=(
                    evidence_rows
                ),
                evidence_links=[],
                claims=[
                    claim
                ],
                claim_links=links,
                observation_dependencies=(
                    dependencies
                ),
                observation_independence_assertions=(
                    independence
                ),
            )
        )

        model_judgments = (
            _semantic_judgments(
                semantic_result,
                claim_id=(
                    normalized_claim_id
                ),
                evidence_ids=(
                    evidence_ids
                ),
            )
        )

        hard_judgments = (
            _authority_judgments(
                claim_id=(
                    normalized_claim_id
                ),
                matches=(
                    authority_matches
                ),
            )
        )

        judgments_by_field = (
            _merge_judgments(
                model_judgments,
                hard_judgments,
            )
        )

        return {
            "version": (
                MULTIMODAL_ADJUDICATION_INTAKE_VERSION
            ),
            "status": "ready",
            "claim_id": (
                normalized_claim_id
            ),
            "media_item_id": (
                normalized_media_item_id
            ),
            "subject_key": (
                subject_key
            ),
            "source_ids": (
                source_ids
            ),
            "aligned_evidence_ids": (
                evidence_ids
            ),
            "source_observation_ids": (
                observation_ids
            ),
            "authority_matches": (
                authority_matches
            ),
            "evidence_analysis_bundle": (
                evidence_bundle
            ),
            "judgments_by_field": (
                judgments_by_field
            ),
            "policy": {
                "multimodal_evidence_remains_unverified":
                    True,
                "model_judgments_are_not_hard_references":
                    True,
                "verified_authority_requires_database_records":
                    True,
                "absence_of_dependency_does_not_establish_independence":
                    True,
                "different_domains_do_not_establish_independence":
                    True,
                "adjudication_not_performed":
                    True,
                "adjudication_state_not_persisted":
                    True,
                "training_eligibility_not_changed_by_model":
                    True,
                "establishes_truth":
                    False,
                "establishes_corroboration":
                    False,
                "establishes_independence":
                    False,
                "affects_live_merit":
                    False,
            },
        }

    finally:
        conn.close()
