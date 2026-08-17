from __future__ import annotations

import json
import math
import sqlite3

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from app.intelligence.stories import story_id_for_canonical_key
from app.services import inbox_candidate_shadow_orchestration
from app.services import inbox_story_cluster_orchestration
from app.services import multimodal_binding_registration
from app.services import multimodal_inbox_shadow_orchestration
from app.services import multimodal_shadow_orchestration


STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION = (
    "story-claim-graph-materialization-v1"
)

STORY_CANONICAL_KEY_PREFIX = (
    "multimodal-exact-claim-v1"
)

STORY_CLAIM_RELATIONSHIP_TYPE = (
    "exact_claim_group"
)

STORY_CLAIM_LINK_BASIS = (
    "downstream_exact_common_claim_id"
)

STORY_MEDIA_RELATIONSHIP_TYPE = (
    "exact_claim_member"
)

STORY_MEDIA_STRUCTURAL_CONFIDENCE = 1.0


class StoryClaimGraphMaterializationError(RuntimeError):
    pass


class StoryClaimGraphMaterializationInputError(
    StoryClaimGraphMaterializationError
):
    pass


class StoryClaimGraphMaterializationPersistenceError(
    StoryClaimGraphMaterializationError
):
    pass


class StoryClaimGraphMaterializationIntegrityError(
    StoryClaimGraphMaterializationError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _mapping(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StoryClaimGraphMaterializationIntegrityError(
            label + " must be an object."
        )

    return dict(value)


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _one(conn, sql: str, params=()):
    row = conn.execute(
        sql,
        params,
    ).fetchone()

    if row is None:
        return None

    return dict(row)


def _cluster_policy(
    result: Mapping[str, Any],
) -> Dict[str, Any]:
    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster safety policy is missing."
        )

    required_true = (
        "cluster_is_routing_candidate_only",
        "cluster_selection_is_read_only",
        "same_story_not_established_by_cluster",
        "same_claim_not_established_by_cluster",
        "claim_groups_formed_only_from_downstream_exact_claim_ids",
        "each_completed_member_passed_exact_common_claim_gate",
        "each_member_revalidated_by_candidate_gate",
        "cluster_does_not_write_story_records_directly",
        "cluster_does_not_link_story_media_directly",
        "cluster_level_corroboration_not_established",
        "cluster_level_independence_not_established",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Story-cluster safety boundary missing: "
                + field
            )

    required_false = (
        "cluster_merit_aggregation_performed",
        "synthetic_merit_baseline_used",
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(policy.get(field)):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Story-cluster enabled forbidden field: "
                + field
            )

    return dict(policy)


def _registration_for_member(
    member: Mapping[str, Any],
    *,
    anchor_capture_record_id: str,
    subject_entity_id: str,
) -> Dict[str, str]:
    candidate_id = _clean(
        member.get("capture_record_id")
    )
    claim_id = _clean(
        member.get("claim_id")
    )

    if not candidate_id or not claim_id:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Completed story-cluster member is incomplete."
        )

    candidate = _mapping(
        member.get("orchestration"),
        label="Candidate shadow result",
    )

    if (
        _clean(candidate.get("version"))
        != (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        )
        or _clean(candidate.get("status")).lower()
        != "completed_shadow"
        or _clean(candidate.get("claim_id"))
        != claim_id
        or _clean(
            candidate.get("anchor_capture_record_id")
        )
        != anchor_capture_record_id
        or _clean(
            candidate.get("candidate_capture_record_id")
        )
        != candidate_id
        or _clean(candidate.get("subject_entity_id"))
        != subject_entity_id
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Candidate shadow provenance changed."
        )

    inbox = _mapping(
        candidate.get("orchestration"),
        label="Inbox shadow result",
    )

    if (
        _clean(inbox.get("version"))
        != (
            multimodal_inbox_shadow_orchestration
            .MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
        )
        or _clean(inbox.get("status")).lower()
        != "completed_shadow"
        or _clean(inbox.get("claim_id"))
        != claim_id
        or _clean(
            inbox.get("left_capture_record_id")
        )
        != anchor_capture_record_id
        or _clean(
            inbox.get("right_capture_record_id")
        )
        != candidate_id
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Inbox shadow provenance changed."
        )

    orchestration = _mapping(
        inbox.get("orchestration"),
        label="Multimodal shadow orchestration",
    )

    if (
        _clean(orchestration.get("version"))
        != (
            multimodal_shadow_orchestration
            .MULTIMODAL_SHADOW_ORCHESTRATION_VERSION
        )
        or _clean(orchestration.get("status")).lower()
        != "completed_shadow"
        or _clean(orchestration.get("claim_id"))
        != claim_id
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Multimodal orchestration provenance changed."
        )

    registration = _mapping(
        orchestration.get("registration"),
        label="Binding registration",
    )

    if (
        _clean(registration.get("version"))
        != (
            multimodal_binding_registration
            .MULTIMODAL_BINDING_REGISTRATION_VERSION
        )
        or _clean(registration.get("status")).lower()
        != "registered"
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Binding registration version/status changed."
        )

    subject = _mapping(
        registration.get("subject"),
        label="Binding subject",
    )

    if (
        _clean(subject.get("entity_id"))
        != subject_entity_id
        or not _clean(subject.get("entity_key"))
        or _clean(registration.get("subject_key"))
        != _clean(subject.get("entity_key"))
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Binding registration subject changed."
        )

    left = _mapping(
        registration.get("left"),
        label="Left binding",
    )
    right = _mapping(
        registration.get("right"),
        label="Right binding",
    )

    left_media_id = _clean(
        left.get("media_item_id")
    )
    right_media_id = _clean(
        right.get("media_item_id")
    )

    if (
        not left_media_id
        or not right_media_id
        or left_media_id == right_media_id
        or _clean(left.get("story_id"))
        or _clean(right.get("story_id"))
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Binding registration media scope is invalid."
        )

    registration_policy = registration.get(
        "policy"
    )

    if (
        not isinstance(registration_policy, Mapping)
        or registration_policy.get(
            "source_and_media_persisted_atomically"
        )
        is not True
        or bool(
            registration_policy.get(
                "story_record_created"
            )
        )
        or bool(
            registration_policy.get(
                "establishes_truth"
            )
        )
        or bool(
            registration_policy.get(
                "affects_live_merit"
            )
        )
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Binding registration safety boundary changed."
        )

    return {
        "candidate_capture_record_id": candidate_id,
        "claim_id": claim_id,
        "subject_key": _clean(
            subject.get("entity_key")
        ),
        "anchor_media_item_id": left_media_id,
        "candidate_media_item_id": right_media_id,
    }


