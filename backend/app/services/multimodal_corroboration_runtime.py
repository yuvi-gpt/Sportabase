from __future__ import annotations

import json
import math

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.analysis import adjudication as adjudication_analysis
from app.analysis import corroboration as corroboration_analysis
from app.analysis import adjudication_state
from app.analysis import evidence as evidence_analysis
from app.analysis import multi_evaluator_adjudication
from app.analysis import stance as stance_analysis
from app.analysis import support as support_analysis
from app.intelligence import claims as claim_intelligence
from app.services import multimodal_adjudication_intake
from app.services import multimodal_adjudication_runtime
from app.services import direct_stakeholder_independence_verifier


MULTIMODAL_CORROBORATION_RUNTIME_VERSION = (
    "multimodal-corroboration-runtime-v1"
)

_MODEL_STANCE_BASIS = {
    "model_inference",
    "structured_fact",
}


class MultimodalCorroborationRuntimeError(RuntimeError):
    pass


class CorroborationInputError(
    MultimodalCorroborationRuntimeError
):
    pass


class CorroborationBindingError(
    MultimodalCorroborationRuntimeError
):
    pass


class CorroborationIntegrityError(
    MultimodalCorroborationRuntimeError
):
    pass


class _SharedTransactionConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, *args, **kwargs):
        return self._connection.execute(
            *args,
            **kwargs,
        )

    def executemany(self, *args, **kwargs):
        return self._connection.executemany(
            *args,
            **kwargs,
        )

    def cursor(self, *args, **kwargs):
        return self._connection.cursor(
            *args,
            **kwargs,
        )

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        return getattr(
            self._connection,
            name,
        )


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _confidence(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(value, bool):
        raise CorroborationInputError(
            label + " must be numeric."
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CorroborationInputError(
            label + " must be numeric."
        ) from exc

    if (
        not math.isfinite(result)
        or result < 0.0
        or result > 1.0
    ):
        raise CorroborationInputError(
            label
            + " must be finite and between 0 and 1."
        )

    return result


def _require_intake(
    raw: Mapping[str, Any],
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CorroborationInputError(
            label + " intake must be a mapping."
        )

    intake = dict(raw)

    if (
        _clean(
            intake.get("version")
        )
        != (
            multimodal_adjudication_intake
            .MULTIMODAL_ADJUDICATION_INTAKE_VERSION
        )
    ):
        raise CorroborationInputError(
            label + " intake version is unsupported."
        )

    if _key(
        intake.get("status")
    ) != "ready":
        raise CorroborationInputError(
            label + " intake is not ready."
        )

    claim_id = _clean(
        intake.get("claim_id")
    )
    media_item_id = _clean(
        intake.get("media_item_id")
    )

    if not claim_id or not media_item_id:
        raise CorroborationInputError(
            label
            + " intake requires claim and media IDs."
        )

    policy = intake.get("policy")

    if not isinstance(policy, Mapping):
        raise CorroborationInputError(
            label + " intake policy is required."
        )

    required_true = (
        "multimodal_evidence_remains_unverified",
        "model_judgments_are_not_hard_references",
        "verified_authority_requires_database_records",
        "adjudication_not_performed",
        "adjudication_state_not_persisted",
    )

    for key in required_true:
        if policy.get(key) is not True:
            raise CorroborationInputError(
                label
                + " intake safety boundary missing: "
                + key
            )

    for key in (
        "establishes_truth",
        "establishes_corroboration",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(policy.get(key)):
            raise CorroborationInputError(
                label
                + " intake may not enable "
                + key
                + "."
            )

    aligned = intake.get(
        "aligned_evidence_ids"
    )

    if not isinstance(aligned, list):
        raise CorroborationInputError(
            label
            + " intake aligned evidence IDs "
            "must be a list."
        )

    intake["claim_id"] = claim_id
    intake["media_item_id"] = (
        media_item_id
    )
    intake["aligned_evidence_ids"] = (
        sorted({
            _clean(value)
            for value in aligned
            if _clean(value)
        })
    )

    return intake


def _require_adjudication(
    raw: Mapping[str, Any],
    *,
    intake: Mapping[str, Any],
    label: str,
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise CorroborationInputError(
            label
            + " adjudication result must "
            "be a mapping."
        )

    result = dict(raw)

    if (
        _clean(
            result.get("version")
        )
        != (
            multimodal_adjudication_runtime
            .MULTIMODAL_ADJUDICATION_RUNTIME_VERSION
        )
    ):
        raise CorroborationInputError(
            label
            + " adjudication runtime version "
            "is unsupported."
        )

    if (
        _clean(
            result.get("claim_id")
        )
        != intake["claim_id"]
        or _clean(
            result.get("media_item_id")
        )
        != intake["media_item_id"]
    ):
        raise CorroborationBindingError(
            label
            + " adjudication does not match "
            "its intake."
        )

    revision_id = _clean(
        result.get("revision_id")
    )

    if not revision_id:
        raise CorroborationInputError(
            label
            + " adjudication revision ID "
            "is required."
        )

    revision = result.get("revision")

    if not isinstance(revision, Mapping):
        raise CorroborationInputError(
            label
            + " adjudication revision "
            "must be a mapping."
        )

    if (
        _clean(
            revision.get("revision_id")
        )
        != revision_id
    ):
        raise CorroborationBindingError(
            label
            + " adjudication revision "
            "identity mismatch."
        )

    adjudication = result.get(
        "adjudication"
    )

    if not isinstance(
        adjudication,
        Mapping,
    ):
        raise CorroborationInputError(
            label
            + " adjudication payload "
            "must be a mapping."
        )

    if (
        _clean(
            adjudication.get("version")
        )
        != (
            multi_evaluator_adjudication
            .MULTI_EVALUATOR_ADJUDICATION_VERSION
        )
    ):
        raise CorroborationInputError(
            label
            + " multi-evaluator version "
            "is unsupported."
        )

    if (
        _clean(
            adjudication.get("claim_id")
        )
        != intake["claim_id"]
    ):
        raise CorroborationBindingError(
            label
            + " adjudication claim mismatch."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise CorroborationInputError(
            label
            + " adjudication policy "
            "is required."
        )

    required_true = (
        "intake_consumed",
        "multimodal_evidence_remains_unverified",
        "model_judgments_are_model_assisted",
        "hard_authority_revalidated_against_database",
        "append_only_history",
        "linear_revision_chain",
        "idempotent_replay",
        "evidence_verification_unchanged",
    )

    for key in required_true:
        if policy.get(key) is not True:
            raise CorroborationInputError(
                label
                + " adjudication safety boundary "
                "missing: "
                + key
            )

    for key in (
        "training_performed",
        "establishes_truth",
        "establishes_corroboration",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(policy.get(key)):
            raise CorroborationInputError(
                label
                + " adjudication may not enable "
                + key
                + "."
            )

    result["revision_id"] = revision_id
    result["revision"] = dict(revision)
    result["adjudication"] = dict(
        adjudication
    )

    return result


def _require_revision_row(
    conn,
    *,
    claim_id: str,
    result: Mapping[str, Any],
    label: str,
):
    row = conn.execute(
        """
        SELECT *
        FROM adjudication_state_revisions
        WHERE id = ?
        """,
        (
            result["revision_id"],
        ),
    ).fetchone()

    if row is None:
        raise CorroborationBindingError(
            label
            + " adjudication revision "
            "is not persisted."
        )

    row = dict(row)

    if (
        _clean(
            row.get("claim_id")
        )
        != claim_id
    ):
        raise CorroborationBindingError(
            label
            + " adjudication revision "
            "belongs to another claim."
        )

    if (
        _clean(
            row.get("state_version")
        )
        != (
            adjudication_state
            .AUTOMATED_ADJUDICATION_STATE_VERSION
        )
        or _clean(
            row.get(
                "adjudication_version"
            )
        )
        != (
            multi_evaluator_adjudication
            .MULTI_EVALUATOR_ADJUDICATION_VERSION
        )
    ):
        raise CorroborationBindingError(
            label
            + " persisted adjudication "
            "version is unsupported."
        )

    try:
        stored_revision = json.loads(
            row["revision_json"]
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise CorroborationIntegrityError(
            label
            + " persisted adjudication revision "
            "is invalid JSON."
        ) from exc

    if (
        _canonical_json(
            stored_revision
        )
        != _canonical_json(
            result["revision"]
        )
    ):
        raise CorroborationBindingError(
            label
            + " adjudication result does not "
            "match persisted revision."
        )

    revision_adjudication = (
        stored_revision.get(
            "adjudication"
        )
        if isinstance(
            stored_revision,
            Mapping,
        )
        else None
    )

    if (
        not isinstance(
            revision_adjudication,
            Mapping,
        )
        or _canonical_json(
            revision_adjudication
        )
        != _canonical_json(
            result["adjudication"]
        )
    ):
        raise CorroborationBindingError(
            label
            + " adjudication payload does not "
            "match its persisted revision."
        )

    if (
        _clean(
            stored_revision.get(
                "claim_id"
            )
        )
        != claim_id
        or _clean(
            stored_revision.get(
                "revision_id"
            )
        )
        != result["revision_id"]
    ):
        raise CorroborationBindingError(
            label
            + " persisted revision identity "
            "is inconsistent."
        )

    if (
        _clean(
            stored_revision.get(
                "adjudication_sha256"
            )
        )
        != _clean(
            row.get(
                "adjudication_sha256"
            )
        )
    ):
        raise CorroborationBindingError(
            label
            + " persisted adjudication hash "
            "is inconsistent."
        )


def _require_current_aligned_evidence(
    conn,
    *,
    claim_id: str,
    intake: Mapping[str, Any],
    label: str,
):
    evidence_ids = intake[
        "aligned_evidence_ids"
    ]

    if not evidence_ids:
        raise CorroborationBindingError(
            label
            + " intake has no aligned "
            "multimodal evidence."
        )

    for evidence_id in evidence_ids:
        row = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (
                evidence_id,
            ),
        ).fetchone()

        if row is None:
            raise CorroborationBindingError(
                label
                + " aligned evidence no "
                "longer exists: "
                + evidence_id
            )

        if (
            _key(
                row[
                    "verification_status"
                ]
            )
            != "unverified"
        ):
            raise CorroborationBindingError(
                label
                + " multimodal aligned evidence "
                "must remain unverified."
            )

        link = conn.execute(
            """
            SELECT 1
            FROM claim_links
            WHERE claim_id = ?
              AND evidence_id = ?
              AND relationship_type = 'aligned_to'
            LIMIT 1
            """,
            (
                claim_id,
                evidence_id,
            ),
        ).fetchone()

        if link is None:
            raise CorroborationBindingError(
                label
                + " aligned evidence is no "
                "longer linked to the claim."
            )


def _resolve_observation(
    conn,
    *,
    claim_id: str,
    media_item_id: str,
    label: str,
) -> Dict[str, Any]:
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT so.*
            FROM claim_links AS cl
            JOIN source_observations AS so
              ON so.id = cl.source_observation_id
            WHERE cl.claim_id = ?
              AND cl.relationship_type = 'observed_in'
              AND so.media_item_id = ?
            ORDER BY so.id
            """,
            (
                claim_id,
                media_item_id,
            ),
        ).fetchall()
    ]

    unique = {
        _clean(row.get("id")): row
        for row in rows
        if _clean(row.get("id"))
    }

    if len(unique) != 1:
        raise CorroborationBindingError(
            label
            + " media item must resolve to "
            "exactly one observed-in "
            "source observation."
        )

    observation = next(
        iter(unique.values())
    )

    if (
        _clean(
            observation.get("subject_key")
        )
        == ""
    ):
        raise CorroborationBindingError(
            label
            + " observation subject is missing."
        )

    return observation


def _adjudicated_stance_rows(
    result: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    fields = (
        result["adjudication"]
        .get("fields")
    )

    if not isinstance(fields, Mapping):
        raise CorroborationInputError(
            "Adjudication fields are required."
        )

    stance = fields.get("stance")

    if not isinstance(
        stance,
        Mapping,
    ):
        raise CorroborationInputError(
            "Adjudication stance field "
            "is required."
        )

    judgments = stance.get(
        "judgments"
    )

    if not isinstance(
        judgments,
        list,
    ):
        raise CorroborationInputError(
            "Adjudication stance judgments "
            "must be a list."
        )

    output = {}

    for raw in judgments:
        if not isinstance(raw, Mapping):
            raise CorroborationInputError(
                "Adjudication stance judgment "
                "must be a mapping."
            )

        row = dict(raw)
        row_id = _clean(
            row.get("id")
        )

        if not row_id or row_id in output:
            raise CorroborationInputError(
                "Adjudication stance judgment "
                "IDs must be unique."
            )

        output[row_id] = row

    return output


def _support_stance(
    intake: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    label: str,
) -> Dict[str, Any]:
    buckets = intake.get(
        "judgments_by_field"
    )

    if not isinstance(
        buckets,
        Mapping,
    ):
        raise CorroborationInputError(
            label
            + " intake judgments are required."
        )

    raw_rows = buckets.get(
        "stance",
        [],
    )

    if not isinstance(raw_rows, list):
        raise CorroborationInputError(
            label
            + " stance judgments must be a list."
        )

    adjudicated = (
        _adjudicated_stance_rows(
            result
        )
    )

    high_confidence = []

    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise CorroborationInputError(
                label
                + " stance judgment must "
                "be a mapping."
            )

        row = dict(raw)

        row_id = _clean(
            row.get("id")
        )
        basis = _key(
            row.get("basis_class")
        )
        evaluator_id = _clean(
            row.get("evaluator_id")
        )
        evaluator_family = _key(
            row.get("evaluator_family")
        )
        value = _key(
            row.get("value")
        )

        if (
            not row_id
            or not evaluator_id
            or not evaluator_family
            or not value
        ):
            raise CorroborationInputError(
                label
                + " stance judgment identity "
                "is incomplete."
            )

        if basis not in _MODEL_STANCE_BASIS:
            raise CorroborationInputError(
                label
                + " stance judgment cannot "
                "claim hard-reference basis."
            )

        if (
            row.get(
                "training_eligible",
                False,
            )
            is not False
        ):
            raise CorroborationInputError(
                label
                + " model stance cannot be "
                "training eligible."
            )

        confidence = _confidence(
            row.get("confidence"),
            label=(
                label
                + " stance confidence"
            ),
        )

        persisted = adjudicated.get(
            row_id
        )

        if persisted is None:
            raise CorroborationBindingError(
                label
                + " stance judgment was not "
                "processed by #17 adjudication."
            )

        raw_evidence_ids = row.get(
            "evidence_ids",
            [],
        )

        if not isinstance(
            raw_evidence_ids,
            list,
        ):
            raise CorroborationInputError(
                label
                + " stance evidence IDs "
                "must be a list."
            )

        normalized_evidence_ids = sorted({
            _clean(value)
            for value in raw_evidence_ids
            if _clean(value)
        })

        if (
            not normalized_evidence_ids
            or not set(
                normalized_evidence_ids
            ).issubset(
                set(
                    intake[
                        "aligned_evidence_ids"
                    ]
                )
            )
        ):
            raise CorroborationBindingError(
                label
                + " stance must remain bound "
                "to aligned multimodal evidence."
            )

        comparable = {
            "id": row_id,
            "value": _clean(
                row.get("value")
            ),
            "confidence": confidence,
            "evaluator_id": evaluator_id,
            "evaluator_family": (
                evaluator_family
            ),
            "basis_class": basis,
            "evidence_ids": (
                normalized_evidence_ids
            ),
        }

        persisted_comparable = {
            "id": _clean(
                persisted.get("id")
            ),
            "value": _clean(
                persisted.get("value")
            ),
            "confidence": _confidence(
                persisted.get(
                    "confidence"
                ),
                label=(
                    label
                    + " persisted stance "
                    "confidence"
                ),
            ),
            "evaluator_id": _clean(
                persisted.get(
                    "evaluator_id"
                )
            ),
            "evaluator_family": _key(
                persisted.get(
                    "evaluator_family"
                )
            ),
            "basis_class": _key(
                persisted.get(
                    "basis_class"
                )
            ),
            "evidence_ids": sorted({
                _clean(value)
                for value
                in persisted.get(
                    "evidence_ids",
                    [],
                )
                if _clean(value)
            }),
        }

        if comparable != persisted_comparable:
            raise CorroborationBindingError(
                label
                + " stance judgment differs "
                "from the #17 adjudicated row."
            )

        if (
            confidence
            >= (
                adjudication_analysis
                .HIGH_CONFIDENCE_THRESHOLD
            )
        ):
            high_confidence.append(
                comparable
            )

    if not high_confidence:
        return {
            "status": (
                "support_stance_not_verified"
            ),
            "supports": False,
            "confidence": None,
            "judgment_ids": [],
        }

    values = {
        _key(row["value"])
        for row in high_confidence
    }

    if len(values) != 1:
        return {
            "status": (
                "support_stance_contested"
            ),
            "supports": False,
            "confidence": None,
            "judgment_ids": sorted(
                row["id"]
                for row
                in high_confidence
            ),
        }

    value = next(
        iter(values)
    )

    if value != "supports":
        return {
            "status": (
                "support_stance_not_supporting"
            ),
            "supports": False,
            "confidence": min(
                row["confidence"]
                for row
                in high_confidence
            ),
            "judgment_ids": sorted(
                row["id"]
                for row
                in high_confidence
            ),
        }

    return {
        "status": (
            "verified_model_support_stance"
        ),
        "supports": True,
        "confidence": min(
            row["confidence"]
            for row
            in high_confidence
        ),
        "judgment_ids": sorted(
            row["id"]
            for row
            in high_confidence
        ),
    }


def _record_support_link(
    *,
    claim_id: str,
    observation: Mapping[str, Any],
    stance: Mapping[str, Any],
    intake: Mapping[str, Any],
    adjudication_result: Mapping[
        str,
        Any,
    ],
    connection_factory,
):
    observed_at = _clean(
        observation.get("observed_at")
    )

    if not observed_at:
        raise CorroborationBindingError(
            "Supporting observation "
            "observed_at is required."
        )

    return (
        claim_intelligence
        .record_claim_link(
            claim_id=claim_id,
            relationship_type="supports",
            observed_at=observed_at,
            confidence=stance[
                "confidence"
            ],
            source_observation_id=(
                _clean(
                    observation.get("id")
                )
            ),
            metadata={
                "runtime_version": (
                    MULTIMODAL_CORROBORATION_RUNTIME_VERSION
                ),
                "basis": (
                    "model_assisted_historical_stance"
                ),
                "intake_version": (
                    intake["version"]
                ),
                "adjudication_runtime_version": (
                    adjudication_result[
                        "version"
                    ]
                ),
                "adjudication_revision_id": (
                    adjudication_result[
                        "revision_id"
                    ]
                ),
                "stance_judgment_ids": (
                    stance[
                        "judgment_ids"
                    ]
                ),
                "model_assisted": True,
                "establishes_truth": False,
                "establishes_corroboration": False,
                "establishes_independence": False,
                "affects_live_merit": False,
            },
            connection_factory=(
                connection_factory
            ),
        )
    )


def _claim_bundle(
    conn,
    *,
    claim_id: str,
    media_item_id: str,
    observation_ids: Sequence[str],
) -> Dict[str, Any]:
    claim = conn.execute(
        """
        SELECT *
        FROM intelligence_claims
        WHERE id = ?
        """,
        (
            claim_id,
        ),
    ).fetchone()

    if claim is None:
        raise CorroborationBindingError(
            "Corroboration claim does not exist."
        )

    observation_ids = sorted({
        _clean(value)
        for value in observation_ids
        if _clean(value)
    })

    if len(observation_ids) != 2:
        raise CorroborationIntegrityError(
            "Corroboration bundle requires "
            "exactly two observations."
        )

    placeholders = ",".join(
        "?"
        for _ in observation_ids
    )

    observations = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT *
            FROM source_observations
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            tuple(observation_ids),
        ).fetchall()
    ]

    links = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT *
            FROM claim_links
            WHERE claim_id = ?
              AND source_observation_id
                  IN ({placeholders})
            ORDER BY id
            """,
            tuple(
                [claim_id]
                + observation_ids
            ),
        ).fetchall()
    ]

    dependencies = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT *
            FROM observation_dependencies
            WHERE downstream_source_observation_id
                  IN ({placeholders})
            ORDER BY id
            """,
            tuple(observation_ids),
        ).fetchall()
    ]

    assertions = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT *
            FROM observation_independence_assertions
            WHERE (
                observation_a_source_observation_id
                IN ({placeholders})
                AND
                observation_b_source_observation_id
                IN ({placeholders})
            )
            ORDER BY id
            """,
            tuple(
                observation_ids
                + observation_ids
            ),
        ).fetchall()
    ]

    evidence_ids = sorted({
        _clean(
            row.get(
                "provenance_evidence_id"
            )
        )
        for row in assertions
        if _clean(
            row.get(
                "provenance_evidence_id"
            )
        )
    })

    evidence_rows = []

    if evidence_ids:
        evidence_placeholders = ",".join(
            "?"
            for _ in evidence_ids
        )

        evidence_rows = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT *
                FROM evidence_records
                WHERE id IN (
                    {evidence_placeholders}
                )
                ORDER BY id
                """,
                tuple(evidence_ids),
            ).fetchall()
        ]

    return (
        evidence_analysis
        .build_evidence_analysis_bundle(
            media_item_id=(
                media_item_id
            ),
            story_links=[],
            source_observations=(
                observations
            ),
            reporter_observations=[],
            evidence_records=(
                evidence_rows
            ),
            evidence_links=[],
            claims=[
                dict(claim)
            ],
            claim_links=links,
            observation_dependencies=(
                dependencies
            ),
            observation_independence_assertions=(
                assertions
            ),
        )
    )


def _claim_state(
    state: Mapping[str, Any],
    *,
    claim_id: str,
) -> Dict[str, Any]:
    rows = state.get(
        "claims",
        [],
    )

    if not isinstance(rows, list):
        raise CorroborationIntegrityError(
            "Corroboration state claims "
            "must be a list."
        )

    matches = [
        dict(row)
        for row in rows
        if (
            isinstance(row, Mapping)
            and _clean(
                row.get("claim_id")
            )
            == claim_id
        )
    ]

    if len(matches) != 1:
        raise CorroborationIntegrityError(
            "Expected exactly one "
            "corroboration claim state."
        )

    return matches[0]


def execute_multimodal_corroboration(
    *,
    claim_id: str,
    left_intake: Mapping[str, Any],
    right_intake: Mapping[str, Any],
    left_adjudication: Mapping[str, Any],
    right_adjudication: Mapping[str, Any],
    connection_factory,
    recorded_at: Optional[str] = None,
    independence_verifier=(
        direct_stakeholder_independence_verifier
        .persist_direct_stakeholder_independence_verification
    ),
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise CorroborationInputError(
            "Corroboration claim ID "
            "is required."
        )

    left = _require_intake(
        left_intake,
        label="Left",
    )
    right = _require_intake(
        right_intake,
        label="Right",
    )

    if (
        left["claim_id"]
        != normalized_claim_id
        or right["claim_id"]
        != normalized_claim_id
    ):
        raise CorroborationBindingError(
            "Both intakes must belong "
            "to the requested claim."
        )

    if (
        left["media_item_id"]
        == right["media_item_id"]
    ):
        raise CorroborationInputError(
            "Corroboration requires "
            "two distinct media items."
        )

    left_result = (
        _require_adjudication(
            left_adjudication,
            intake=left,
            label="Left",
        )
    )
    right_result = (
        _require_adjudication(
            right_adjudication,
            intake=right,
            label="Right",
        )
    )

    left_stance = _support_stance(
        left,
        left_result,
        label="Left",
    )
    right_stance = _support_stance(
        right,
        right_result,
        label="Right",
    )

    conn = connection_factory()

    if conn is None:
        raise MultimodalCorroborationRuntimeError(
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
                MultimodalCorroborationRuntimeError(
                    "Corroboration requires "
                    "a fresh connection."
                )
            )

        conn.execute(
            "PRAGMA foreign_keys=ON;"
        )

        foreign_keys = conn.execute(
            "PRAGMA foreign_keys;"
        ).fetchone()

        if (
            foreign_keys is None
            or int(
                foreign_keys[0]
            ) != 1
        ):
            raise (
                MultimodalCorroborationRuntimeError(
                    "SQLite foreign-key "
                    "enforcement is required."
                )
            )

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        claim = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE id = ?
            """,
            (
                normalized_claim_id,
            ),
        ).fetchone()

        if claim is None:
            raise CorroborationBindingError(
                "Corroboration claim "
                "does not exist."
            )

        _require_revision_row(
            conn,
            claim_id=(
                normalized_claim_id
            ),
            result=left_result,
            label="Left",
        )
        _require_revision_row(
            conn,
            claim_id=(
                normalized_claim_id
            ),
            result=right_result,
            label="Right",
        )

        _require_current_aligned_evidence(
            conn,
            claim_id=(
                normalized_claim_id
            ),
            intake=left,
            label="Left",
        )
        _require_current_aligned_evidence(
            conn,
            claim_id=(
                normalized_claim_id
            ),
            intake=right,
            label="Right",
        )

        left_observation = (
            _resolve_observation(
                conn,
                claim_id=(
                    normalized_claim_id
                ),
                media_item_id=(
                    left["media_item_id"]
                ),
                label="Left",
            )
        )
        right_observation = (
            _resolve_observation(
                conn,
                claim_id=(
                    normalized_claim_id
                ),
                media_item_id=(
                    right["media_item_id"]
                ),
                label="Right",
            )
        )

        if (
            _clean(
                left_observation["id"]
            )
            == _clean(
                right_observation["id"]
            )
        ):
            raise CorroborationBindingError(
                "Corroboration observations "
                "must be distinct."
            )

        claim_subject = _clean(
            claim["subject_key"]
        )

        for (
            label,
            observation,
        ) in (
            (
                "Left",
                left_observation,
            ),
            (
                "Right",
                right_observation,
            ),
        ):
            if (
                _clean(
                    observation[
                        "subject_key"
                    ]
                )
                != claim_subject
            ):
                raise (
                    CorroborationBindingError(
                        label
                        + " observation subject "
                        "does not match claim."
                    )
                )

        proxy = (
            _SharedTransactionConnection(
                conn
            )
        )

        def shared_factory():
            return proxy

        support_results = []

        if left_stance["supports"]:
            support_results.append(
                _record_support_link(
                    claim_id=(
                        normalized_claim_id
                    ),
                    observation=(
                        left_observation
                    ),
                    stance=(
                        left_stance
                    ),
                    intake=left,
                    adjudication_result=(
                        left_result
                    ),
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

        if right_stance["supports"]:
            support_results.append(
                _record_support_link(
                    claim_id=(
                        normalized_claim_id
                    ),
                    observation=(
                        right_observation
                    ),
                    stance=(
                        right_stance
                    ),
                    intake=right,
                    adjudication_result=(
                        right_result
                    ),
                    connection_factory=(
                        shared_factory
                    ),
                )
            )

        independence = None

        if (
            left_stance["supports"]
            and right_stance["supports"]
        ):
            independence = (
                independence_verifier(
                    claim_id=(
                        normalized_claim_id
                    ),
                    left_observation_id=(
                        _clean(
                            left_observation[
                                "id"
                            ]
                        )
                    ),
                    right_observation_id=(
                        _clean(
                            right_observation[
                                "id"
                            ]
                        )
                    ),
                    connection_factory=(
                        shared_factory
                    ),
                    recorded_at=(
                        recorded_at
                    ),
                )
            )

            if not isinstance(
                independence,
                Mapping,
            ):
                raise (
                    CorroborationIntegrityError(
                        "Direct-stakeholder "
                        "independence verifier "
                        "returned invalid data."
                    )
                )

            if (
                _clean(
                    independence.get(
                        "version"
                    )
                )
                != (
                    direct_stakeholder_independence_verifier
                    .DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION
                )
            ):
                raise (
                    CorroborationIntegrityError(
                        "Direct-stakeholder "
                        "independence verifier "
                        "version mismatch."
                    )
                )

        bundle = _claim_bundle(
            conn,
            claim_id=(
                normalized_claim_id
            ),
            media_item_id=(
                left["media_item_id"]
            ),
            observation_ids=[
                left_observation["id"],
                right_observation["id"],
            ],
        )

        stance_state = (
            stance_analysis
            .build_claim_stance_analysis(
                bundle
            )
        )

        support_state = (
            support_analysis
            .build_claim_support_provenance(
                bundle
            )
        )

        corroboration_state = (
            corroboration_analysis
            .build_claim_corroboration_assessment(
                support_state=(
                    support_state
                ),
                stance_state=(
                    stance_state
                ),
            )
        )

        support_claim = _claim_state(
            support_state,
            claim_id=(
                normalized_claim_id
            ),
        )

        corroboration_claim = (
            _claim_state(
                corroboration_state,
                claim_id=(
                    normalized_claim_id
                ),
            )
        )

        verifier_persisted = bool(
            independence
            and independence.get(
                "persisted"
            )
            is True
        )

        if verifier_persisted:
            if (
                not support_claim.get(
                    "independent_support_established"
                )
                or not corroboration_claim.get(
                    "corroboration_established"
                )
            ):
                raise (
                    CorroborationIntegrityError(
                        "Verified independence "
                        "did not materialize as "
                        "verified corroboration."
                    )
                )

        if (
            corroboration_claim.get(
                "corroboration_established"
            )
            and not support_claim.get(
                "independent_support_established"
            )
        ):
            raise (
                CorroborationIntegrityError(
                    "Corroboration cannot be "
                    "established without verified "
                    "independent support."
                )
            )

        conn.commit()

        if verifier_persisted:
            status = (
                "verified_direct_stakeholder_corroboration"
            )
        elif not (
            left_stance["supports"]
            and right_stance["supports"]
        ):
            status = (
                "support_stance_not_verified"
            )
        else:
            status = (
                _clean(
                    independence.get(
                        "status"
                    )
                )
                if independence
                else (
                    "independence_not_verified"
                )
            )

        return {
            "version": (
                MULTIMODAL_CORROBORATION_RUNTIME_VERSION
            ),
            "status": status,
            "claim_id": (
                normalized_claim_id
            ),
            "left_media_item_id": (
                left["media_item_id"]
            ),
            "right_media_item_id": (
                right["media_item_id"]
            ),
            "left_observation_id": (
                _clean(
                    left_observation[
                        "id"
                    ]
                )
            ),
            "right_observation_id": (
                _clean(
                    right_observation[
                        "id"
                    ]
                )
            ),
            "left_stance": (
                left_stance
            ),
            "right_stance": (
                right_stance
            ),
            "support_link_count": len(
                support_results
            ),
            "independence": (
                dict(independence)
                if independence
                else None
            ),
            "support_state": (
                support_state
            ),
            "corroboration_state": (
                corroboration_state
            ),
            "independent_support_established": bool(
                support_claim.get(
                    "independent_support_established"
                )
            ),
            "corroboration_established": bool(
                corroboration_claim.get(
                    "corroboration_established"
                )
            ),
            "contested": bool(
                corroboration_claim.get(
                    "contested"
                )
            ),
            "policy": {
                "model_stance_materializes_historical_support_only":
                    True,
                "support_edge_does_not_establish_truth":
                    True,
                "support_edge_does_not_establish_independence":
                    True,
                "independence_requires_existing_direct_stakeholder_verifier":
                    True,
                "requires_two_distinct_sources":
                    True,
                "requires_two_distinct_verified_direct_stakeholders":
                    True,
                "requires_origin_destination_role_pair":
                    True,
                "recorded_cross_dependency_fails_closed":
                    True,
                "source_domain_diversity_alone_is_not_independence":
                    True,
                "model_output_is_not_independence_proof":
                    True,
                "verified_independence_may_establish_corroboration":
                    True,
                "establishes_truth":
                    False,
                "live_merit_evaluated":
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
