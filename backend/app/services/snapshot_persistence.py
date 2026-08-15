import hashlib
import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from app.analysis.snapshot_assembly import MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
from app.intelligence.claims import record_claim_link
from app.intelligence.evidence import record_evidence
from app.intelligence.observations import (
    record_reporter_observation,
    record_source_observation,
)

MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION = (
    "model-assisted-snapshot-persistence-v1"
)
MODEL_ASSISTED_SNAPSHOT_EVIDENCE_TYPE = "claim_evidence_snapshot"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _snapshot_hash(snapshot: Dict[str, Any]) -> str:
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(
        ("model-assisted-snapshot-content|" + payload).encode("utf-8")
    ).hexdigest()


def _domain_for_url(url: str, normalize_url) -> str:
    hostname = str(
        urlparse(_clean(normalize_url(url))).hostname or ""
    ).strip().lower()
    return hostname[4:] if hostname.startswith("www.") else hostname


def _row(conn, table: str, record_id: str, label: str):
    row = conn.execute(
        f"SELECT * FROM {table} WHERE id = ?",
        (record_id,),
    ).fetchone()

    if row is None:
        raise ValueError(f"{label} does not exist.")

    return row


def _preflight(
    *,
    claim_id: str,
    source_id: str,
    reporter_id: Optional[str],
    subject_key: str,
    claim_text: str,
    source_url: str,
    media_item_id: Optional[str],
    story_id: Optional[str],
    normalize_url,
    connection_factory,
) -> None:
    conn = connection_factory()

    try:
        claim = _row(
            conn,
            "intelligence_claims",
            claim_id,
            "Persistence claim",
        )
        source = _row(
            conn,
            "intelligence_sources",
            source_id,
            "Persistence source",
        )

        if _clean(claim["subject_key"]) != subject_key:
            raise ValueError(
                "Persistence subject key does not match the persisted claim."
            )

        persisted_text = _clean(claim["canonical_text"])

        if persisted_text and persisted_text != claim_text:
            raise ValueError(
                "Persistence claim text does not match the persisted claim."
            )

        expected_domain = _clean(source["canonical_domain"]).lower()
        actual_domain = _domain_for_url(
            source_url,
            normalize_url,
        )

        if not actual_domain or actual_domain != expected_domain:
            raise ValueError(
                "Persistence source ID does not match the snapshot source URL."
            )

        if reporter_id:
            _row(
                conn,
                "intelligence_reporters",
                reporter_id,
                "Persistence reporter",
            )

        if media_item_id:
            _row(
                conn,
                "media_items",
                media_item_id,
                "Persistence media item",
            )

        if story_id:
            _row(
                conn,
                "intelligence_stories",
                story_id,
                "Persistence story",
            )

    finally:
        conn.close()