def _validated_cluster(
    value: Any,
) -> Dict[str, Any]:
    result = _mapping(
        value,
        label="Story-cluster result",
    )

    if (
        _clean(result.get("version"))
        != (
            inbox_story_cluster_orchestration
            .MULTIMODAL_INBOX_STORY_CLUSTER_VERSION
        )
        or _clean(result.get("status")).lower()
        != "completed_shadow"
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster version/status is invalid."
        )

    _cluster_policy(result)

    anchor_id = _clean(
        result.get("anchor_capture_record_id")
    )
    subject_entity_id = _clean(
        result.get("selected_subject_entity_id")
    )

    if not anchor_id or not subject_entity_id:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster anchor/subject scope is missing."
        )

    claim_ids = result.get("claim_ids")
    claim_groups = result.get("claim_groups")
    completed_members = result.get(
        "completed_members"
    )
    selected_member_ids = result.get(
        "selected_candidate_capture_record_ids"
    )

    if (
        not isinstance(claim_ids, list)
        or not claim_ids
        or not isinstance(claim_groups, list)
        or not claim_groups
        or not isinstance(completed_members, list)
        or not completed_members
        or not isinstance(selected_member_ids, list)
        or not selected_member_ids
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster exact-claim membership is incomplete."
        )

    normalized_claim_ids = [
        _clean(item)
        for item in claim_ids
    ]

    if (
        any(not item for item in normalized_claim_ids)
        or normalized_claim_ids
        != sorted(set(normalized_claim_ids))
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster claim IDs are not canonical."
        )

    member_by_capture: Dict[str, Dict[str, str]] = {}
    anchor_media_item_id = ""
    subject_key = ""

    for raw_member in completed_members:
        member = _mapping(
            raw_member,
            label="Completed story-cluster member",
        )
        normalized = _registration_for_member(
            member,
            anchor_capture_record_id=anchor_id,
            subject_entity_id=subject_entity_id,
        )
        candidate_id = normalized[
            "candidate_capture_record_id"
        ]

        if candidate_id in member_by_capture:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Story-cluster contains a duplicate completed member."
            )

        if (
            anchor_media_item_id
            and normalized["anchor_media_item_id"]
            != anchor_media_item_id
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Story-cluster anchor media identity changed between members."
            )

        if (
            subject_key
            and normalized["subject_key"]
            != subject_key
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Story-cluster subject key changed between members."
            )

        anchor_media_item_id = normalized[
            "anchor_media_item_id"
        ]
        subject_key = normalized[
            "subject_key"
        ]
        member_by_capture[
            candidate_id
        ] = normalized

    normalized_selected_ids = [
        _clean(item)
        for item in selected_member_ids
    ]

    if (
        any(not item for item in normalized_selected_ids)
        or len(normalized_selected_ids)
        != len(set(normalized_selected_ids))
        or set(normalized_selected_ids)
        != set(member_by_capture)
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-cluster selected-member scope changed."
        )

    groups = []
    grouped_member_ids = []
    seen_group_claim_ids = set()

    for raw_group in claim_groups:
        group = _mapping(
            raw_group,
            label="Exact claim group",
        )
        claim_id = _clean(
            group.get("claim_id")
        )
        member_ids = group.get(
            "member_capture_record_ids"
        )

        if (
            not claim_id
            or claim_id in seen_group_claim_ids
            or not isinstance(member_ids, list)
            or not member_ids
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Exact claim group is invalid."
            )

        normalized_member_ids = [
            _clean(item)
            for item in member_ids
        ]

        if (
            any(
                not item
                for item in normalized_member_ids
            )
            or normalized_member_ids
            != sorted(
                set(normalized_member_ids)
            )
            or int(group.get("member_count") or 0)
            != len(normalized_member_ids)
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Exact claim group membership is not canonical."
            )

        media_ids = [
            anchor_media_item_id
        ]

        for candidate_id in normalized_member_ids:
            member = member_by_capture.get(
                candidate_id
            )

            if (
                member is None
                or member["claim_id"] != claim_id
            ):
                raise StoryClaimGraphMaterializationIntegrityError(
                    "Exact claim group does not match completed-member provenance."
                )

            media_ids.append(
                member[
                    "candidate_media_item_id"
                ]
            )
            grouped_member_ids.append(
                candidate_id
            )

        if len(media_ids) != len(set(media_ids)):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Exact claim group contains duplicate media identity."
            )

        groups.append({
            "claim_id": claim_id,
            "member_capture_record_ids": normalized_member_ids,
            "media_item_ids": media_ids,
        })
        seen_group_claim_ids.add(claim_id)

    if (
        sorted(seen_group_claim_ids)
        != normalized_claim_ids
        or sorted(grouped_member_ids)
        != sorted(member_by_capture)
        or len(grouped_member_ids)
        != len(set(grouped_member_ids))
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Exact claim groups do not partition completed members exactly once."
        )

    return {
        "anchor_capture_record_id": anchor_id,
        "selected_subject_entity_id": subject_entity_id,
        "subject_key": subject_key,
        "anchor_media_item_id": anchor_media_item_id,
        "claim_ids": normalized_claim_ids,
        "groups": groups,
    }


