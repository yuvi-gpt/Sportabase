from typing import Any, Dict


EVIDENCE_SIGNAL_POLICY_VERSION = (
    "evidence-signals-v1"
)

EVIDENCE_FEATURE_VERSION = (
    "evidence-features-v1"
)

EVIDENCE_ACTOR_FEATURE_VERSION = (
    "evidence-actors-v1"
)

OBSERVATION_DEPENDENCY_POLICY_VERSION = (
    "dependency-relationships-v1"
)

OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY = (
    "attributed_to",
    "derived_from",
)

EVIDENCE_SIGNAL_VOCABULARY = {
    "story_relationship_types": (
        "confirms",
        "reports",
    ),
    "observation_types": (
        "report",
    ),
    "observation_statuses": (
        "confirmed",
        "unresolved",
    ),
    "evidence_types": (
        "independent_report",
        "official_statement",
        "primary_document",
        "quote",
    ),
    "verification_statuses": (
        "unverified",
        "verified",
    ),
    "evidence_relationship_types": (
        "contradicts",
        "published_by",
        "supports",
    ),
}


def inspect_observation_dependency_vocabulary(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Observation dependency vocabulary "
            "inspection requires a dictionary."
        )

    observed = set()

    for row in bundle.get(
        "observation_dependencies",
        [],
    ):
        if not isinstance(row, dict):
            continue

        relationship_type = str(
            row.get(
                "relationship_type",
                "",
            )
            or ""
        ).strip().lower()

        if relationship_type:
            observed.add(
                relationship_type
            )

    allowed = set(
        OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY
    )

    return {
        "version": (
            OBSERVATION_DEPENDENCY_POLICY_VERSION
        ),
        "recognized": sorted(
            observed & allowed
        ),
        "unknown": sorted(
            observed - allowed
        ),
    }


def inspect_evidence_signal_vocabulary(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Evidence signal vocabulary "
            "inspection requires a dictionary."
        )

    observed = {
        "story_relationship_types": set(),
        "observation_types": set(),
        "observation_statuses": set(),
        "evidence_types": set(),
        "verification_statuses": set(),
        "evidence_relationship_types": set(),
    }

    for row in bundle.get(
        "story_links",
        [],
    ):
        if isinstance(row, dict):
            value = str(
                row.get(
                    "relationship_type",
                    "",
                )
                or ""
            ).strip().lower()

            if value:
                observed[
                    "story_relationship_types"
                ].add(value)

    for collection_name in (
        "source_observations",
        "reporter_observations",
    ):
        for row in bundle.get(
            collection_name,
            [],
        ):
            if not isinstance(row, dict):
                continue

            observation_type = str(
                row.get(
                    "observation_type",
                    "",
                )
                or ""
            ).strip().lower()

            status = str(
                row.get(
                    "status",
                    "",
                )
                or ""
            ).strip().lower()

            if observation_type:
                observed[
                    "observation_types"
                ].add(
                    observation_type
                )

            if status:
                observed[
                    "observation_statuses"
                ].add(status)

    for row in bundle.get(
        "evidence_records",
        [],
    ):
        if not isinstance(row, dict):
            continue

        evidence_type = str(
            row.get(
                "evidence_type",
                "",
            )
            or ""
        ).strip().lower()

        verification_status = str(
            row.get(
                "verification_status",
                "",
            )
            or ""
        ).strip().lower()

        if evidence_type:
            observed[
                "evidence_types"
            ].add(evidence_type)

        if verification_status:
            observed[
                "verification_statuses"
            ].add(
                verification_status
            )

    for row in bundle.get(
        "evidence_links",
        [],
    ):
        if not isinstance(row, dict):
            continue

        relationship_type = str(
            row.get(
                "relationship_type",
                "",
            )
            or ""
        ).strip().lower()

        if relationship_type:
            observed[
                "evidence_relationship_types"
            ].add(
                relationship_type
            )

    recognized = {}
    unknown = {}

    for category in sorted(
        EVIDENCE_SIGNAL_VOCABULARY
    ):
        allowed = set(
            EVIDENCE_SIGNAL_VOCABULARY[
                category
            ]
        )

        values = observed[category]

        recognized[category] = sorted(
            values & allowed
        )

        unknown[category] = sorted(
            values - allowed
        )

    return {
        "version": (
            EVIDENCE_SIGNAL_POLICY_VERSION
        ),
        "recognized": recognized,
        "unknown": unknown,
    }