def persist_model_assisted_evidence_snapshot(
    *,
    assembly: Dict[str, Any],
    source_id: str,
    subject_key: str,
    reporter_id: Optional[str] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    normalize_url=None,
    connection_factory=None,
) -> Dict[str, Any]:
    if not isinstance(assembly, dict):
        raise ValueError(
            "Snapshot persistence assembly must be a dictionary."
        )

    if normalize_url is None or connection_factory is None:
        raise ValueError(
            "Snapshot persistence requires URL normalization and DB access."
        )

    if (
        _clean(assembly.get("version"))
        != MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
    ):
        raise ValueError(
            "Unsupported model-assisted snapshot assembly version."
        )

    if _clean(assembly.get("status")).lower() != "assembled":
        raise ValueError(
            "Only assembled snapshots can be persisted."
        )

    snapshot = assembly.get("snapshot")

    if not isinstance(snapshot, dict):
        raise ValueError(
            "Assembled snapshot is required."
        )

    claim_id = _clean(assembly.get("claim_id"))
    snapshot_id = _clean(assembly.get("snapshot_id"))
    assembly_observation_id = _clean(
        assembly.get("observation_id")
    )
    semantic_assessment_id = _clean(
        assembly.get("semantic_assessment_id")
    )

    if not all(
        (
            claim_id,
            snapshot_id,
            assembly_observation_id,
            semantic_assessment_id,
        )
    ):
        raise ValueError(
            "Snapshot persistence lineage IDs are incomplete."
        )

    if _clean(snapshot.get("id")) != snapshot_id:
        raise ValueError(
            "Snapshot ID does not match the assembly."
        )

    if _clean(snapshot.get("claim_id")) != claim_id:
        raise ValueError(
            "Snapshot claim ID does not match the assembly."
        )

    claim_text = _clean(snapshot.get("claim_text"))
    snapshot_as_of = _clean(snapshot.get("as_of"))

    if not claim_text or not snapshot_as_of:
        raise ValueError(
            "Snapshot persistence requires claim text and as-of time."
        )

    review = snapshot.get("review", {})
    derivation = snapshot.get("derivation", {})

    if (
        not isinstance(review, dict)
        or _clean(review.get("status")).lower() != "draft"
    ):
        raise ValueError(
            "Model-assisted persistence requires draft review status."
        )

    if (
        not isinstance(derivation, dict)
        or _clean(derivation.get("mode")).lower()
        != "model_assisted"
    ):
        raise ValueError(
            "Model-assisted persistence requires model-assisted derivation."
        )

    observations = snapshot.get("observations")

    if (
        not isinstance(observations, list)
        or len(observations) != 1
        or not isinstance(observations[0], dict)
    ):
        raise ValueError(
            "Persistence v1 requires exactly one assembled observation."
        )

    observation = observations[0]

    if (
        _clean(observation.get("id"))
        != assembly_observation_id
    ):
        raise ValueError(
            "Observation ID does not match the assembly."
        )

    if observation.get("depends_on_observation_ids", []):
        raise ValueError(
            "Persistence v1 refuses assembly-provided "
            "dependency observation IDs."
        )

    source_url = _clean(assembly.get("source_url"))
    observed_at = _clean(observation.get("observed_at"))

    if (
        not source_url
        or _clean(observation.get("source_url"))
        != source_url
    ):
        raise ValueError(
            "Snapshot source URL does not match the observation."
        )

    if not observed_at:
        raise ValueError(
            "Snapshot observation time is required."
        )

    source_id = _clean(source_id)
    subject_key = _clean(subject_key)
    reporter_id = _clean(reporter_id) or None
    media_item_id = _clean(media_item_id) or None
    story_id = _clean(story_id) or None

    if not source_id or not subject_key:
        raise ValueError(
            "Persistence requires source ID and subject key."
        )

    adjudication = assembly.get(
        "authority_adjudication",
        {},
    )

    learning_signal = (
        adjudication.get(
            "learning_signal",
            {},
        )
        if isinstance(adjudication, dict)
        else {}
    )

    if not isinstance(learning_signal, dict):
        raise ValueError(
            "Snapshot learning signal is invalid."
        )

    if bool(
        learning_signal.get("training_eligible")
    ):
        raise ValueError(
            "Model-assisted reference input cannot be training eligible."
        )

    unresolved_targets = assembly.get(
        "unresolved_dependency_targets",
        [],
    )

    if not isinstance(unresolved_targets, list):
        raise ValueError(
            "Unresolved dependency targets must be a list."
        )

    unresolved_targets = sorted(
        {
            _clean(value)
            for value in unresolved_targets
            if _clean(value)
        }
    )

    _preflight(
        claim_id=claim_id,
        source_id=source_id,
        reporter_id=reporter_id,
        subject_key=subject_key,
        claim_text=claim_text,
        source_url=source_url,
        media_item_id=media_item_id,
        story_id=story_id,
        normalize_url=normalize_url,
        connection_factory=connection_factory,
    )

    content_hash = _snapshot_hash(snapshot)

    lineage = {
        "persistence_version": (
            MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION
        ),
        "assembly_version": (
            MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
        ),
        "snapshot_id": snapshot_id,
        "snapshot_content_sha256": content_hash,
        "assembly_observation_id": (
            assembly_observation_id
        ),
        "semantic_assessment_id": (
            semantic_assessment_id
        ),
        "actor_id": _clean(
            observation.get("actor_id")
        ),
        "source_role": _clean(
            observation.get("source_role")
        ).lower(),
        "authority_class": _clean(
            observation.get("authority_class")
        ).lower(),
        "reliability_class": _clean(
            observation.get("reliability_class")
        ).lower(),
        "provenance_class": _clean(
            observation.get("provenance_class")
        ).lower(),
        "stance": _clean(
            observation.get("stance")
        ).lower(),
        "independence_status": _clean(
            observation.get("independence_status")
        ).lower(),
        "derivation_mode": "model_assisted",
        "training_eligible": False,
        "unresolved_dependency_targets": (
            unresolved_targets
        ),
    }

    observation_args = {
        "subject_key": subject_key,
        "observation_type": "report",
        "observed_at": observed_at,
        "status": "unresolved",
        "claim_summary": "",
        "provenance_url": source_url,
        "confidence": None,
        "media_item_id": media_item_id,
        "story_id": story_id,
        "recorded_at": recorded_at,
        "metadata": {
            "derivation_mode": "model_assisted",
            "review_status": "draft",
            "training_eligible": False,
        },
        "normalize_url": normalize_url,
        "connection_factory": (
            connection_factory
        ),
    }

    # Storage target follows resolved identity input,
    # never the model's source_role proposal.
    if reporter_id:
        observation_result = (
            record_reporter_observation(
                reporter_id=reporter_id,
                source_id=source_id,
                **observation_args,
            )
        )
        observation_kind = (
            "reporter_observation"
        )
        observation_target = {
            "reporter_observation_id": (
                observation_result[
                    "observation"
                ]["id"]
            )
        }
    else:
        observation_result = (
            record_source_observation(
                source_id=source_id,
                **observation_args,
            )
        )
        observation_kind = (
            "source_observation"
        )
        observation_target = {
            "source_observation_id": (
                observation_result[
                    "observation"
                ]["id"]
            )
        }

    persisted_observation_id = (
        observation_result[
            "observation"
        ]["id"]
    )

    # Deliberately neutral. The model-proposed stance is kept
    # in the snapshot evidence, not activated in live stance logic.
    observation_link = record_claim_link(
        claim_id=claim_id,
        relationship_type="aligned_to",
        observed_at=observed_at,
        confidence=None,
        metadata={
            "derivation_mode": (
                "model_assisted"
            ),
            "explicit_stance_activated": (
                False
            ),
            "training_eligible": False,
        },
        recorded_at=recorded_at,
        connection_factory=(
            connection_factory
        ),
        **observation_target,
    )

    # snapshot_id is a logical ID, not a complete content
    # identity. Include the canonical content hash so a changed
    # evaluator revision cannot silently collide with an older one.
    evidence_reference = (
        f"{snapshot_id}:{content_hash}"
    )

    evidence_result = record_evidence(
        evidence_type=(
            MODEL_ASSISTED_SNAPSHOT_EVIDENCE_TYPE
        ),
        subject_key=subject_key,
        observed_at=snapshot_as_of,
        claim_summary=claim_text,
        canonical_url=source_url,
        reference_key=evidence_reference,
        verification_status="unverified",
        published_at=(
            _clean(
                observation.get("published_at")
            )
            or None
        ),
        recorded_at=recorded_at,
        metadata={
            "artifact_kind": (
                "model_assisted_claim_"
                "evidence_snapshot"
            ),
            "lineage": lineage,
            "snapshot": snapshot,
            "authority_adjudication": (
                adjudication
            ),
            "trust": {
                "review_status": "draft",
                "verification_status": (
                    "unverified"
                ),
                "self_validating": False,
                "training_eligible": False,
            },
        },
        normalize_url=normalize_url,
        connection_factory=(
            connection_factory
        ),
    )

    evidence_id = evidence_result[
        "evidence"
    ]["id"]

    snapshot_link = record_claim_link(
        claim_id=claim_id,
        relationship_type="aligned_to",
        observed_at=snapshot_as_of,
        confidence=None,
        evidence_id=evidence_id,
        metadata={
            "snapshot_id": snapshot_id,
            "snapshot_content_sha256": (
                content_hash
            ),
            "artifact_kind": (
                "model_assisted_claim_"
                "evidence_snapshot"
            ),
            "explicit_stance_activated": (
                False
            ),
            "training_eligible": False,
        },
        recorded_at=recorded_at,
        connection_factory=(
            connection_factory
        ),
    )

    return {
        "version": (
            MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION
        ),
        "status": "persisted",
        "claim_id": claim_id,
        "snapshot_id": snapshot_id,
        "snapshot_content_sha256": (
            content_hash
        ),
        "assembly_observation_id": (
            assembly_observation_id
        ),
        "persisted_observation": {
            "kind": observation_kind,
            "id": persisted_observation_id,
            "created": bool(
                observation_result[
                    "created"
                ]
            ),
        },
        "observation_id_map": {
            assembly_observation_id: (
                persisted_observation_id
            ),
        },
        "snapshot_evidence": {
            "id": evidence_id,
            "created": bool(
                evidence_result["created"]
            ),
            "verification_status": (
                "unverified"
            ),
        },
        "claim_links": {
            "observation": {
                "id": observation_link[
                    "link"
                ]["id"],
                "created": bool(
                    observation_link[
                        "created"
                    ]
                ),
                "relationship_type": (
                    "aligned_to"
                ),
            },
            "snapshot": {
                "id": snapshot_link[
                    "link"
                ]["id"],
                "created": bool(
                    snapshot_link[
                        "created"
                    ]
                ),
                "relationship_type": (
                    "aligned_to"
                ),
            },
        },
        "unresolved_dependency_targets": (
            unresolved_targets
        ),
        "policy": {
            "model_assisted_remains_untrusted": (
                True
            ),
            "training_eligible": False,
            "observation_status_is_unresolved": (
                True
            ),
            "snapshot_verification_is_unverified": (
                True
            ),
            "model_stance_is_not_activated_as_explicit_stance": (
                True
            ),
            "unresolved_dependency_targets_are_not_persisted_as_edges": (
                True
            ),
            "claim_specific_semantics_live_on_snapshot_evidence": (
                True
            ),
            "source_registry_role_is_not_mutated_from_model_output": (
                True
            ),
            "observation_table_follows_resolved_identity_not_model_role": (
                True
            ),
            "persistence_reuses_existing_intelligence_tables": (
                True
            ),
            "persistence_is_idempotent_and_replay_safe": (
                True
            ),
            "persistence_is_multi_write_not_single_transaction": (
                True
            ),
            "persistence_does_not_change_live_merit": (
                True
            ),
        },
    }
