from __future__ import annotations

import hashlib
import json
import math

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.analysis import multi_evaluator_adjudication
from app.intelligence import adjudication_history
from app.services import multimodal_adjudication_intake


MULTIMODAL_ADJUDICATION_RUNTIME_VERSION = "multimodal-adjudication-runtime-v1"

_MODEL_ALLOWED_BASIS = {
    "model_inference",
    "structured_fact",
}

_HARD_AUTHORITY_FIELDS = {
    "source_role",
    "authority_class",
}

_HARD_EVALUATOR_ID = "verified-source-claim-entity-match"
_HARD_EVALUATOR_FAMILY = "verified_authority_record"
_HARD_BASIS = "direct_authority_record"

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

_FORBIDDEN_INDEPENDENCE_VALUES = {
    "established",
    "independent",
    "verified_independent",
    "independence_established",
}


class MultimodalAdjudicationRuntimeError(RuntimeError):
    pass


class AdjudicationIntakeValidationError(MultimodalAdjudicationRuntimeError):
    pass


class AdjudicationEvidenceValidationError(MultimodalAdjudicationRuntimeError):
    pass


class AdjudicationAuthorityValidationError(MultimodalAdjudicationRuntimeError):
    pass


class AdjudicationHistoryValidationError(MultimodalAdjudicationRuntimeError):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


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


