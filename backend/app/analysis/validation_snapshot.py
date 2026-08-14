from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
)

from urllib.parse import (
    urlsplit,
)


from app.analysis.authority import (
    build_claim_authority_assessment,
)


CLAIM_EVIDENCE_SNAPSHOT_VERSION = (
    "claim-evidence-snapshot-v1"
)

SNAPSHOT_REVIEW_STATUSES = (
    "draft",
    "approved",
    "rejected",
)

SNAPSHOT_INDEPENDENCE_STATUSES = (
    "established",
    "not_established",
    "unknown",
    "not_applicable",
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
    result = _clean(
        value
    ).lower()

    if result not in allowed:
        raise ValueError(
            f"{label} is unsupported."
        )

    return result


def _timestamp(
    value: Any,
    *,
    label: str,
    required: bool = True,
) -> str:
    text = _clean(
        value
    )

    if not text:
        if required:
            raise ValueError(
                f"{label} is required."
            )

        return ""

    candidate = text

    if candidate.endswith("Z"):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return (
        parsed
        .astimezone(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _timestamp_value(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def _source_url(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    parsed = urlsplit(
        text
    )

    if (
        parsed.scheme.lower()
        not in {
            "http",
            "https",
        }
        or not parsed.hostname
    ):
        raise ValueError(
            "Validation observation source_url "
            "must be an absolute HTTP(S) URL."
        )

    return text


def build_claim_evidence_snapshot(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        case,
        dict,
    ):
        raise ValueError(
            "Claim evidence snapshot "
            "must be a dictionary."
        )

    if (
        _clean(
            case.get(
                "version"
            )
        )
        != CLAIM_EVIDENCE_SNAPSHOT_VERSION
    ):
        raise ValueError(
            "Unsupported claim evidence "
            "snapshot version."
        )

    case_id = _clean(
        case.get("id")
    )

    claim_id = _clean(
        case.get("claim_id")
    )

    claim_text = _clean(
        case.get("claim_text")
    )

    if not case_id:
        raise ValueError(
            "Claim evidence snapshot ID "
            "is required."
        )

    if not claim_id:
        raise ValueError(
            "Claim evidence snapshot claim ID "
            "is required."
        )

    if not claim_text:
        raise ValueError(
            "Claim evidence snapshot claim text "
            "is required."
        )

    as_of = _timestamp(
        case.get("as_of"),
        label=(
            "Claim evidence snapshot as_of"
        ),
    )

    as_of_value = _timestamp_value(
        as_of
    )

    raw_observations = case.get(
        "observations",
        [],
    )

    if not isinstance(
        raw_observations,
        list,
    ):
        raise ValueError(
            "Claim evidence snapshot observations "
            "must be a list."
        )

    normalized = {}

    for raw in raw_observations:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Validation observation "
                "must be a dictionary."
            )

        observation_id = _clean(
            raw.get("id")
        )

        actor_id = _clean(
            raw.get("actor_id")
        )

        if not observation_id:
            raise ValueError(
                "Validation observation ID "
                "is required."
            )

        if not actor_id:
            raise ValueError(
                "Validation observation actor ID "
                "is required."
            )

        observed_at = _timestamp(
            raw.get(
                "observed_at"
            ),
            label=(
                "Validation observation "
                "observed_at"
            ),
        )

        published_at = _timestamp(
            raw.get(
                "published_at"
            ),
            label=(
                "Validation observation "
                "published_at"
            ),
            required=False,
        )

        if (
            _timestamp_value(
                observed_at
            )
            > as_of_value
        ):
            raise ValueError(
                "Validation observation occurs "
                "after the snapshot as_of time."
            )

        if (
            published_at
            and _timestamp_value(
                published_at
            )
            > as_of_value
        ):
            raise ValueError(
                "Validation observation publication "
                "occurs after the snapshot as_of time."
            )

        independence_status = _choice(
            raw.get(
                "independence_status",
                "unknown",
            ),
            label=(
                "Validation observation "
                "independence status"
            ),
            allowed=(
                SNAPSHOT_INDEPENDENCE_STATUSES
            ),
        )

        depends_on = raw.get(
            "depends_on_observation_ids",
            [],
        )

        if not isinstance(
            depends_on,
            list,
        ):
            raise ValueError(
                "Validation observation "
                "dependencies must be a list."
            )

        dependency_ids = sorted(
            {
                _clean(
                    value
                )
                for value in depends_on
                if _clean(
                    value
                )
            }
        )

        if (
            observation_id
            in dependency_ids
        ):
            raise ValueError(
                "Validation observation cannot "
                "depend on itself."
            )

        if (
            dependency_ids
            and independence_status
            == "established"
        ):
            raise ValueError(
                "An observation with recorded "
                "dependencies cannot be marked "
                "independence established."
            )

        normalized_row = {
            "id": observation_id,
            "actor_id": actor_id,
            "source_url": (
                _source_url(
                    raw.get(
                        "source_url"
                    )
                )
            ),
            "source_role": _clean(
                raw.get(
                    "source_role"
                )
            ).lower(),
            "authority_class": _clean(
                raw.get(
                    "authority_class"
                )
            ).lower(),
            "reliability_class": _clean(
                raw.get(
                    "reliability_class"
                )
            ).lower(),
            "provenance_class": _clean(
                raw.get(
                    "provenance_class"
                )
            ).lower(),
            "stance": _clean(
                raw.get(
                    "stance"
                )
            ).lower(),
            "independence_status": (
                independence_status
            ),
            "depends_on_observation_ids": (
                dependency_ids
            ),
            "published_at": (
                published_at
            ),
            "observed_at": (
                observed_at
            ),
        }

        existing = normalized.get(
            observation_id
        )

        if (
            existing is not None
            and existing != normalized_row
        ):
            raise ValueError(
                "Claim evidence snapshot "
                "contains conflicting duplicate "
                "observation IDs."
            )

        normalized[
            observation_id
        ] = normalized_row

    observation_ids = set(
        normalized
    )

    for row in normalized.values():
        missing_dependencies = sorted(
            set(
                row[
                    "depends_on_observation_ids"
                ]
            )
            - observation_ids
        )

        if missing_dependencies:
            raise ValueError(
                "Validation observation references "
                "an unknown dependency."
            )

    observations = sorted(
        normalized.values(),
        key=lambda row: (
            row["observed_at"],
            row["id"],
        ),
    )

    authority_rows = [
        {
            "id": row["id"],
            "claim_id": claim_id,
            "actor_id": row[
                "actor_id"
            ],
            "source_role": row[
                "source_role"
            ],
            "authority_class": row[
                "authority_class"
            ],
            "reliability_class": row[
                "reliability_class"
            ],
            "provenance_class": row[
                "provenance_class"
            ],
            "stance": row[
                "stance"
            ],
            "observed_at": row[
                "observed_at"
            ],
        }
        for row in observations
    ]

    authority_assessment = (
        build_claim_authority_assessment(
            claim_id=claim_id,
            observations=(
                authority_rows
            ),
        )
    )

    raw_review = case.get(
        "review",
        {},
    )

    if not isinstance(
        raw_review,
        dict,
    ):
        raise ValueError(
            "Claim evidence snapshot review "
            "must be a dictionary."
        )

    review_status = _choice(
        raw_review.get(
            "status",
            "draft",
        ),
        label=(
            "Claim evidence snapshot "
            "review status"
        ),
        allowed=(
            SNAPSHOT_REVIEW_STATUSES
        ),
    )

    reviewer = _clean(
        raw_review.get(
            "reviewer"
        )
    )

    rationale = _clean(
        raw_review.get(
            "rationale"
        )
    )

    reviewed_at = _timestamp(
        raw_review.get(
            "reviewed_at"
        ),
        label=(
            "Claim evidence snapshot "
            "reviewed_at"
        ),
        required=False,
    )

    if review_status == "approved":
        if not reviewer:
            raise ValueError(
                "Approved claim evidence "
                "snapshot requires a reviewer."
            )

        if not reviewed_at:
            raise ValueError(
                "Approved claim evidence "
                "snapshot requires reviewed_at."
            )

        if not rationale:
            raise ValueError(
                "Approved claim evidence "
                "snapshot requires a rationale."
            )

    outcome = case.get(
        "outcome",
        {},
    )

    if not isinstance(
        outcome,
        dict,
    ):
        raise ValueError(
            "Claim evidence snapshot outcome "
            "must be a dictionary."
        )

    return {
        "version": (
            CLAIM_EVIDENCE_SNAPSHOT_VERSION
        ),
        "id": case_id,
        "claim_id": claim_id,
        "claim_text": claim_text,
        "as_of": as_of,
        "observations": (
            observations
        ),
        "authority_assessment": (
            authority_assessment
        ),
        "review": {
            "status": (
                review_status
            ),
            "reviewer": (
                reviewer
            ),
            "reviewed_at": (
                reviewed_at
            ),
            "rationale": (
                rationale
            ),
        },
        "outcome": dict(
            outcome
        ),
        "policy": {
            "snapshot_is_time_bounded": True,
            "observations_after_as_of_are_rejected": True,
            "later_outcomes_do_not_relabel_historical_snapshot": True,
            "outcome_is_separate_from_evidence_state": True,
            "authority_reliability_and_provenance_are_separate": True,
            "stakeholder_confirmation_does_not_require_cross_source_corroboration": True,
            "institutional_confirmation_remains_distinct": True,
            "reporter_reliability_does_not_create_official_authority": True,
            "independence_does_not_create_authority": True,
            "recorded_dependencies_prevent_independence_established": True,
            "approved_snapshots_require_human_review": True,
            "snapshot_does_not_change_live_merit": True,
        },
    }