def build_evidence_signal_features(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Evidence signal features require "
            "a dictionary."
        )

    vocabulary_report = (
        inspect_evidence_signal_vocabulary(
            bundle
        )
    )

    counts = {
        category: {
            value: 0
            for value in (
                EVIDENCE_SIGNAL_VOCABULARY[
                    category
                ]
            )
        }
        for category in sorted(
            EVIDENCE_SIGNAL_VOCABULARY
        )
    }

    def increment(
        category: str,
        value: Any,
    ) -> None:
        normalized_value = str(
            value or ""
        ).strip().lower()

        if (
            normalized_value
            in counts[category]
        ):
            counts[
                category
            ][
                normalized_value
            ] += 1

    for row in bundle.get(
        "story_links",
        [],
    ):
        if not isinstance(row, dict):
            continue

        increment(
            "story_relationship_types",
            row.get(
                "relationship_type"
            ),
        )

    for collection_name in (
        "source_observations",
        "reporter_observations",
    ):
        for row in bundle.get(
            collection_name,
            [],
        ):
            if not isinstance(row, dict):
                continue

            increment(
                "observation_types",
                row.get(
                    "observation_type"
                ),
            )

            increment(
                "observation_statuses",
                row.get(
                    "status"
                ),
            )

    for row in bundle.get(
        "evidence_records",
        [],
    ):
        if not isinstance(row, dict):
            continue

        increment(
            "evidence_types",
            row.get(
                "evidence_type"
            ),
        )

        increment(
            "verification_statuses",
            row.get(
                "verification_status"
            ),
        )

    for row in bundle.get(
        "evidence_links",
        [],
    ):
        if not isinstance(row, dict):
            continue

        increment(
            "evidence_relationship_types",
            row.get(
                "relationship_type"
            ),
        )

    return {
        "version": (
            EVIDENCE_FEATURE_VERSION
        ),
        "policy_version": (
            EVIDENCE_SIGNAL_POLICY_VERSION
        ),
        "counts": counts,
        "unknown": (
            vocabulary_report[
                "unknown"
            ]
        ),
    }


def build_evidence_actor_features(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Evidence actor features require "
            "a dictionary."
        )

    observation_source_ids = set()
    reporter_ids = set()
    subject_keys = set()

    for row in bundle.get(
        "source_observations",
        [],
    ):
        if not isinstance(row, dict):
            continue

        source_id = str(
            row.get("source_id") or ""
        ).strip()

        subject_key = str(
            row.get("subject_key") or ""
        ).strip()

        if source_id:
            observation_source_ids.add(
                source_id
            )

        if subject_key:
            subject_keys.add(
                subject_key
            )

    for row in bundle.get(
        "reporter_observations",
        [],
    ):
        if not isinstance(row, dict):
            continue

        source_id = str(
            row.get("source_id") or ""
        ).strip()

        reporter_id = str(
            row.get("reporter_id") or ""
        ).strip()

        subject_key = str(
            row.get("subject_key") or ""
        ).strip()

        if source_id:
            observation_source_ids.add(
                source_id
            )

        if reporter_id:
            reporter_ids.add(
                reporter_id
            )

        if subject_key:
            subject_keys.add(
                subject_key
            )

    for row in bundle.get(
        "evidence_records",
        [],
    ):
        if not isinstance(row, dict):
            continue

        subject_key = str(
            row.get("subject_key") or ""
        ).strip()

        if subject_key:
            subject_keys.add(
                subject_key
            )

    normalized_sources = sorted(
        observation_source_ids
    )

    normalized_reporters = sorted(
        reporter_ids
    )

    normalized_subjects = sorted(
        subject_keys
    )

    return {
        "version": (
            EVIDENCE_ACTOR_FEATURE_VERSION
        ),
        "distinct": {
            "observation_source_ids": (
                normalized_sources
            ),
            "reporter_ids": (
                normalized_reporters
            ),
            "subject_keys": (
                normalized_subjects
            ),
        },
        "counts": {
            "observation_sources": len(
                normalized_sources
            ),
            "reporters": len(
                normalized_reporters
            ),
            "subjects": len(
                normalized_subjects
            ),
        },
    }

CLAIM_DEPENDENCY_FEATURE_VERSION = (
    "claim-dependency-features-v1"
)


