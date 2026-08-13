from typing import Any, Dict, Optional
from urllib.parse import urlparse


CORROBORATION_GRAPH_PLAN_VERSION = (
    "corroboration-graph-plan-v1"
)

CLAIM_GRAPH_RELATIONSHIPS = {
    "supports",
    "contradicts",
    "aligned_to",
}

DEPENDENCY_GRAPH_RELATIONSHIPS = {
    "attributed_to",
    "derived_from",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _confidence(
    value: Any,
) -> Optional[float]:
    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not 0.0 <= result <= 1.0:
        return None

    return result


def _absolute_http_url(
    value: str,
) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False

    return (
        parsed.scheme.lower() in {
            "http",
            "https",
        }
        and bool(parsed.hostname)
    )


def build_corroboration_graph_plan(
    *,
    claim: Dict[str, Any],
    collection: Dict[str, Any],
    semantic_batch: Dict[str, Any],
    normalize_url,
    domain_resolver,
) -> Dict[str, Any]:
    if not isinstance(claim, dict):
        raise ValueError(
            "Graph-plan claim must be a dictionary."
        )

    if not isinstance(collection, dict):
        raise ValueError(
            "Graph-plan collection must be a dictionary."
        )

    if not isinstance(semantic_batch, dict):
        raise ValueError(
            "Graph-plan semantic batch must be a dictionary."
        )

    claim_id = _clean(
        claim.get("id")
    )

    subject_key = _clean(
        claim.get("subject_key")
    )

    canonical_text = _clean(
        claim.get("canonical_text")
    )

    if not claim_id:
        raise ValueError(
            "Graph-plan claim ID is required."
        )

    if not subject_key:
        raise ValueError(
            "Graph-plan claim subject key is required."
        )

    resolved_by_url = {}

    raw_candidates = collection.get(
        "resolved_candidates",
        [],
    )

    if not isinstance(raw_candidates, list):
        raw_candidates = []

    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue

        if (
            _clean(
                candidate.get(
                    "resolution_status"
                )
            ).lower()
            != "resolved"
        ):
            continue

        raw_url = _clean(
            candidate.get("final_url")
            or candidate.get("normalized_url")
            or candidate.get("url")
        )

        canonical_url = (
            normalize_url(raw_url)
            if raw_url
            else ""
        )

        if (
            canonical_url
            and canonical_url
            not in resolved_by_url
        ):
            resolved_by_url[
                canonical_url
            ] = candidate

    semantic_rows = semantic_batch.get(
        "candidate_assessments",
        [],
    )

    if not isinstance(semantic_rows, list):
        semantic_rows = []

    actions = []
    skipped = []
    seen_semantic_urls = set()

    dependency_intent_count = 0
    unresolved_dependency_count = 0

    for row in semantic_rows:
        if not isinstance(row, dict):
            continue

        raw_semantic_url = _clean(
            row.get("candidate_url")
        )

        candidate_url = (
            normalize_url(
                raw_semantic_url
            )
            if raw_semantic_url
            else ""
        )

        if not candidate_url:
            skipped.append(
                {
                    "candidate_url": "",
                    "reason": (
                        "candidate_url_missing"
                    ),
                }
            )
            continue

        if candidate_url in seen_semantic_urls:
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "duplicate_semantic_candidate"
                    ),
                }
            )
            continue

        seen_semantic_urls.add(
            candidate_url
        )

        if (
            _clean(
                row.get("status")
            ).lower()
            != "assessed"
        ):
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "semantic_not_assessed"
                    ),
                }
            )
            continue

        semantic_result = row.get(
            "semantic_result"
        )

        if not isinstance(
            semantic_result,
            dict,
        ):
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "semantic_result_missing"
                    ),
                }
            )
            continue

        assessment = semantic_result.get(
            "assessment"
        )

        if not isinstance(
            assessment,
            dict,
        ):
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "semantic_assessment_missing"
                    ),
                }
            )
            continue

        relationship = _clean(
            assessment.get(
                "claim_relationship_type"
            )
        ).lower()

        if (
            relationship
            not in CLAIM_GRAPH_RELATIONSHIPS
        ):
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "no_materializable_"
                        "claim_relationship"
                    ),
                }
            )
            continue

        candidate = resolved_by_url.get(
            candidate_url
        )

        if candidate is None:
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "resolved_candidate_missing"
                    ),
                }
            )
            continue

        published_at = _clean(
            candidate.get(
                "published_at"
            )
        )

        publication_status = _clean(
            candidate.get(
                "publication_time_status"
            )
        ).lower()

        if (
            not published_at
            or publication_status
            != "found"
        ):
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "deterministic_"
                        "publication_time_missing"
                    ),
                }
            )
            continue

        source_domain = _clean(
            candidate.get(
                "final_source_domain"
            )
        ).lower()

        if not source_domain:
            source_domain = _clean(
                domain_resolver(
                    candidate_url
                )
            ).lower()

        if not source_domain:
            skipped.append(
                {
                    "candidate_url": (
                        candidate_url
                    ),
                    "reason": (
                        "source_identity_unresolved"
                    ),
                }
            )
            continue

        stance_confidence = _confidence(
            assessment.get(
                "stance_confidence"
            )
        )

        dependency_confidence = (
            _confidence(
                assessment.get(
                    "dependency_confidence"
                )
            )
        )

        dependency_intents = []
        unresolved_targets = []

        if (
            assessment.get(
                "explicit_dependency_present"
            )
            is True
        ):
            dependency_relationship = (
                _clean(
                    assessment.get(
                        "dependency_relationship"
                    )
                ).lower()
            )

            raw_targets = assessment.get(
                "dependency_targets",
                [],
            )

            if not isinstance(
                raw_targets,
                list,
            ):
                raw_targets = []

            seen_targets = set()

            for raw_target in raw_targets:
                target = _clean(
                    raw_target
                )

                if not target:
                    continue

                target_key = (
                    target.lower()
                )

                if target_key in seen_targets:
                    continue

                seen_targets.add(
                    target_key
                )

                if (
                    dependency_relationship
                    not in
                    DEPENDENCY_GRAPH_RELATIONSHIPS
                ):
                    unresolved_targets.append(
                        {
                            "target": target,
                            "reason": (
                                "dependency_"
                                "relationship_unusable"
                            ),
                        }
                    )
                    continue

                if not _absolute_http_url(
                    target
                ):
                    unresolved_targets.append(
                        {
                            "target": target,
                            "reason": (
                                "dependency_target_"
                                "not_resolvable_url"
                            ),
                        }
                    )
                    continue

                upstream_url = (
                    normalize_url(
                        target
                    )
                )

                upstream_domain = (
                    _clean(
                        domain_resolver(
                            upstream_url
                        )
                    ).lower()
                    if upstream_url
                    else ""
                )

                if (
                    not upstream_url
                    or not upstream_domain
                ):
                    unresolved_targets.append(
                        {
                            "target": target,
                            "reason": (
                                "dependency_source_"
                                "identity_unresolved"
                            ),
                        }
                    )
                    continue

                if (
                    upstream_url
                    == candidate_url
                ):
                    unresolved_targets.append(
                        {
                            "target": target,
                            "reason": (
                                "dependency_self_"
                                "reference"
                            ),
                        }
                    )
                    continue

                dependency_intents.append(
                    {
                        "relationship_type": (
                            dependency_relationship
                        ),
                        "upstream_source_url": (
                            upstream_url
                        ),
                        "upstream_source_domain": (
                            upstream_domain
                        ),
                        "observed_at": (
                            published_at
                        ),
                        "confidence": (
                            dependency_confidence
                        ),
                        "dependency_evidence": (
                            assessment.get(
                                "dependency_evidence",
                                [],
                            )
                            if isinstance(
                                assessment.get(
                                    "dependency_evidence",
                                    [],
                                ),
                                list,
                            )
                            else []
                        ),
                    }
                )

        dependency_intent_count += len(
            dependency_intents
        )

        unresolved_dependency_count += len(
            unresolved_targets
        )

        actions.append(
            {
                "candidate_url": (
                    candidate_url
                ),
                "source_domain": (
                    source_domain
                ),
                "same_source_domain": bool(
                    candidate.get(
                        "final_same_source_domain",
                        False,
                    )
                ),
                "source": {
                    "url": candidate_url,
                    "display_name": (
                        source_domain
                    ),
                    "source_type": (
                        "publisher"
                    ),
                },
                "observation": {
                    "subject_key": (
                        subject_key
                    ),
                    "observation_type": (
                        "report"
                    ),
                    "observed_at": (
                        published_at
                    ),
                    "status": (
                        "unresolved"
                    ),
                    "claim_summary": (
                        canonical_text
                    ),
                    "provenance_url": (
                        candidate_url
                    ),
                    "confidence": None,
                },
                "claim_link": {
                    "claim_id": claim_id,
                    "relationship_type": (
                        relationship
                    ),
                    "observed_at": (
                        published_at
                    ),
                    "confidence": (
                        stance_confidence
                    ),
                },
                "dependency_intents": (
                    dependency_intents
                ),
                "unresolved_dependency_targets": (
                    unresolved_targets
                ),
                "provenance": {
                    "provider": _clean(
                        row.get("provider")
                        or candidate.get(
                            "provider"
                        )
                    ),
                    "provider_rank": (
                        row.get(
                            "provider_rank"
                        )
                        if row.get(
                            "provider_rank"
                        )
                        is not None
                        else candidate.get(
                            "provider_rank"
                        )
                    ),
                    "publication_time_version": (
                        _clean(
                            candidate.get(
                                "publication_time_version"
                            )
                        )
                    ),
                    "publication_time_source_type": (
                        _clean(
                            candidate.get(
                                "publication_time_source_type"
                            )
                        )
                    ),
                    "publication_time_source_key": (
                        _clean(
                            candidate.get(
                                "publication_time_source_key"
                            )
                        )
                    ),
                },
            }
        )

    return {
        "version": (
            CORROBORATION_GRAPH_PLAN_VERSION
        ),
        "claim_id": claim_id,
        "subject_key": subject_key,
        "status": (
            "materializable_actions_available"
            if actions
            else "no_materializable_actions"
        ),
        "actions": actions,
        "skipped": skipped,
        "counts": {
            "resolved_candidates": len(
                resolved_by_url
            ),
            "semantic_rows": len(
                semantic_rows
            ),
            "materializable": len(
                actions
            ),
            "skipped": len(
                skipped
            ),
            "claim_links": len(
                actions
            ),
            "dependency_intents": (
                dependency_intent_count
            ),
            "unresolved_dependency_targets": (
                unresolved_dependency_count
            ),
            "independence_assertions": 0,
            "corroboration_decisions": 0,
        },
        "policy": {
            (
                "semantic_relationships_may_"
                "materialize_claim_links"
            ): True,
            (
                "observations_remain_unresolved"
            ): True,
            (
                "dependency_requires_explicit_"
                "resolvable_target"
            ): True,
            (
                "absence_of_dependency_does_not_"
                "establish_independence"
            ): True,
            (
                "graph_plan_does_not_establish_"
                "corroboration"
            ): True,
            (
                "graph_plan_has_no_merit_effect"
            ): True,
        },
    }
