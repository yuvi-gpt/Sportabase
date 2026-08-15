import hashlib
import json

from typing import (
    Any,
    Dict,
)


from app.analysis.adjudication_evaluators import (
    build_authority_state_adjudication,
)

from app.analysis.authority import (
    CLAIM_AUTHORITY_CLASSES,
    CLAIM_PROVENANCE_CLASSES,
    CLAIM_RELIABILITY_CLASSES,
    CLAIM_SOURCE_ROLES,
)

from app.analysis.observation_semantics import (
    CLAIM_OBSERVATION_SEMANTICS_VERSION,
)

from app.analysis.validation_snapshot import (
    CLAIM_EVIDENCE_SNAPSHOT_VERSION,
    SNAPSHOT_INDEPENDENCE_STATUSES,
    build_claim_evidence_snapshot,
)


MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION = (
    "model-assisted-snapshot-assembly-v1"
)

ASSEMBLY_STATUSES = (
    "assembled",
    "unresolved",
)

_VALID_STANCES = {
    "supports",
    "contradicts",
    "neutral",
    "uncertain",
}

_VALID_RELEVANCE = {
    "same_claim",
    "related_claim",
    "unrelated",
    "uncertain",
}

_VALID_DEPENDENCY_STATUSES = {
    "explicit_dependency",
    "no_explicit_dependency_detected",
    "uncertain",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _claim_fields(
    claim: Dict[str, Any],
):
    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Snapshot assembly claim "
            "must be a dictionary."
        )

    claim_id = _clean(
        claim.get(
            "id"
        )
        or claim.get(
            "claim_id"
        )
    )

    claim_text = _clean(
        claim.get(
            "canonical_text"
        )
        or claim.get(
            "claim_text"
        )
        or claim.get(
            "text"
        )
    )

    if not claim_id:
        raise ValueError(
            "Snapshot assembly claim ID "
            "is required."
        )

    if not claim_text:
        raise ValueError(
            "Snapshot assembly claim text "
            "is required."
        )

    return (
        claim_id,
        claim_text,
    )


def _source_fields(
    source: Dict[str, Any],
):
    if not isinstance(
        source,
        dict,
    ):
        raise ValueError(
            "Snapshot assembly source "
            "must be a dictionary."
        )

    source_url = _clean(
        source.get(
            "final_url"
        )
        or source.get(
            "normalized_url"
        )
        or source.get(
            "url"
        )
    )

    actor_id = _clean(
        source.get(
            "actor_id"
        )
    )

    if not source_url:
        raise ValueError(
            "Snapshot assembly source URL "
            "is required."
        )

    if not actor_id:
        raise ValueError(
            "Snapshot assembly actor ID "
            "is required."
        )

    return (
        source_url,
        actor_id,
    )


