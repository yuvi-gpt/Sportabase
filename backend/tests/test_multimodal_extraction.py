import unittest

from app.services import (
    multimodal_extraction as mm,
)


OBSERVED = "2026-08-16T10:00:00Z"


class MultimodalExtractionTests(
    unittest.TestCase
):
    def test_structural_social_targets_and_ambiguous_shortlink(
        self,
    ):
        cases = [
            (
                "https://www.instagram.com/"
                "p/ABC_123/?utm_source=x",
                "instagram",
                "post",
                "ABC_123",
            ),
            (
                "https://instagram.com/"
                "reels/REEL123/",
                "instagram",
                "reel",
                "REEL123",
            ),
            (
                "https://instagram.com/"
                "stories/fabriziorom/555",
                "instagram",
                "story",
                "555",
            ),
            (
                "https://twitter.com/"
                "FabrizioRomano/status/"
                "1234567890123456789?s=20",
                "x",
                "post",
                "1234567890123456789",
            ),
            (
                "https://x.com/i/web/status/"
                "1234567890123456789",
                "x",
                "post",
                "1234567890123456789",
            ),
            (
                "https://www.tiktok.com/"
                "@club/video/"
                "7381234567890123456",
                "tiktok",
                "video",
                "7381234567890123456",
            ),
            (
                "https://reddit.com/r/soccer/"
                "comments/abc123/title/",
                "reddit",
                "post",
                "abc123",
            ),
            (
                "https://www.facebook.com/"
                "arsenal/posts/123456789",
                "facebook",
                "post",
                "123456789",
            ),
            (
                "https://www.facebook.com/"
                "watch?v=123456789",
                "facebook",
                "video",
                "123456789",
            ),
            (
                "https://youtu.be/"
                "abcDEF12345?t=10",
                "youtube",
                "video",
                "abcDEF12345",
            ),
        ]

        for (
            url,
            platform,
            surface,
            content_id,
        ) in cases:
            with self.subTest(
                url=url
            ):
                target = (
                    mm.detect_content_target(
                        url
                    )
                )

                self.assertEqual(
                    target.platform,
                    platform,
                )

                self.assertEqual(
                    target.surface,
                    surface,
                )

                self.assertEqual(
                    target.platform_content_id,
                    content_id,
                )

                self.assertTrue(
                    target.structurally_specific
                )

        shortlink = (
            mm.detect_content_target(
                "https://vm.tiktok.com/"
                "ZM123abc/"
            )
        )

        self.assertEqual(
            shortlink.platform,
            "tiktok",
        )

        self.assertEqual(
            shortlink.detection,
            "platform_only",
        )

        self.assertEqual(
            shortlink.platform_content_id,
            "",
        )

        self.assertFalse(
            shortlink.structurally_specific
        )

    def test_twitter_alias_canonicalizes_to_x_and_preserves_actor_hint(
        self,
    ):
        target = (
            mm.detect_content_target(
                "https://twitter.com/"
                "FabrizioRomano/status/"
                "1234567890123456789"
            )
        )

        self.assertEqual(
            target.platform,
            "x",
        )

        self.assertEqual(
            target.canonical_url,
            (
                "https://x.com/"
                "FabrizioRomano/status/"
                "1234567890123456789"
            ),
        )

        self.assertEqual(
            target.actor_hint[
                "handle"
            ],
            "FabrizioRomano",
        )

        self.assertEqual(
            target.actor_hint[
                "profile_url"
            ],
            (
                "https://x.com/"
                "FabrizioRomano"
            ),
        )

    def test_reddit_comment_parent_and_youtube_surfaces(
        self,
    ):
        reddit = (
            mm.detect_content_target(
                "https://www.reddit.com/"
                "r/soccer/comments/"
                "abc123/title/def456/"
            )
        )

        self.assertEqual(
            reddit.surface,
            "comment",
        )

        self.assertEqual(
            reddit.platform_content_id,
            "def456",
        )

        self.assertEqual(
            reddit.parent_content_id,
            "abc123",
        )

        short = (
            mm.detect_content_target(
                "https://youtube.com/"
                "shorts/abcDEF12345"
            )
        )

        self.assertEqual(
            short.surface,
            "short",
        )

        self.assertEqual(
            short.container_kind,
            "media",
        )

        self.assertEqual(
            short.platform_content_id,
            "abcDEF12345",
        )

        community = (
            mm.detect_content_target(
                "https://youtube.com/"
                "post/UgkxABC_123"
            )
        )

        self.assertEqual(
            community.surface,
            "community_post",
        )

        self.assertEqual(
            community.container_kind,
            "post",
        )

        self.assertEqual(
            community.platform_content_id,
            "UgkxABC_123",
        )

    def test_generic_web_strips_tracking_without_fabricating_content_id(
        self,
    ):
        target = (
            mm.detect_content_target(
                "https://example.com/"
                "story?id=7"
                "&utm_source=test"
                "&fbclid=nope"
                "#section"
            )
        )

        self.assertEqual(
            target.platform,
            "web",
        )

        self.assertEqual(
            target.surface,
            "web_page",
        )

        self.assertEqual(
            target.platform_content_id,
            "",
        )

        self.assertEqual(
            target.detection,
            "generic_web",
        )

        self.assertEqual(
            target.canonical_url,
            (
                "https://example.com/"
                "story?id=7"
            ),
        )

    def test_snapshot_identity_normalization_and_engagement_remain_structural(
        self,
    ):
        snapshot = (
            mm.ExtractedSnapshot(
                source_url=(
                    "https://twitter.com/"
                    "Reporter/status/"
                    "1234567890123456789"
                    "?s=20"
                ),
                extraction_method=(
                    "browser_dom"
                ),
                observed_at=(
                    OBSERVED
                ),
                payload={
                    "text": (
                        "Arsenal have "
                        "agreed a deal."
                    ),
                    "engagement": {
                        "likes": "12.5K",
                        "reposts": "1,234",
                    },
                },
                actor={
                    "handle": "@Reporter",
                    "display_name": (
                        "Reporter Name"
                    ),
                    "platform_actor_id": (
                        "actor-1"
                    ),
                },
            )
        )

        item = (
            mm.normalize_extracted_snapshot(
                snapshot
            )
        )

        self.assertEqual(
            item.item_id,
            (
                "x:"
                "1234567890123456789"
            ),
        )

        self.assertEqual(
            item.platform,
            "x",
        )

        self.assertEqual(
            item.actor.handle,
            "Reporter",
        )

        self.assertEqual(
            item.actor.display_name,
            "Reporter Name",
        )

        self.assertEqual(
            item.actor.platform_actor_id,
            "actor-1",
        )

        self.assertEqual(
            (
                item.text_components[
                    0
                ]
                .provenance
                .extraction_method
            ),
            "browser_dom",
        )

        self.assertEqual(
            (
                item.text_components[
                    0
                ]
                .provenance
                .observed_at
            ),
            OBSERVED,
        )

        self.assertEqual(
            (
                item.engagement_snapshots[
                    0
                ].metrics[
                    "likes"
                ]
            ),
            12500.0,
        )

        self.assertEqual(
            (
                item.engagement_snapshots[
                    0
                ].metrics[
                    "reposts"
                ]
            ),
            1234.0,
        )

        self.assertEqual(
            item.claim_candidates,
            [],
        )

        self.assertEqual(
            item.alignments,
            [],
        )

    def test_adapter_canonical_url_can_resolve_platform_only_shortlink(
        self,
    ):
        snapshot = (
            mm.ExtractedSnapshot(
                source_url=(
                    "https://vm.tiktok.com/"
                    "ZM123abc/"
                ),
                extraction_method=(
                    "browser_dom"
                ),
                observed_at=(
                    OBSERVED
                ),
                payload={
                    "canonical_url": (
                        "https://www."
                        "tiktok.com/@club/"
                        "video/"
                        "7381234567890123456"
                    ),
                    "caption": (
                        "Matchday."
                    ),
                    "media": [
                        {
                            "media_kind": (
                                "video"
                            ),
                            "media_url": (
                                "https://cdn."
                                "example/"
                                "video.mp4"
                            ),
                        }
                    ],
                },
            )
        )

        item = (
            mm.normalize_extracted_snapshot(
                snapshot
            )
        )

        self.assertEqual(
            item.platform,
            "tiktok",
        )

        self.assertEqual(
            item.platform_content_id,
            "7381234567890123456",
        )

        self.assertEqual(
            item.actor.handle,
            "club",
        )

        self.assertEqual(
            item.canonical_url,
            (
                "https://www."
                "tiktok.com/@club/"
                "video/"
                "7381234567890123456"
            ),
        )

    def test_snapshot_rejects_conflicts_semantic_fields_and_missing_observed_at(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            (
                mm.normalize_extracted_snapshot(
                    mm.ExtractedSnapshot(
                        source_url=(
                            "https://x.com/"
                            "a/status/111111"
                        ),
                        extraction_method=(
                            "dom"
                        ),
                        observed_at=(
                            OBSERVED
                        ),
                        payload={
                            (
                                "platform_"
                                "content_id"
                            ): "222222",
                            "text": "x",
                        },
                    )
                )
            )

        with self.assertRaises(
            ValueError
        ):
            (
                mm.normalize_extracted_snapshot(
                    mm.ExtractedSnapshot(
                        source_url=(
                            "https://x.com/"
                            "a/status/111111"
                        ),
                        extraction_method=(
                            "dom"
                        ),
                        observed_at=(
                            OBSERVED
                        ),
                        payload={
                            "text": "x",
                            "metadata": {
                                "nested": {
                                    (
                                        "merit_"
                                        "score"
                                    ): 99
                                }
                            },
                        },
                    )
                )
            )

        with self.assertRaises(
            ValueError
        ):
            (
                mm.normalize_extracted_snapshot(
                    mm.ExtractedSnapshot(
                        source_url=(
                            "https://x.com/"
                            "a/status/111111"
                        ),
                        extraction_method=(
                            "dom"
                        ),
                        observed_at=(
                            OBSERVED
                        ),
                        payload={
                            "text": "x",
                            "actor": {
                                "metadata": {
                                    "authority": (
                                        "official"
                                    )
                                }
                            },
                        },
                    )
                )
            )

        with self.assertRaises(
            ValueError
        ):
            (
                mm.normalize_extracted_snapshot(
                    mm.ExtractedSnapshot(
                        source_url=(
                            "https://x.com/"
                            "a/status/111111"
                        ),
                        extraction_method=(
                            "dom"
                        ),
                        observed_at="",
                        payload={
                            "text": "x"
                        },
                    )
                )
            )

    def test_article_bridge_preserves_legacy_extraction_without_truth_inference(
        self,
    ):
        item = (
            mm.bridge_article_resolution(
                source_url=(
                    "https://example.com/"
                    "news/story"
                    "?utm_source=test"
                ),
                canonical_url=(
                    "https://example.com/"
                    "news/story"
                ),
                observed_at=OBSERVED,
                article={
                    "title": (
                        "Transfer update"
                    ),
                    "text": (
                        "A sufficiently "
                        "meaningful legacy "
                        "article body for "
                        "the unified content "
                        "bridge."
                    ),
                    "extraction_method": (
                        "article"
                    ),
                    "paragraph_count": 3,
                },
                actor={
                    "display_name": (
                        "Example Sports"
                    )
                },
            )
        )

        self.assertEqual(
            item.platform,
            "web",
        )

        self.assertEqual(
            item.platform_surface,
            "article",
        )

        self.assertEqual(
            item.container_kind,
            "article",
        )

        self.assertEqual(
            item.actor.display_name,
            "Example Sports",
        )

        self.assertEqual(
            item.metadata[
                "legacy_bridge"
            ],
            "article",
        )

        self.assertEqual(
            item.metadata[
                (
                    "legacy_article_"
                    "extraction_method"
                )
            ],
            "article",
        )

        self.assertEqual(
            item.claim_candidates,
            [],
        )

        self.assertEqual(
            item.alignments,
            [],
        )

        self.assertEqual(
            (
                item.text_components[
                    0
                ]
                .provenance
                .extraction_method
            ),
            (
                "article_resolver:"
                "article"
            ),
        )

    def test_youtube_bridge_keeps_one_video_architecture_and_duration_changes_strategy(
        self,
    ):
        short_item = (
            mm.normalize_extracted_snapshot(
                mm.bridge_youtube_snapshot(
                    source_url=(
                        "https://youtube.com/"
                        "shorts/"
                        "abcDEF12345"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    title="Short",
                    transcript=(
                        "Existing transcript"
                    ),
                    duration_seconds=45,
                )
            )
        )

        short_plan = (
            mm.plan_content_item(
                short_item
            )
        )

        self.assertEqual(
            (
                short_item
                .media_components[
                    0
                ].media_kind
            ),
            "video",
        )

        self.assertEqual(
            (
                short_plan
                .short_video_component_ids
            ),
            (
                "video:0",
            ),
        )

        self.assertEqual(
            (
                short_plan
                .long_video_component_ids
            ),
            (),
        )

        self.assertEqual(
            (
                short_plan
                .transcription_component_ids
            ),
            (),
        )

        long_item = (
            mm.normalize_extracted_snapshot(
                mm.bridge_youtube_snapshot(
                    source_url=(
                        "https://youtube.com/"
                        "watch?v="
                        "abcDEF12345"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    title="Long",
                    duration_seconds=(
                        1200
                    ),
                )
            )
        )

        long_plan = (
            mm.plan_content_item(
                long_item
            )
        )

        self.assertEqual(
            (
                long_item
                .media_components[
                    0
                ].media_kind
            ),
            "video",
        )

        self.assertEqual(
            (
                long_plan
                .long_video_component_ids
            ),
            (
                "video:0",
            ),
        )

        self.assertEqual(
            (
                long_plan
                .short_video_component_ids
            ),
            (),
        )

        self.assertEqual(
            (
                long_plan
                .transcription_component_ids
            ),
            (
                "video:0",
            ),
        )

    def test_caption_media_stay_separate_and_alignment_is_only_planned(
        self,
    ):
        item = (
            mm.normalize_extracted_snapshot(
                mm.ExtractedSnapshot(
                    source_url=(
                        "https://instagram.com/"
                        "p/ABC123"
                    ),
                    extraction_method=(
                        "browser_dom"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    payload={
                        "caption": (
                            "Caption says "
                            "one thing."
                        ),
                        "media": [
                            {
                                "component_id": (
                                    "image:hero"
                                ),
                                "media_kind": (
                                    "image"
                                ),
                                "media_url": (
                                    "https://cdn."
                                    "example/a.jpg"
                                ),
                            }
                        ],
                        "engagement": {
                            "likes": "2M"
                        },
                    },
                )
            )
        )

        plan = (
            mm.plan_content_item(
                item
            )
        )

        self.assertEqual(
            [
                component.role
                for component
                in item.text_components
            ],
            [
                "caption"
            ],
        )

        self.assertEqual(
            [
                media.media_kind
                for media
                in item.media_components
            ],
            [
                "image"
            ],
        )

        self.assertEqual(
            item.alignments,
            [],
        )

        self.assertEqual(
            (
                plan
                .caption_media_alignment_pairs
            ),
            (
                (
                    "caption",
                    "image:hero",
                ),
            ),
        )

        self.assertEqual(
            (
                item.engagement_snapshots[
                    0
                ].metrics[
                    "likes"
                ]
            ),
            2000000.0,
        )

    def test_linked_existing_ocr_and_transcript_avoid_redundant_processing(
        self,
    ):
        item = (
            mm.normalize_extracted_snapshot(
                mm.ExtractedSnapshot(
                    source_url=(
                        "https://instagram.com/"
                        "p/ABC123"
                    ),
                    extraction_method=(
                        "browser_dom"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    payload={
                        "caption": (
                            "Two videos"
                        ),
                        "media": [
                            {
                                "component_id": (
                                    "video:a"
                                ),
                                "media_kind": (
                                    "video"
                                ),
                                "has_audio": (
                                    True
                                ),
                            },
                            {
                                "component_id": (
                                    "video:b"
                                ),
                                "media_kind": (
                                    "video"
                                ),
                                "has_audio": (
                                    True
                                ),
                            },
                        ],
                        "text_components": [
                            {
                                "component_id": (
                                    "ocr:a"
                                ),
                                "role": (
                                    "on_screen_text"
                                ),
                                "text": (
                                    "Score graphic"
                                ),
                                "metadata": {
                                    (
                                        "source_media_"
                                        "component_id"
                                    ): (
                                        "video:a"
                                    )
                                },
                            },
                            {
                                "component_id": (
                                    "transcript:b"
                                ),
                                "role": (
                                    "transcript"
                                ),
                                "text": (
                                    "Spoken words"
                                ),
                                "metadata": {
                                    (
                                        "source_media_"
                                        "component_id"
                                    ): (
                                        "video:b"
                                    )
                                },
                            },
                        ],
                    },
                )
            )
        )

        plan = (
            mm.plan_content_item(
                item
            )
        )

        self.assertNotIn(
            "video:a",
            plan.ocr_component_ids,
        )

        self.assertIn(
            "video:b",
            plan.ocr_component_ids,
        )

        self.assertIn(
            "video:a",
            (
                plan
                .transcription_component_ids
            ),
        )

        self.assertNotIn(
            "video:b",
            (
                plan
                .transcription_component_ids
            ),
        )

    def test_unknown_video_duration_remains_unknown(
        self,
    ):
        item = (
            mm.normalize_extracted_snapshot(
                mm.ExtractedSnapshot(
                    source_url=(
                        "https://instagram.com/"
                        "reel/ABC123"
                    ),
                    extraction_method=(
                        "browser_dom"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    payload={
                        "media": [
                            {
                                "component_id": (
                                    "video:0"
                                ),
                                "media_kind": (
                                    "video"
                                ),
                            }
                        ]
                    },
                )
            )
        )

        plan = (
            mm.plan_content_item(
                item
            )
        )

        self.assertEqual(
            plan.short_video_component_ids,
            (),
        )

        self.assertEqual(
            plan.long_video_component_ids,
            (),
        )

        self.assertEqual(
            (
                plan
                .unknown_duration_video_component_ids
            ),
            (
                "video:0",
            ),
        )

    def test_bundle_delegates_relationship_aliases_and_plans_dependency_and_conversation(
        self,
    ):
        bundle = (
            mm.normalize_extracted_bundle(
                mm.ExtractedBundle(
                    items=(
                        mm.ExtractedSnapshot(
                            source_url=(
                                "https://x.com/"
                                "a/status/111111"
                            ),
                            extraction_method=(
                                "dom"
                            ),
                            observed_at=(
                                OBSERVED
                            ),
                            payload={
                                "text": (
                                    "Original"
                                )
                            },
                        ),
                        mm.ExtractedSnapshot(
                            source_url=(
                                "https://x.com/"
                                "b/status/222222"
                            ),
                            extraction_method=(
                                "dom"
                            ),
                            observed_at=(
                                OBSERVED
                            ),
                            payload={
                                "text": (
                                    "Reposted "
                                    "representation"
                                )
                            },
                        ),
                        mm.ExtractedSnapshot(
                            source_url=(
                                "https://reddit.com/"
                                "r/soccer/comments/"
                                "abc123/title/"
                                "def456/"
                            ),
                            extraction_method=(
                                "api"
                            ),
                            observed_at=(
                                OBSERVED
                            ),
                            payload={
                                "text": "Reply"
                            },
                        ),
                    ),
                    root_indices=(
                        0,
                    ),
                    relationships=(
                        mm.ExtractedRelationship(
                            1,
                            0,
                            "derived_from",
                        ),
                        mm.ExtractedRelationship(
                            2,
                            0,
                            "reply",
                        ),
                    ),
                )
            )
        )

        relationship_types = [
            relationship
            .relationship_type
            for relationship
            in bundle.relationships
        ]

        self.assertEqual(
            relationship_types,
            [
                "derives_from",
                "reply_to",
            ],
        )

        plan = (
            mm.plan_content_bundle(
                bundle
            )
        )

        self.assertTrue(
            plan.dependency_tracing_required
        )

        self.assertTrue(
            (
                plan
                .conversation_traversal_required
            )
        )

        self.assertEqual(
            len(
                plan
                .dependency_relationship_ids
            ),
            1,
        )

        self.assertEqual(
            len(
                plan
                .conversation_relationship_ids
            ),
            1,
        )

    def test_relationship_metadata_cannot_smuggle_independence_or_truth(
        self,
    ):
        base = (
            mm.ExtractedSnapshot(
                source_url=(
                    "https://x.com/"
                    "a/status/111111"
                ),
                extraction_method="dom",
                observed_at=OBSERVED,
                payload={
                    "text": "A"
                },
            ),
            mm.ExtractedSnapshot(
                source_url=(
                    "https://x.com/"
                    "b/status/222222"
                ),
                extraction_method="dom",
                observed_at=OBSERVED,
                payload={
                    "text": "B"
                },
            ),
        )

        with self.assertRaises(
            ValueError
        ):
            mm.normalize_extracted_bundle(
                mm.ExtractedBundle(
                    items=base,
                    root_indices=(
                        0,
                    ),
                    relationships=(
                        mm.ExtractedRelationship(
                            1,
                            0,
                            "repost",
                            metadata={
                                (
                                    "independence_"
                                    "status"
                                ): (
                                    "independent"
                                )
                            },
                        ),
                    ),
                )
            )

        with self.assertRaises(
            ValueError
        ):
            mm.normalize_extracted_bundle(
                mm.ExtractedBundle(
                    items=base,
                    root_indices=(
                        0,
                    ),
                    relationships=(
                        mm.ExtractedRelationship(
                            1,
                            0,
                            "repost",
                            metadata={
                                "nested": {
                                    (
                                        "truth_"
                                        "status"
                                    ): (
                                        "true"
                                    )
                                }
                            },
                        ),
                    ),
                )
            )

    def test_build_processing_plan_dispatches_and_rejects_wrong_type(
        self,
    ):
        item = (
            mm.normalize_extracted_snapshot(
                mm.ExtractedSnapshot(
                    source_url=(
                        "https://x.com/"
                        "a/status/111111"
                    ),
                    extraction_method=(
                        "dom"
                    ),
                    observed_at=(
                        OBSERVED
                    ),
                    payload={
                        "text": "A"
                    },
                )
            )
        )

        item_plan = (
            mm.build_processing_plan(
                item
            )
        )

        self.assertIsInstance(
            item_plan,
            mm.ModalityProcessingPlan,
        )

        bundle = (
            mm.normalize_extracted_bundle(
                mm.ExtractedBundle(
                    items=(
                        mm.ExtractedSnapshot(
                            source_url=(
                                "https://x.com/"
                                "a/status/111111"
                            ),
                            extraction_method=(
                                "dom"
                            ),
                            observed_at=(
                                OBSERVED
                            ),
                            payload={
                                "text": "A"
                            },
                        ),
                    )
                )
            )
        )

        bundle_plan = (
            mm.build_processing_plan(
                bundle
            )
        )

        self.assertIsInstance(
            bundle_plan,
            mm.BundleProcessingPlan,
        )

        with self.assertRaises(
            TypeError
        ):
            mm.build_processing_plan(
                {
                    "item_id": (
                        "not-a-model"
                    )
                }
            )


if __name__ == "__main__":
    unittest.main()
