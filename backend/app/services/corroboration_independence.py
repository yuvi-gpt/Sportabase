import hashlib

from itertools import combinations
from typing import Any, Dict

from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)


CORROBORATION_INDEPENDENCE_PLAN_VERSION = (
    "corroboration-independence-plan-v1"
)


def _clean(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def _pair_key(
    first_id: str,
    second_id: str,
):
    return tuple(
        sorted(
            (
                _clean(first_id),
                _clean(second_id),
            )
        )
    )


def _pair_id(
    *,
    claim_id: str,
    first_id: str,
    second_id: str,
) -> str:
    observation_a_id, observation_b_id = (
        _pair_key(
            first_id,
            second_id,
        )
    )

    return hashlib.sha256(
        (
            "corroboration-independence-pair|"
            + claim_id
            + "|"
            + observation_a_id
            + "|"
            + observation_b_id
        ).encode("utf-8")
    ).hexdigest()


def _dependency_points_to_observation(
    dependency: Dict[str, Any],
    observation: Dict[str, Any],
) -> bool:
    upstream_type = _clean(
        dependency.get(
            "upstream_type"
        )
    ).lower()

    upstream_id = _clean(
        dependency.get(
            "upstream_id"
        )
    )

    observation_id = _clean(
        observation.get("id")
    )

    source_id = _clean(
        observation.get("source_id")
    )

    if (
        upstream_type
        == "source_observation"
    ):
        return bool(
            observation_id
            and upstream_id
            == observation_id
        )

    if upstream_type == "source":
        return bool(
            source_id
            and upstream_id
            == source_id
        )

    return False


def _dependency_conflicts_with_pair(
    dependency: Dict[str, Any],
    first: Dict[str, Any],
    second: Dict[str, Any],
) -> bool:
    downstream_type = _clean(
        dependency.get(
            "downstream_type"
        )
    ).lower()

    downstream_id = _clean(
        dependency.get(
            "downstream_id"
        )
    )

    if (
        downstream_type
        != "source_observation"
    ):
        return False

    first_id = _clean(
        first.get("id")
    )

    second_id = _clean(
        second.get("id")
    )

    if (
        downstream_id == first_id
        and
        _dependency_points_to_observation(
            dependency,
            second,
        )
    ):
        return True

    if (
        downstream_id == second_id
        and
        _dependency_points_to_observation(
            dependency,
            first,
        )
    ):
        return True

    return False


def build_corroboration_independence_plan(
    *,
    evidence_bundle: Dict[str, Any],
    claim_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        evidence_bundle,
        dict,
    ):
        raise ValueError(
            "Corroboration independence "
            "planning requires an evidence "
            "bundle dictionary."
        )

    bundle_version = _clean(
        evidence_bundle.get(
            "version"
        )
    )

    if (
        bundle_version
        != EVIDENCE_ANALYSIS_BUNDLE_VERSION
    ):
        raise ValueError(
            "Unsupported evidence analysis "
            "bundle version."
        )

    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Corroboration independence "
            "claim ID is required."
        )

    claims = [
        row
        for row in evidence_bundle.get(
            "claims",
            [],
        )
        if isinstance(row, dict)
        and _clean(
            row.get("id")
        )
        == normalized_claim_id
    ]

    if len(claims) != 1:
        raise ValueError(
            "Corroboration independence "
            "claim must exist exactly once "
            "in the evidence bundle."
        )

    claim = claims[0]

    observations_by_id = {}

    for row in evidence_bundle.get(
        "source_observations",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        observation_id = _clean(
            row.get("id")
        )

        if not observation_id:
            continue

        observations_by_id[
            observation_id
        ] = row

    support_observation_ids = set()

    for link in evidence_bundle.get(
        "claim_links",
        [],
    ):
        if not isinstance(
            link,
            dict,
        ):
            continue

        if (
            _clean(
                link.get(
                    "claim_id"
                )
            )
            != normalized_claim_id
        ):
            continue

        if (
            _clean(
                link.get(
                    "relationship_type"
                )
            ).lower()
            != "supports"
        ):
            continue

        if (
            _clean(
                link.get(
                    "target_type"
                )
            ).lower()
            != "source_observation"
        ):
            continue

        target_id = _clean(
            link.get(
                "target_id"
            )
        )

        if (
            target_id
            in observations_by_id
        ):
            support_observation_ids.add(
                target_id
            )

    supporting_observations = [
        observations_by_id[
            observation_id
        ]
        for observation_id in sorted(
            support_observation_ids
        )
    ]

    dependencies = [
        row
        for row in evidence_bundle.get(
            "observation_dependencies",
            [],
        )
        if isinstance(
            row,
            dict,
        )
    ]

    verified_pairs = set()
    unverified_assertions_by_pair = {}

    for assertion in evidence_bundle.get(
        "observation_independence_assertions",
        [],
    ):
        if not isinstance(
            assertion,
            dict,
        ):
            continue

        if (
            _clean(
                assertion.get(
                    "observation_a_type"
                )
            ).lower()
            != "source_observation"
            or
            _clean(
                assertion.get(
                    "observation_b_type"
                )
            ).lower()
            != "source_observation"
        ):
            continue

        pair = _pair_key(
            assertion.get(
                "observation_a_id"
            ),
            assertion.get(
                "observation_b_id"
            ),
        )

        if not all(pair):
            continue

        verification_status = _clean(
            assertion.get(
                "verification_status"
            )
        ).lower()

        if (
            verification_status
            == "verified"
        ):
            verified_pairs.add(
                pair
            )

        elif (
            verification_status
            == "unverified"
        ):
            assertion_id = _clean(
                assertion.get("id")
            )

            if assertion_id:
                (
                    unverified_assertions_by_pair
                    .setdefault(
                        pair,
                        [],
                    )
                    .append(
                        assertion_id
                    )
                )

    pairs = []
    skipped = []

    for first, second in combinations(
        supporting_observations,
        2,
    ):
        first_id, second_id = (
            _pair_key(
                first.get("id"),
                second.get("id"),
            )
        )

        first = observations_by_id[
            first_id
        ]

        second = observations_by_id[
            second_id
        ]

        pair = (
            first_id,
            second_id,
        )

        first_source_id = _clean(
            first.get("source_id")
        )

        second_source_id = _clean(
            second.get("source_id")
        )

        first_url = _clean(
            first.get(
                "provenance_url"
            )
        )

        second_url = _clean(
            second.get(
                "provenance_url"
            )
        )

        base = {
            "pair_id": _pair_id(
                claim_id=(
                    normalized_claim_id
                ),
                first_id=first_id,
                second_id=second_id,
            ),
            "claim_id": (
                normalized_claim_id
            ),
            "observation_a_id": (
                first_id
            ),
            "observation_b_id": (
                second_id
            ),
            "source_a_id": (
                first_source_id
            ),
            "source_b_id": (
                second_source_id
            ),
            "provenance_url_a": (
                first_url
            ),
            "provenance_url_b": (
                second_url
            ),
        }

        if (
            not first_source_id
            or not second_source_id
        ):
            skipped.append(
                {
                    **base,
                    "reason": (
                        "source_identity_unresolved"
                    ),
                }
            )
            continue

        if (
            first_source_id
            == second_source_id
        ):
            skipped.append(
                {
                    **base,
                    "reason": (
                        "same_source"
                    ),
                }
            )
            continue

        if not first_url or not second_url:
            skipped.append(
                {
                    **base,
                    "reason": (
                        "provenance_url_missing"
                    ),
                }
            )
            continue

        if first_url == second_url:
            skipped.append(
                {
                    **base,
                    "reason": (
                        "same_provenance_url"
                    ),
                }
            )
            continue

        if pair in verified_pairs:
            skipped.append(
                {
                    **base,
                    "reason": (
                        "verified_assertion_exists"
                    ),
                }
            )
            continue

        dependency_conflicts = [
            dependency
            for dependency in dependencies
            if (
                _dependency_conflicts_with_pair(
                    dependency,
                    first,
                    second,
                )
            )
        ]

        dependency_conflict_ids = sorted(
            {
                _clean(
                    dependency.get("id")
                )
                for dependency
                in dependency_conflicts
                if _clean(
                    dependency.get("id")
                )
            }
        )

        if dependency_conflicts:
            skipped.append(
                {
                    **base,
                    "reason": (
                        "recorded_pair_dependency"
                    ),
                    (
                        "dependency_conflict_ids"
                    ): (
                        dependency_conflict_ids
                    ),
                }
            )
            continue

        pairs.append(
            {
                **base,
                "status": (
                    "verification_required"
                ),
                "subject_key": _clean(
                    claim.get(
                        "subject_key"
                    )
                ),
                "canonical_text": _clean(
                    claim.get(
                        "canonical_text"
                    )
                ),
                "observation_a": {
                    "id": first_id,
                    "source_id": (
                        first_source_id
                    ),
                    "provenance_url": (
                        first_url
                    ),
                    "observed_at": _clean(
                        first.get(
                            "observed_at"
                        )
                    ),
                    "claim_summary": _clean(
                        first.get(
                            "claim_summary"
                        )
                    ),
                },
                "observation_b": {
                    "id": second_id,
                    "source_id": (
                        second_source_id
                    ),
                    "provenance_url": (
                        second_url
                    ),
                    "observed_at": _clean(
                        second.get(
                            "observed_at"
                        )
                    ),
                    "claim_summary": _clean(
                        second.get(
                            "claim_summary"
                        )
                    ),
                },
                (
                    "existing_unverified_"
                    "assertion_ids"
                ): sorted(
                    unverified_assertions_by_pair.get(
                        pair,
                        [],
                    )
                ),
                (
                    "dependency_conflict_ids"
                ): [],
            }
        )

    return {
        "version": (
            CORROBORATION_INDEPENDENCE_PLAN_VERSION
        ),
        "evidence_bundle_version": (
            bundle_version
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "status": (
            "verification_pairs_available"
            if pairs
            else "no_verification_pairs"
        ),
        "pairs": pairs,
        "skipped": skipped,
        "counts": {
            "supporting_source_observations": (
                len(
                    supporting_observations
                )
            ),
            "possible_pairs": (
                len(
                    supporting_observations
                )
                * (
                    len(
                        supporting_observations
                    )
                    - 1
                )
                // 2
            ),
            "verification_pairs": (
                len(pairs)
            ),
            "skipped_pairs": (
                len(skipped)
            ),
        },
        "policy": {
            (
                "explicit_support_is_required"
            ): True,
            (
                "distinct_sources_do_not_"
                "establish_independence"
            ): True,
            (
                "absence_of_dependency_does_"
                "not_establish_independence"
            ): True,
            (
                "direct_pair_dependency_blocks_"
                "positive_verification"
            ): True,
            (
                "unrelated_third_party_"
                "dependency_does_not_block_pair"
            ): True,
            (
                "verified_pairs_are_not_"
                "reverified"
            ): True,
            (
                "plan_creates_no_independence_"
                "assertions"
            ): True,
            (
                "plan_is_source_observation_"
                "only_v1"
            ): True,
            (
                "plan_has_no_merit_effect"
            ): True,
        },
    }