def _semantic_fingerprint(
    semantic_assessment: Dict[
        str,
        Any,
    ],
) -> str:
    payload = json.dumps(
        semantic_assessment,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        (
            "observation-semantic-assessment|"
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _observation_id(
    *,
    claim_id: str,
    source_url: str,
    actor_id: str,
) -> str:
    payload = json.dumps(
        {
            "claim_id": claim_id,
            "source_url": source_url,
            "actor_id": actor_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        (
            "model-assisted-observation|"
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _snapshot_id(
    *,
    claim_id: str,
    as_of: str,
    observation_id: str,
) -> str:
    payload = json.dumps(
        {
            "claim_id": claim_id,
            "as_of": _clean(
                as_of
            ),
            "observation_id": (
                observation_id
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )

    return hashlib.sha256(
        (
            "model-assisted-snapshot|"
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _validate_semantic_assessment(
    *,
    semantic_assessment: Dict[
        str,
        Any,
    ],
    claim_id: str,
    source_url: str,
) -> None:
    if not isinstance(
        semantic_assessment,
        dict,
    ):
        raise ValueError(
            "Snapshot assembly semantic "
            "assessment must be a dictionary."
        )

    if (
        _clean(
            semantic_assessment.get(
                "version"
            )
        )
        != CLAIM_OBSERVATION_SEMANTICS_VERSION
    ):
        raise ValueError(
            "Snapshot assembly requires the "
            "current observation semantic version."
        )

    if (
        _clean(
            semantic_assessment.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Snapshot assembly semantic claim ID "
            "does not match the claim."
        )

    if (
        _clean(
            semantic_assessment.get(
                "source_url"
            )
        )
        != source_url
    ):
        raise ValueError(
            "Snapshot assembly semantic source URL "
            "does not match the source."
        )

    derivation = semantic_assessment.get(
        "derivation",
        {},
    )

    if not isinstance(
        derivation,
        dict,
    ):
        raise ValueError(
            "Snapshot assembly semantic "
            "derivation is invalid."
        )

    if (
        _clean(
            derivation.get(
                "mode"
            )
        )
        != "model_assisted"
    ):
        raise ValueError(
            "Snapshot assembly requires "
            "model-assisted semantic derivation."
        )

    if bool(
        derivation.get(
            "self_validating"
        )
    ):
        raise ValueError(
            "Model-assisted semantic assessment "
            "cannot be self-validating."
        )

    if bool(
        derivation.get(
            "training_eligible"
        )
    ):
        raise ValueError(
            "Model-assisted semantic assessment "
            "cannot be training eligible."
        )

    source_role = _clean(
        semantic_assessment.get(
            "source_role"
        )
    ).lower()

    authority_class = _clean(
        semantic_assessment.get(
            "authority_class"
        )
    ).lower()

    reliability_class = _clean(
        semantic_assessment.get(
            "reliability_class"
        )
    ).lower()

    provenance_class = _clean(
        semantic_assessment.get(
            "provenance_class"
        )
    ).lower()

    stance = _clean(
        semantic_assessment.get(
            "stance"
        )
    ).lower()

    independence_status = _clean(
        semantic_assessment.get(
            "independence_status"
        )
    ).lower()

    relevance = _clean(
        semantic_assessment.get(
            "claim_relevance"
        )
    ).lower()

    dependency_status = _clean(
        semantic_assessment.get(
            "dependency_status"
        )
    ).lower()

    if (
        source_role
        not in CLAIM_SOURCE_ROLES
    ):
        raise ValueError(
            "Snapshot assembly source role "
            "is unsupported."
        )

    if (
        authority_class
        not in CLAIM_AUTHORITY_CLASSES
    ):
        raise ValueError(
            "Snapshot assembly authority class "
            "is unsupported."
        )

    if (
        reliability_class
        not in CLAIM_RELIABILITY_CLASSES
    ):
        raise ValueError(
            "Snapshot assembly reliability class "
            "is unsupported."
        )

    if (
        provenance_class
        not in CLAIM_PROVENANCE_CLASSES
    ):
        raise ValueError(
            "Snapshot assembly provenance class "
            "is unsupported."
        )

    if stance not in _VALID_STANCES:
        raise ValueError(
            "Snapshot assembly stance "
            "is unsupported."
        )

    if (
        independence_status
        not in SNAPSHOT_INDEPENDENCE_STATUSES
    ):
        raise ValueError(
            "Snapshot assembly independence "
            "status is unsupported."
        )

    if relevance not in _VALID_RELEVANCE:
        raise ValueError(
            "Snapshot assembly claim relevance "
            "is unsupported."
        )

    if (
        dependency_status
        not in _VALID_DEPENDENCY_STATUSES
    ):
        raise ValueError(
            "Snapshot assembly dependency status "
            "is unsupported."
        )


def _assembly_blockers(
    semantic_assessment: Dict[
        str,
        Any,
    ],
):
    blockers = []

    relevance = _clean(
        semantic_assessment.get(
            "claim_relevance"
        )
    ).lower()

    source_role = _clean(
        semantic_assessment.get(
            "source_role"
        )
    ).lower()

    authority_class = _clean(
        semantic_assessment.get(
            "authority_class"
        )
    ).lower()

    stance = _clean(
        semantic_assessment.get(
            "stance"
        )
    ).lower()

    independence_status = _clean(
        semantic_assessment.get(
            "independence_status"
        )
    ).lower()

    dependency_status = _clean(
        semantic_assessment.get(
            "dependency_status"
        )
    ).lower()

    if relevance != "same_claim":
        blockers.append(
            "claim_relevance_not_same_claim"
        )

    if stance == "uncertain":
        blockers.append(
            "stance_unresolved"
        )

    if (
        source_role
        == "primary_stakeholder"
        and authority_class
        != "direct"
    ):
        blockers.append(
            "primary_stakeholder_authority_unresolved"
        )

    if (
        source_role
        == "official_institution"
        and authority_class
        != "institutional"
    ):
        blockers.append(
            "official_institution_authority_unresolved"
        )

    if (
        source_role
        in {
            "privileged_reporter",
            "publisher",
            "aggregator",
        }
        and authority_class
        != "none"
    ):
        blockers.append(
            "reporting_role_authority_inconsistent"
        )

    if (
        independence_status
        == "established"
    ):
        blockers.append(
            "model_cannot_establish_independence"
        )

    if (
        dependency_status
        == "explicit_dependency"
        and independence_status
        != "not_established"
    ):
        blockers.append(
            "explicit_dependency_requires_"
            "independence_not_established"
        )

    return sorted(
        set(
            blockers
        )
    )


def build_model_assisted_evidence_snapshot(
    *,
    claim: Dict[str, Any],
    source: Dict[str, Any],
    semantic_assessment: Dict[
        str,
        Any,
    ],
    as_of: str,
) -> Dict[str, Any]:
    (
        claim_id,
        claim_text,
    ) = _claim_fields(
        claim
    )

    (
        source_url,
        actor_id,
    ) = _source_fields(
        source
    )

    normalized_as_of = _clean(
        as_of
    )

    if not normalized_as_of:
        raise ValueError(
            "Snapshot assembly as_of "
            "is required."
        )

    _validate_semantic_assessment(
        semantic_assessment=(
            semantic_assessment
        ),
        claim_id=claim_id,
        source_url=source_url,
    )

    semantic_assessment_id = (
        _semantic_fingerprint(
            semantic_assessment
        )
    )

    blockers = _assembly_blockers(
        semantic_assessment
    )

    dependency_targets = (
        semantic_assessment.get(
            "dependency_targets",
            [],
        )
    )

    if not isinstance(
        dependency_targets,
        list,
    ):
        dependency_targets = []

    dependency_targets = sorted(
        {
            _clean(
                value
            )
            for value
            in dependency_targets
            if _clean(
                value
            )
        }
    )

    base = {
        "version": (
            MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
        ),
        "claim_id": claim_id,
        "source_url": source_url,
        "semantic_assessment_id": (
            semantic_assessment_id
        ),
        "blockers": blockers,
        "unresolved_dependency_targets": (
            dependency_targets
        ),
        "policy": {
            "semantic_model_proposes_observation_fields": True,
            "semantic_model_is_not_self_validating": True,
            "unresolved_semantics_do_not_create_snapshot": True,
            "model_cannot_establish_independence": True,
            "dependency_targets_are_not_fabricated_as_observation_ids": True,
            "snapshot_is_always_created_as_draft": True,
            "snapshot_derivation_is_model_assisted": True,
            "automatic_authority_may_be_computed_from_model_assisted_snapshot": True,
            "model_assisted_snapshot_cannot_become_training_reference_by_itself": True,
            "assembly_does_not_establish_truth": True,
            "assembly_does_not_change_live_merit": True,
        },
    }

    if blockers:
        return {
            **base,
            "status": "unresolved",
            "snapshot": None,
            "authority_adjudication": None,
        }

    observation_id = _observation_id(
        claim_id=claim_id,
        source_url=source_url,
        actor_id=actor_id,
    )

    snapshot_id = _snapshot_id(
        claim_id=claim_id,
        as_of=normalized_as_of,
        observation_id=(
            observation_id
        ),
    )

    availability = source.get(
        "availability"
    )

    capture = source.get(
        "capture",
        {},
    )

    if capture is None:
        capture = {}

    if not isinstance(
        capture,
        dict,
    ):
        raise ValueError(
            "Snapshot assembly capture "
            "must be a dictionary."
        )

    observation = {
        "id": observation_id,
        "actor_id": actor_id,
        "source_url": source_url,
        "source_role": _clean(
            semantic_assessment[
                "source_role"
            ]
        ).lower(),
        "authority_class": _clean(
            semantic_assessment[
                "authority_class"
            ]
        ).lower(),
        "reliability_class": _clean(
            semantic_assessment[
                "reliability_class"
            ]
        ).lower(),
        "provenance_class": _clean(
            semantic_assessment[
                "provenance_class"
            ]
        ).lower(),
        "stance": _clean(
            semantic_assessment[
                "stance"
            ]
        ).lower(),
        "independence_status": _clean(
            semantic_assessment[
                "independence_status"
            ]
        ).lower(),
        "depends_on_observation_ids": [],
        "published_at": _clean(
            source.get(
                "published_at"
            )
        ),
        "observed_at": _clean(
            source.get(
                "observed_at"
            )
        ),
        "availability": (
            availability
        ),
        "capture": dict(
            capture
        ),
    }

    snapshot_input = {
        "version": (
            CLAIM_EVIDENCE_SNAPSHOT_VERSION
        ),
        "id": snapshot_id,
        "claim_id": claim_id,
        "claim_text": claim_text,
        "as_of": normalized_as_of,
        "observations": [
            observation
        ],
        "review": {
            "status": "draft",
            "reviewer": "",
            "reviewed_at": "",
            "rationale": "",
        },
        "derivation": {
            "mode": (
                "model_assisted"
            ),
            "producer": (
                MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
            ),
            "producer_version": (
                MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION
            ),
            "evidence_ids": [
                observation_id,
                semantic_assessment_id,
            ],
            "note": (
                "Draft evidence snapshot assembled "
                "from model-assisted observation "
                "semantics. Model output is not "
                "self-validating or training truth. "
                "Explicit dependency targets remain "
                "unresolved until separately mapped "
                "to concrete observations."
            ),
        },
        "outcome": {},
    }

    snapshot = (
        build_claim_evidence_snapshot(
            snapshot_input
        )
    )

    authority_adjudication = (
        build_authority_state_adjudication(
            evidence_snapshot=(
                snapshot
            )
        )
    )

    return {
        **base,
        "status": "assembled",
        "observation_id": (
            observation_id
        ),
        "snapshot_id": (
            snapshot_id
        ),
        "snapshot": snapshot,
        "authority_adjudication": (
            authority_adjudication
        ),
    }
