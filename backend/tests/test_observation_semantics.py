import json
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.analysis.observation_semantics import (
    CLAIM_OBSERVATION_SEMANTICS_VERSION,
    build_claim_observation_semantic_prompt,
    normalize_claim_observation_semantics,
)


class ClaimObservationSemanticsTests(
    unittest.TestCase
):
    def claim(
        self,
    ):
        return {
            "id": "claim-1",
            "canonical_text": (
                "Player A will join Team A."
            ),
        }

    def source(
        self,
    ):
        return {
            "url": (
                "https://example.com/story"
            ),
            "title": (
                "Team statement"
            ),
            "text": (
                "Team A announces that "
                "Player A will join the team."
            ),
            "actor_id": (
                "team-a"
            ),
            "source_domain": (
                "example.com"
            ),
        }

    def raw(
        self,
        **overrides,
    ):
        data = {
            "claim_relevance": (
                "same_claim"
            ),
            "source_role": (
                "primary_stakeholder"
            ),
            "authority_class": (
                "direct"
            ),
            "reliability_class": (
                "not_applicable"
            ),
            "provenance_class": (
                "direct_statement"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [
                (
                    "Team A announces that "
                    "Player A will join."
                )
            ],
            "source_role_confidence": (
                0.98
            ),
            "authority_confidence": (
                0.99
            ),
            "reliability_confidence": (
                0.95
            ),
            "provenance_confidence": (
                0.97
            ),
            "stance_confidence": (
                0.99
            ),
            "dependency_confidence": (
                0.90
            ),
        }

        data.update(
            overrides
        )

        return data

    def normalize(
        self,
        raw=None,
        *,
        context=None,
    ):
        if raw is None:
            raw = self.raw()

        return (
            normalize_claim_observation_semantics(
                raw,
                claim_id="claim-1",
                source_url=(
                    "https://example.com/story"
                ),
                context=context,
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

    def test_version(
        self,
    ):
        self.assertEqual(
            CLAIM_OBSERVATION_SEMANTICS_VERSION,
            "claim-observation-semantics-v1",
        )

    def test_prompt_locks_safety_rules(
        self,
    ):
        prompt = (
            build_claim_observation_semantic_prompt(
                claim=self.claim(),
                source=self.source(),
                context={},
            )
        )

        self.assertIn(
            "UNTRUSTED DATA",
            prompt,
        )

        self.assertIn(
            "Do not browse the web",
            prompt,
        )

        self.assertIn(
            "Do not determine truth",
            prompt,
        )

        self.assertIn(
            "Absence of attribution does NOT establish independence",
            prompt,
        )

        self.assertIn(
            "Do NOT infer reliability",
            prompt,
        )

    def test_primary_stakeholder_fields_are_proposed(
        self,
    ):
        result = self.normalize()

        self.assertEqual(
            result[
                "source_role"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            result[
                "authority_class"
            ],
            "direct",
        )

        self.assertEqual(
            result[
                "provenance_class"
            ],
            "direct_statement",
        )

        self.assertEqual(
            result[
                "stance"
            ],
            "supports",
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "not_applicable",
        )

    def test_model_cannot_invent_reliability_reputation(
        self,
    ):
        result = self.normalize(
            self.raw(
                reliability_class=(
                    "elite_specialist"
                )
            )
        )

        self.assertEqual(
            result[
                "reliability_class"
            ],
            "unknown",
        )

        self.assertIn(
            (
                "reliability_requires_"
                "empirical_context"
            ),
            result[
                "issues"
            ],
        )

    def test_empirical_reliability_context_overrides_model(
        self,
    ):
        result = self.normalize(
            self.raw(
                reliability_class=(
                    "unrated"
                )
            ),
            context={
                "known_reliability_class": (
                    "elite_specialist"
                )
            },
        )

        self.assertEqual(
            result[
                "reliability_class"
            ],
            "elite_specialist",
        )

        judgment = [
            row
            for row in result[
                "field_judgments"
            ]
            if row[
                "field"
            ]
            == "reliability_class"
        ][0]

        self.assertEqual(
            judgment[
                "basis_class"
            ],
            "structured_fact",
        )

        self.assertEqual(
            judgment[
                "evaluator_family"
            ],
            (
                "empirical_reliability_context"
            ),
        )

        self.assertEqual(
            judgment[
                "confidence"
            ],
            1.0,
        )

    def test_explicit_dependency_prevents_independence(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role="publisher",
                authority_class="none",
                provenance_class=(
                    "attributed_reporting"
                ),
                dependency_status=(
                    "explicit_dependency"
                ),
                dependency_targets=[
                    "Reporter A",
                ],
            )
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "not_established",
        )

        self.assertEqual(
            result[
                "dependency_targets"
            ],
            [
                "Reporter A",
            ],
        )

    def test_no_detected_dependency_does_not_establish_independence(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role="publisher",
                authority_class="none",
                dependency_status=(
                    "no_explicit_dependency_detected"
                ),
            )
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "unknown",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "absence_of_dependency_does_not_establish_independence"
            ]
        )

    def test_reporting_role_cannot_claim_direct_authority(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role=(
                    "privileged_reporter"
                ),
                authority_class="direct",
                reliability_class="unknown",
                provenance_class=(
                    "firsthand_reporting"
                ),
            )
        )

        self.assertEqual(
            result[
                "authority_class"
            ],
            "none",
        )

        self.assertIn(
            (
                "reporting_role_cannot_"
                "claim_official_authority"
            ),
            result[
                "issues"
            ],
        )

    def test_stakeholder_authority_mismatch_fails_closed(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role=(
                    "primary_stakeholder"
                ),
                authority_class="none",
            )
        )

        self.assertEqual(
            result[
                "authority_class"
            ],
            "unknown",
        )

        self.assertIn(
            (
                "primary_stakeholder_"
                "authority_mismatch"
            ),
            result[
                "issues"
            ],
        )

    def test_institution_authority_mismatch_fails_closed(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role=(
                    "official_institution"
                ),
                authority_class="direct",
            )
        )

        self.assertEqual(
            result[
                "authority_class"
            ],
            "unknown",
        )

        self.assertIn(
            (
                "official_institution_"
                "authority_mismatch"
            ),
            result[
                "issues"
            ],
        )

    def test_unrelated_source_cannot_supply_stance(
        self,
    ):
        result = self.normalize(
            self.raw(
                claim_relevance="unrelated",
                stance="supports",
            )
        )

        self.assertEqual(
            result[
                "stance"
            ],
            "uncertain",
        )

    def test_invalid_confidences_fail_to_none(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_role_confidence=(
                    4.5
                ),
                stance_confidence=(
                    "garbage"
                ),
            )
        )

        self.assertIsNone(
            result[
                "confidences"
            ][
                "source_role"
            ]
        )

        self.assertIsNone(
            result[
                "confidences"
            ][
                "stance"
            ]
        )

    def test_field_judgments_are_not_training_eligible(
        self,
    ):
        result = self.normalize()

        self.assertEqual(
            {
                row[
                    "field"
                ]
                for row in result[
                    "field_judgments"
                ]
            },
            {
                "source_role",
                "authority_class",
                "reliability_class",
                "provenance_class",
                "stance",
                "independence_status",
            },
        )

        self.assertTrue(
            all(
                row[
                    "training_eligible"
                ]
                is False
                for row in result[
                    "field_judgments"
                ]
            )
        )

    def test_model_assisted_derivation_is_explicit(
        self,
    ):
        result = self.normalize()

        self.assertEqual(
            result[
                "derivation"
            ],
            {
                "mode": (
                    "model_assisted"
                ),
                "self_validating": (
                    False
                ),
                "training_eligible": (
                    False
                ),
            },
        )

    def test_json_text_is_normalized(
        self,
    ):
        raw = json.dumps(
            self.raw()
        )

        result = self.normalize(
            raw
        )

        self.assertEqual(
            result[
                "source_role"
            ],
            "primary_stakeholder",
        )

    def test_malformed_response_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "not valid JSON",
        ):
            self.normalize(
                "this is not json"
            )


if __name__ == "__main__":
    unittest.main()
