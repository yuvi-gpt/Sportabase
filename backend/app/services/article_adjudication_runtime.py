import hashlib
import json

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from app.intelligence.adjudication_history import (
    load_latest_adjudication_state_revision,
    re_adjudicate_claim,
)

from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
)


ARTICLE_ADJUDICATION_RUNTIME_VERSION = (
    "article-adjudication-runtime-v1"
)

ARTICLE_GRAPH_EVALUATOR_VERSION = (
    "article-provenance-graph-v1"
)

ARTICLE_GRAPH_EVALUATOR_FAMILY = (
    "provenance_graph"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _stable_id(
    value: Any,
    *,
    prefix: str,
) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            prefix
            + payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _timestamp(
    value: Any,
) -> Optional[
    datetime
]:
    text = _clean(
        value
    )

    if not text:
        return None

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                text
            )
        )

    except ValueError:
        return None

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        return None

    return parsed.astimezone(
        timezone.utc
    )


def _require_pipeline(
    *,
    claim_id: str,
    pipeline: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    if not isinstance(
        pipeline,
        dict,
    ):
        raise ValueError(
            "Article adjudication pipeline "
            "must be a dictionary."
        )

    if (
        _clean(
            pipeline.get(
                "version"
            )
        )
        != (
            SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
        )
    ):
        raise ValueError(
            "Article adjudication requires "
            "the current intelligence pipeline."
        )

    if (
        _key(
            pipeline.get(
                "status"
            )
        )
        != "completed"
    ):
        raise ValueError(
            "Article adjudication requires "
            "a completed intelligence pipeline."
        )

    if (
        _key(
            pipeline.get(
                "mode"
            )
        )
        != "shadow"
    ):
        raise ValueError(
            "Article adjudication integration "
            "requires shadow intelligence mode."
        )

    pipeline_claim_id = _clean(
        pipeline.get(
            "claim_id"
        )
    )

    if (
        pipeline_claim_id
        and pipeline_claim_id
        != claim_id
    ):
        raise ValueError(
            "Article adjudication pipeline "
            "claim ID does not match."
        )

    live = pipeline.get(
        "live",
        {},
    )

    if not isinstance(
        live,
        dict,
    ):
        raise ValueError(
            "Article adjudication requires "
            "pipeline live-state metadata."
        )

    if (
        live.get(
            "merit_score_effect_enabled"
        )
        is not False
    ):
        raise ValueError(
            "Article adjudication runtime "
            "cannot consume a live Merit pipeline."
        )

    return pipeline


def _resolution(
    pipeline: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    stages = pipeline.get(
        "stages",
        {},
    )

    if not isinstance(
        stages,
        dict,
    ):
        return {}

    result = stages.get(
        "corroboration_resolution",
        {},
    )

    return (
        result
        if isinstance(
            result,
            dict,
        )
        else {}
    )


def _independence_batch(
    pipeline: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    stages = pipeline.get(
        "stages",
        {},
    )

    if not isinstance(
        stages,
        dict,
    ):
        return {}

    result = stages.get(
        "independence_batch",
        {},
    )

    return (
        result
        if isinstance(
            result,
            dict,
        )
        else {}
    )


def _target_stance(
    *,
    claim_id: str,
    resolution: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    stages = resolution.get(
        "stages",
        {},
    )

    if not isinstance(
        stages,
        dict,
    ):
        return {}

    stance = stages.get(
        "stance",
        {},
    )

    if not isinstance(
        stance,
        dict,
    ):
        return {}

    claims = stance.get(
        "claims",
        [],
    )

    if not isinstance(
        claims,
        list,
    ):
        return {}

    matches = [
        row
        for row in claims
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

    if len(
        matches
    ) > 1:
        raise ValueError(
            "Article adjudication found "
            "duplicate stance states."
        )

    return (
        matches[0]
        if matches
        else {}
    )


def _target_corroboration(
    *,
    claim_id: str,
    resolution: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    target = resolution.get(
        "target_claim",
        {},
    )

    if not isinstance(
        target,
        dict,
    ):
        return {}

    if (
        _clean(
            target.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        return {}

    return target


def _link_ids(
    rows: Any,
) -> List[str]:
    if not isinstance(
        rows,
        list,
    ):
        return []

    values = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        value = _clean(
            row.get(
                "id"
            )
            or row.get(
                "target_id"
            )
        )

        if value:
            values.append(
                value
            )

    return sorted(
        set(
            values
        )
    )


def _verified_independence_evidence_ids(
    batch: Dict[
        str,
        Any,
    ],
) -> List[str]:
    rows = batch.get(
        "results",
        [],
    )

    if not isinstance(
        rows,
        list,
    ):
        return []

    values = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        status = _key(
            row.get(
                "status"
            )
        )

        if status not in {
            "materialized_verified_independence",
            "already_materialized",
        }:
            continue

        materialization = row.get(
            "materialization"
        )

        if not isinstance(
            materialization,
            dict,
        ):
            continue

        evidence = materialization.get(
            "evidence"
        )

        if not isinstance(
            evidence,
            dict,
        ):
            continue

        evidence_id = _clean(
            evidence.get(
                "id"
            )
        )

        if evidence_id:
            values.append(
                evidence_id
            )

    return sorted(
        set(
            values
        )
    )


def _judgment(
    *,
    claim_id: str,
    field: str,
    value: str,
    suffix: str,
    evidence_ids: List[str],
) -> Dict[str, Any]:
    identity = {
        "claim_id": claim_id,
        "field": field,
        "value": value,
        "suffix": suffix,
        "evidence_ids": sorted(
            set(
                evidence_ids
            )
        ),
    }

    return {
        "id": _stable_id(
            identity,
            prefix=(
                "article-graph-judgment|"
            ),
        ),
        "field": field,
        "value": value,
        "confidence": 1.0,
        "evaluator_id": (
            ARTICLE_GRAPH_EVALUATOR_VERSION
        ),
        "evaluator_family": (
            ARTICLE_GRAPH_EVALUATOR_FAMILY
        ),
        "basis_class": (
            "provenance_graph"
        ),
        "evidence_ids": (
            identity[
                "evidence_ids"
            ]
        ),
        "training_eligible": False,
    }


def _run(
    *,
    claim_id: str,
    suffix: str,
    judgment: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    run_identity = {
        "claim_id": claim_id,
        "suffix": suffix,
        "judgment_id": (
            judgment[
                "id"
            ]
        ),
    }

    return {
        "run_id": _stable_id(
            run_identity,
            prefix=(
                "article-graph-run|"
            ),
        ),
        "evaluator_id": (
            ARTICLE_GRAPH_EVALUATOR_VERSION
        ),
        "evaluator_family": (
            ARTICLE_GRAPH_EVALUATOR_FAMILY
        ),

        # The graph itself is deterministic, but
        # parts of the persisted graph may originate
        # from model-assisted semantic extraction.
        # "mixed" deliberately prevents this runtime
        # from creating trusted training truth.
        "derivation_mode": "mixed",

        "judgments": [
            judgment
        ],
    }


def build_article_adjudication_evaluator_runs(
    *,
    claim_id: str,
    pipeline: Dict[
        str,
        Any,
    ],
) -> List[Dict[str, Any]]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Article adjudication claim ID "
            "is required."
        )

    pipeline = _require_pipeline(
        claim_id=(
            normalized_claim_id
        ),
        pipeline=pipeline,
    )

    resolution = _resolution(
        pipeline
    )

    stance = _target_stance(
        claim_id=(
            normalized_claim_id
        ),
        resolution=(
            resolution
        ),
    )

    target = _target_corroboration(
        claim_id=(
            normalized_claim_id
        ),
        resolution=(
            resolution
        ),
    )

    batch = _independence_batch(
        pipeline
    )

    runs = []

    support_ids = _link_ids(
        stance.get(
            "support_links",
            [],
        )
        if stance
        else []
    )

    contradiction_ids = _link_ids(
        stance.get(
            "contradiction_links",
            [],
        )
        if stance
        else []
    )

    if support_ids:
        runs.append(
            _run(
                claim_id=(
                    normalized_claim_id
                ),
                suffix="stance-support",
                judgment=_judgment(
                    claim_id=(
                        normalized_claim_id
                    ),
                    field="stance",
                    value="supports",
                    suffix=(
                        "stance-support"
                    ),
                    evidence_ids=(
                        support_ids
                    ),
                ),
            )
        )

    if contradiction_ids:
        runs.append(
            _run(
                claim_id=(
                    normalized_claim_id
                ),
                suffix=(
                    "stance-contradiction"
                ),
                judgment=_judgment(
                    claim_id=(
                        normalized_claim_id
                    ),
                    field="stance",
                    value="contradicts",
                    suffix=(
                        "stance-contradiction"
                    ),
                    evidence_ids=(
                        contradiction_ids
                    ),
                ),
            )
        )

    if target:
        independence_established = bool(
            target.get(
                "independent_support_established",
                False,
            )
        )

        dependency_ids = sorted(
            {
                _clean(
                    value
                )
                for value in target.get(
                    "recorded_support_dependency_ids",
                    [],
                )
                if _clean(
                    value
                )
            }
        )

        if independence_established:
            evidence_ids = (
                _verified_independence_evidence_ids(
                    batch
                )
            )

            runs.append(
                _run(
                    claim_id=(
                        normalized_claim_id
                    ),
                    suffix=(
                        "independence-established"
                    ),
                    judgment=_judgment(
                        claim_id=(
                            normalized_claim_id
                        ),
                        field=(
                            "independence_status"
                        ),
                        value="established",
                        suffix=(
                            "independence-established"
                        ),
                        evidence_ids=(
                            evidence_ids
                        ),
                    ),
                )
            )

        elif dependency_ids:
            runs.append(
                _run(
                    claim_id=(
                        normalized_claim_id
                    ),
                    suffix=(
                        "independence-not-established"
                    ),
                    judgment=_judgment(
                        claim_id=(
                            normalized_claim_id
                        ),
                        field=(
                            "independence_status"
                        ),
                        value=(
                            "not_established"
                        ),
                        suffix=(
                            "independence-not-established"
                        ),
                        evidence_ids=(
                            dependency_ids
                        ),
                    ),
                )
            )

        # No recorded dependency and no verified
        # independence is intentionally left without
        # a judgment. Absence of dependency is not
        # evidence of independence.

    return sorted(
        runs,
        key=lambda row: (
            row[
                "run_id"
            ]
        ),
    )


def _runtime_as_of(
    *,
    fallback_as_of: str,
    pipeline: Dict[
        str,
        Any,
    ],
) -> str:
    candidates = []

    fallback = _timestamp(
        fallback_as_of
    )

    if fallback is not None:
        candidates.append(
            fallback
        )

    batch = _independence_batch(
        pipeline
    )

    bundle = batch.get(
        "evidence_bundle",
        {},
    )

    if isinstance(
        bundle,
        dict,
    ):
        for collection_name in (
            "source_observations",
            "reporter_observations",
            "evidence_records",
        ):
            rows = bundle.get(
                collection_name,
                [],
            )

            if not isinstance(
                rows,
                list,
            ):
                continue

            for row in rows:
                if not isinstance(
                    row,
                    dict,
                ):
                    continue

                for key in (
                    "observed_at",
                    "published_at",
                ):
                    parsed = _timestamp(
                        row.get(
                            key
                        )
                    )

                    if parsed is not None:
                        candidates.append(
                            parsed
                        )

    for row in batch.get(
        "results",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        materialization = row.get(
            "materialization"
        )

        if not isinstance(
            materialization,
            dict,
        ):
            continue

        parsed = _timestamp(
            materialization.get(
                "verification_observed_at"
            )
        )

        if parsed is not None:
            candidates.append(
                parsed
            )

    if not candidates:
        raise ValueError(
            "Article adjudication requires "
            "a timezone-aware as-of timestamp."
        )

    return max(
        candidates
    ).isoformat()


def run_article_adjudication_runtime(
    *,
    claim: Dict[
        str,
        Any,
    ],
    pipeline: Dict[
        str,
        Any,
    ],
    as_of: str,
    connection_factory,
    latest_loader=(
        load_latest_adjudication_state_revision
    ),
    history_runner=(
        re_adjudicate_claim
    ),
) -> Dict[str, Any]:
    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Article adjudication claim "
            "must be a dictionary."
        )

    claim_id = _clean(
        claim.get(
            "id"
        )
    )

    if not claim_id:
        raise ValueError(
            "Article adjudication claim ID "
            "is required."
        )

    if connection_factory is None:
        raise ValueError(
            "Article adjudication requires "
            "database access."
        )

    evaluator_runs = (
        build_article_adjudication_evaluator_runs(
            claim_id=(
                claim_id
            ),
            pipeline=(
                pipeline
            ),
        )
    )

    fields_evaluated = sorted(
        {
            judgment[
                "field"
            ]
            for run in evaluator_runs
            for judgment in run.get(
                "judgments",
                [],
            )
            if isinstance(
                judgment,
                dict,
            )
        }
    )

    if not evaluator_runs:
        return {
            "version": (
                ARTICLE_ADJUDICATION_RUNTIME_VERSION
            ),
            "status": (
                "no_evaluator_runs"
            ),
            "claim_id": claim_id,
            "trigger_type": "",
            "revision_id": "",
            "transition_count": 0,
            "evaluator_run_count": 0,
            "fields_evaluated": [],
            "policy": {
                "fully_automatic": True,
                "unresolved_evidence_is_not_guessed": True,
                "model_derived_graph_is_not_trusted_training_truth": True,
                "does_not_change_live_merit": True,
            },
        }

    normalized_as_of = _runtime_as_of(
        fallback_as_of=as_of,
        pipeline=pipeline,
    )

    latest = latest_loader(
        claim_id=claim_id,
        connection_factory=(
            connection_factory
        ),
    )

    trigger_type = (
        "initial_evaluation"
        if latest is None
        else "evaluator_refresh"
    )

    history = history_runner(
        claim_id=claim_id,
        evaluator_runs=(
            evaluator_runs
        ),
        as_of=(
            normalized_as_of
        ),
        trigger_type=(
            trigger_type
        ),
        trigger_evidence_ids=[],
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        history,
        dict,
    ):
        raise RuntimeError(
            "Article adjudication history "
            "runner returned an invalid result."
        )

    revision = history.get(
        "revision",
        {},
    )

    if not isinstance(
        revision,
        dict,
    ):
        revision = {}

    persistence = history.get(
        "persistence",
        {},
    )

    if not isinstance(
        persistence,
        dict,
    ):
        persistence = {}

    transition_count = int(
        persistence.get(
            "transition_count",
            len(
                revision.get(
                    "transitions",
                    [],
                )
                if isinstance(
                    revision.get(
                        "transitions",
                        [],
                    ),
                    list,
                )
                else []
            ),
        )
        or 0
    )

    return {
        "version": (
            ARTICLE_ADJUDICATION_RUNTIME_VERSION
        ),
        "status": _clean(
            history.get(
                "status"
            )
            or "completed"
        ).lower(),
        "claim_id": claim_id,
        "trigger_type": (
            trigger_type
        ),
        "as_of": (
            normalized_as_of
        ),
        "revision_id": _clean(
            revision.get(
                "revision_id"
            )
        ),
        "transition_count": (
            transition_count
        ),
        "evaluator_run_count": (
            len(
                evaluator_runs
            )
        ),
        "fields_evaluated": (
            fields_evaluated
        ),
        "policy": {
            "fully_automatic": True,
            "uses_existing_persisted_corroboration_graph": True,
            "same_family_votes_do_not_create_false_consensus": True,
            "support_and_contradiction_can_remain_contested": True,
            "absence_of_dependency_does_not_establish_independence": True,
            "model_derived_graph_is_not_trusted_training_truth": True,
            "does_not_verify_new_evidence": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
        },
    }
