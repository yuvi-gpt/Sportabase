import hashlib
import json

from datetime import datetime
from typing import Any, Dict, Optional

from app.intelligence.evidence import record_evidence
from app.intelligence.independence_assertions import record_observation_independence_assertion
from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
)


DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION = (
    "direct-stakeholder-independence-verifier-v1"
)
DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS = (
    "distinct_direct_stakeholder_transfer_records"
)
DIRECT_STAKEHOLDER_TRANSFER_ROLES = frozenset(
    {"origin", "destination"}
)


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


def _parse_time(value: Any, *, label: str) -> datetime:
    text = _clean(value)
    if not text:
        raise ValueError(f"{label} is required.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include timezone.")
    return parsed


def _load_context(
    *,
    claim_id: str,
    left_observation_id: str,
    right_observation_id: str,
    connection_factory,
) -> Dict[str, Any]:
    conn = connection_factory()
    try:
        claim = conn.execute(
            "SELECT * FROM intelligence_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
        observations = conn.execute(
            """
            SELECT *
            FROM source_observations
            WHERE id IN (?, ?)
            ORDER BY id
            """,
            (left_observation_id, right_observation_id),
        ).fetchall()
        links = conn.execute(
            """
            SELECT *
            FROM claim_links
            WHERE claim_id = ?
              AND source_observation_id IN (?, ?)
              AND relationship_type = 'supports'
            ORDER BY id
            """,
            (claim_id, left_observation_id, right_observation_id),
        ).fetchall()
        dependencies = conn.execute(
            """
            SELECT *
            FROM observation_dependencies
            WHERE downstream_source_observation_id IN (?, ?)
            ORDER BY id
            """,
            (left_observation_id, right_observation_id),
        ).fetchall()
    finally:
        conn.close()

    if claim is None:
        raise ValueError("Direct-stakeholder independence claim does not exist.")
    if len(observations) != 2:
        raise ValueError("Direct-stakeholder independence requires two persisted source observations.")

    observation_map = {str(row["id"]): dict(row) for row in observations}
    if set(observation_map) != {left_observation_id, right_observation_id}:
        raise ValueError("Direct-stakeholder observation identity mismatch.")

    linked_ids = {str(row["source_observation_id"]) for row in links}

    return {
        "claim": dict(claim),
        "observations": observation_map,
        "supported_observation_ids": linked_ids,
        "dependencies": [dict(row) for row in dependencies],
    }


def _participant_roles(
    *,
    claim_id: str,
    entity_id: str,
    connection_factory,
):
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT participant_role
            FROM verified_claim_entity_participants
            WHERE claim_id = ?
              AND entity_id = ?
              AND verification_status = 'verified'
            ORDER BY participant_role
            """,
            (claim_id, entity_id),
        ).fetchall()
    finally:
        conn.close()

    return sorted({_key(row["participant_role"]) for row in rows if _key(row["participant_role"])})


def _cross_dependency_exists(
    *,
    dependencies,
    left_observation_id: str,
    right_observation_id: str,
    left_source_id: str,
    right_source_id: str,
) -> bool:
    pair = {
        left_observation_id: {
            "other_observation": right_observation_id,
            "other_source": right_source_id,
        },
        right_observation_id: {
            "other_observation": left_observation_id,
            "other_source": left_source_id,
        },
    }

    for dependency in dependencies:
        downstream = _clean(dependency.get("downstream_source_observation_id"))
        if downstream not in pair:
            continue
        expected = pair[downstream]
        upstream_observation = _clean(dependency.get("upstream_source_observation_id"))
        upstream_source = _clean(dependency.get("upstream_source_id"))
        if upstream_observation == expected["other_observation"]:
            return True
        if upstream_source == expected["other_source"]:
            return True
    return False


def build_direct_stakeholder_independence_candidate(
    *,
    claim_id: str,
    left_observation_id: str,
    right_observation_id: str,
    connection_factory,
    authority_candidate_builder=build_direct_authority_entity_candidate,
) -> Dict[str, Any]:
    normalized_claim = _clean(claim_id)
    left_id = _clean(left_observation_id)
    right_id = _clean(right_observation_id)

    if not normalized_claim or not left_id or not right_id:
        raise ValueError("Claim and both source observation IDs are required.")
    if left_id == right_id:
        raise ValueError("Direct-stakeholder independence requires two distinct observations.")
    if connection_factory is None:
        raise ValueError("Direct-stakeholder independence requires database access.")

    context = _load_context(
        claim_id=normalized_claim,
        left_observation_id=left_id,
        right_observation_id=right_id,
        connection_factory=connection_factory,
    )
    claim = context["claim"]
    left = context["observations"][left_id]
    right = context["observations"][right_id]

    if context["supported_observation_ids"] != {left_id, right_id}:
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "explicit_support_not_verified",
            "candidate": None,
        }

    claim_subject = _clean(claim.get("subject_key"))
    if (
        _clean(left.get("subject_key")) != claim_subject
        or _clean(right.get("subject_key")) != claim_subject
    ):
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "claim_subject_mismatch",
            "candidate": None,
        }

    left_source = _clean(left.get("source_id"))
    right_source = _clean(right.get("source_id"))
    if not left_source or not right_source:
        raise ValueError("Supporting observations must preserve source identity.")
    if left_source == right_source:
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "same_source",
            "candidate": None,
        }

    if _cross_dependency_exists(
        dependencies=context["dependencies"],
        left_observation_id=left_id,
        right_observation_id=right_id,
        left_source_id=left_source,
        right_source_id=right_source,
    ):
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "recorded_dependency_conflict",
            "candidate": None,
        }

    authority_results = []
    for source_id in (left_source, right_source):
        result = authority_candidate_builder(
            source_id=source_id,
            claim_id=normalized_claim,
            connection_factory=connection_factory,
        )
        if not isinstance(result, dict):
            raise ValueError("Direct-authority candidate returned invalid data.")
        if _clean(result.get("version")) != DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION:
            raise ValueError("Direct-authority verifier version is unsupported.")
        if result.get("status") != "verified_direct_stakeholder":
            return {
                "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
                "status": "direct_stakeholder_not_verified",
                "candidate": None,
                "authority_status": result.get("status"),
            }
        authority_results.append(result["candidate"])

    entity_ids = [_clean(row["entity"].get("id")) for row in authority_results]
    if not all(entity_ids) or entity_ids[0] == entity_ids[1]:
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "distinct_stakeholders_not_verified",
            "candidate": None,
        }

    roles = [
        _participant_roles(
            claim_id=normalized_claim,
            entity_id=entity_id,
            connection_factory=connection_factory,
        )
        for entity_id in entity_ids
    ]

    eligible_roles = [
        sorted(set(role_rows) & DIRECT_STAKEHOLDER_TRANSFER_ROLES)
        for role_rows in roles
    ]
    if any(len(role_rows) != 1 for role_rows in eligible_roles):
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "transfer_role_not_verified",
            "candidate": None,
        }
    if {role_rows[0] for role_rows in eligible_roles} != DIRECT_STAKEHOLDER_TRANSFER_ROLES:
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": "origin_destination_pair_not_verified",
            "candidate": None,
        }

    confidence = min(float(row["confidence"]) for row in authority_results)
    availability_at = max(
        _parse_time(row["availability_at"], label="Direct-authority availability")
        for row in authority_results
    ).isoformat()

    return {
        "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
        "status": "verified_direct_stakeholder_independence",
        "candidate": {
            "claim_id": normalized_claim,
            "observation_ids": sorted([left_id, right_id]),
            "source_ids": sorted([left_source, right_source]),
            "entity_ids": sorted(entity_ids),
            "participant_roles": sorted(role_rows[0] for role_rows in eligible_roles),
            "confidence": confidence,
            "availability_at": availability_at,
            "basis": DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS,
            "authority_lineage": [
                {
                    "entity": row["entity"],
                    "source_binding_ids": row["source_binding_ids"],
                    "claim_participant_ids": row["claim_participant_ids"],
                    "source_evidence_ids": row["source_evidence_ids"],
                    "participant_evidence_ids": row["participant_evidence_ids"],
                }
                for row in authority_results
            ],
        },
        "policy": {
            "requires_two_distinct_sources": True,
            "requires_two_distinct_direct_stakeholders": True,
            "requires_origin_destination_role_pair": True,
            "recorded_cross_dependency_fails_closed": True,
            "source_domain_diversity_alone_is_not_independence": True,
            "model_output_is_not_independence_proof": True,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }


def persist_direct_stakeholder_independence_verification(
    *,
    claim_id: str,
    left_observation_id: str,
    right_observation_id: str,
    connection_factory,
    recorded_at: Optional[str] = None,
    candidate_builder=build_direct_stakeholder_independence_candidate,
    evidence_recorder=record_evidence,
    assertion_recorder=record_observation_independence_assertion,
) -> Dict[str, Any]:
    result = candidate_builder(
        claim_id=claim_id,
        left_observation_id=left_observation_id,
        right_observation_id=right_observation_id,
        connection_factory=connection_factory,
    )

    if result.get("status") != "verified_direct_stakeholder_independence":
        return {
            "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "status": result.get("status"),
            "persisted": False,
            "candidate": result,
            "evidence": None,
            "assertion": None,
        }

    candidate = result["candidate"]
    identity = {
        "claim_id": candidate["claim_id"],
        "observation_ids": candidate["observation_ids"],
        "source_ids": candidate["source_ids"],
        "entity_ids": candidate["entity_ids"],
        "participant_roles": candidate["participant_roles"],
        "basis": candidate["basis"],
    }
    reference_hash = hashlib.sha256(
        _canonical_json(identity).encode("utf-8")
    ).hexdigest()

    evidence = evidence_recorder(
        evidence_type="direct_stakeholder_independence_reference",
        subject_key="merit-score-release|" + candidate["claim_id"],
        observed_at=candidate["availability_at"],
        reference_key="direct-stakeholder-independence:" + reference_hash,
        verification_status="verified",
        recorded_at=recorded_at,
        metadata={
            "verifier_version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "basis": candidate["basis"],
            "observation_ids": candidate["observation_ids"],
            "source_ids": candidate["source_ids"],
            "entity_ids": candidate["entity_ids"],
            "participant_roles": candidate["participant_roles"],
            "authority_lineage": candidate["authority_lineage"],
            "machine_verified": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
        connection_factory=connection_factory,
    )["evidence"]

    assertion = assertion_recorder(
        observed_at=candidate["availability_at"],
        provenance_evidence_id=evidence["id"],
        verification_status="verified",
        confidence=candidate["confidence"],
        left_source_observation_id=candidate["observation_ids"][0],
        right_source_observation_id=candidate["observation_ids"][1],
        recorded_at=recorded_at,
        metadata={
            "verifier_version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
            "basis": candidate["basis"],
            "machine_verified": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        },
        connection_factory=connection_factory,
    )

    return {
        "version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
        "status": "persisted_verified_direct_stakeholder_independence",
        "persisted": True,
        "candidate": result,
        "evidence": evidence,
        "assertion": assertion,
        "policy": {
            "append_only_verified_evidence": True,
            "append_only_independence_assertion": True,
            "does_not_establish_claim_truth": True,
            "does_not_change_live_merit": True,
        },
    }
