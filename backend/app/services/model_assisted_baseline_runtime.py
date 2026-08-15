import copy

from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    Optional,
)


from app.analysis.model_assisted_baseline import (
    MODEL_ASSISTED_BASELINE_VERSION,
    build_model_assisted_baseline_evaluator_runs,
)

from app.intelligence.adjudication_history import (
    AUTOMATED_ADJUDICATION_HISTORY_VERSION,
    load_latest_adjudication_state_revision,
    re_adjudicate_claim,
)

from app.services.snapshot_persistence import (
    MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION,
    persist_model_assisted_evidence_snapshot,
)


MODEL_ASSISTED_BASELINE_RUNTIME_VERSION = (
    "model-assisted-baseline-runtime-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _canonical_timestamp(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            "Model-assisted baseline timestamp "
            "is required."
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
        parsed = datetime.fromisoformat(
            candidate
        )

    except ValueError as exc:
        raise ValueError(
            "Model-assisted baseline timestamp "
            "must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            "Model-assisted baseline timestamp "
            "must include a timezone."
        )

    return parsed.isoformat()


def persist_model_assisted_baseline_revision(
    *,
    assembly: Dict[str, Any],
    semantic_assessment: Dict[str, Any],
    source_id: str,
    subject_key: str,
    reporter_id: Optional[str] = None,
    media_item_id: Optional[str] = None,
    story_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    normalize_url=None,
    connection_factory=None,
    snapshot_persister=(
        persist_model_assisted_evidence_snapshot
    ),
    latest_loader=(
        load_latest_adjudication_state_revision
    ),
    history_writer=(
        re_adjudicate_claim
    ),
) -> Dict[str, Any]:
    if not isinstance(
        assembly,
        dict,
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "assembly must be a dictionary."
        )

    if not isinstance(
        semantic_assessment,
        dict,
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "semantic assessment must be a dictionary."
        )

    if (
        normalize_url is None
        or connection_factory is None
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "requires URL normalization and DB access."
        )

    baseline = (
        build_model_assisted_baseline_evaluator_runs(
            semantic_assessment=(
                semantic_assessment
            )
        )
    )

    if (
        _clean(
            baseline.get(
                "version"
            )
        )
        != MODEL_ASSISTED_BASELINE_VERSION
    ):
        raise ValueError(
            "Unsupported model-assisted baseline version."
        )

    claim_id = _clean(
        assembly.get(
            "claim_id"
        )
    )

    source_url = _clean(
        assembly.get(
            "source_url"
        )
    )

    if not claim_id:
        raise ValueError(
            "Model-assisted baseline runtime "
            "claim ID is required."
        )

    if (
        baseline[
            "claim_id"
        ]
        != claim_id
    ):
        raise ValueError(
            "Model-assisted baseline claim ID "
            "does not match the snapshot assembly."
        )

    if (
        baseline[
            "source_url"
        ]
        != source_url
    ):
        raise ValueError(
            "Model-assisted baseline source URL "
            "does not match the snapshot assembly."
        )

    if (
        baseline[
            "scored_field_count"
        ]
        < 1
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "requires at least one scored field."
        )

    snapshot = assembly.get(
        "snapshot"
    )

    if not isinstance(
        snapshot,
        dict,
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "requires an assembled snapshot."
        )

    snapshot_as_of = _clean(
        snapshot.get(
            "as_of"
        )
    )

    if not snapshot_as_of:
        raise ValueError(
            "Model-assisted baseline runtime "
            "snapshot as-of time is required."
        )

    # Build and validate the baseline BEFORE persistence.
    # If the semantic packet is malformed, no DB state is
    # written at all.
    evaluator_runs = copy.deepcopy(
        baseline[
            "evaluator_runs"
        ]
    )

    for run in evaluator_runs:
        if (
            _clean(
                run.get(
                    "derivation_mode"
                )
            ).lower()
            != "model_assisted"
        ):
            raise ValueError(
                "Baseline runtime refuses "
                "non-model-assisted evaluator runs."
            )

        for judgment in run.get(
            "judgments",
            [],
        ):
            if bool(
                judgment.get(
                    "training_eligible"
                )
            ):
                raise ValueError(
                    "Model-assisted baseline judgment "
                    "cannot be training eligible."
                )

            if judgment.get(
                "evidence_ids"
            ):
                raise ValueError(
                    "Model-assisted baseline must not "
                    "claim evidence before persistence."
                )

    persistence = snapshot_persister(
        assembly=assembly,
        source_id=source_id,
        subject_key=subject_key,
        reporter_id=reporter_id,
        media_item_id=media_item_id,
        story_id=story_id,
        recorded_at=recorded_at,
        normalize_url=normalize_url,
        connection_factory=connection_factory,
    )

    if not isinstance(
        persistence,
        dict,
    ):
        raise ValueError(
            "Snapshot persistence returned "
            "an invalid result."
        )

    if (
        _clean(
            persistence.get(
                "version"
            )
        )
        != MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION
    ):
        raise ValueError(
            "Unsupported snapshot persistence version."
        )

    if (
        _clean(
            persistence.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Snapshot persistence claim ID "
            "does not match baseline claim."
        )

    evidence = persistence.get(
        "snapshot_evidence"
    )

    if not isinstance(
        evidence,
        dict,
    ):
        raise ValueError(
            "Snapshot persistence did not return "
            "snapshot evidence."
        )

    evidence_id = _clean(
        evidence.get(
            "id"
        )
    )

    verification_status = _clean(
        evidence.get(
            "verification_status"
        )
    ).lower()

    if not evidence_id:
        raise ValueError(
            "Persisted snapshot evidence ID "
            "is required."
        )

    if (
        verification_status
        != "unverified"
    ):
        raise ValueError(
            "Model-assisted baseline evidence "
            "must remain unverified."
        )

    # Now that the evidence is real and persisted,
    # bind that exact evidence ID into every baseline
    # judgment. This is lineage only; it does not make
    # the model judgment trusted.
    for run in evaluator_runs:
        for judgment in run.get(
            "judgments",
            [],
        ):
            judgment[
                "evidence_ids"
            ] = [
                evidence_id
            ]

            judgment[
                "training_eligible"
            ] = False

    baseline_run_ids = {
        _clean(
            run.get(
                "run_id"
            )
        )
        for run
        in evaluator_runs
        if _clean(
            run.get(
                "run_id"
            )
        )
    }

    latest = latest_loader(
        claim_id=claim_id,
        connection_factory=(
            connection_factory
        ),
    )

    latest_run_ids = set()

    if isinstance(
        latest,
        dict,
    ):
        latest_adjudication = (
            latest.get(
                "adjudication",
                {},
            )
        )

        if isinstance(
            latest_adjudication,
            dict,
        ):
            latest_evaluators = (
                latest_adjudication.get(
                    "evaluators",
                    [],
                )
            )

            if isinstance(
                latest_evaluators,
                list,
            ):
                latest_run_ids = {
                    _clean(
                        run.get(
                            "run_id"
                        )
                    )
                    for run
                    in latest_evaluators
                    if (
                        isinstance(
                            run,
                            dict,
                        )
                        and _clean(
                            run.get(
                                "run_id"
                            )
                        )
                    )
                }

    baseline_already_present = bool(
        latest is not None
        and baseline_run_ids
        and baseline_run_ids.issubset(
            latest_run_ids
        )
    )

    exact_baseline_leaf = bool(
        baseline_already_present
        and latest_run_ids
        == baseline_run_ids
        and _canonical_timestamp(
            latest.get(
                "as_of"
            )
        )
        == _canonical_timestamp(
            snapshot_as_of
        )
        and latest.get(
            "trigger"
        )
        == {
            "type": "evidence_added",
            "evidence_ids": [
                evidence_id
            ],
        }
    )

    if exact_baseline_leaf:
        # Preserve existing replay semantics for the
        # isolated baseline revision.
        history = history_writer(
            claim_id=claim_id,
            evaluator_runs=evaluator_runs,
            as_of=snapshot_as_of,
            trigger_type="evidence_added",
            trigger_evidence_ids=[
                evidence_id
            ],
            recorded_at=recorded_at,
            connection_factory=(
                connection_factory
            ),
        )

    elif baseline_already_present:
        # A later revision already carries these
        # baseline runs. Never rewind the append-only
        # chain just to recreate the old baseline leaf.
        history = {
            "version": (
                AUTOMATED_ADJUDICATION_HISTORY_VERSION
            ),
            "status": (
                "baseline_already_present"
            ),
            "revision": latest,
            "persistence": {
                "status": "unchanged",
                "transition_count": 0,
            },
        }

    elif latest is not None:
        # Existing pre-#8A history: defer persistence
        # until the article runtime writes one combined
        # evaluator refresh containing both old graph
        # evidence and the new baseline runs.
        history = {
            "version": (
                AUTOMATED_ADJUDICATION_HISTORY_VERSION
            ),
            "status": (
                "baseline_deferred_to_combined_refresh"
            ),
            "revision": latest,
            "persistence": {
                "status": "unchanged",
                "transition_count": 0,
            },
        }

    else:
        history = history_writer(
            claim_id=claim_id,
            evaluator_runs=evaluator_runs,
            as_of=snapshot_as_of,
            trigger_type="evidence_added",
            trigger_evidence_ids=[
                evidence_id
            ],
            recorded_at=recorded_at,
            connection_factory=(
                connection_factory
            ),
        )

    if not isinstance(
        history,
        dict,
    ):
        raise ValueError(
            "Adjudication history returned "
            "an invalid result."
        )

    if (
        _clean(
            history.get(
                "version"
            )
        )
        != AUTOMATED_ADJUDICATION_HISTORY_VERSION
    ):
        raise ValueError(
            "Unsupported adjudication history version."
        )

    revision = history.get(
        "revision"
    )

    if not isinstance(
        revision,
        dict,
    ):
        raise ValueError(
            "Baseline runtime requires a persisted "
            "adjudication revision."
        )

    history_status = _clean(
        history.get(
            "status"
        )
    ).lower()

    baseline_leaf_statuses = {
        "persisted",
        "replayed",
    }

    carried_history_statuses = {
        "baseline_already_present",
        (
            "baseline_deferred_to_"
            "combined_refresh"
        ),
    }

    if (
        history_status
        not in (
            baseline_leaf_statuses
            | carried_history_statuses
        )
    ):
        raise ValueError(
            "Model-assisted baseline runtime "
            "received an unsupported history status."
        )

    # A newly created/replayed baseline leaf must be
    # directly anchored to the persisted unverified
    # snapshot evidence.
    #
    # A later combined revision is different: it may
    # legitimately use evaluator_refresh or another
    # later trigger while still carrying the original
    # baseline evaluator runs. Do not rewind that
    # append-only history just to recreate evidence_added.
    if history_status in baseline_leaf_statuses:
        trigger = revision.get(
            "trigger"
        )

        if not isinstance(
            trigger,
            dict,
        ):
            raise ValueError(
                "Baseline revision trigger is missing."
            )

        if (
            _clean(
                trigger.get(
                    "type"
                )
            ).lower()
            != "evidence_added"
        ):
            raise ValueError(
                "Baseline revision must use "
                "the evidence_added trigger."
            )

        if trigger.get(
            "evidence_ids"
        ) != [
            evidence_id
        ]:
            raise ValueError(
                "Baseline revision trigger lineage "
                "does not match persisted evidence."
            )

    return {
        "version": (
            MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
        ),
        "status": (
            history.get(
                "status"
            )
        ),
        "claim_id": claim_id,
        "snapshot_persistence": (
            persistence
        ),
        "baseline": baseline,
        "bound_evaluator_runs": (
            evaluator_runs
        ),
        "adjudication_history": (
            history
        ),
        "revision": revision,
        "snapshot_evidence_id": (
            evidence_id
        ),
        "policy": {
            "snapshot_persisted_before_history": True,
            "baseline_lineage_uses_persisted_evidence": True,
            "snapshot_evidence_remains_unverified": True,
            "baseline_derivation_remains_model_assisted": True,
            "model_output_is_not_truth": True,
            "model_output_is_not_self_validating": True,
            "training_eligible": False,
            "append_only_adjudication_history": True,
            "exact_replay_is_idempotent": True,
            "later_combined_revision_is_not_rewound": True,
            "existing_history_can_defer_baseline_to_combined_refresh": True,
            "human_review_required": False,
            "does_not_train_model": True,
            "does_not_verify_evidence": True,
            "does_not_change_live_merit": True,
        },
    }