def _timestamp(value: Any, *, label: str) -> str:
    text = _clean(value)

    if not text:
        raise AdjudicationIntakeValidationError(
            f"{label} is required."
        )

    candidate = text
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise AdjudicationIntakeValidationError(
            f"{label} must be ISO-8601."
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AdjudicationIntakeValidationError(
            f"{label} must include a timezone."
        )

    return parsed.isoformat()


def _confidence(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise AdjudicationIntakeValidationError(
            f"{label} must be numeric."
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AdjudicationIntakeValidationError(
            f"{label} must be numeric."
        ) from exc

    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise AdjudicationIntakeValidationError(
            f"{label} must be finite and between 0 and 1."
        )

    return result


def _row(conn, query: str, params: Sequence[Any]):
    return conn.execute(
        query,
        tuple(params),
    ).fetchone()


def _rows(conn, query: str, params: Sequence[Any] = ()):
    return [
        dict(row)
        for row in conn.execute(
            query,
            tuple(params),
        ).fetchall()
    ]


def _require_intake(
    intake: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(intake, Mapping):
        raise AdjudicationIntakeValidationError(
            "Multimodal adjudication intake must be a mapping."
        )

    intake = dict(intake)

    if _clean(intake.get("version")) != (
        multimodal_adjudication_intake
        .MULTIMODAL_ADJUDICATION_INTAKE_VERSION
    ):
        raise AdjudicationIntakeValidationError(
            "Unsupported multimodal adjudication intake version."
        )

    if _key(intake.get("status")) != "ready":
        raise AdjudicationIntakeValidationError(
            "Multimodal adjudication intake is not ready."
        )

    claim_id = _clean(intake.get("claim_id"))
    media_item_id = _clean(intake.get("media_item_id"))

    if not claim_id:
        raise AdjudicationIntakeValidationError(
            "Multimodal adjudication intake claim ID is required."
        )

    if not media_item_id:
        raise AdjudicationIntakeValidationError(
            "Multimodal adjudication intake media item ID is required."
        )

    policy = intake.get("policy")

    if not isinstance(policy, Mapping):
        raise AdjudicationIntakeValidationError(
            "Multimodal adjudication intake policy is required."
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
            raise AdjudicationIntakeValidationError(
                "Multimodal adjudication intake is missing "
                f"required safety policy: {key}"
            )

    required_false = (
        "establishes_truth",
        "establishes_corroboration",
        "establishes_independence",
        "affects_live_merit",
    )

    for key in required_false:
        if bool(policy.get(key)):
            raise AdjudicationIntakeValidationError(
                "Multimodal adjudication intake may not enable "
                f"{key}."
            )

    aligned_evidence_ids = intake.get("aligned_evidence_ids")
    judgments_by_field = intake.get("judgments_by_field")

    if not isinstance(aligned_evidence_ids, list):
        raise AdjudicationIntakeValidationError(
            "Aligned evidence IDs must be a list."
        )

    normalized_evidence_ids = sorted({
        _clean(value)
        for value in aligned_evidence_ids
        if _clean(value)
    })

    if not normalized_evidence_ids:
        raise AdjudicationIntakeValidationError(
            "At least one aligned evidence ID is required."
        )

    if not isinstance(judgments_by_field, Mapping):
        raise AdjudicationIntakeValidationError(
            "Intake judgments_by_field must be a mapping."
        )

    intake["claim_id"] = claim_id
    intake["media_item_id"] = media_item_id
    intake["aligned_evidence_ids"] = normalized_evidence_ids

    return intake


def _validate_claim_and_evidence(
    conn,
    *,
    intake: Mapping[str, Any],
) -> Dict[str, str]:
    claim_id = intake["claim_id"]

    claim = _row(
        conn,
        """
        SELECT *
        FROM intelligence_claims
        WHERE id = ?
        """,
        (claim_id,),
    )

    if claim is None:
        raise AdjudicationEvidenceValidationError(
            "Persisted adjudication claim does not exist."
        )

    media = _row(
        conn,
        """
        SELECT *
        FROM media_items
        WHERE id = ?
        """,
        (intake["media_item_id"],),
    )

    if media is None:
        raise AdjudicationEvidenceValidationError(
            "Persisted adjudication media item does not exist."
        )

    statuses: Dict[str, str] = {}

    for evidence_id in intake["aligned_evidence_ids"]:
        row = _row(
            conn,
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (evidence_id,),
        )

        if row is None:
            raise AdjudicationEvidenceValidationError(
                "Aligned multimodal evidence does not exist: "
                + evidence_id
            )

        evidence = dict(row)

        link = _row(
            conn,
            """
            SELECT *
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
        )

        if link is None:
            raise AdjudicationEvidenceValidationError(
                "Aligned multimodal evidence is not linked "
                "to the adjudicated claim: "
                + evidence_id
            )

        status = _key(
            evidence.get("verification_status")
        )

        statuses[evidence_id] = status

        if (
            _key(evidence.get("evidence_type"))
            == "multimodal_claim_candidate"
            and status != "unverified"
        ):
            raise AdjudicationEvidenceValidationError(
                "Multimodal claim-candidate evidence must "
                "remain unverified."
            )

    return statuses


def _judgment_groups(
    intake: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    fields = intake["judgments_by_field"]
    seen_ids = set()
    model_groups: Dict[
        Tuple[str, str],
        List[Dict[str, Any]],
    ] = {}
    hard_rows: List[Dict[str, Any]] = []
    aligned = set(intake["aligned_evidence_ids"])

    unknown_fields = (
        set(fields.keys())
        - set(
            multi_evaluator_adjudication
            .MULTI_EVALUATOR_FIELDS
        )
    )

    if unknown_fields:
        raise AdjudicationIntakeValidationError(
            "Unsupported intake adjudication fields: "
            + ", ".join(
                sorted(map(str, unknown_fields))
            )
        )

    for field in (
        multi_evaluator_adjudication
        .MULTI_EVALUATOR_FIELDS
    ):
        raw_rows = fields.get(field, [])

        if not isinstance(raw_rows, list):
            raise AdjudicationIntakeValidationError(
                f"Judgments for {field} must be a list."
            )

        for raw in raw_rows:
            if not isinstance(raw, Mapping):
                raise AdjudicationIntakeValidationError(
                    "Each intake judgment must be a mapping."
                )

            row = dict(raw)
            row_id = _clean(row.get("id"))
            row_field = _key(row.get("field"))
            evaluator_id = _clean(row.get("evaluator_id"))
            evaluator_family = _key(row.get("evaluator_family"))
            basis = _key(row.get("basis_class"))
            value = _clean(row.get("value"))
            evidence_ids = row.get("evidence_ids")

            if not row_id or row_id in seen_ids:
                raise AdjudicationIntakeValidationError(
                    "Judgment IDs must be globally unique and non-empty."
                )

            seen_ids.add(row_id)

            if row_field != field:
                raise AdjudicationIntakeValidationError(
                    "Judgment field does not match its intake bucket."
                )

            if not evaluator_id or not evaluator_family:
                raise AdjudicationIntakeValidationError(
                    "Judgment evaluator identity is required."
                )

            if not value:
                raise AdjudicationIntakeValidationError(
                    "Judgment value is required."
                )

            confidence = _confidence(
                row.get("confidence"),
                label="Judgment confidence",
            )

            if not isinstance(evidence_ids, list):
                raise AdjudicationIntakeValidationError(
                    "Judgment evidence IDs must be a list."
                )

            normalized_evidence_ids = sorted({
                _clean(item)
                for item in evidence_ids
                if _clean(item)
            })

            normalized = {
                "id": row_id,
                "field": row_field,
                "value": value,
                "confidence": confidence,
                "evaluator_id": evaluator_id,
                "evaluator_family": evaluator_family,
                "basis_class": basis,
                "evidence_ids": normalized_evidence_ids,
                "training_eligible": row.get(
                    "training_eligible",
                    False,
                ),
            }

            if not isinstance(
                normalized["training_eligible"],
                bool,
            ):
                raise AdjudicationIntakeValidationError(
                    "Judgment training eligibility must be boolean."
                )

            is_hard = (
                evaluator_family
                == _HARD_EVALUATOR_FAMILY
                or evaluator_id
                == _HARD_EVALUATOR_ID
                or basis
                == _HARD_BASIS
                or normalized["training_eligible"] is True
            )

            if is_hard:
                if (
                    evaluator_id != _HARD_EVALUATOR_ID
                    or evaluator_family != _HARD_EVALUATOR_FAMILY
                    or basis != _HARD_BASIS
                    or normalized["training_eligible"] is not True
                    or field not in _HARD_AUTHORITY_FIELDS
                ):
                    raise AdjudicationAuthorityValidationError(
                        "Hard authority judgment has unsupported identity "
                        "or policy."
                    )

                hard_rows.append(normalized)
                continue

            if basis not in _MODEL_ALLOWED_BASIS:
                raise AdjudicationIntakeValidationError(
                    "Model-assisted judgment cannot claim hard-reference basis."
                )

            if normalized["training_eligible"] is not False:
                raise AdjudicationIntakeValidationError(
                    "Model-assisted judgment cannot be training eligible."
                )

            if not normalized_evidence_ids:
                raise AdjudicationIntakeValidationError(
                    "Model-assisted judgment must reference aligned evidence."
                )

            if not set(normalized_evidence_ids).issubset(aligned):
                raise AdjudicationIntakeValidationError(
                    "Model-assisted judgment references evidence outside "
                    "the aligned multimodal evidence set."
                )

            if (
                field == "independence_status"
                and _key(value) in _FORBIDDEN_INDEPENDENCE_VALUES
            ):
                raise AdjudicationIntakeValidationError(
                    "Model-assisted judgment cannot establish independence."
                )

            model_groups.setdefault(
                (
                    evaluator_id,
                    evaluator_family,
                ),
                [],
            ).append(normalized)

    runs: List[Dict[str, Any]] = []

    for (
        evaluator_id,
        evaluator_family,
    ), rows in sorted(model_groups.items()):
        fields_seen = set()

        for row in rows:
            if row["field"] in fields_seen:
                raise AdjudicationIntakeValidationError(
                    "One model evaluator supplied multiple judgments "
                    "for the same field."
                )

            fields_seen.add(row["field"])

        identity = _canonical_json({
            "claim_id": intake["claim_id"],
            "evaluator_id": evaluator_id,
            "evaluator_family": evaluator_family,
            "judgment_ids": sorted(
                row["id"]
                for row in rows
            ),
        })

        run_id = "multimodal-evaluator:" + hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()

        runs.append({
            "run_id": run_id,
            "evaluator_id": evaluator_id,
            "evaluator_family": evaluator_family,
            "derivation_mode": "model_assisted",
            "judgments": sorted(
                rows,
                key=lambda item: (
                    item["field"],
                    item["id"],
                ),
            ),
        })

    for row in sorted(
        hard_rows,
        key=lambda item: (
            item["field"],
            item["id"],
        ),
    ):
        suffix = hashlib.sha256(
            row["id"].encode("utf-8")
        ).hexdigest()[:20]

        evaluator_id = (
            _HARD_EVALUATOR_ID
            + ":"
            + suffix
        )

        hard_row = {
            **row,
            "evaluator_id": evaluator_id,
        }

        runs.append({
            "run_id": (
                "multimodal-hard-reference:"
                + suffix
            ),
            "evaluator_id": evaluator_id,
            "evaluator_family": _HARD_EVALUATOR_FAMILY,
            "derivation_mode": "machine_verified",
            "judgments": [hard_row],
        })

    if not runs:
        raise AdjudicationIntakeValidationError(
            "Adjudication intake produced no evaluator runs."
        )

    return sorted(
        runs,
        key=lambda run: (
            run["evaluator_family"],
            run["evaluator_id"],
            run["run_id"],
        ),
    )


def _authority_match_key(row: Mapping[str, Any]) -> Tuple[str, str]:
    return (
        _clean(row.get("source_binding_id")),
        _clean(row.get("participant_id")),
    )


def _expected_hard_judgment_ids(
    intake: Mapping[str, Any],
) -> Dict[str, Tuple[str, str]]:
    output: Dict[str, Tuple[str, str]] = {}

    matches = intake.get("authority_matches", [])

    if not isinstance(matches, list):
        raise AdjudicationAuthorityValidationError(
            "Authority matches must be a list."
        )

    for match in matches:
        if not isinstance(match, Mapping):
            raise AdjudicationAuthorityValidationError(
                "Authority match must be a mapping."
            )

        source_binding_id, participant_id = _authority_match_key(match)

        if not source_binding_id or not participant_id:
            raise AdjudicationAuthorityValidationError(
                "Authority match identity is incomplete."
            )

        identity = (
            source_binding_id
            + ":"
            + participant_id
        )

        for field in _HARD_AUTHORITY_FIELDS:
            output[
                "verified-authority:"
                + intake["claim_id"]
                + ":"
                + field
                + ":"
                + identity
            ] = (
                source_binding_id,
                participant_id,
            )

    return output


def _revalidate_hard_authority(
    conn,
    *,
    intake: Mapping[str, Any],
    evaluator_runs: Sequence[Mapping[str, Any]],
) -> None:
    expected_ids = _expected_hard_judgment_ids(
        intake
    )

    hard_judgments = [
        judgment
        for run in evaluator_runs
        if run["derivation_mode"] == "machine_verified"
        for judgment in run["judgments"]
    ]

    hard_ids = {
        judgment["id"]
        for judgment in hard_judgments
    }

    if hard_ids != set(expected_ids):
        raise AdjudicationAuthorityValidationError(
            "Hard authority judgments do not exactly match "
            "the intake authority records."
        )

    for judgment in hard_judgments:
        source_binding_id, participant_id = expected_ids[
            judgment["id"]
        ]

        row = _row(
            conn,
            """
            SELECT
              seb.id AS source_binding_id,
              seb.source_id,
              seb.entity_id AS source_entity_id,
              seb.evidence_id AS source_evidence_id,
              seb.verification_status AS source_status,
              seb.confidence AS source_confidence,
              cp.id AS participant_id,
              cp.claim_id,
              cp.entity_id AS participant_entity_id,
              cp.participant_role,
              cp.evidence_id AS participant_evidence_id,
              cp.verification_status AS participant_status,
              cp.confidence AS participant_confidence,
              se.verification_status AS source_evidence_status,
              pe.verification_status AS participant_evidence_status
            FROM verified_source_entity_bindings seb
            JOIN verified_claim_entity_participants cp
              ON cp.id = ?
            JOIN evidence_records se
              ON se.id = seb.evidence_id
            JOIN evidence_records pe
              ON pe.id = cp.evidence_id
            WHERE seb.id = ?
            """,
            (
                participant_id,
                source_binding_id,
            ),
        )

        if row is None:
            raise AdjudicationAuthorityValidationError(
                "Verified authority database record no longer exists."
            )

        db = dict(row)

        if (
            _key(db["source_status"]) != "verified"
            or _key(db["participant_status"]) != "verified"
            or _key(db["source_evidence_status"]) != "verified"
            or _key(db["participant_evidence_status"]) != "verified"
        ):
            raise AdjudicationAuthorityValidationError(
                "Hard authority requires verified binding and evidence records."
            )

        if (
            _clean(db["claim_id"]) != intake["claim_id"]
            or _clean(db["source_entity_id"])
            != _clean(db["participant_entity_id"])
        ):
            raise AdjudicationAuthorityValidationError(
                "Verified authority database identity no longer matches."
            )

        source_ids = {
            _clean(value)
            for value in intake.get("source_ids", [])
            if _clean(value)
        }

        if (
            not source_ids
            or _clean(db["source_id"]) not in source_ids
        ):
            raise AdjudicationAuthorityValidationError(
                "Verified authority source is not one of the intake sources."
            )

        source_confidence = _confidence(
            db["source_confidence"],
            label="Source binding confidence",
        )

        participant_confidence = _confidence(
            db["participant_confidence"],
            label="Claim participant confidence",
        )

        expected_confidence = min(
            source_confidence,
            participant_confidence,
        )

        if expected_confidence < 0.95:
            raise AdjudicationAuthorityValidationError(
                "Verified authority fell below the 0.95 confidence floor."
            )

        if abs(
            judgment["confidence"]
            - expected_confidence
        ) > 1e-12:
            raise AdjudicationAuthorityValidationError(
                "Hard authority judgment confidence does not match "
                "the verified database records."
            )

        expected_evidence = {
            _clean(db["source_evidence_id"]),
            _clean(db["participant_evidence_id"]),
        } - {""}

        if set(judgment["evidence_ids"]) != expected_evidence:
            raise AdjudicationAuthorityValidationError(
                "Hard authority judgment evidence does not match "
                "the verified database records."
            )

        role = _key(db["participant_role"])

        if role in _INSTITUTION_PARTICIPANT_ROLES:
            expected_values = {
                "source_role": "official_institution",
                "authority_class": "institutional",
            }
        elif role in _HARD_PARTICIPANT_ROLES:
            expected_values = {
                "source_role": "primary_stakeholder",
                "authority_class": "direct",
            }
        else:
            raise AdjudicationAuthorityValidationError(
                "Claim participant role is not hard-authority eligible."
            )

        if (
            judgment["field"] not in expected_values
            or _key(judgment["value"])
            != expected_values[
                judgment["field"]
            ]
        ):
            raise AdjudicationAuthorityValidationError(
                "Hard authority judgment value does not match "
                "the verified participant role."
            )


def _evidence_statuses(
    conn,
    evidence_ids: Sequence[str],
) -> Dict[str, str]:
    output = {}

    for evidence_id in sorted(set(evidence_ids)):
        row = _row(
            conn,
            """
            SELECT verification_status
            FROM evidence_records
            WHERE id = ?
            """,
            (evidence_id,),
        )

        if row is None:
            raise AdjudicationEvidenceValidationError(
                "Referenced adjudication evidence does not exist: "
                + evidence_id
            )

        output[evidence_id] = _key(
            row["verification_status"]
        )

    return output


def _all_judgment_evidence_ids(
    evaluator_runs: Sequence[Mapping[str, Any]],
) -> List[str]:
    return sorted({
        _clean(evidence_id)
        for run in evaluator_runs
        for judgment in run["judgments"]
        for evidence_id in judgment.get(
            "evidence_ids",
            [],
        )
        if _clean(evidence_id)
    })


def _choose_trigger(
    *,
    latest: Optional[Mapping[str, Any]],
    adjudication: Mapping[str, Any],
    normalized_as_of: str,
) -> str:
    if latest is None:
        return "initial_evaluation"

    if (
        _clean(latest.get("as_of"))
        == normalized_as_of
        and _canonical_json(
            latest.get("adjudication")
        )
        == _canonical_json(adjudication)
    ):
        previous_type = _key(
            (latest.get("trigger") or {}).get("type")
        )

        if previous_type in {
            "initial_evaluation",
            "evaluator_refresh",
        }:
            return previous_type

    return "evaluator_refresh"


def execute_multimodal_adjudication(
    *,
    intake: Mapping[str, Any],
    as_of: str,
    connection_factory,
    recorded_at: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_intake = _require_intake(
        intake
    )

    normalized_as_of = _timestamp(
        as_of,
        label="Multimodal adjudication as_of",
    )

    conn = connection_factory()

    if conn is None:
        raise MultimodalAdjudicationRuntimeError(
            "Connection factory returned no connection."
        )

    try:
        aligned_statuses = _validate_claim_and_evidence(
            conn,
            intake=normalized_intake,
        )

        evaluator_runs = _judgment_groups(
            normalized_intake
        )

        _revalidate_hard_authority(
            conn,
            intake=normalized_intake,
            evaluator_runs=evaluator_runs,
        )

        judgment_evidence_ids = (
            _all_judgment_evidence_ids(
                evaluator_runs
            )
        )

        before_statuses = _evidence_statuses(
            conn,
            judgment_evidence_ids,
        )

    finally:
        conn.close()

    preview = (
        multi_evaluator_adjudication
        .build_multi_evaluator_adjudication(
            claim_id=(
                normalized_intake[
                    "claim_id"
                ]
            ),
            evaluator_runs=(
                evaluator_runs
            ),
        )
    )

    preview_policy = (
        preview.get("policy")
        or {}
    )

    if (
        preview_policy.get(
            "multi_evaluator_adjudication_does_not_establish_truth"
        )
        is not True
        or preview_policy.get(
            "multi_evaluator_adjudication_does_not_change_live_merit"
        )
        is not True
    ):
        raise AdjudicationHistoryValidationError(
            "Existing adjudication engine safety policy is unavailable."
        )

    latest = (
        adjudication_history
        .load_latest_adjudication_state_revision(
            claim_id=(
                normalized_intake[
                    "claim_id"
                ]
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    trigger_type = _choose_trigger(
        latest=latest,
        adjudication=preview,
        normalized_as_of=(
            normalized_as_of
        ),
    )

    result = (
        adjudication_history
        .re_adjudicate_claim(
            claim_id=(
                normalized_intake[
                    "claim_id"
                ]
            ),
            evaluator_runs=(
                evaluator_runs
            ),
            as_of=(
                normalized_as_of
            ),
            trigger_type=(
                trigger_type
            ),
            trigger_evidence_ids=[],
            recorded_at=(
                recorded_at
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if _canonical_json(
        result.get("adjudication")
    ) != _canonical_json(preview):
        raise AdjudicationHistoryValidationError(
            "Persisted adjudication does not match the validated preview."
        )

    revision = result.get("revision")

    if not isinstance(revision, Mapping):
        raise AdjudicationHistoryValidationError(
            "Adjudication history did not return a revision."
        )

    latest_after = (
        adjudication_history
        .load_latest_adjudication_state_revision(
            claim_id=(
                normalized_intake[
                    "claim_id"
                ]
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    if (
        not isinstance(latest_after, Mapping)
        or _clean(latest_after.get("revision_id"))
        != _clean(revision.get("revision_id"))
    ):
        raise AdjudicationHistoryValidationError(
            "Latest adjudication revision does not match "
            "the persisted multimodal revision."
        )

    conn = connection_factory()

    if conn is None:
        raise MultimodalAdjudicationRuntimeError(
            "Connection factory returned no connection."
        )

    try:
        after_statuses = _evidence_statuses(
            conn,
            judgment_evidence_ids,
        )
    finally:
        conn.close()

    if before_statuses != after_statuses:
        raise AdjudicationHistoryValidationError(
            "Adjudication runtime changed evidence verification state."
        )

    for (
        evidence_id,
        status,
    ) in aligned_statuses.items():
        if (
            evidence_id in after_statuses
            and after_statuses[evidence_id]
            != status
        ):
            raise AdjudicationHistoryValidationError(
                "Aligned multimodal evidence verification state changed."
            )

    model_run_count = sum(
        1
        for run in evaluator_runs
        if run["derivation_mode"]
        == "model_assisted"
    )

    hard_reference_run_count = sum(
        1
        for run in evaluator_runs
        if run["derivation_mode"]
        == "machine_verified"
    )

    return {
        "version": (
            MULTIMODAL_ADJUDICATION_RUNTIME_VERSION
        ),
        "status": _key(
            result.get("status")
        ),
        "claim_id": (
            normalized_intake[
                "claim_id"
            ]
        ),
        "media_item_id": (
            normalized_intake[
                "media_item_id"
            ]
        ),
        "as_of": normalized_as_of,
        "trigger_type": (
            trigger_type
        ),
        "revision_id": _clean(
            revision.get("revision_id")
        ),
        "transition_count": len(
            revision.get(
                "transitions",
                [],
            )
        ),
        "evaluator_run_count": len(
            evaluator_runs
        ),
        "model_run_count": (
            model_run_count
        ),
        "hard_reference_run_count": (
            hard_reference_run_count
        ),
        "adjudication": (
            result["adjudication"]
        ),
        "revision": dict(
            revision
        ),
        "summary": (
            result["adjudication"][
                "summary"
            ]
        ),
        "evidence_verification_statuses": (
            after_statuses
        ),
        "policy": {
            "intake_consumed":
                True,
            "multimodal_evidence_remains_unverified":
                True,
            "model_judgments_are_model_assisted":
                True,
            "hard_authority_judgments_are_machine_verified":
                True,
            "hard_authority_revalidated_against_database":
                True,
            "append_only_history":
                True,
            "linear_revision_chain":
                True,
            "idempotent_replay":
                True,
            "evidence_verification_unchanged":
                True,
            "training_performed":
                False,
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
