import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
    load_evidence_analysis_bundle_for_media_item,
)
from app.analysis.independence_verification import (
    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
)
from app.intelligence.evidence import (
    record_evidence,
    record_evidence_link,
)
from app.intelligence.independence_assertions import (
    record_observation_independence_assertion,
)
from app.services.corroboration_independence_semantics import (
    CORROBORATION_INDEPENDENCE_GEMINI_MODE,
    CORROBORATION_INDEPENDENCE_GEMINI_MODEL,
    CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
)


CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION = (
    "corroboration-independence-materialization-v1"
)

INDEPENDENCE_EVIDENCE_TYPE = (
    "independence_verification"
)

INDEPENDENCE_EVIDENCE_LINK_RELATIONSHIP = (
    "provenance"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _confidence(
    value: Any,
) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(
            "Independence verification confidence "
            "must be numeric."
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Independence verification confidence "
            "must be numeric."
        ) from exc

    if not 0.0 <= result <= 1.0:
        raise ValueError(
            "Independence verification confidence "
            "must be between 0 and 1."
        )

    return result


def _utc_datetime(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    candidate = text

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                candidate
            )
        )
    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed.astimezone(
        timezone.utc
    )


def _normalized_url(
    value: Any,
    *,
    normalize_url,
) -> str:
    text = _clean(
        value
    )

    if not text:
        return ""

    return _clean(
        normalize_url(
            text
        )
    )


def _grounded(
    excerpts,
    article_text: str,
) -> bool:
    if not isinstance(
        excerpts,
        list,
    ) or not excerpts:
        return False

    normalized_article = _clean(
        article_text
    ).lower()

    if not normalized_article:
        return False

    for raw_excerpt in excerpts:
        excerpt = _clean(
            raw_excerpt
        )

        if (
            not excerpt
            or excerpt.lower()
            not in normalized_article
        ):
            return False

    return True


def _evidence_fingerprint(
    *,
    semantic_result: Dict[str, Any],
    assessment: Dict[str, Any],
) -> str:
    payload = {
        "adapter_version": _clean(
            semantic_result.get(
                "version"
            )
        ),
        "mode": _clean(
            semantic_result.get(
                "mode"
            )
        ),
        "model": _clean(
            semantic_result.get(
                "model"
            )
        ),
        "claim_id": _clean(
            assessment.get(
                "claim_id"
            )
        ),
        "pair_id": _clean(
            assessment.get(
                "pair_id"
            )
        ),
        "assessment_version": _clean(
            assessment.get(
                "version"
            )
        ),
        "status": _clean(
            assessment.get(
                "status"
            )
        ),
        "source_a_reporting_basis": (
            _clean(
                assessment.get(
                    "source_a_reporting_basis"
                )
            )
        ),
        "source_b_reporting_basis": (
            _clean(
                assessment.get(
                    "source_b_reporting_basis"
                )
            )
        ),
        "cross_source_dependency": (
            _clean(
                assessment.get(
                    "cross_source_dependency"
                )
            )
        ),
        "source_a_evidence": [
            _clean(
                value
            )
            for value in assessment.get(
                "source_a_evidence",
                [],
            )
        ],
        "source_b_evidence": [
            _clean(
                value
            )
            for value in assessment.get(
                "source_b_evidence",
                [],
            )
        ],
        "dependency_evidence": [
            _clean(
                value
            )
            for value in assessment.get(
                "dependency_evidence",
                [],
            )
        ],
        "confidence": (
            assessment.get(
                "confidence"
            )
        ),
    }

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "corroboration-independence-evidence|"
            + canonical
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _pair_matches(
    assertion: Dict[str, Any],
    observation_a_id: str,
    observation_b_id: str,
) -> bool:
    if (
        _clean(
            assertion.get(
                "observation_a_type"
            )
        ).lower()
        != "source_observation"
        or _clean(
            assertion.get(
                "observation_b_type"
            )
        ).lower()
        != "source_observation"
    ):
        return False

    assertion_pair = {
        _clean(
            assertion.get(
                "observation_a_id"
            )
        ),
        _clean(
            assertion.get(
                "observation_b_id"
            )
        ),
    }

    return assertion_pair == {
        observation_a_id,
        observation_b_id,
    }


