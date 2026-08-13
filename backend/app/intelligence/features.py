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