def build_claim_dependency_features(
    bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise ValueError(
            "Claim dependency features require "
            "a dictionary."
        )

    observation_actors = {}

    for row in bundle.get(
        "source_observations",
        [],
    ):
        if not isinstance(row, dict):
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
                row.get("source_id") or ""
            ).strip(),
            "reporter_id": "",
        }

    for row in bundle.get(
        "reporter_observations",
        [],
    ):
        if not isinstance(row, dict):
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
                row.get("source_id") or ""
            ).strip(),
            "reporter_id": str(
                row.get("reporter_id") or ""
            ).strip(),
        }

    claims_by_id = {}

    for row in bundle.get(
        "claims",
        [],
    ):
        if not isinstance(row, dict):
            continue

        claim_id = str(
            row.get("id") or ""
        ).strip()

        if not claim_id:
            continue

        claims_by_id[claim_id] = {
            "canonical_key": str(
                row.get("canonical_key") or ""
            ).strip(),
            "subject_key": str(
                row.get("subject_key") or ""
            ).strip(),
        }

    alignments = {}

    for row in bundle.get(
        "claim_links",
        [],
    ):
        if not isinstance(row, dict):
            continue

        claim_id = str(
            row.get("claim_id") or ""
        ).strip()

        target_type = str(
            row.get("target_type") or ""
        ).strip().lower()

        target_id = str(
            row.get("target_id") or ""
        ).strip()

        if (
            not claim_id
            or not target_type
            or not target_id
        ):
            continue

        state = alignments.setdefault(
            claim_id,
            {
                "observations": set(),
                "evidence": set(),
            },
        )

        if target_type in (
            "source_observation",
            "reporter_observation",
        ):
            state["observations"].add(
                (
                    target_type,
                    target_id,
                )
            )

        elif target_type == "evidence":
            state["evidence"].add(
                target_id
            )

    dependencies = []

    for row in bundle.get(
        "observation_dependencies",
        [],
    ):
        if not isinstance(row, dict):
            continue

        downstream_type = str(
            row.get("downstream_type") or ""
        ).strip().lower()

        downstream_id = str(
            row.get("downstream_id") or ""
        ).strip()

        upstream_type = str(
            row.get("upstream_type") or ""
        ).strip().lower()

        upstream_id = str(
            row.get("upstream_id") or ""
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
                "confidence": row.get(
                    "confidence"
                ),
                "observed_at": str(
                    row.get("observed_at") or ""
                ).strip(),
            }
        )

    claim_ids = sorted(
        set(claims_by_id)
        | set(alignments)
    )

    claim_features = []

    for claim_id in claim_ids:
        alignment = alignments.get(
            claim_id,
            {
                "observations": set(),
                "evidence": set(),
            },
        )

        aligned_observations = sorted(
            alignment["observations"]
        )

        aligned_observation_set = set(
            aligned_observations
        )

        relevant_dependencies = [
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
                in aligned_observation_set
            )
        ]

        relevant_dependencies.sort(
            key=lambda row: (
                row["downstream_type"],
                row["downstream_id"],
                row["upstream_type"],
                row["upstream_id"],
                row["relationship_type"],
                str(row["confidence"]),
                row["observed_at"],
                row["id"],
            )
        )

        observations_with_dependency = {
            (
                row["downstream_type"],
                row["downstream_id"],
            )
            for row in relevant_dependencies
        }

        observations_without_dependency = (
            aligned_observation_set
            - observations_with_dependency
        )

        source_ids = set()
        reporter_ids = set()

        for target in aligned_observations:
            actor = observation_actors.get(
                target,
                {},
            )

            source_id = str(
                actor.get("source_id") or ""
            ).strip()

            reporter_id = str(
                actor.get("reporter_id") or ""
            ).strip()

            if source_id:
                source_ids.add(
                    source_id
                )

            if reporter_id:
                reporter_ids.add(
                    reporter_id
                )

        claim = claims_by_id.get(
            claim_id,
            {},
        )

        claim_features.append(
            {
                "claim_id": claim_id,
                "canonical_key": str(
                    claim.get(
                        "canonical_key"
                    ) or ""
                ).strip(),
                "subject_key": str(
                    claim.get(
                        "subject_key"
                    ) or ""
                ).strip(),
                "aligned_observations": [
                    {
                        "target_type": (
                            target_type
                        ),
                        "target_id": target_id,
                    }
                    for (
                        target_type,
                        target_id,
                    ) in aligned_observations
                ],
                "aligned_evidence_ids": (
                    sorted(
                        alignment["evidence"]
                    )
                ),
                "aligned_source_ids": (
                    sorted(source_ids)
                ),
                "aligned_reporter_ids": (
                    sorted(reporter_ids)
                ),
                "recorded_dependencies": (
                    relevant_dependencies
                ),
                "observations_with_recorded_dependency": [
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
                        observations_with_dependency
                    )
                ],
                "observations_without_recorded_dependency": [
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
                        observations_without_dependency
                    )
                ],
                "counts": {
                    "aligned_observations": len(
                        aligned_observation_set
                    ),
                    "aligned_evidence": len(
                        alignment["evidence"]
                    ),
                    "recorded_dependencies": len(
                        relevant_dependencies
                    ),
                    "observations_with_recorded_dependency": len(
                        observations_with_dependency
                    ),
                    "observations_without_recorded_dependency": len(
                        observations_without_dependency
                    ),
                },
            }
        )

    return {
        "version": (
            CLAIM_DEPENDENCY_FEATURE_VERSION
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
        },
        "claims": claim_features,
    }
