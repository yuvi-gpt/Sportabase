import sys
import unittest

from pathlib import Path

from pydantic import ValidationError


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.models import content


class UnifiedContentModelTests(
    unittest.TestCase
):
    def text(
        self,
        component_id,
        role,
        text,
        **kwargs,
    ):
        return content.TextComponent(
            component_id=component_id,
            role=role,
            text=text,
            **kwargs,
        )

    def test_platform_is_metadata_and_version_is_stable(
        self,
    ):
        for platform in (
            "instagram",
            "x",
            "tiktok",
            "reddit",
            "facebook",
            "youtube",
            "future-platform",
        ):
            with self.subTest(
                platform=platform
            ):
                item = (
                    content
                    .UnifiedContentItem(
                        item_id=(
                            "item-"
                            + platform
                        ),
                        platform=platform,
                        container_kind="post",
                        text_components=[
                            self.text(
                                "body",
                                "body",
                                (
                                    "A sports "
                                    "claim."
                                ),
                            )
                        ],
                    )
                )

                (
                    content
                    .validate_unified_content_item(
                        item
                    )
                )

                self.assertEqual(
                    item.version,
                    (
                        "unified-content-"
                        "model-v1"
                    ),
                )

                self.assertEqual(
                    item.platform,
                    platform,
                )

    def test_reel_keeps_caption_transcript_ocr_and_claim_origins_separate(
        self,
    ):
        item = (
            content
            .UnifiedContentItem(
                item_id="ig-reel",
                platform="instagram",
                platform_surface="reel",
                container_kind="post",
                text_components=[
                    self.text(
                        "caption",
                        "caption",
                        (
                            "Follow for "
                            "giveaways and "
                            "more football "
                            "content."
                        ),
                    ),
                    self.text(
                        "transcript",
                        "transcript",
                        (
                            "The manager says "
                            "the player will "
                            "miss Sunday."
                        ),
                        start_seconds=2.0,
                        end_seconds=6.0,
                    ),
                    self.text(
                        "ocr",
                        "on_screen_text",
                        (
                            "Player ruled out "
                            "for Sunday"
                        ),
                    ),
                ],
                media_components=[
                    content.MediaComponent(
                        component_id="video",
                        media_kind="video",
                        duration_seconds=28.0,
                        has_audio=True,
                    )
                ],
                claim_candidates=[
                    (
                        content
                        .ContentClaimCandidate(
                            candidate_id=(
                                "spoken-claim"
                            ),
                            text=(
                                "The player will "
                                "miss Sunday."
                            ),
                            origin_component_ids=[
                                "transcript",
                                "ocr",
                            ],
                            extraction_method=(
                                "multimodal"
                            ),
                            extraction_confidence=(
                                0.95
                            ),
                        )
                    ),
                    (
                        content
                        .ContentClaimCandidate(
                            candidate_id=(
                                "caption-claim"
                            ),
                            text=(
                                "The account "
                                "promotes a "
                                "giveaway."
                            ),
                            origin_component_ids=[
                                "caption"
                            ],
                            extraction_method=(
                                "text"
                            ),
                            extraction_confidence=(
                                0.9
                            ),
                        )
                    ),
                ],
                alignments=[
                    (
                        content
                        .AlignmentAssessment(
                            left_component_id=(
                                "caption"
                            ),
                            right_component_id=(
                                "transcript"
                            ),
                            status="unrelated",
                            confidence=0.96,
                            method=(
                                "semantic_alignment"
                            ),
                        )
                    ),
                    (
                        content
                        .AlignmentAssessment(
                            left_component_id=(
                                "ocr"
                            ),
                            right_component_id=(
                                "transcript"
                            ),
                            status="aligned",
                            confidence=0.93,
                            method=(
                                "semantic_alignment"
                            ),
                        )
                    ),
                ],
            )
        )

        (
            content
            .validate_unified_content_item(
                item
            )
        )

        self.assertEqual(
            item.alignments[0].status,
            "unrelated",
        )

        self.assertEqual(
            (
                item
                .claim_candidates[0]
                .origin_component_ids
            ),
            [
                "transcript",
                "ocr",
            ],
        )

        self.assertEqual(
            (
                item
                .claim_candidates[1]
                .origin_component_ids
            ),
            [
                "caption"
            ],
        )

    def test_native_surface_does_not_force_media_kind(
        self,
    ):
        still_reel = (
            content
            .UnifiedContentItem(
                item_id="still-reel",
                platform="instagram",
                platform_surface="reel",
                container_kind="post",
                media_components=[
                    content.MediaComponent(
                        component_id="image",
                        media_kind="image",
                        sequence_index=0,
                    ),
                    content.MediaComponent(
                        component_id="music",
                        media_kind="audio",
                        duration_seconds=15.0,
                    ),
                ],
            )
        )

        carousel = (
            content
            .UnifiedContentItem(
                item_id="carousel",
                platform="instagram",
                platform_surface="carousel",
                container_kind="post",
                text_components=[
                    self.text(
                        "slide-caption",
                        "caption",
                        (
                            "Second slide "
                            "caption."
                        ),
                        sequence_index=1,
                    )
                ],
                media_components=[
                    content.MediaComponent(
                        component_id="slide-0",
                        media_kind="image",
                        sequence_index=0,
                    ),
                    content.MediaComponent(
                        component_id="slide-1",
                        media_kind="video",
                        sequence_index=1,
                        duration_seconds=12.0,
                    ),
                ],
            )
        )

        (
            content
            .validate_unified_content_item(
                still_reel
            )
        )

        (
            content
            .validate_unified_content_item(
                carousel
            )
        )

        self.assertEqual(
            [
                value.media_kind
                for value
                in still_reel.media_components
            ],
            [
                "image",
                "audio",
            ],
        )

        self.assertEqual(
            [
                value.media_kind
                for value
                in carousel.media_components
            ],
            [
                "image",
                "video",
            ],
        )

    def test_video_duration_and_ephemerality_are_properties_not_platforms(
        self,
    ):
        short = content.MediaComponent(
            component_id="short",
            media_kind="video",
            duration_seconds=42.0,
        )

        long = content.MediaComponent(
            component_id="long",
            media_kind="video",
            duration_seconds=7200.0,
        )

        self.assertEqual(
            short.media_kind,
            long.media_kind,
        )

        self.assertLess(
            short.duration_seconds,
            long.duration_seconds,
        )

        story = (
            content
            .UnifiedContentItem(
                item_id="story",
                platform="tiktok",
                platform_surface="story",
                container_kind="story",
                observed_at=(
                    "2026-08-16T08:00:00Z"
                ),
                ephemeral=True,
                expires_at=(
                    "2026-08-17T08:00:00Z"
                ),
                media_components=[
                    content.MediaComponent(
                        component_id=(
                            "story-image"
                        ),
                        media_kind="image",
                    )
                ],
            )
        )

        (
            content
            .validate_unified_content_item(
                story
            )
        )

        self.assertTrue(
            story.ephemeral
        )

    def test_conversation_and_dependency_relationships_share_one_graph(
        self,
    ):
        def make_item(
            item_id,
            platform,
            kind,
            text,
        ):
            return (
                content
                .UnifiedContentItem(
                    item_id=item_id,
                    platform=platform,
                    container_kind=kind,
                    text_components=[
                        self.text(
                            (
                                item_id
                                + "-text"
                            ),
                            "body",
                            text,
                        )
                    ],
                )
            )

        root = make_item(
            "root",
            "reddit",
            "thread",
            "Initial claim.",
        )

        comment = make_item(
            "comment",
            "reddit",
            "comment",
            "Official link here.",
        )

        quote = make_item(
            "quote",
            "x",
            "post",
            "Quoting the report.",
        )

        reel = (
            content
            .UnifiedContentItem(
                item_id="reel",
                platform="instagram",
                platform_surface="reel",
                container_kind="post",
                media_components=[
                    content.MediaComponent(
                        component_id=(
                            "reel-video"
                        ),
                        media_kind="video",
                        duration_seconds=20.0,
                    )
                ],
            )
        )

        bundle = (
            content
            .UnifiedContentBundle(
                bundle_id="graph",
                root_item_ids=[
                    "root"
                ],
                items=[
                    root,
                    comment,
                    quote,
                    reel,
                ],
                relationships=[
                    (
                        content
                        .ContentRelationship(
                            relationship_id=(
                                "reply"
                            ),
                            source_item_id=(
                                "comment"
                            ),
                            target_item_id=(
                                "root"
                            ),
                            relationship_type=(
                                "reply_to"
                            ),
                        )
                    ),
                    (
                        content
                        .ContentRelationship(
                            relationship_id=(
                                "quote-rel"
                            ),
                            source_item_id=(
                                "quote"
                            ),
                            target_item_id=(
                                "root"
                            ),
                            relationship_type=(
                                "quote_of"
                            ),
                        )
                    ),
                    (
                        content
                        .ContentRelationship(
                            relationship_id=(
                                "derived"
                            ),
                            source_item_id=(
                                "reel"
                            ),
                            target_item_id=(
                                "quote"
                            ),
                            relationship_type=(
                                "derives_from"
                            ),
                        )
                    ),
                ],
            )
        )

        (
            content
            .validate_unified_content_bundle(
                bundle
            )
        )

        self.assertEqual(
            [
                value.relationship_type
                for value
                in bundle.relationships
            ],
            [
                "reply_to",
                "quote_of",
                "derives_from",
            ],
        )

    def test_engagement_is_attention_metadata_not_truth(
        self,
    ):
        item = (
            content
            .UnifiedContentItem(
                item_id="reddit-post",
                platform="reddit",
                container_kind="post",
                text_components=[
                    self.text(
                        "body",
                        "body",
                        (
                            "Highly upvoted "
                            "claim."
                        ),
                    )
                ],
                engagement_snapshots=[
                    (
                        content
                        .EngagementSnapshot(
                            observed_at=(
                                "2026-08-16"
                                "T08:00:00Z"
                            ),
                            metrics={
                                "upvotes": 10000,
                                "comments": 800,
                            },
                        )
                    )
                ],
            )
        )

        (
            content
            .validate_unified_content_item(
                item
            )
        )

        self.assertEqual(
            (
                item
                .engagement_snapshots[0]
                .metrics["upvotes"]
            ),
            10000.0,
        )

        with self.assertRaises(
            ValidationError
        ):
            content.EngagementSnapshot(
                metrics={
                    "upvotes": 10000
                },
                truth_status="verified",
            )

        with self.assertRaises(
            ValidationError
        ):
            (
                content
                .ContentClaimCandidate(
                    candidate_id="unsafe",
                    text="Claim",
                    origin_component_ids=[
                        "body"
                    ],
                    authority_class=(
                        "direct"
                    ),
                )
            )

    def test_cross_reference_and_temporal_invariants_fail_closed(
        self,
    ):
        bad_claim = (
            content
            .UnifiedContentItem(
                item_id="bad-claim",
                platform="x",
                container_kind="post",
                text_components=[
                    self.text(
                        "body",
                        "body",
                        "Claim.",
                    )
                ],
                claim_candidates=[
                    (
                        content
                        .ContentClaimCandidate(
                            candidate_id=(
                                "claim"
                            ),
                            text="Claim.",
                            origin_component_ids=[
                                "missing"
                            ],
                        )
                    )
                ],
            )
        )

        bad_alignment = (
            content
            .UnifiedContentItem(
                item_id="bad-alignment",
                platform="instagram",
                container_kind="post",
                text_components=[
                    self.text(
                        "caption",
                        "caption",
                        "Caption.",
                    )
                ],
                alignments=[
                    (
                        content
                        .AlignmentAssessment(
                            left_component_id=(
                                "caption"
                            ),
                            right_component_id=(
                                "missing"
                            ),
                        )
                    )
                ],
            )
        )

        bad_time = (
            content
            .UnifiedContentItem(
                item_id="bad-time",
                platform="youtube",
                container_kind="media",
                text_components=[
                    self.text(
                        "transcript",
                        "transcript",
                        "Timed speech.",
                        start_seconds=10.0,
                        end_seconds=5.0,
                    )
                ],
            )
        )

        for value in (
            bad_claim,
            bad_alignment,
            bad_time,
        ):
            with self.subTest(
                item=value.item_id
            ):
                with self.assertRaises(
                    ValueError
                ):
                    (
                        content
                        .validate_unified_content_item(
                            value
                        )
                    )

    def test_mutable_defaults_are_not_shared(
        self,
    ):
        first = (
            content
            .UnifiedContentItem(
                item_id="first",
                platform="x",
                container_kind="post",
            )
        )

        second = (
            content
            .UnifiedContentItem(
                item_id="second",
                platform="x",
                container_kind="post",
            )
        )

        first.metadata[
            "x"
        ] = 1

        first.text_components.append(
            self.text(
                "body",
                "body",
                "Text",
            )
        )

        self.assertEqual(
            second.metadata,
            {},
        )

        self.assertEqual(
            second.text_components,
            [],
        )


if __name__ == "__main__":
    unittest.main()
