from typing import Any, Dict


CLAIM_CORROBORATION_POLICY_VERSION = (
    "claim-corroboration-v1"
)

CLAIM_CORROBORATION_STATUS_VOCABULARY = (
    "no_explicit_support",
    "evidence_only_support",
    "single_support_observation",
    "recorded_support_dependency_present",
    "support_source_diversity_not_established",
    "support_independence_unknown",
    "corroboration_established",
    "support_provenance_unknown",
)


def _claim_state_map(
    state: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    mapped = {}

    for raw_claim in state.get(
        "claims",
        [],
    ):
        if not isinstance(
            raw_claim,
            dict,
        ):
            continue

        claim_id = str(
            raw_claim.get("claim_id") or ""
        ).strip()

        if not claim_id:
            continue

        existing = mapped.get(
            claim_id
        )

        if (
            existing is not None
            and existing != raw_claim
        ):
            raise ValueError(
                "Corroboration analysis contains "
                "conflicting rows for claim "
                f"{claim_id}."
            )

        mapped[claim_id] = raw_claim

    return mapped


def _count_value(
    counts: Dict[str, Any],
    key: str,
) -> int:
    value = counts.get(
        key,
        0,
    )

    try:
        normalized = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        normalized,
        0,
    )


def build_claim_corroboration_assessment(
    *,
    support_state: Dict[str, Any],
    stance_state: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        support_state,
        dict,
    ):
        raise ValueError(
            "Claim corroboration support state "
            "must be a dictionary."
        )

    if not isinstance(
        stance_state,
        dict,
    ):
        raise ValueError(
            "Claim corroboration stance state "
            "must be a dictionary."
        )

    support_by_id = _claim_state_map(
        support_state
    )

    stance_by_id = _claim_state_map(
        stance_state
    )

    claim_ids = sorted(
        set(support_by_id)
        | set(stance_by_id)
    )

    results = []

    for claim_id in claim_ids:
        support = support_by_id.get(
            claim_id,
            {},
        )

        stance = stance_by_id.get(
            claim_id,
            {},
        )

        support_status = str(
            support.get("status") or ""
        ).strip().lower()

        stance_status = str(
            stance.get("status") or ""
        ).strip().lower()

        support_counts = support.get(
            "counts",
            {},
        )

        if not isinstance(
            support_counts,
            dict,
        ):
            support_counts = {}

        stance_counts = stance.get(
            "counts",
            {},
        )

        if not isinstance(
            stance_counts,
            dict,
        ):
            stance_counts = {}

        supporting_observation_count = (
            _count_value(
                support_counts,
                "supporting_observations",
            )
        )

        supporting_evidence_count = (
            _count_value(
                support_counts,
                "supporting_evidence",
            )
        )

        distinct_supporting_sources = (
            _count_value(
                support_counts,
                "distinct_supporting_sources",
            )
        )

        support_dependency_count = (
            _count_value(
                support_counts,
                "recorded_support_dependencies",
            )
        )

        contradiction_count = (
            _count_value(
                stance_counts,
                "contradiction_links",
            )
        )

        independent_support_established = bool(
            support.get(
                "independent_support_established",
                False,
            )
        )

        qualifies_for_corroboration = (
            independent_support_established
            and supporting_observation_count >= 2
            and distinct_supporting_sources >= 2
        )

        if qualifies_for_corroboration:
            status = (
                "corroboration_established"
            )

        elif support_status == (
            "no_explicit_support"
        ):
            status = (
                "no_explicit_support"
            )

        elif support_status == (
            "evidence_only_support"
        ):
            status = (
                "evidence_only_support"
            )

        elif support_status == (
            "single_support_observation"
        ):
            status = (
                "single_support_observation"
            )

        elif support_status == (
            "recorded_support_dependency_present"
        ):
            status = (
                "recorded_support_dependency_present"
            )

        elif support_status == (
            "support_source_diversity_not_established"
        ):
            status = (
                "support_source_diversity_not_established"
            )

        elif support_status == (
            "multi_source_support_independence_unknown"
        ):
            status = (
                "support_independence_unknown"
            )

        else:
            status = (
                "support_provenance_unknown"
            )

        contradiction_present = (
            contradiction_count > 0
        )

        recorded_dependency_ids = sorted(
            {
                str(
                    row.get("id") or ""
                ).strip()
                for row in support.get(
                    "recorded_support_dependencies",
                    [],
                )
                if (
                    isinstance(
                        row,
                        dict,
                    )
                    and str(
                        row.get("id") or ""
                    ).strip()
                )
            }
        )

        results.append(
            {
                "claim_id": claim_id,
                "canonical_key": str(
                    support.get(
                        "canonical_key"
                    )
                    or stance.get(
                        "canonical_key"
                    )
                    or ""
                ).strip(),
                "subject_key": str(
                    support.get(
                        "subject_key"
                    )
                    or stance.get(
                        "subject_key"
                    )
                    or ""
                ).strip(),
                "status": status,
                "corroboration_established": (
                    status
                    == "corroboration_established"
                ),
                "contested": (
                    contradiction_present
                ),
                "contradiction_present": (
                    contradiction_present
                ),
                "support_status": (
                    support_status
                ),
                "stance_status": (
                    stance_status
                ),
                "independent_support_established": (
                    independent_support_established
                ),
                "supporting_source_ids": sorted(
                    {
                        str(
                            value or ""
                        ).strip()
                        for value in support.get(
                            "supporting_source_ids",
                            [],
                        )
                        if str(
                            value or ""
                        ).strip()
                    }
                ),
                "recorded_support_dependency_ids": (
                    recorded_dependency_ids
                ),
                "counts": {
                    "supporting_observations": (
                        supporting_observation_count
                    ),
                    "supporting_evidence": (
                        supporting_evidence_count
                    ),
                    "distinct_supporting_sources": (
                        distinct_supporting_sources
                    ),
                    "recorded_support_dependencies": (
                        support_dependency_count
                    ),
                    "contradictions": (
                        contradiction_count
                    ),
                },
            }
        )

    return {
        "version": (
            CLAIM_CORROBORATION_POLICY_VERSION
        ),
        "status_vocabulary": list(
            CLAIM_CORROBORATION_STATUS_VOCABULARY
        ),
        "policy": {
            (
                "corroboration_requires_explicit_"
                "support"
            ): True,
            (
                "corroboration_requires_established_"
                "independent_support"
            ): True,
            (
                "source_diversity_alone_does_not_"
                "establish_corroboration"
            ): True,
            (
                "absence_of_dependency_does_not_"
                "establish_corroboration"
            ): True,
            (
                "evidence_only_support_does_not_"
                "establish_corroboration"
            ): True,
            (
                "contradiction_does_not_erase_"
                "recorded_support"
            ): True,
            (
                "corroboration_does_not_establish_"
                "truth"
            ): True,
        },
        "claims": results,
    }
