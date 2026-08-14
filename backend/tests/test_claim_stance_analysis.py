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

from app import main


class ClaimStanceAnalysisTests(
    unittest.TestCase
):
    def claim(self):
        return {
            "id": "claim-1",
            "canonical_key": (
                "transfer|a|b|agreement"
            ),
            "subject_key": "transfer|a|b",
            "canonical_text": (
                "Agreement reached."
            ),
            "claim_type": "assertion",
        }

    def link(
        self,
        *,
        link_id,
        relationship_type,
        target_id="obs-1",
        observed_at=(
            "2026-08-13T14:00:00+00:00"
        ),
    ):
        return {
            "id": link_id,
            "claim_id": "claim-1",
            "target_type": (
                "source_observation"
            ),
            "target_id": target_id,
            "relationship_type": (
                relationship_type
            ),
            "confidence": 0.9,
            "observed_at": observed_at,
        }

    def test_dictionary_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_stance_analysis(
                []
            )

    def test_aligned_to_is_neutral(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id="link-1",
                            relationship_type=(
                                "ALIGNED_TO"
                            ),
                        )
                    ],
                }
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "no_explicit_stance",
        )

        self.assertEqual(
            claim["counts"][
                "neutral_alignment_links"
            ],
            1,
        )

        self.assertEqual(
            claim["counts"][
                "support_links"
            ],
            0,
        )

    def test_support_is_explicit_stance(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id="support-1",
                            relationship_type=(
                                " SUPPORTS "
                            ),
                        )
                    ],
                }
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "explicit_support",
        )

        self.assertEqual(
            claim[
                "support_links"
            ][0]["stance"],
            "support",
        )

    def test_contradiction_is_explicit_stance(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id=(
                                "contradiction-1"
                            ),
                            relationship_type=(
                                "CONTRADICTS"
                            ),
                        )
                    ],
                }
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "explicit_contradiction"
            ),
        )

        self.assertEqual(
            claim[
                "contradiction_links"
            ][0]["stance"],
            "contradiction",
        )

    def test_support_and_contradiction_are_mixed(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id="support-1",
                            relationship_type=(
                                "supports"
                            ),
                            target_id="obs-1",
                        ),
                        self.link(
                            link_id=(
                                "contradiction-1"
                            ),
                            relationship_type=(
                                "contradicts"
                            ),
                            target_id="obs-2",
                        ),
                    ],
                }
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "mixed_explicit_stance",
        )

        self.assertEqual(
            claim["counts"][
                "support_links"
            ],
            1,
        )

        self.assertEqual(
            claim["counts"][
                "contradiction_links"
            ],
            1,
        )

    def test_unknown_relationship_is_not_coerced(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id="unknown-1",
                            relationship_type=(
                                "mentions"
                            ),
                        )
                    ],
                }
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "no_explicit_stance",
        )

        self.assertEqual(
            claim["counts"][
                "unknown_relationship_links"
            ],
            1,
        )

        self.assertTrue(
            result["policy"][
                (
                    "unknown_relationship_does_"
                    "not_imply_stance"
                )
            ]
        )

    def test_stance_does_not_establish_truth_or_corroboration(
        self,
    ):
        result = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        self.link(
                            link_id="support-1",
                            relationship_type=(
                                "supports"
                            ),
                        )
                    ],
                }
            )
        )

        self.assertTrue(
            result["policy"][
                (
                    "explicit_stance_does_not_"
                    "establish_truth"
                )
            ]
        )

        self.assertTrue(
            result["policy"][
                (
                    "explicit_stance_does_not_"
                    "establish_corroboration"
                )
            ]
        )

    def test_input_order_is_stable(
        self,
    ):
        first_link = self.link(
            link_id="support-1",
            relationship_type="supports",
            target_id="obs-1",
        )

        second_link = self.link(
            link_id="neutral-1",
            relationship_type="aligned_to",
            target_id="obs-2",
        )

        first = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        first_link,
                        second_link,
                    ],
                }
            )
        )

        second = (
            main.build_claim_stance_analysis(
                {
                    "claims": [
                        self.claim()
                    ],
                    "claim_links": [
                        second_link,
                        first_link,
                    ],
                }
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_bundle_pipeline_preserves_explicit_stance(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                claims=[
                    self.claim()
                ],
                claim_links=[
                    {
                        "id": "support-1",
                        "claim_id": "claim-1",
                        "source_observation_id": (
                            "obs-1"
                        ),
                        "reporter_observation_id": (
                            None
                        ),
                        "evidence_id": None,
                        "relationship_type": (
                            "supports"
                        ),
                        "confidence": 0.9,
                        "observed_at": (
                            "2026-08-13"
                            "T14:00:00+00:00"
                        ),
                    }
                ],
            )
        )

        stance = (
            main.build_claim_stance_analysis(
                bundle
            )
        )

        self.assertEqual(
            stance["claims"][0][
                "status"
            ],
            "explicit_support",
        )

        self.assertEqual(
            stance["claims"][0][
                "support_links"
            ][0]["target_id"],
            "obs-1",
        )

    def test_relationship_changes_claim_link_identity(
        self,
    ):
        common = {
            "claim_id": "claim-1",
            "observed_at": (
                "2026-08-13T14:00:00+00:00"
            ),
            "confidence": 0.9,
            "source_observation_id": (
                "obs-1"
            ),
        }

        support_id = (
            main.claim_link_id_for_record(
                relationship_type="supports",
                **common,
            )
        )

        contradiction_id = (
            main.claim_link_id_for_record(
                relationship_type=(
                    "contradicts"
                ),
                **common,
            )
        )

        neutral_id = (
            main.claim_link_id_for_record(
                relationship_type=(
                    "aligned_to"
                ),
                **common,
            )
        )

        self.assertEqual(
            len(
                {
                    support_id,
                    contradiction_id,
                    neutral_id,
                }
            ),
            3,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