def _assert_media_exists(
    conn,
    media_item_id: str,
) -> Dict[str, Any]:
    row = _one(
        conn,
        """
        SELECT *
        FROM media_items
        WHERE id = ?
        """,
        (media_item_id,),
    )

    if row is None:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Validated story member media item is missing."
        )

    return row


def _upsert_story(
    conn,
    *,
    claim: Mapping[str, Any],
    subject_entity_id: str,
    subject_key: str,
    linked_at: str,
) -> Dict[str, Any]:
    claim_id = _clean(claim.get("id"))
    canonical_key = (
        STORY_CANONICAL_KEY_PREFIX
        + "|claim:"
        + claim_id
    )
    story_id = story_id_for_canonical_key(
        canonical_key
    )
    canonical_title = _clean(
        claim.get("canonical_text")
    )
    metadata_json = _json({
        "materialization_version": (
            STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION
        ),
        "materialization_basis": (
            STORY_CLAIM_LINK_BASIS
        ),
        "claim_id": claim_id,
        "subject_entity_id": subject_entity_id,
        "subject_key": subject_key,
        "truth_established": False,
        "authority_established": False,
        "independence_established": False,
        "affects_live_merit": False,
    })

    existing_by_key = _one(
        conn,
        """
        SELECT *
        FROM intelligence_stories
        WHERE canonical_key = ?
        """,
        (canonical_key,),
    )

    existing_by_id = _one(
        conn,
        """
        SELECT *
        FROM intelligence_stories
        WHERE id = ?
        """,
        (story_id,),
    )

    if (
        existing_by_key is not None
        and _clean(existing_by_key.get("id"))
        != story_id
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Deterministic story canonical key resolved to an unexpected ID."
        )

    if (
        existing_by_id is not None
        and _clean(existing_by_id.get("canonical_key"))
        != canonical_key
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Deterministic story ID collision detected."
        )

    conn.execute(
        """
        INSERT INTO intelligence_stories (
          id,
          canonical_key,
          canonical_title,
          status,
          first_seen_at,
          last_seen_at,
          metadata_json
        )
        VALUES (?, ?, ?, 'developing', ?, ?, ?)
        ON CONFLICT(canonical_key)
        DO UPDATE SET
          canonical_title = CASE
            WHEN excluded.canonical_title != ''
            THEN excluded.canonical_title
            ELSE intelligence_stories.canonical_title
          END,
          last_seen_at = excluded.last_seen_at,
          metadata_json = excluded.metadata_json
        """,
        (
            story_id,
            canonical_key,
            canonical_title,
            linked_at,
            linked_at,
            metadata_json,
        ),
    )

    story = _one(
        conn,
        """
        SELECT *
        FROM intelligence_stories
        WHERE canonical_key = ?
        """,
        (canonical_key,),
    )

    if (
        story is None
        or _clean(story.get("id")) != story_id
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story materialization identity validation failed."
        )

    return story


