import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.services import (
    content_normalization
    as normalization,
)


class ContentNormalizationTests(
    unittest.TestCase
):
    def test_messy_platform_aliases_normalize_without_platform_logic(
        self,
    ):
        item = (
            normalization
            .normalize_content_item(
                {
                    "source_platform": (
                        " Twitter "
                    ),
                    "format": " TWEET ",
                    "post_id": "12345",
                    "text": (
                        "  Arsenal   have "
                        "signed Player X. "
                    ),
                }
            )
        )

        self.assertEqual(
            item.platform,
            "x",
        )

        self.assertEqual(
            item.platform_surface,
            "post",
        )

        self.assertEqual(
            item.item_id,
            "x:12345",
        )

        self.assertEqual(
            item.text_components[
                0
            ].text,
            (
                "Arsenal have signed "
                "Player X."
            ),
        )

    def test_caption_transcript_and_ocr_stay_separate(
        self,
    ):
        item = (
            normalization
            .normalize_content_item(
                {
                    "platform": (
                        "Instagram"
                    ),
                    "surface": "REEL",
                    "url": (
                        "https://"
                        "instagram.com/"
                        "reel/example"
                    ),
                    "caption": (
                        "Follow for prizes."
                    ),
                    "transcript": (
                        "The manager says "
                        "the player is out."
                    ),
                    "on_screen_text": [
                        "PLAYER OUT",
                        "SUNDAY MATCH",
                    ],
                    "media": [
                        {
                            "type": "video",
                            "duration": 25,
                            "has_audio": True,
                        }
                    ],
                }
            )
        )

        roles = [
            component.role
            for component
            in item.text_components
        ]

        self.assertEqual(
            roles,
            [
                "caption",
                "transcript",
                "on_screen_text",
                "on_screen_text",
            ],
        )

        self.assertEqual(
            item.claim_candidates,
            [],
        )

        self.assertEqual(
            item.alignments,
            [],
        )

    def test_still_reel_and_mixed_carousel_do_not_force_video(
        self,
    ):
        reel = (
            normalization
            .normalize_content_item(
                {
                    "platform": (
                        "instagram"
                    ),
                    "surface": "reels",
                    "content_id": "r1",
                    "media": [
                        {
                            "type": "photo"
                        },
                        {
                            "type": "audio",
                            "duration": "15",
                        },
                    ],
                }
            )
        )

        carousel = (
            normalization
            .normalize_content_item(
                {
                    "platform": (
                        "instagram"
                    ),
                    "surface": (
                        "carousel"
                    ),
                    "content_id": "c1",
                    "media": [
                        {
                            "type": "image"
                        },
                        {
                            "type": "clip",
                            "duration": 11,
                        },
                    ],
                }
            )
        )

        self.assertEqual(
            [
                value.media_kind
                for value
                in reel.media_components
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

    def test_engagement_suffixes_are_attention_only(
        self,
    ):
        item = (
            normalization
            .normalize_content_item(
                {
                    "platform": "reddit",
                    "content_id": "abc",
                    "body": (
                        "A heavily upvoted "
                        "claim."
                    ),
                    "engagement": {
                        "upvotes": "12.5K",
                        "comments": "1,234",
                        "views": "2M",
                    },
                }
            )
        )

        metrics = (
            item
            .engagement_snapshots[
                0
            ]
            .metrics
        )

        self.assertEqual(
            metrics["upvotes"],
            12500.0,
        )

        self.assertEqual(
            metrics["comments"],
            1234.0,
        )

        self.assertEqual(
            metrics["views"],
            2000000.0,
        )

        self.assertFalse(
            hasattr(
                item,
                "truth_status",
            )
        )

    def test_actor_aliases_normalize_identity_without_authority(
        self,
    ):
        item = (
            normalization
            .normalize_content_item(
                {
                    "platform": "x",
                    "content_id": "99",
                    "body": "Statement.",
                    "author": {
                        "id": "actor-1",
                        "username": (
                            "@ExampleFC"
                        ),
                        "name": (
                            "Example FC"
                        ),
                        "url": (
                            "https://x.com/"
                            "ExampleFC"
                        ),
                    },
                }
            )
        )

        self.assertEqual(
            item.actor.platform_actor_id,
            "actor-1",
        )

        self.assertEqual(
            item.actor.handle,
            "ExampleFC",
        )

        self.assertEqual(
            item.actor.display_name,
            "Example FC",
        )

        self.assertFalse(
            hasattr(
                item.actor,
                "authority_class",
            )
        )

    def test_story_preserves_ephemerality_and_provenance(
        self,
    ):
        item = (
            normalization
            .normalize_content_item(
                {
                    "platform": "tiktok",
                    "surface": "story",
                    "content_id": "story-7",
                    "captured_at": (
                        "2026-08-16T"
                        "08:00:00Z"
                    ),
                    "ephemeral": "true",
                    "expires_at": (
                        "2026-08-17T"
                        "08:00:00Z"
                    ),
                    "media": [
                        {
                            "type": "still"
                        }
                    ],
                    "provenance": {
                        "extraction_method": (
                            "browser_dom"
                        ),
                        (
                            "extraction_confidence"
                        ): 0.91,
                    },
                }
            )
        )

        self.assertTrue(
            item.ephemeral
        )

        self.assertEqual(
            item.container_kind,
            "story",
        )

        self.assertEqual(
            (
                item
                .media_components[
                    0
                ]
                .provenance
                .extraction_method
            ),
            "browser_dom",
        )

        self.assertEqual(
            (
                item
                .media_components[
                    0
                ]
                .provenance
                .extraction_confidence
            ),
            0.91,
        )

    def test_semantic_intelligence_fields_fail_closed(
        self,
    ):
        unsafe_payloads = [
            {
                "platform": "x",
                "content_id": "1",
                "body": "Claim.",
                "truth_status": (
                    "verified"
                ),
            },
            {
                "platform": "reddit",
                "content_id": "2",
                "body": "Claim.",
                "authority_class": (
                    "direct"
                ),
            },
            {
                "platform": (
                    "facebook"
                ),
                "content_id": "3",
                "body": "Claim.",
                "merit_score": 99,
            },
        ]

        for payload in unsafe_payloads:
            with self.subTest(
                payload=payload
            ):
                with self.assertRaises(
                    ValueError
                ):
                    (
                        normalization
                        .normalize_content_item(
                            payload
                        )
                    )

    def test_normalization_is_deterministic_and_unknown_fields_fail_closed(
        self,
    ):
        payload = {
            "platform": "youtube",
            "surface": "shorts",
            "url": (
                "https://youtube.com/"
                "shorts/example"
            ),
            "title": "Match update",
            "media": [
                {
                    "kind": "video",
                    "duration": "42",
                    "width": "1080",
                    "height": "1920",
                }
            ],
            "metadata": {
                "adapter": "test"
            },
        }

        first = (
            normalization
            .normalize_content_item(
                payload
            )
        )

        second = (
            normalization
            .normalize_content_item(
                payload
            )
        )

        self.assertEqual(
            first.item_id,
            second.item_id,
        )

        self.assertEqual(
            (
                normalization
                .normalized_item_fingerprint(
                    first
                )
            ),
            (
                normalization
                .normalized_item_fingerprint(
                    second
                )
            ),
        )

        self.assertEqual(
            first.platform_surface,
            "short",
        )

        with self.assertRaises(
            ValueError
        ):
            (
                normalization
                .normalize_content_item(
                    {
                        **payload,
                        (
                            "mystery_platform_"
                            "field"
                        ): "value",
                    }
                )
            )


    def test_reddit_thread_normalizes_as_bundle_graph(
        self,
    ):
        bundle = normalization.normalize_content_bundle(
            {
                "roots": ["post-1"],
                "items": [
                    {
                        "platform": "reddit",
                        "surface": "thread",
                        "content_id": "post-1",
                        "body": (
                            "Initial claim which may be wrong."
                        ),
                    },
                    {
                        "platform": "reddit",
                        "surface": "comment",
                        "content_id": "comment-1",
                        "body": (
                            "The official club statement says otherwise."
                        ),
                    },
                ],
                "relationships": [
                    {
                        "source": "comment-1",
                        "target": "post-1",
                        "type": "reply",
                    }
                ],
            }
        )

        self.assertEqual(
            bundle.root_item_ids,
            ["reddit:post-1"],
        )

        relation = bundle.relationships[0]

        self.assertEqual(
            relation.source_item_id,
            "reddit:comment-1",
        )

        self.assertEqual(
            relation.target_item_id,
            "reddit:post-1",
        )

        self.assertEqual(
            relation.relationship_type,
            "reply_to",
        )

    def test_cross_platform_derivation_uses_same_graph(
        self,
    ):
        bundle = normalization.normalize_content_bundle(
            {
                "roots": "tweet-1",
                "items": [
                    {
                        "platform": "twitter",
                        "content_id": "tweet-1",
                        "body": "Original report.",
                    },
                    {
                        "platform": "instagram",
                        "surface": "reel",
                        "content_id": "reel-1",
                        "media": [
                            {
                                "type": "video",
                                "duration": 20,
                            }
                        ],
                    },
                ],
                "relationships": [
                    {
                        "from": "reel-1",
                        "to": "tweet-1",
                        "relation": "derived_from",
                    }
                ],
            }
        )

        relation = bundle.relationships[0]

        self.assertEqual(
            relation.source_item_id,
            "instagram:reel-1",
        )

        self.assertEqual(
            relation.target_item_id,
            "x:tweet-1",
        )

        self.assertEqual(
            relation.relationship_type,
            "derives_from",
        )

    def test_quote_repost_and_crosspost_aliases_normalize(
        self,
    ):
        results = []

        for alias in (
            "quote",
            "retweet",
            "crosspost",
        ):
            bundle = normalization.normalize_content_bundle(
                {
                    "roots": "a",
                    "items": [
                        {
                            "platform": "x",
                            "content_id": "a",
                            "body": "A",
                        },
                        {
                            "platform": "x",
                            "content_id": "b",
                            "body": "B",
                        },
                    ],
                    "relationships": [
                        {
                            "source": "b",
                            "target": "a",
                            "type": alias,
                        }
                    ],
                }
            )

            results.append(
                bundle.relationships[
                    0
                ].relationship_type
            )

        self.assertEqual(
            results,
            [
                "quote_of",
                "repost_of",
                "crosspost_of",
            ],
        )

    def test_single_item_bundle_infers_safe_root(
        self,
    ):
        bundle = normalization.normalize_content_bundle(
            {
                "items": [
                    {
                        "platform": "facebook",
                        "content_id": "post-7",
                        "body": "Club update.",
                    }
                ]
            }
        )

        self.assertEqual(
            bundle.root_item_ids,
            ["facebook:post-7"],
        )

    def test_multi_item_bundle_without_root_fails_closed(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            normalization.normalize_content_bundle(
                {
                    "items": [
                        {
                            "platform": "reddit",
                            "content_id": "one",
                            "body": "One",
                        },
                        {
                            "platform": "reddit",
                            "content_id": "two",
                            "body": "Two",
                        },
                    ]
                }
            )

    def test_bad_relationships_and_semantic_fields_fail_closed(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            normalization.normalize_content_bundle(
                {
                    "roots": "root",
                    "items": [
                        {
                            "platform": "x",
                            "content_id": "root",
                            "body": "Root",
                        }
                    ],
                    "relationships": [
                        {
                            "source": "missing",
                            "target": "root",
                            "type": "reply",
                        }
                    ],
                }
            )

        with self.assertRaises(
            ValueError
        ):
            normalization.normalize_content_bundle(
                {
                    "items": [
                        {
                            "platform": "x",
                            "content_id": "1",
                            "body": "Claim",
                        }
                    ],
                    "truth_status": "verified",
                }
            )

        with self.assertRaises(
            ValueError
        ):
            normalization.normalize_content_bundle(
                {
                    "roots": "1",
                    "items": [
                        {
                            "platform": "x",
                            "content_id": "1",
                            "body": "One",
                        },
                        {
                            "platform": "x",
                            "content_id": "2",
                            "body": "Two",
                        },
                    ],
                    "relationships": [
                        {
                            "source": "2",
                            "target": "1",
                            "type": "quote",
                            "authority_class": "direct",
                        }
                    ],
                }
            )

    def test_bundle_normalization_is_deterministic(
        self,
    ):
        payload = {
            "roots": "root",
            "items": [
                {
                    "platform": "reddit",
                    "content_id": "root",
                    "body": "Root claim.",
                },
                {
                    "platform": "reddit",
                    "content_id": "reply",
                    "body": "Reply.",
                },
            ],
            "relationships": [
                {
                    "source": "reply",
                    "target": "root",
                    "type": "reply",
                }
            ],
        }

        first = normalization.normalize_content_bundle(
            payload
        )

        second = normalization.normalize_content_bundle(
            payload
        )

        self.assertEqual(
            first.bundle_id,
            second.bundle_id,
        )

        self.assertEqual(
            first.relationships[
                0
            ].relationship_id,
            second.relationships[
                0
            ].relationship_id,
        )

        self.assertEqual(
            normalization.normalized_bundle_fingerprint(
                first
            ),
            normalization.normalized_bundle_fingerprint(
                second
            ),
        )

if __name__ == "__main__":
    unittest.main()