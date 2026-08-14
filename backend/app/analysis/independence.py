from typing import Any, Dict


CLAIM_INDEPENDENCE_POLICY_VERSION = (
    "claim-independence-v1"
)

CLAIM_INDEPENDENCE_STATUS_VOCABULARY = (
    "insufficient_observations",
    "recorded_dependency_present",
    "source_diversity_not_established",
    "multi_source_independence_unknown",
)


def _normalized_unique_strings(
    values,
) -> list:
    return sorted(
        {
            str(value or "").strip()
            for value in values or []
            if str(value or "").strip()
        }
    )


def build_claim_independence_assessment(
    feature_state: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        feature_state,
        dict,
    ):
        raise ValueError(
            "Claim independence assessment "
            "requires a dictionary."
        )

    normalized_claims = {}

    for raw_claim in feature_state.get(
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

        observation_targets = set()

        for raw_target in raw_claim.get(
            "aligned_observations",
            [],
        ):
            if not isinstance(
                raw_target,
                dict,
            ):
                continue

            target_type = str(
                raw_target.get(
                    "target_type"
                ) or ""
            ).strip().lower()

            target_id = str(
                raw_target.get(
                    "target_id"
                ) or ""
            ).strip()

            if (
                target_type
                and target_id
            ):
                observation_targets.add(
                    (
                        target_type,
                        target_id,
                    )
                )

        source_ids = (
            _normalized_unique_strings(
                raw_claim.get(
                    "aligned_source_ids",
                    [],
                )
            )
        )

        reporter_ids = (
            _normalized_unique_strings(
                raw_claim.get(
                    "aligned_reporter_ids",
                    [],
                )
            )
        )

        dependencies = [
            row
            for row in raw_claim.get(
                "recorded_dependencies",
                [],
            )
            if isinstance(
                row,
                dict,
            )
        ]

        dependency_ids = (
            _normalized_unique_strings(
                [
                    row.get("id")
                    for row in dependencies
                ]
            )
        )

        observation_count = len(
            observation_targets
        )

        dependency_count = len(
            dependencies
        )

        if observation_count < 2:
            status = (
                "insufficient_observations"
            )

            reason = (
                "At least two observations "
                "aligned to the same canonical "
                "claim are required before "
                "reporting independence can be "
                "assessed."
            )

        elif dependency_count > 0:
            status = (
                "recorded_dependency_present"
            )

            reason = (
                "At least one aligned observation "
                "has a recorded upstream reporting "
                "dependency."
            )

        elif len(source_ids) < 2:
            status = (
                "source_diversity_not_established"
            )

            reason = (
                "The aligned observations do not "
                "establish multiple distinct "
                "reporting sources."
            )

        else:
            status = (
                "multi_source_independence_unknown"
            )

            reason = (
                "Multiple sources are aligned to "
                "the same canonical claim, but "
                "the absence of a recorded "
                "dependency does not establish "
                "independence."
            )

        normalized = {
            "claim_id": claim_id,
            "canonical_key": str(
                raw_claim.get(
                    "canonical_key"
                ) or ""
            ).strip(),
            "subject_key": str(
                raw_claim.get(
                    "subject_key"
                ) or ""
            ).strip(),
            "status": status,
            "independence_established": False,
            "corroboration_status": (
                "not_assessed"
            ),
            "reason": reason,
            "aligned_source_ids": (
                source_ids
            ),
            "aligned_reporter_ids": (
                reporter_ids
            ),
            "recorded_dependency_ids": (
                dependency_ids
            ),
            "counts": {
                "aligned_observations": (
                    observation_count
                ),
                "distinct_sources": len(
                    source_ids
                ),
                "distinct_reporters": len(
                    reporter_ids
                ),
                "recorded_dependencies": (
                    dependency_count
                ),
            },
        }

        existing = normalized_claims.get(
            claim_id
        )

        if (
            existing is not None
            and existing != normalized
        ):
            raise ValueError(
                "Claim independence assessment "
                "contains conflicting rows for "
                f"claim {claim_id}."
            )

        normalized_claims[
            claim_id
        ] = normalized

    return {
        "version": (
            CLAIM_INDEPENDENCE_POLICY_VERSION
        ),
        "status_vocabulary": list(
            CLAIM_INDEPENDENCE_STATUS_VOCABULARY
        ),
        "policy": {
            (
                "absence_of_dependency_does_not_"
                "imply_independence"
            ): True,
            (
                "distinct_sources_do_not_imply_"
                "independence"
            ): True,
            (
                "claim_alignment_does_not_imply_"
                "corroboration"
            ): True,
            (
                "corroboration_requires_explicit_"
                "support_semantics"
            ): True,
        },
        "claims": [
            normalized_claims[
                claim_id
            ]
            for claim_id in sorted(
                normalized_claims
            )
        ],
    }