def _link_story_claim(
    conn,
    *,
    story_id: str,
    claim_id: str,
    linked_at: str,
) -> Dict[str, Any]:
    metadata_json = _json({
        "materialization_version": (
            STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION
        ),
        "truth_established": False,
        "authority_established": False,
        "independence_established": False,
        "affects_live_merit": False,
    })

    conn.execute(
        """
        INSERT INTO story_claim_links (
          story_id,
          claim_id,
          relationship_type,
          link_basis,
          linked_at,
          metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(story_id, claim_id)
        DO NOTHING
        """,
        (
            story_id,
            claim_id,
            STORY_CLAIM_RELATIONSHIP_TYPE,
            STORY_CLAIM_LINK_BASIS,
            linked_at,
            metadata_json,
        ),
    )

    row = _one(
        conn,
        """
        SELECT *
        FROM story_claim_links
        WHERE story_id = ?
          AND claim_id = ?
        """,
        (story_id, claim_id),
    )

    if (
        row is None
        or _clean(row.get("relationship_type"))
        != STORY_CLAIM_RELATIONSHIP_TYPE
        or _clean(row.get("link_basis"))
        != STORY_CLAIM_LINK_BASIS
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-claim link conflicts with validated exact-claim provenance."
        )

    return row


def _link_story_media(
    conn,
    *,
    story_id: str,
    media_item_id: str,
    linked_at: str,
) -> Dict[str, Any]:
    existing = _one(
        conn,
        """
        SELECT *
        FROM story_media_links
        WHERE story_id = ?
          AND media_item_id = ?
        """,
        (story_id, media_item_id),
    )

    if existing is None:
        conn.execute(
            """
            INSERT INTO story_media_links (
              story_id,
              media_item_id,
              relationship_type,
              confidence,
              linked_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                story_id,
                media_item_id,
                STORY_MEDIA_RELATIONSHIP_TYPE,
                STORY_MEDIA_STRUCTURAL_CONFIDENCE,
                linked_at,
            ),
        )
    else:
        try:
            confidence = float(
                existing.get("confidence")
            )
        except (TypeError, ValueError) as error:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Existing story-media structural confidence is invalid."
            ) from error

        if (
            _clean(existing.get("relationship_type"))
            != STORY_MEDIA_RELATIONSHIP_TYPE
            or not math.isfinite(confidence)
            or abs(
                confidence
                - STORY_MEDIA_STRUCTURAL_CONFIDENCE
            )
            > 1e-9
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Existing story-media link conflicts with exact-claim membership."
            )

    row = _one(
        conn,
        """
        SELECT *
        FROM story_media_links
        WHERE story_id = ?
          AND media_item_id = ?
        """,
        (story_id, media_item_id),
    )

    if row is None:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story-media link persistence failed."
        )

    return row


def materialize_story_claim_graph(
    *,
    cluster_result: Mapping[str, Any],
    connection_factory,
    now_provider=_now,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise StoryClaimGraphMaterializationInputError(
            "Connection factory is required."
        )

    normalized = _validated_cluster(
        cluster_result
    )
    linked_at = _clean(
        now_provider()
    )

    if not linked_at:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story graph materialization timestamp is unavailable."
        )

    try:
        conn = connection_factory()
    except Exception as error:
        raise StoryClaimGraphMaterializationPersistenceError(
            "Story graph database is unavailable."
        ) from error

    if conn is None:
        raise StoryClaimGraphMaterializationPersistenceError(
            "Story graph database is unavailable."
        )

    stories = []

    try:
        conn.execute("BEGIN IMMEDIATE")

        entity = _one(
            conn,
            """
            SELECT *
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                normalized[
                    "selected_subject_entity_id"
                ],
            ),
        )

        if (
            entity is None
            or _clean(entity.get("entity_key"))
            != normalized["subject_key"]
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Validated story subject identity is not persisted consistently."
            )

        _assert_media_exists(
            conn,
            normalized[
                "anchor_media_item_id"
            ],
        )

        for group in normalized["groups"]:
            claim_id = group["claim_id"]
            claim = _one(
                conn,
                """
                SELECT *
                FROM intelligence_claims
                WHERE id = ?
                """,
                (claim_id,),
            )

            if claim is None:
                raise StoryClaimGraphMaterializationIntegrityError(
                    "Validated exact claim is not persisted."
                )

            if (
                _clean(claim.get("subject_key"))
                != normalized["subject_key"]
            ):
                raise StoryClaimGraphMaterializationIntegrityError(
                    "Validated claim subject does not match cluster subject."
                )

            for media_item_id in group[
                "media_item_ids"
            ]:
                _assert_media_exists(
                    conn,
                    media_item_id,
                )

            story = _upsert_story(
                conn,
                claim=claim,
                subject_entity_id=(
                    normalized[
                        "selected_subject_entity_id"
                    ]
                ),
                subject_key=(
                    normalized["subject_key"]
                ),
                linked_at=linked_at,
            )

            _link_story_claim(
                conn,
                story_id=story["id"],
                claim_id=claim_id,
                linked_at=linked_at,
            )

            for media_item_id in group[
                "media_item_ids"
            ]:
                _link_story_media(
                    conn,
                    story_id=story["id"],
                    media_item_id=media_item_id,
                    linked_at=linked_at,
                )

            stories.append({
                "story_id": story["id"],
                "canonical_key": story[
                    "canonical_key"
                ],
                "claim_id": claim_id,
                "anchor_media_item_id": (
                    normalized[
                        "anchor_media_item_id"
                    ]
                ),
                "member_media_item_ids": [
                    item
                    for item in group[
                        "media_item_ids"
                    ]
                    if item
                    != normalized[
                        "anchor_media_item_id"
                    ]
                ],
                "media_item_ids": list(
                    group["media_item_ids"]
                ),
            })

        conn.commit()

    except StoryClaimGraphMaterializationError:
        conn.rollback()
        raise
    except sqlite3.Error as error:
        conn.rollback()
        raise StoryClaimGraphMaterializationPersistenceError(
            "Story graph persistence failed."
        ) from error
    except Exception as error:
        conn.rollback()
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story graph materialization failed closed."
        ) from error
    finally:
        conn.close()

    if len(stories) != len(
        normalized["claim_ids"]
    ):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Story graph did not materialize every exact claim group."
        )

    story_ids = sorted({
        item["story_id"]
        for item in stories
    })

    if len(story_ids) != len(stories):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Multiple exact claim groups collapsed into one story identity."
        )

    return {
        "version": (
            STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION
        ),
        "status": "materialized",
        "anchor_capture_record_id": (
            normalized[
                "anchor_capture_record_id"
            ]
        ),
        "selected_subject_entity_id": (
            normalized[
                "selected_subject_entity_id"
            ]
        ),
        "claim_ids": list(
            normalized["claim_ids"]
        ),
        "story_ids": story_ids,
        "story_count": len(stories),
        "stories": stories,
        "policy": {
            "source_cluster_version_required": True,
            "materialization_requires_downstream_exact_claim_groups": True,
            "nested_binding_provenance_required": True,
            "persisted_claim_subject_must_match_cluster_subject": True,
            "persisted_media_identity_required": True,
            "one_deterministic_story_per_exact_claim_id": True,
            "story_claim_edge_persisted": True,
            "story_media_links_persisted": True,
            "materialization_is_atomic": True,
            "materialization_is_idempotent": True,
            "raw_candidate_scores_not_persisted": True,
            "rejected_cluster_members_not_persisted": True,
            "structural_link_confidence_is_not_truth_confidence": True,
            "story_membership_does_not_establish_truth": True,
            "story_membership_does_not_establish_authority": True,
            "story_membership_does_not_establish_independence": True,
            "story_membership_does_not_verify_evidence": True,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
