from typing import Any, Dict, List


CLAIM_AUTHORITY_POLICY_VERSION = (
    "claim-authority-v1"
)

CLAIM_SOURCE_ROLES = (
    "primary_stakeholder",
    "official_institution",
    "privileged_reporter",
    "publisher",
    "aggregator",
    "unknown",
)

CLAIM_AUTHORITY_CLASSES = (
    "direct",
    "institutional",
    "none",
    "unknown",
)

CLAIM_RELIABILITY_CLASSES = (
    "elite_specialist",
    "established",
    "unrated",
    "unknown",
    "not_applicable",
)

CLAIM_PROVENANCE_CLASSES = (
    "direct_statement",
    "direct_official_reporting",
    "firsthand_reporting",
    "attributed_reporting",
    "aggregation",
    "unknown",
)

CLAIM_AUTHORITY_STANCES = (
    "supports",
    "contradicts",
    "neutral",
)

CLAIM_CONFIRMATION_STATES = (
    "unconfirmed",
    "reported_unconfirmed",
    "institutionally_confirmed",
    "institutionally_contradicted",
    "institutionally_contested",
    "stakeholder_confirmed",
    "stakeholder_contradicted",
    "stakeholder_contested",
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _choice(
    value: Any,
    *,
    label: str,
    allowed,
) -> str:
    normalized = _clean(
        value
    ).lower()

    if normalized not in allowed:
        raise ValueError(
            f"{label} is unsupported."
        )

    return normalized


def _normalize_observation(
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            "Claim authority observation "
            "must be a dictionary."
        )

    observation_id = _clean(
        raw.get("id")
    )

    claim_id = _clean(
        raw.get("claim_id")
    )

    actor_id = _clean(
        raw.get("actor_id")
    )

    if not observation_id:
        raise ValueError(
            "Claim authority observation "
            "ID is required."
        )

    if not claim_id:
        raise ValueError(
            "Claim authority observation "
            "claim ID is required."
        )

    if not actor_id:
        raise ValueError(
            "Claim authority observation "
            "actor ID is required."
        )

    source_role = _choice(
        raw.get(
            "source_role",
            "unknown",
        ),
        label="Claim source role",
        allowed=CLAIM_SOURCE_ROLES,
    )

    authority_class = _choice(
        raw.get(
            "authority_class",
            "unknown",
        ),
        label="Claim authority class",
        allowed=CLAIM_AUTHORITY_CLASSES,
    )

    reliability_class = _choice(
        raw.get(
            "reliability_class",
            "unknown",
        ),
        label="Claim reliability class",
        allowed=CLAIM_RELIABILITY_CLASSES,
    )

    provenance_class = _choice(
        raw.get(
            "provenance_class",
            "unknown",
        ),
        label="Claim provenance class",
        allowed=CLAIM_PROVENANCE_CLASSES,
    )

    stance = _choice(
        raw.get(
            "stance",
            "neutral",
        ),
        label="Claim authority stance",
        allowed=CLAIM_AUTHORITY_STANCES,
    )

    observed_at = _clean(
        raw.get("observed_at")
    )

    if (
        source_role
        == "primary_stakeholder"
        and authority_class
        != "direct"
    ):
        raise ValueError(
            "Primary stakeholder observations "
            "require direct authority."
        )

    if (
        source_role
        == "official_institution"
        and authority_class
        != "institutional"
    ):
        raise ValueError(
            "Official institution observations "
            "require institutional authority."
        )

    if (
        source_role
        in {
            "privileged_reporter",
            "publisher",
            "aggregator",
        }
        and authority_class
        not in {
            "none",
            "unknown",
        }
    ):
        raise ValueError(
            "Reporter and publisher roles "
            "cannot claim stakeholder or "
            "institutional authority."
        )

    return {
        "id": observation_id,
        "claim_id": claim_id,
        "actor_id": actor_id,
        "source_role": source_role,
        "authority_class": authority_class,
        "reliability_class": reliability_class,
        "provenance_class": provenance_class,
        "stance": stance,
        "observed_at": observed_at,
    }


def build_claim_authority_assessment(
    *,
    claim_id: str,
    observations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Claim authority assessment "
            "requires a claim ID."
        )

    if not isinstance(
        observations,
        list,
    ):
        raise ValueError(
            "Claim authority observations "
            "must be a list."
        )

    normalized = {}

    for raw in observations:
        row = _normalize_observation(
            raw
        )

        if (
            row["claim_id"]
            != normalized_claim_id
        ):
            raise ValueError(
                "Claim authority assessment "
                "cannot mix different claims."
            )

        existing = normalized.get(
            row["id"]
        )

        if (
            existing is not None
            and existing != row
        ):
            raise ValueError(
                "Claim authority assessment "
                "contains conflicting duplicate "
                "observation IDs."
            )

        normalized[
            row["id"]
        ] = row

    rows = sorted(
        normalized.values(),
        key=lambda row: (
            row["observed_at"],
            row["id"],
        ),
    )

    stakeholder_support = [
        row
        for row in rows
        if (
            row["source_role"]
            == "primary_stakeholder"
            and row["authority_class"]
            == "direct"
            and row["provenance_class"]
            == "direct_statement"
            and row["stance"]
            == "supports"
        )
    ]

    stakeholder_contradictions = [
        row
        for row in rows
        if (
            row["source_role"]
            == "primary_stakeholder"
            and row["authority_class"]
            == "direct"
            and row["provenance_class"]
            == "direct_statement"
            and row["stance"]
            == "contradicts"
        )
    ]

    institution_support = [
        row
        for row in rows
        if (
            row["source_role"]
            == "official_institution"
            and row["authority_class"]
            == "institutional"
            and row["provenance_class"]
            in {
                "direct_statement",
                "direct_official_reporting",
            }
            and row["stance"]
            == "supports"
        )
    ]

    institution_contradictions = [
        row
        for row in rows
        if (
            row["source_role"]
            == "official_institution"
            and row["authority_class"]
            == "institutional"
            and row["provenance_class"]
            in {
                "direct_statement",
                "direct_official_reporting",
            }
            and row["stance"]
            == "contradicts"
        )
    ]

    reporting_support = [
        row
        for row in rows
        if (
            row["source_role"]
            in {
                "privileged_reporter",
                "publisher",
                "aggregator",
            }
            and row["stance"]
            == "supports"
        )
    ]

    reporting_contradictions = [
        row
        for row in rows
        if (
            row["source_role"]
            in {
                "privileged_reporter",
                "publisher",
                "aggregator",
            }
            and row["stance"]
            == "contradicts"
        )
    ]

    if (
        stakeholder_support
        and stakeholder_contradictions
    ):
        confirmation_state = (
            "stakeholder_contested"
        )

    elif stakeholder_support:
        confirmation_state = (
            "stakeholder_confirmed"
        )

    elif stakeholder_contradictions:
        confirmation_state = (
            "stakeholder_contradicted"
        )

    elif (
        institution_support
        and institution_contradictions
    ):
        confirmation_state = (
            "institutionally_contested"
        )

    elif institution_support:
        confirmation_state = (
            "institutionally_confirmed"
        )

    elif institution_contradictions:
        confirmation_state = (
            "institutionally_contradicted"
        )

    elif (
        reporting_support
        or reporting_contradictions
    ):
        confirmation_state = (
            "reported_unconfirmed"
        )

    else:
        confirmation_state = (
            "unconfirmed"
        )

    return {
        "version": (
            CLAIM_AUTHORITY_POLICY_VERSION
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "confirmation_state": (
            confirmation_state
        ),
        "stakeholder_confirmation_established": (
            bool(
                stakeholder_support
            )
        ),
        "institutional_confirmation_established": (
            bool(
                institution_support
            )
        ),
        "contradiction_present": any(
            row["stance"]
            == "contradicts"
            for row in rows
        ),
        "counts": {
            "observations": len(
                rows
            ),
            "stakeholder_support": len(
                stakeholder_support
            ),
            "stakeholder_contradictions": len(
                stakeholder_contradictions
            ),
            "institution_support": len(
                institution_support
            ),
            "institution_contradictions": len(
                institution_contradictions
            ),
            "reporting_support": len(
                reporting_support
            ),
            "reporting_contradictions": len(
                reporting_contradictions
            ),
        },
        "observations": rows,
        "policy": {
            "primary_stakeholder_direct_statement_can_confirm_claim": True,
            "stakeholder_confirmation_does_not_require_cross_source_corroboration": True,
            "institutional_confirmation_is_distinct_from_stakeholder_confirmation": True,
            "reporter_reliability_does_not_create_official_authority": True,
            "multiple_reporters_do_not_become_primary_stakeholders": True,
            "authority_and_reliability_are_separate_dimensions": True,
            "authority_and_provenance_are_separate_dimensions": True,
            "contradicting_stakeholder_statements_are_preserved": True,
            "authority_assessment_does_not_establish_permanent_truth": True,
            "authority_assessment_does_not_change_live_merit": True,
        },
    }