def _dependency_conflicts(
    dependency: Dict[str, Any],
    *,
    observation_a_id: str,
    source_a_id: str,
    observation_b_id: str,
    source_b_id: str,
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

    if (
        downstream_type
        != "source_observation"
    ):
        return False

    if downstream_id == observation_a_id:
        return (
            (
                upstream_type
                == "source_observation"
                and upstream_id
                == observation_b_id
            )
            or (
                upstream_type
                == "source"
                and upstream_id
                == source_b_id
            )
        )

    if downstream_id == observation_b_id:
        return (
            (
                upstream_type
                == "source_observation"
                and upstream_id
                == observation_a_id
            )
            or (
                upstream_type
                == "source"
                and upstream_id
                == source_a_id
            )
        )

    return False


def materialize_verified_independence_evidence(
    *,
    claim: Dict[str, Any],
    pair: Dict[str, Any],
    semantic_result: Dict[str, Any],
    media_item_id: str,
    article_a_text: str,
    article_b_text: str,
    normalize_url,
    connection_factory,
    evidence_loader=(
        load_evidence_analysis_bundle_for_media_item
    ),
    evidence_recorder=(
        record_evidence
    ),
    evidence_link_recorder=(
        record_evidence_link
    ),
    assertion_recorder=(
        record_observation_independence_assertion
    ),
) -> Dict[str, Any]:
    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Independence materialization claim "
            "must be a dictionary."
        )

    if not isinstance(
        pair,
        dict,
    ):
        raise ValueError(
            "Independence materialization pair "
            "must be a dictionary."
        )

    if not isinstance(
        semantic_result,
        dict,
    ):
        raise ValueError(
            "Independence semantic result must "
            "be a dictionary."
        )

    claim_id = _clean(
        claim.get("id")
    )

    subject_key = _clean(
        claim.get(
            "subject_key"
        )
    )

    canonical_text = _clean(
        claim.get(
            "canonical_text"
        )
    )

    media_id = _clean(
        media_item_id
    )

    pair_id = _clean(
        pair.get(
            "pair_id"
        )
    )

    pair_claim_id = _clean(
        pair.get(
            "claim_id"
        )
    )

    observation_a_id = _clean(
        pair.get(
            "observation_a_id"
        )
    )

    observation_b_id = _clean(
        pair.get(
            "observation_b_id"
        )
    )

    source_a_id = _clean(
        pair.get(
            "source_a_id"
        )
    )

    source_b_id = _clean(
        pair.get(
            "source_b_id"
        )
    )

    url_a = _normalized_url(
        pair.get(
            "provenance_url_a"
        ),
        normalize_url=(
            normalize_url
        ),
    )

    url_b = _normalized_url(
        pair.get(
            "provenance_url_b"
        ),
        normalize_url=(
            normalize_url
        ),
    )

    if not claim_id:
        raise ValueError(
            "Independence materialization "
            "claim ID is required."
        )

    if not subject_key:
        raise ValueError(
            "Independence materialization "
            "claim subject key is required."
        )

    if not canonical_text:
        raise ValueError(
            "Independence materialization "
            "canonical claim text is required."
        )

    if not media_id:
        raise ValueError(
            "Independence materialization "
            "media item ID is required."
        )

    if (
        not pair_id
        or not observation_a_id
        or not observation_b_id
        or not source_a_id
        or not source_b_id
        or not url_a
        or not url_b
    ):
        raise ValueError(
            "Independence materialization "
            "pair identity is incomplete."
        )

    if pair_claim_id != claim_id:
        raise ValueError(
            "Independence materialization "
            "pair claim ID does not match."
        )

    if (
        observation_a_id
        == observation_b_id
    ):
        raise ValueError(
            "Independence materialization "
            "requires two observations."
        )

    if source_a_id == source_b_id:
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": "same_source",
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    adapter_version = _clean(
        semantic_result.get(
            "version"
        )
    )

    if (
        adapter_version
        != CORROBORATION_INDEPENDENCE_GEMINI_VERSION
    ):
        raise ValueError(
            "Unsupported independence semantic "
            "adapter version."
        )

    if (
        _clean(
            semantic_result.get(
                "mode"
            )
        )
        != CORROBORATION_INDEPENDENCE_GEMINI_MODE
    ):
        raise ValueError(
            "Unsupported independence semantic "
            "adapter mode."
        )

    if (
        _clean(
            semantic_result.get(
                "model"
            )
        )
        != CORROBORATION_INDEPENDENCE_GEMINI_MODEL
    ):
        raise ValueError(
            "Unsupported independence semantic "
            "adapter model."
        )

    if (
        _clean(
            semantic_result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Independence semantic result "
            "claim ID does not match."
        )

    if (
        _clean(
            semantic_result.get(
                "pair_id"
            )
        )
        != pair_id
    ):
        raise ValueError(
            "Independence semantic result "
            "pair ID does not match."
        )

    semantic_status = _clean(
        semantic_result.get(
            "status"
        )
    ).lower()

    if semantic_status != "assessed":
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                "semantic_result_not_assessed"
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    assessment = semantic_result.get(
        "assessment"
    )

    if not isinstance(
        assessment,
        dict,
    ):
        raise ValueError(
            "Assessed independence semantic "
            "result requires an assessment."
        )

    if (
        _clean(
            assessment.get(
                "version"
            )
        )
        != CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
    ):
        raise ValueError(
            "Unsupported independence evidence "
            "assessment version."
        )

    if (
        _clean(
            assessment.get(
                "claim_id"
            )
        )
        != claim_id
        or _clean(
            assessment.get(
                "pair_id"
            )
        )
        != pair_id
    ):
        raise ValueError(
            "Independence assessment identity "
            "does not match."
        )

    assessment_status = _clean(
        assessment.get(
            "status"
        )
    ).lower()

    if (
        assessment_status
        != "positive_independence_evidence"
    ):
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                assessment_status
                or "assessment_not_positive"
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    if (
        assessment.get(
            "positive_independence_evidence_present"
        )
        is not True
        or assessment.get(
            "explicit_dependency_present"
        )
        is True
        or _clean(
            assessment.get(
                "source_a_reporting_basis"
            )
        ).lower()
        != "original_reporting"
        or _clean(
            assessment.get(
                "source_b_reporting_basis"
            )
        ).lower()
        != "original_reporting"
        or _clean(
            assessment.get(
                "cross_source_dependency"
            )
        ).lower()
        != "not_detected"
    ):
        raise ValueError(
            "Positive independence assessment "
            "is internally inconsistent."
        )

    if (
        assessment.get(
            "independence_established"
        )
        is True
        or assessment.get(
            "independence_assertion_created"
        )
        is True
    ):
        raise ValueError(
            "Semantic assessment cannot "
            "pre-establish independence."
        )

    source_a_evidence = (
        assessment.get(
            "source_a_evidence"
        )
    )

    source_b_evidence = (
        assessment.get(
            "source_b_evidence"
        )
    )

    dependency_evidence = (
        assessment.get(
            "dependency_evidence",
            [],
        )
    )

    if not _grounded(
        source_a_evidence,
        article_a_text,
    ):
        raise ValueError(
            "Source A independence evidence "
            "is not grounded in article A."
        )

    if not _grounded(
        source_b_evidence,
        article_b_text,
    ):
        raise ValueError(
            "Source B independence evidence "
            "is not grounded in article B."
        )

    if dependency_evidence:
        raise ValueError(
            "Positive independence assessment "
            "cannot carry dependency evidence."
        )

    confidence = _confidence(
        assessment.get(
            "confidence"
        )
    )

    current_bundle = evidence_loader(
        media_item_id=media_id,
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        current_bundle,
        dict,
    ):
        raise ValueError(
            "Current evidence bundle must "
            "be a dictionary."
        )

    if (
        _clean(
            current_bundle.get(
                "version"
            )
        )
        != EVIDENCE_ANALYSIS_BUNDLE_VERSION
    ):
        raise ValueError(
            "Unsupported current evidence "
            "bundle version."
        )

    current_claims = [
        row
        for row in current_bundle.get(
            "claims",
            [],
        )
        if isinstance(
            row,
            dict,
        )
        and _clean(
            row.get("id")
        )
        == claim_id
    ]

    if len(current_claims) != 1:
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                "claim_not_in_current_media_scope"
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    current_claim = (
        current_claims[0]
    )

    if (
        _clean(
            current_claim.get(
                "subject_key"
            )
        )
        != subject_key
        or _clean(
            current_claim.get(
                "canonical_text"
            )
        )
        != canonical_text
    ):
        raise ValueError(
            "Current claim state does not "
            "match materialization input."
        )

    observations_by_id = {}

    for row in current_bundle.get(
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

        if observation_id:
            observations_by_id[
                observation_id
            ] = row

    if (
        observation_a_id
        not in observations_by_id
        or observation_b_id
        not in observations_by_id
    ):
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                "pair_not_in_current_evidence_scope"
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    observation_a = (
        observations_by_id[
            observation_a_id
        ]
    )

    observation_b = (
        observations_by_id[
            observation_b_id
        ]
    )

    if (
        _clean(
            observation_a.get(
                "source_id"
            )
        )
        != source_a_id
        or _clean(
            observation_b.get(
                "source_id"
            )
        )
        != source_b_id
    ):
        raise ValueError(
            "Current observation source "
            "identity does not match pair."
        )

    current_url_a = _normalized_url(
        observation_a.get(
            "provenance_url"
        ),
        normalize_url=(
            normalize_url
        ),
    )

    current_url_b = _normalized_url(
        observation_b.get(
            "provenance_url"
        ),
        normalize_url=(
            normalize_url
        ),
    )

    if (
        current_url_a != url_a
        or current_url_b != url_b
    ):
        raise ValueError(
            "Current observation provenance "
            "URL does not match pair."
        )

    supporting_ids = set()

    for link in current_bundle.get(
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
            == claim_id
            and _clean(
                link.get(
                    "target_type"
                )
            ).lower()
            == "source_observation"
            and _clean(
                link.get(
                    "relationship_type"
                )
            ).lower()
            == "supports"
        ):
            target_id = _clean(
                link.get(
                    "target_id"
                )
            )

            if target_id:
                supporting_ids.add(
                    target_id
                )

    if not {
        observation_a_id,
        observation_b_id,
    }.issubset(
        supporting_ids
    ):
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                "pair_no_longer_explicitly_supports_claim"
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    conflict_ids = sorted(
        {
            _clean(
                dependency.get(
                    "id"
                )
            )
            for dependency
            in current_bundle.get(
                "observation_dependencies",
                [],
            )
            if isinstance(
                dependency,
                dict,
            )
            and _dependency_conflicts(
                dependency,
                observation_a_id=(
                    observation_a_id
                ),
                source_a_id=(
                    source_a_id
                ),
                observation_b_id=(
                    observation_b_id
                ),
                source_b_id=(
                    source_b_id
                ),
            )
            and _clean(
                dependency.get(
                    "id"
                )
            )
        }
    )

    if conflict_ids:
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": claim_id,
            "pair_id": pair_id,
            "status": "not_materialized",
            "reason": (
                "recorded_pair_dependency"
            ),
            "dependency_conflict_ids": (
                conflict_ids
            ),
            "evidence": None,
            "evidence_link": None,
            "assertion": None,
            "counts": {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        }

    for assertion in current_bundle.get(
        "observation_independence_assertions",
        [],
    ):
        if (
            isinstance(
                assertion,
                dict,
            )
            and _clean(
                assertion.get(
                    "verification_status"
                )
            ).lower()
            == "verified"
            and _pair_matches(
                assertion,
                observation_a_id,
                observation_b_id,
            )
        ):
            return {
                "version": (
                    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
                ),
                "claim_id": claim_id,
                "pair_id": pair_id,
                "status": (
                    "already_materialized"
                ),
                "reason": (
                    "verified_assertion_exists"
                ),
                "evidence": {
                    "id": _clean(
                        assertion.get(
                            "provenance_evidence_id"
                        )
                    ),
                },
                "evidence_link": None,
                "assertion": (
                    assertion
                ),
                "counts": {
                    "evidence_records_created": 0,
                    "evidence_links_created": 0,
                    "assertions_created": 0,
                },
            }

    observed_a = _utc_datetime(
        observation_a.get(
            "observed_at"
        ),
        label=(
            "Observation A observed time"
        ),
    )

    observed_b = _utc_datetime(
        observation_b.get(
            "observed_at"
        ),
        label=(
            "Observation B observed time"
        ),
    )

    verification_observed_at = max(
        observed_a,
        observed_b,
    ).isoformat()

    fingerprint = (
        _evidence_fingerprint(
            semantic_result=(
                semantic_result
            ),
            assessment=(
                assessment
            ),
        )
    )

    reference_key = (
        "corroboration-independence:"
        + pair_id
        + ":"
        + fingerprint
    )

    metadata = {
        "origin": (
            "corroboration_independence"
        ),
        "materialization_version": (
            CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
        ),
        "semantic_adapter_version": (
            adapter_version
        ),
        "semantic_mode": (
            CORROBORATION_INDEPENDENCE_GEMINI_MODE
        ),
        "semantic_model": (
            CORROBORATION_INDEPENDENCE_GEMINI_MODEL
        ),
        "semantic_assessment_version": (
            CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
        ),
        "claim_id": claim_id,
        "pair_id": pair_id,
        "observation_a_id": (
            observation_a_id
        ),
        "observation_b_id": (
            observation_b_id
        ),
        "source_a_id": (
            source_a_id
        ),
        "source_b_id": (
            source_b_id
        ),
        "provenance_url_a": (
            url_a
        ),
        "provenance_url_b": (
            url_b
        ),
        "source_a_reporting_basis": (
            _clean(
                assessment.get(
                    "source_a_reporting_basis"
                )
            )
        ),
        "source_b_reporting_basis": (
            _clean(
                assessment.get(
                    "source_b_reporting_basis"
                )
            )
        ),
        "cross_source_dependency": (
            _clean(
                assessment.get(
                    "cross_source_dependency"
                )
            )
        ),
        "source_a_evidence": [
            _clean(
                value
            )
            for value in source_a_evidence
        ],
        "source_b_evidence": [
            _clean(
                value
            )
            for value in source_b_evidence
        ],
        "confidence": confidence,
        "evidence_fingerprint": (
            fingerprint
        ),
    }

    evidence_result = (
        evidence_recorder(
            evidence_type=(
                INDEPENDENCE_EVIDENCE_TYPE
            ),
            subject_key=(
                subject_key
            ),
            observed_at=(
                verification_observed_at
            ),
            claim_summary=(
                canonical_text
            ),
            reference_key=(
                reference_key
            ),
            verification_status=(
                "verified"
            ),
            metadata=metadata,
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    evidence = (
        evidence_result.get(
            "evidence"
        )
        if isinstance(
            evidence_result,
            dict,
        )
        else None
    )

    if not isinstance(
        evidence,
        dict,
    ):
        raise RuntimeError(
            "Independence provenance evidence "
            "persistence failed."
        )

    evidence_id = _clean(
        evidence.get("id")
    )

    if not evidence_id:
        raise RuntimeError(
            "Independence provenance evidence "
            "returned no ID."
        )

    evidence_link_result = (
        evidence_link_recorder(
            evidence_id=(
                evidence_id
            ),
            relationship_type=(
                INDEPENDENCE_EVIDENCE_LINK_RELATIONSHIP
            ),
            confidence=(
                confidence
            ),
            media_item_id=(
                media_id
            ),
            linked_at=(
                verification_observed_at
            ),
            metadata={
                "origin": (
                    "corroboration_independence"
                ),
                "pair_id": (
                    pair_id
                ),
                "materialization_version": (
                    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
                ),
            },
            connection_factory=(
                connection_factory
            ),
        )
    )

    evidence_link = (
        evidence_link_result.get(
            "link"
        )
        if isinstance(
            evidence_link_result,
            dict,
        )
        else None
    )

    if not isinstance(
        evidence_link,
        dict,
    ):
        raise RuntimeError(
            "Independence provenance evidence "
            "link persistence failed."
        )

    assertion_result = (
        assertion_recorder(
            observed_at=(
                verification_observed_at
            ),
            provenance_evidence_id=(
                evidence_id
            ),
            verification_status=(
                "verified"
            ),
            confidence=(
                confidence
            ),
            left_source_observation_id=(
                observation_a_id
            ),
            right_source_observation_id=(
                observation_b_id
            ),
            metadata={
                "origin": (
                    "corroboration_independence"
                ),
                "claim_id": (
                    claim_id
                ),
                "pair_id": (
                    pair_id
                ),
                "materialization_version": (
                    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
                ),
                "semantic_adapter_version": (
                    adapter_version
                ),
                "semantic_assessment_version": (
                    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
                ),
            },
            connection_factory=(
                connection_factory
            ),
        )
    )

    assertion = (
        assertion_result.get(
            "assertion"
        )
        if isinstance(
            assertion_result,
            dict,
        )
        else None
    )

    if not isinstance(
        assertion,
        dict,
    ):
        raise RuntimeError(
            "Verified independence assertion "
            "persistence failed."
        )

    return {
        "version": (
            CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
        ),
        "claim_id": claim_id,
        "pair_id": pair_id,
        "status": (
            "materialized_verified_independence"
        ),
        "reason": "",
        "verification_observed_at": (
            verification_observed_at
        ),
        "evidence": (
            evidence
        ),
        "evidence_link": (
            evidence_link
        ),
        "assertion": (
            assertion
        ),
        "counts": {
            "evidence_records_created": (
                1
                if evidence_result.get(
                    "created"
                )
                is True
                else 0
            ),
            "evidence_links_created": (
                1
                if evidence_link_result.get(
                    "created"
                )
                is True
                else 0
            ),
            "assertions_created": (
                1
                if assertion_result.get(
                    "created"
                )
                is True
                else 0
            ),
        },
        "policy": {
            (
                "positive_grounded_semantic_"
                "evidence_is_required"
            ): True,
            (
                "current_support_state_is_"
                "revalidated_before_write"
            ): True,
            (
                "current_pair_dependencies_are_"
                "rechecked_before_write"
            ): True,
            (
                "provenance_evidence_is_"
                "persisted_before_assertion"
            ): True,
            (
                "verified_assertion_requires_"
                "persisted_evidence"
            ): True,
            (
                "exact_retry_is_idempotent"
            ): True,
            (
                "materialization_does_not_"
                "determine_truth"
            ): True,
            (
                "materialization_does_not_"
                "decide_corroboration"
            ): True,
            (
                "materialization_has_no_"
                "merit_effect"
            ): True,
        },
    }
