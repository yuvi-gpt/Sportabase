from typing import Any, Dict

from app.analysis.stance import (
    build_claim_stance_analysis,
)


CLAIM_SUPPORT_PROVENANCE_VERSION = (
    "claim-support-provenance-v2"
)

CLAIM_SUPPORT_PROVENANCE_STATUS_VOCABULARY = (
    "no_explicit_support",
    "evidence_only_support",
    "single_support_observation",
    "recorded_support_dependency_present",
    "support_source_diversity_not_established",
    "multi_source_support_independence_unknown",
    "verified_independent_support",
)


def _dependency_upstream_matches_observation(
    dependency: Dict[str, Any],
    observation_target,
    observation_actors: Dict[Any, Any],
) -> bool:
    target_type, target_id = (
        observation_target
    )

    upstream_type = str(
        dependency.get(
            "upstream_type"
        ) or ""
    ).strip().lower()

    upstream_id = str(
        dependency.get(
            "upstream_id"
        ) or ""
    ).strip()

    if not upstream_type or not upstream_id:
        return False

    if upstream_type in (
        "source_observation",
        "reporter_observation",
    ):
        return (
            upstream_type,
            upstream_id,
        ) == (
            target_type,
            target_id,
        )

    actor = observation_actors.get(
        observation_target,
        {},
    )

    if upstream_type == "source":
        source_id = str(
            actor.get(
                "source_id"
            ) or ""
        ).strip()

        return bool(
            source_id
            and source_id == upstream_id
        )

    if upstream_type == "reporter":
        reporter_id = str(
            actor.get(
                "reporter_id"
            ) or ""
        ).strip()

        return bool(
            reporter_id
            and reporter_id == upstream_id
        )

    return False


def _dependency_conflicts_with_pair(
    dependency: Dict[str, Any],
    first_target,
    second_target,
    observation_actors: Dict[Any, Any],
) -> bool:
    downstream = (
        str(
            dependency.get(
                "downstream_type"
            ) or ""
        ).strip().lower(),
        str(
            dependency.get(
                "downstream_id"
            ) or ""
        ).strip(),
    )

    if (
        downstream == first_target
        and _dependency_upstream_matches_observation(
            dependency,
            second_target,
            observation_actors,
        )
    ):
        return True

    if (
        downstream == second_target
        and _dependency_upstream_matches_observation(
            dependency,
            first_target,
            observation_actors,
        )
    ):
        return True

    return False


