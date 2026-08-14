from typing import Any, Dict

from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
    build_claim_corroboration_assessment,
)
from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)
from app.analysis.stance import (
    CLAIM_STANCE_POLICY_VERSION,
    build_claim_stance_analysis,
)
from app.analysis.support import (
    CLAIM_SUPPORT_PROVENANCE_VERSION,
    build_claim_support_provenance,
)
from app.services.corroboration_independence_pipeline import (
    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
)


CORROBORATION_RESOLUTION_VERSION = (
    "corroboration-resolution-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _require_analysis_stage(
    *,
    stage_name: str,
    result: Any,
    expected_version: str,
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            f"{stage_name} must return "
            "a dictionary."
        )

    if (
        _clean(
            result.get("version")
        )
        != expected_version
    ):
        raise ValueError(
            f"{stage_name} returned an "
            "unsupported version."
        )

    claims = result.get(
        "claims",
        [],
    )

    if not isinstance(
        claims,
        list,
    ):
        raise ValueError(
            f"{stage_name} claims must "
            "be a list."
        )

    return result


def resolve_corroboration_from_independence_batch(
    *,
    batch_result: Dict[str, Any],
    stance_builder=(
        build_claim_stance_analysis
    ),
    support_builder=(
        build_claim_support_provenance
    ),
    corroboration_builder=(
        build_claim_corroboration_assessment
    ),
) -> Dict[str, Any]:
    if not isinstance(
        batch_result,
        dict,
    ):
        raise ValueError(
            "Corroboration resolution requires "
            "an independence batch result."
        )

    if (
        _clean(
            batch_result.get(
                "version"
            )
        )
        != CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
    ):
        raise ValueError(
            "Unsupported independence batch "
            "version."
        )

    batch_status = _clean(
        batch_result.get(
            "status"
        )
    ).lower()

    if batch_status not in {
        "completed",
        "no_verification_pairs",
    }:
        raise ValueError(
            "Independence batch must be "
            "completed before corroboration "
            "resolution."
        )

    claim_id = _clean(
        batch_result.get(
            "claim_id"
        )
    )

    media_item_id = _clean(
        batch_result.get(
            "media_item_id"
        )
    )

    if not claim_id:
        raise ValueError(
            "Corroboration resolution claim "
            "ID is required."
        )

    if not media_item_id:
        raise ValueError(
            "Corroboration resolution media "
            "item ID is required."
        )

    evidence_bundle = (
        batch_result.get(
            "evidence_bundle"
        )
    )

    if not isinstance(
        evidence_bundle,
        dict,
    ):
        raise ValueError(
            "Corroboration resolution requires "
            "a final evidence bundle."
        )

    if (
        _clean(
            evidence_bundle.get(
                "version"
            )
        )
        != EVIDENCE_ANALYSIS_BUNDLE_VERSION
    ):
        raise ValueError(
            "Unsupported final evidence "
            "bundle version."
        )

    scope = evidence_bundle.get(
        "scope",
        {},
    )

    if not isinstance(
        scope,
        dict,
    ):
        raise ValueError(
            "Final evidence bundle scope "
            "must be a dictionary."
        )

    if (
        _clean(
            scope.get(
                "media_item_id"
            )
        )
        != media_item_id
    ):
        raise ValueError(
            "Final evidence bundle media "
            "scope does not match the batch."
        )

    stance_state = (
        stance_builder(
            evidence_bundle
        )
    )

    stance_state = (
        _require_analysis_stage(
            stage_name=(
                "Claim stance analysis"
            ),
            result=(
                stance_state
            ),
            expected_version=(
                CLAIM_STANCE_POLICY_VERSION
            ),
        )
    )

    support_state = (
        support_builder(
            evidence_bundle
        )
    )

    support_state = (
        _require_analysis_stage(
            stage_name=(
                "Claim support provenance"
            ),
            result=(
                support_state
            ),
            expected_version=(
                CLAIM_SUPPORT_PROVENANCE_VERSION
            ),
        )
    )

    corroboration_state = (
        corroboration_builder(
            support_state=(
                support_state
            ),
            stance_state=(
                stance_state
            ),
        )
    )

    corroboration_state = (
        _require_analysis_stage(
            stage_name=(
                "Claim corroboration assessment"
            ),
            result=(
                corroboration_state
            ),
            expected_version=(
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
        )
    )

    target_claims = [
        row
        for row in corroboration_state.get(
            "claims",
            [],
        )
        if (
            isinstance(
                row,
                dict,
            )
            and _clean(
                row.get(
                    "claim_id"
                )
            )
            == claim_id
        )
    ]

    if len(target_claims) != 1:
        raise ValueError(
            "Corroboration resolution requires "
            "exactly one target claim result."
        )

    target_claim = (
        target_claims[0]
    )

    corroboration_established = bool(
        target_claim.get(
            "corroboration_established",
            False,
        )
    )

    contested = bool(
        target_claim.get(
            "contested",
            False,
        )
    )

    return {
        "version": (
            CORROBORATION_RESOLUTION_VERSION
        ),
        "status": "assessed",
        "claim_id": (
            claim_id
        ),
        "media_item_id": (
            media_item_id
        ),
        "corroboration_status": (
            _clean(
                target_claim.get(
                    "status"
                )
            )
        ),
        "corroboration_established": (
            corroboration_established
        ),
        "contested": (
            contested
        ),
        "target_claim": (
            target_claim
        ),
        "stages": {
            "stance": (
                stance_state
            ),
            "support_provenance": (
                support_state
            ),
            "corroboration": (
                corroboration_state
            ),
        },
        "versions": {
            "independence_batch": (
                CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
            ),
            "evidence_bundle": (
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
            ),
            "stance": (
                CLAIM_STANCE_POLICY_VERSION
            ),
            "support_provenance": (
                CLAIM_SUPPORT_PROVENANCE_VERSION
            ),
            "corroboration": (
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
        },
        "policy": {
            (
                "corroboration_uses_existing_"
                "analysis_policy"
            ): True,
            (
                "explicit_support_is_required"
            ): True,
            (
                "verified_independent_support_"
                "is_required"
            ): True,
            (
                "source_diversity_alone_does_"
                "not_establish_corroboration"
            ): True,
            (
                "absence_of_dependency_does_"
                "not_establish_corroboration"
            ): True,
            (
                "contradiction_does_not_erase_"
                "recorded_support"
            ): True,
            (
                "corroboration_does_not_"
                "establish_truth"
            ): True,
            (
                "resolution_has_no_"
                "merit_effect"
            ): True,
        },
    }
