from typing import Any, Dict, List

from app.intelligence.claims import (
    record_claim_link,
)
from app.intelligence.dependencies import (
    record_observation_dependency,
)
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    upsert_intelligence_source,
)
from app.services.corroboration_graph import (
    CLAIM_GRAPH_RELATIONSHIPS,
    CORROBORATION_GRAPH_PLAN_VERSION,
    DEPENDENCY_GRAPH_RELATIONSHIPS,
)


CORROBORATION_GRAPH_MATERIALIZATION_VERSION = (
    "corroboration-graph-materialization-v1"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _require_dict(
    value: Any,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be a dictionary."
        )

    return value


def _validate_plan(
    plan: Dict[str, Any],
    *,
    normalize_url,
    domain_resolver,
) -> List[Dict[str, Any]]:
    if not isinstance(plan, dict):
        raise ValueError(
            "Corroboration graph plan must "
            "be a dictionary."
        )

    version = _clean(
        plan.get("version")
    )

    if (
        version
        != CORROBORATION_GRAPH_PLAN_VERSION
    ):
        raise ValueError(
            "Unsupported corroboration graph "
            "plan version."
        )

    claim_id = _clean(
        plan.get("claim_id")
    )

    if not claim_id:
        raise ValueError(
            "Corroboration graph plan claim "
            "ID is required."
        )

    actions = plan.get(
        "actions",
        [],
    )

    if not isinstance(actions, list):
        raise ValueError(
            "Corroboration graph plan actions "
            "must be a list."
        )

    validated = []

    for index, raw_action in enumerate(
        actions
    ):
        action = _require_dict(
            raw_action,
            (
                "Corroboration graph action "
                f"{index}"
            ),
        )

        source = _require_dict(
            action.get("source"),
            (
                "Corroboration graph action "
                f"{index} source"
            ),
        )

        observation = _require_dict(
            action.get("observation"),
            (
                "Corroboration graph action "
                f"{index} observation"
            ),
        )

        claim_link = _require_dict(
            action.get("claim_link"),
            (
                "Corroboration graph action "
                f"{index} claim link"
            ),
        )

        candidate_url = _clean(
            action.get("candidate_url")
        )

        source_url = _clean(
            source.get("url")
        )

        normalized_candidate_url = (
            normalize_url(
                candidate_url
            )
            if candidate_url
            else ""
        )

        normalized_source_url = (
            normalize_url(
                source_url
            )
            if source_url
            else ""
        )

        if (
            not normalized_candidate_url
            or normalized_candidate_url
            != normalized_source_url
        ):
            raise ValueError(
                "Graph action source URL must "
                "match its candidate URL."
            )

        source_domain = _clean(
            domain_resolver(
                normalized_source_url
            )
        ).lower()

        planned_domain = _clean(
            action.get(
                "source_domain"
            )
        ).lower()

        if (
            not source_domain
            or (
                planned_domain
                and source_domain
                != planned_domain
            )
        ):
            raise ValueError(
                "Graph action source identity "
                "does not match its URL."
            )

        observed_at = _clean(
            observation.get(
                "observed_at"
            )
        )

        if not observed_at:
            raise ValueError(
                "Graph action observation time "
                "is required."
            )

        if (
            _clean(
                claim_link.get(
                    "claim_id"
                )
            )
            != claim_id
        ):
            raise ValueError(
                "Graph action claim link does "
                "not match plan claim ID."
            )

        relationship = _clean(
            claim_link.get(
                "relationship_type"
            )
        ).lower()

        if (
            relationship
            not in CLAIM_GRAPH_RELATIONSHIPS
        ):
            raise ValueError(
                "Graph action claim relationship "
                "is not materializable."
            )

        if (
            _clean(
                claim_link.get(
                    "observed_at"
                )
            )
            != observed_at
        ):
            raise ValueError(
                "Graph action claim-link time "
                "must match observation time."
            )

        dependency_intents = (
            action.get(
                "dependency_intents",
                [],
            )
        )

        if not isinstance(
            dependency_intents,
            list,
        ):
            raise ValueError(
                "Graph action dependency intents "
                "must be a list."
            )

        validated_dependencies = []

        for dependency in (
            dependency_intents
        ):
            dependency = _require_dict(
                dependency,
                (
                    "Graph action dependency "
                    "intent"
                ),
            )

            dependency_relationship = (
                _clean(
                    dependency.get(
                        "relationship_type"
                    )
                ).lower()
            )

            if (
                dependency_relationship
                not in
                DEPENDENCY_GRAPH_RELATIONSHIPS
            ):
                raise ValueError(
                    "Graph dependency relationship "
                    "is not materializable."
                )

            upstream_url = _clean(
                dependency.get(
                    "upstream_source_url"
                )
            )

            normalized_upstream_url = (
                normalize_url(
                    upstream_url
                )
                if upstream_url
                else ""
            )

            upstream_domain = (
                _clean(
                    domain_resolver(
                        normalized_upstream_url
                    )
                ).lower()
                if normalized_upstream_url
                else ""
            )

            planned_upstream_domain = (
                _clean(
                    dependency.get(
                        "upstream_source_domain"
                    )
                ).lower()
            )

            if (
                not normalized_upstream_url
                or not upstream_domain
                or (
                    planned_upstream_domain
                    and upstream_domain
                    != planned_upstream_domain
                )
            ):
                raise ValueError(
                    "Graph dependency upstream "
                    "source identity is invalid."
                )

            if (
                normalized_upstream_url
                == normalized_candidate_url
            ):
                raise ValueError(
                    "Graph dependency cannot point "
                    "to its own candidate URL."
                )

            if (
                _clean(
                    dependency.get(
                        "observed_at"
                    )
                )
                != observed_at
            ):
                raise ValueError(
                    "Graph dependency time must "
                    "match downstream observation."
                )

            validated_dependencies.append(
                {
                    **dependency,
                    "upstream_source_url": (
                        normalized_upstream_url
                    ),
                    "upstream_source_domain": (
                        upstream_domain
                    ),
                }
            )

        validated.append(
            {
                **action,
                "candidate_url": (
                    normalized_candidate_url
                ),
                "source_domain": (
                    source_domain
                ),
                "dependency_intents": (
                    validated_dependencies
                ),
            }
        )

    return validated


def materialize_corroboration_graph_plan(
    *,
    plan: Dict[str, Any],
    normalize_url,
    domain_resolver,
    connection_factory,
    source_upserter=(
        upsert_intelligence_source
    ),
    observation_recorder=(
        record_source_observation
    ),
    claim_link_recorder=(
        record_claim_link
    ),
    dependency_recorder=(
        record_observation_dependency
    ),
) -> Dict[str, Any]:
    actions = _validate_plan(
        plan,
        normalize_url=normalize_url,
        domain_resolver=domain_resolver,
    )

    base = {
        "version": (
            CORROBORATION_GRAPH_MATERIALIZATION_VERSION
        ),
        "plan_version": (
            CORROBORATION_GRAPH_PLAN_VERSION
        ),
        "claim_id": _clean(
            plan.get("claim_id")
        ),
        "policy": {
            (
                "existing_intelligence_"
                "primitives_are_reused"
            ): True,
            (
                "materialization_is_"
                "deterministic_and_idempotent"
            ): True,
            (
                "explicit_dependency_may_"
                "target_upstream_source"
            ): True,
            (
                "upstream_observation_is_"
                "not_invented"
            ): True,
            (
                "absence_of_dependency_does_"
                "not_establish_independence"
            ): True,
            (
                "materialization_does_not_"
                "create_independence_assertions"
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

    if not actions:
        return {
            **base,
            "status": (
                "no_materializable_actions"
            ),
            "results": [],
            "counts": {
                "actions": 0,
                "source_observations_created": 0,
                "claim_links_created": 0,
                "dependencies_created": 0,
                "independence_assertions_created": 0,
            },
        }

    results = []

    observations_created = 0
    claim_links_created = 0
    dependencies_created = 0

    for action in actions:
        candidate_url = action[
            "candidate_url"
        ]

        source_spec = action[
            "source"
        ]

        observation_spec = action[
            "observation"
        ]

        claim_link_spec = action[
            "claim_link"
        ]

        provenance = action.get(
            "provenance",
            {},
        )

        if not isinstance(
            provenance,
            dict,
        ):
            provenance = {}

        source = source_upserter(
            url=candidate_url,
            display_name=(
                _clean(
                    source_spec.get(
                        "display_name"
                    )
                )
                or action[
                    "source_domain"
                ]
            ),
            source_type=(
                _clean(
                    source_spec.get(
                        "source_type"
                    )
                )
                or "publisher"
            ),
            seen_at=(
                observation_spec[
                    "observed_at"
                ]
            ),
            metadata={
                "origin": (
                    "corroboration_graph"
                ),
                "graph_plan_version": (
                    CORROBORATION_GRAPH_PLAN_VERSION
                ),
                "provider": _clean(
                    provenance.get(
                        "provider"
                    )
                ),
                "provider_rank": (
                    provenance.get(
                        "provider_rank"
                    )
                ),
            },
            domain_resolver=(
                domain_resolver
            ),
            connection_factory=(
                connection_factory
            ),
        )

        source_id = _clean(
            source.get("id")
        )

        if not source_id:
            raise RuntimeError(
                "Corroboration source "
                "persistence returned no ID."
            )

        observation_result = (
            observation_recorder(
                source_id=source_id,
                subject_key=_clean(
                    observation_spec.get(
                        "subject_key"
                    )
                ),
                observation_type=_clean(
                    observation_spec.get(
                        "observation_type"
                    )
                ),
                observed_at=_clean(
                    observation_spec.get(
                        "observed_at"
                    )
                ),
                status=_clean(
                    observation_spec.get(
                        "status"
                    )
                ),
                claim_summary=_clean(
                    observation_spec.get(
                        "claim_summary"
                    )
                ),
                provenance_url=(
                    candidate_url
                ),
                confidence=(
                    observation_spec.get(
                        "confidence"
                    )
                ),
                metadata={
                    "origin": (
                        "corroboration_graph"
                    ),
                    "graph_plan_version": (
                        CORROBORATION_GRAPH_PLAN_VERSION
                    ),
                    "publication_time_version": (
                        _clean(
                            provenance.get(
                                "publication_time_version"
                            )
                        )
                    ),
                    "publication_time_source_type": (
                        _clean(
                            provenance.get(
                                "publication_time_source_type"
                            )
                        )
                    ),
                    "publication_time_source_key": (
                        _clean(
                            provenance.get(
                                "publication_time_source_key"
                            )
                        )
                    ),
                },
                normalize_url=normalize_url,
                connection_factory=(
                    connection_factory
                ),
            )
        )

        observation = (
            observation_result.get(
                "observation"
            )
            if isinstance(
                observation_result,
                dict,
            )
            else None
        )

        if not isinstance(
            observation,
            dict,
        ):
            raise RuntimeError(
                "Corroboration observation "
                "persistence failed."
            )

        observation_id = _clean(
            observation.get("id")
        )

        if not observation_id:
            raise RuntimeError(
                "Corroboration observation "
                "returned no ID."
            )

        if (
            observation_result.get(
                "created"
            )
            is True
        ):
            observations_created += 1

        claim_link_result = (
            claim_link_recorder(
                claim_id=_clean(
                    claim_link_spec.get(
                        "claim_id"
                    )
                ),
                relationship_type=_clean(
                    claim_link_spec.get(
                        "relationship_type"
                    )
                ),
                observed_at=_clean(
                    claim_link_spec.get(
                        "observed_at"
                    )
                ),
                confidence=(
                    claim_link_spec.get(
                        "confidence"
                    )
                ),
                source_observation_id=(
                    observation_id
                ),
                metadata={
                    "origin": (
                        "corroboration_graph"
                    ),
                    "graph_plan_version": (
                        CORROBORATION_GRAPH_PLAN_VERSION
                    ),
                    "candidate_url": (
                        candidate_url
                    ),
                },
                connection_factory=(
                    connection_factory
                ),
            )
        )

        claim_link = (
            claim_link_result.get(
                "link"
            )
            if isinstance(
                claim_link_result,
                dict,
            )
            else None
        )

        if not isinstance(
            claim_link,
            dict,
        ):
            raise RuntimeError(
                "Corroboration claim-link "
                "persistence failed."
            )

        if (
            claim_link_result.get(
                "created"
            )
            is True
        ):
            claim_links_created += 1

        dependency_rows = []

        for dependency_spec in (
            action[
                "dependency_intents"
            ]
        ):
            upstream_source = (
                source_upserter(
                    url=(
                        dependency_spec[
                            "upstream_source_url"
                        ]
                    ),
                    display_name=(
                        dependency_spec[
                            "upstream_source_domain"
                        ]
                    ),
                    source_type="publisher",
                    seen_at=_clean(
                        dependency_spec.get(
                            "observed_at"
                        )
                    ),
                    metadata={
                        "origin": (
                            "corroboration_graph_"
                            "explicit_dependency"
                        ),
                        "graph_plan_version": (
                            CORROBORATION_GRAPH_PLAN_VERSION
                        ),
                    },
                    domain_resolver=(
                        domain_resolver
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

            upstream_source_id = _clean(
                upstream_source.get(
                    "id"
                )
            )

            if not upstream_source_id:
                raise RuntimeError(
                    "Dependency upstream source "
                    "persistence returned no ID."
                )

            dependency_result = (
                dependency_recorder(
                    relationship_type=_clean(
                        dependency_spec.get(
                            "relationship_type"
                        )
                    ),
                    observed_at=_clean(
                        dependency_spec.get(
                            "observed_at"
                        )
                    ),
                    confidence=(
                        dependency_spec.get(
                            "confidence"
                        )
                    ),
                    downstream_source_observation_id=(
                        observation_id
                    ),
                    upstream_source_id=(
                        upstream_source_id
                    ),
                    metadata={
                        "origin": (
                            "corroboration_graph"
                        ),
                        "graph_plan_version": (
                            CORROBORATION_GRAPH_PLAN_VERSION
                        ),
                        "candidate_url": (
                            candidate_url
                        ),
                        "dependency_evidence": (
                            dependency_spec.get(
                                "dependency_evidence",
                                [],
                            )
                        ),
                    },
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

            dependency = (
                dependency_result.get(
                    "dependency"
                )
                if isinstance(
                    dependency_result,
                    dict,
                )
                else None
            )

            if not isinstance(
                dependency,
                dict,
            ):
                raise RuntimeError(
                    "Corroboration dependency "
                    "persistence failed."
                )

            if (
                dependency_result.get(
                    "created"
                )
                is True
            ):
                dependencies_created += 1

            dependency_rows.append(
                {
                    "dependency_id": (
                        _clean(
                            dependency.get(
                                "id"
                            )
                        )
                    ),
                    "upstream_source_id": (
                        upstream_source_id
                    ),
                    "upstream_source_url": (
                        dependency_spec[
                            "upstream_source_url"
                        ]
                    ),
                    "upstream_observation_id": "",
                }
            )

        results.append(
            {
                "candidate_url": (
                    candidate_url
                ),
                "source_id": source_id,
                "source_observation_id": (
                    observation_id
                ),
                "claim_link_id": _clean(
                    claim_link.get("id")
                ),
                "dependencies": (
                    dependency_rows
                ),
            }
        )

    return {
        **base,
        "status": "materialized",
        "results": results,
        "counts": {
            "actions": len(
                actions
            ),
            "source_observations_created": (
                observations_created
            ),
            "claim_links_created": (
                claim_links_created
            ),
            "dependencies_created": (
                dependencies_created
            ),
            "independence_assertions_created": 0,
        },
    }