def build_claim_support_provenance(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        bundle,
        dict,
    ):
        raise ValueError(
            "Claim support provenance requires "
            "a dictionary."
        )

    stance_state = (
        build_claim_stance_analysis(
            bundle
        )
    )

    observation_actors = {}

    for row in bundle.get(
        "source_observations",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        observation_id = str(
            row.get("id") or ""
        ).strip()

        if not observation_id:
            continue

        observation_actors[
            (
                "source_observation",
                observation_id,
            )
        ] = {
            "source_id": str(
                row.get(
                    "source_id"
                ) or ""
            ).strip(),
            "reporter_id": "",
        }

    for row in bundle.get(
        "reporter_observations",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        observation_id = str(
            row.get("id") or ""
        ).strip()

        if not observation_id:
            continue

        observation_actors[
            (
                "reporter_observation",
                observation_id,
            )
        ] = {
            "source_id": str(
                row.get(
                    "source_id"
                ) or ""
            ).strip(),
            "reporter_id": str(
                row.get(
                    "reporter_id"
                ) or ""
            ).strip(),
        }

    dependencies = []

    for row in bundle.get(
        "observation_dependencies",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        downstream_type = str(
            row.get(
                "downstream_type"
            ) or ""
        ).strip().lower()

        downstream_id = str(
            row.get(
                "downstream_id"
            ) or ""
        ).strip()

        upstream_type = str(
            row.get(
                "upstream_type"
            ) or ""
        ).strip().lower()

        upstream_id = str(
            row.get(
                "upstream_id"
            ) or ""
        ).strip()

        if (
            not downstream_type
            or not downstream_id
            or not upstream_type
            or not upstream_id
        ):
            continue

        dependencies.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "downstream_type": (
                    downstream_type
                ),
                "downstream_id": (
                    downstream_id
                ),
                "upstream_type": (
                    upstream_type
                ),
                "upstream_id": (
                    upstream_id
                ),
                "relationship_type": str(
                    row.get(
                        "relationship_type"
                    ) or ""
                ).strip().lower(),
                "confidence": (
                    row.get("confidence")
                ),
                "observed_at": str(
                    row.get(
                        "observed_at"
                    ) or ""
                ).strip(),
            }
        )

    independence_assertions = []

    for row in bundle.get(
        "observation_independence_assertions",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        observation_a_type = str(
            row.get(
                "observation_a_type"
            ) or ""
        ).strip().lower()

        observation_a_id = str(
            row.get(
                "observation_a_id"
            ) or ""
        ).strip()

        observation_b_type = str(
            row.get(
                "observation_b_type"
            ) or ""
        ).strip().lower()

        observation_b_id = str(
            row.get(
                "observation_b_id"
            ) or ""
        ).strip()

        provenance_evidence_id = str(
            row.get(
                "provenance_evidence_id"
            ) or ""
        ).strip()

        verification_status = str(
            row.get(
                "verification_status"
            ) or ""
        ).strip().lower()

        if (
            observation_a_type
            not in (
                "source_observation",
                "reporter_observation",
            )
            or not observation_a_id
            or observation_b_type
            not in (
                "source_observation",
                "reporter_observation",
            )
            or not observation_b_id
            or not provenance_evidence_id
        ):
            continue

        first_target, second_target = sorted(
            (
                (
                    observation_a_type,
                    observation_a_id,
                ),
                (
                    observation_b_type,
                    observation_b_id,
                ),
            )
        )

        independence_assertions.append(
            {
                "id": str(
                    row.get("id") or ""
                ).strip(),
                "observation_a_type": (
                    first_target[0]
                ),
                "observation_a_id": (
                    first_target[1]
                ),
                "observation_b_type": (
                    second_target[0]
                ),
                "observation_b_id": (
                    second_target[1]
                ),
                "provenance_evidence_id": (
                    provenance_evidence_id
                ),
                "verification_status": (
                    verification_status
                ),
                "confidence": (
                    row.get("confidence")
                ),
                "observed_at": str(
                    row.get(
                        "observed_at"
                    ) or ""
                ).strip(),
            }
        )

    independence_assertions.sort(
        key=lambda row: (
            row["observation_a_type"],
            row["observation_a_id"],
            row["observation_b_type"],
            row["observation_b_id"],
            row["verification_status"],
            row["provenance_evidence_id"],
            row["observed_at"],
            str(row["confidence"]),
            row["id"],
        )
    )

    claim_states = []

    for stance_claim in stance_state.get(
        "claims",
        [],
    ):
        claim_id = str(
            stance_claim.get(
                "claim_id"
            ) or ""
        ).strip()

        if not claim_id:
            continue

        supporting_observations = set()
        supporting_evidence_ids = set()

        for link in stance_claim.get(
            "support_links",
            [],
        ):
            if not isinstance(
                link,
                dict,
            ):
                continue

            target_type = str(
                link.get(
                    "target_type"
                ) or ""
            ).strip().lower()

            target_id = str(
                link.get(
                    "target_id"
                ) or ""
            ).strip()

            if (
                target_type
                in (
                    "source_observation",
                    "reporter_observation",
                )
                and target_id
            ):
                supporting_observations.add(
                    (
                        target_type,
                        target_id,
                    )
                )

            elif (
                target_type == "evidence"
                and target_id
            ):
                supporting_evidence_ids.add(
                    target_id
                )

        supporting_source_ids = set()
        supporting_reporter_ids = set()

        for observation_target in (
            supporting_observations
        ):
            actor = observation_actors.get(
                observation_target,
                {},
            )

            source_id = str(
                actor.get(
                    "source_id"
                ) or ""
            ).strip()

            reporter_id = str(
                actor.get(
                    "reporter_id"
                ) or ""
            ).strip()

            if source_id:
                supporting_source_ids.add(
                    source_id
                )

            if reporter_id:
                supporting_reporter_ids.add(
                    reporter_id
                )

        support_dependencies = [
            dependency
            for dependency in dependencies
            if (
                (
                    dependency[
                        "downstream_type"
                    ],
                    dependency[
                        "downstream_id"
                    ],
                )
                in supporting_observations
            )
        ]

        support_dependencies.sort(
            key=lambda row: (
                row["downstream_type"],
                row["downstream_id"],
                row["upstream_type"],
                row["upstream_id"],
                row["relationship_type"],
                row["observed_at"],
                str(row["confidence"]),
                row["id"],
            )
        )

        supporter_to_supporter_dependencies = []

        for dependency in (
            support_dependencies
        ):
            upstream_type = (
                dependency[
                    "upstream_type"
                ]
            )

            upstream_id = (
                dependency[
                    "upstream_id"
                ]
            )

            points_to_supporter = False

            if (
                upstream_type
                in (
                    "source_observation",
                    "reporter_observation",
                )
                and (
                    upstream_type,
                    upstream_id,
                )
                in supporting_observations
            ):
                points_to_supporter = True

            elif (
                upstream_type == "source"
                and upstream_id
                in supporting_source_ids
            ):
                points_to_supporter = True

            elif (
                upstream_type == "reporter"
                and upstream_id
                in supporting_reporter_ids
            ):
                points_to_supporter = True

            if points_to_supporter:
                supporter_to_supporter_dependencies.append(
                    dependency
                )

        claim_independence_assertions = []
        qualifying_independence_assertions = []
        blocked_independence_assertions = []

        for assertion in independence_assertions:
            first_target = (
                assertion[
                    "observation_a_type"
                ],
                assertion[
                    "observation_a_id"
                ],
            )

            second_target = (
                assertion[
                    "observation_b_type"
                ],
                assertion[
                    "observation_b_id"
                ],
            )

            if (
                first_target
                not in supporting_observations
                or second_target
                not in supporting_observations
            ):
                continue

            first_actor = (
                observation_actors.get(
                    first_target,
                    {},
                )
            )

            second_actor = (
                observation_actors.get(
                    second_target,
                    {},
                )
            )

            first_source_id = str(
                first_actor.get(
                    "source_id"
                ) or ""
            ).strip()

            second_source_id = str(
                second_actor.get(
                    "source_id"
                ) or ""
            ).strip()

            dependency_conflicts = [
                dependency
                for dependency in support_dependencies
                if _dependency_conflicts_with_pair(
                    dependency,
                    first_target,
                    second_target,
                    observation_actors,
                )
            ]

            dependency_conflict_ids = sorted(
                {
                    str(
                        dependency.get(
                            "id"
                        ) or ""
                    ).strip()
                    for dependency
                    in dependency_conflicts
                    if str(
                        dependency.get(
                            "id"
                        ) or ""
                    ).strip()
                }
            )

            block_reasons = []

            if (
                assertion[
                    "verification_status"
                ]
                != "verified"
            ):
                block_reasons.append(
                    "assertion_not_verified"
                )

            if (
                not first_source_id
                or not second_source_id
            ):
                block_reasons.append(
                    "source_identity_unresolved"
                )

            elif (
                first_source_id
                == second_source_id
            ):
                block_reasons.append(
                    "same_source"
                )

            if dependency_conflicts:
                block_reasons.append(
                    "recorded_dependency_conflict"
                )

            evaluated = {
                **assertion,
                "supporting_source_ids": sorted(
                    {
                        first_source_id,
                        second_source_id,
                    }
                    - {""}
                ),
                "dependency_conflict_ids": (
                    dependency_conflict_ids
                ),
                "block_reasons": (
                    sorted(
                        set(
                            block_reasons
                        )
                    )
                ),
            }

            claim_independence_assertions.append(
                evaluated
            )

            if block_reasons:
                blocked_independence_assertions.append(
                    evaluated
                )
            else:
                qualifying_independence_assertions.append(
                    evaluated
                )

        independent_support_established = bool(
            qualifying_independence_assertions
        )

        observation_count = len(
            supporting_observations
        )

        evidence_count = len(
            supporting_evidence_ids
        )

        if (
            observation_count == 0
            and evidence_count == 0
        ):
            status = (
                "no_explicit_support"
            )

        elif observation_count == 0:
            status = (
                "evidence_only_support"
            )

        elif observation_count == 1:
            status = (
                "single_support_observation"
            )

        elif independent_support_established:
            status = (
                "verified_independent_support"
            )

        elif support_dependencies:
            status = (
                "recorded_support_dependency_present"
            )

        elif (
            len(
                supporting_source_ids
            )
            < 2
        ):
            status = (
                "support_source_diversity_not_established"
            )

        else:
            status = (
                "multi_source_support_independence_unknown"
            )

        claim_states.append(
            {
                "claim_id": claim_id,
                "canonical_key": str(
                    stance_claim.get(
                        "canonical_key"
                    ) or ""
                ).strip(),
                "subject_key": str(
                    stance_claim.get(
                        "subject_key"
                    ) or ""
                ).strip(),
                "status": status,
                "independent_support_established": (
                    independent_support_established
                ),
                "corroboration_status": (
                    "not_assessed"
                ),
                "supporting_observations": [
                    {
                        "target_type": (
                            target_type
                        ),
                        "target_id": target_id,
                    }
                    for (
                        target_type,
                        target_id,
                    ) in sorted(
                        supporting_observations
                    )
                ],
                "supporting_evidence_ids": (
                    sorted(
                        supporting_evidence_ids
                    )
                ),
                "supporting_source_ids": (
                    sorted(
                        supporting_source_ids
                    )
                ),
                "supporting_reporter_ids": (
                    sorted(
                        supporting_reporter_ids
                    )
                ),
                "recorded_support_dependencies": (
                    support_dependencies
                ),
                (
                    "supporter_to_supporter_"
                    "dependencies"
                ): (
                    supporter_to_supporter_dependencies
                ),
                "support_independence_assertions": (
                    claim_independence_assertions
                ),
                "qualifying_independence_assertions": (
                    qualifying_independence_assertions
                ),
                "blocked_independence_assertions": (
                    blocked_independence_assertions
                ),
                "counts": {
                    "supporting_observations": (
                        observation_count
                    ),
                    "supporting_evidence": (
                        evidence_count
                    ),
                    "distinct_supporting_sources": len(
                        supporting_source_ids
                    ),
                    "distinct_supporting_reporters": len(
                        supporting_reporter_ids
                    ),
                    "recorded_support_dependencies": len(
                        support_dependencies
                    ),
                    (
                        "supporter_to_supporter_"
                        "dependencies"
                    ): len(
                        supporter_to_supporter_dependencies
                    ),
                    (
                        "support_independence_"
                        "assertions"
                    ): len(
                        claim_independence_assertions
                    ),
                    (
                        "qualifying_independence_"
                        "assertions"
                    ): len(
                        qualifying_independence_assertions
                    ),
                    (
                        "blocked_independence_"
                        "assertions"
                    ): len(
                        blocked_independence_assertions
                    ),
                },
            }
        )

    claim_states.sort(
        key=lambda row: row["claim_id"]
    )

    return {
        "version": (
            CLAIM_SUPPORT_PROVENANCE_VERSION
        ),
        "status_vocabulary": list(
            CLAIM_SUPPORT_PROVENANCE_STATUS_VOCABULARY
        ),
        "policy": {
            (
                "only_explicit_support_edges_"
                "count_as_support"
            ): True,
            (
                "claim_wide_dependencies_do_not_"
                "automatically_apply_to_support"
            ): True,
            (
                "absence_of_support_dependency_"
                "does_not_imply_independence"
            ): True,
            (
                "multiple_supporting_sources_do_"
                "not_imply_independence"
            ): True,
            (
                "verified_pair_assertion_requires_"
                "distinct_supporting_sources"
            ): True,
            (
                "direct_dependency_conflict_blocks_"
                "verified_independent_pair"
            ): True,
            (
                "unrelated_support_dependency_does_"
                "not_erase_verified_independent_pair"
            ): True,
            (
                "independence_confidence_is_recorded_"
                "but_not_thresholded"
            ): True,
            (
                "support_provenance_does_not_"
                "establish_corroboration"
            ): True,
        },
        "claims": claim_states,
    }
