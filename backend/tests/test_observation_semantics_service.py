import json
import sys
import unittest

from pathlib import Path
from types import SimpleNamespace


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


from app.services.observation_semantics import (
    OBSERVATION_SEMANTIC_GEMINI_MODE,
    OBSERVATION_SEMANTIC_GEMINI_MODEL,
    OBSERVATION_SEMANTIC_GEMINI_VERSION,
    assess_claim_observation_semantics_with_gemini,
)


class ObservationSemanticServiceTests(
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
                "Team A announces Player A "
                "will join the team."
            ),
            "actor_id": (
                "team-a"
            ),
        }

    def response_payload(
        self,
    ):
        return {
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
                "Team A announces Player A."
            ],
            "source_role_confidence": (
                0.99
            ),
            "authority_confidence": (
                0.99
            ),
            "reliability_confidence": (
                0.50
            ),
            "provenance_confidence": (
                0.98
            ),
            "stance_confidence": (
                0.99
            ),
            "dependency_confidence": (
                0.90
            ),
        }

    def test_versions(
        self,
    ):
        self.assertEqual(
            OBSERVATION_SEMANTIC_GEMINI_VERSION,
            (
                "claim-observation-"
                "semantic-gemini-v1"
            ),
        )

        self.assertEqual(
            OBSERVATION_SEMANTIC_GEMINI_MODE,
            "claim_observation_semantics",
        )

        self.assertEqual(
            OBSERVATION_SEMANTIC_GEMINI_MODEL,
            "gemini-3.5-flash",
        )

    def test_unavailable_client_is_best_effort(
        self,
    ):
        called = []

        def generator(
            **kwargs,
        ):
            called.append(
                kwargs
            )

            raise AssertionError(
                "generator should not run"
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={},
                client=None,
                client_key="client",
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "unavailable",
        )

        self.assertEqual(
            result[
                "reason"
            ],
            "gemini_unavailable",
        )

        self.assertEqual(
            called,
            [],
        )

    def test_assessed_response_is_normalized(
        self,
    ):
        calls = []

        def generator(
            **kwargs,
        ):
            calls.append(
                kwargs
            )

            return SimpleNamespace(
                text=json.dumps(
                    self.response_payload()
                )
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={},
                client=object(),
                client_key="client-1",
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "assessed",
        )

        assessment = result[
            "assessment"
        ]

        self.assertEqual(
            assessment[
                "source_role"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            assessment[
                "authority_class"
            ],
            "direct",
        )

        self.assertEqual(
            assessment[
                "derivation"
            ][
                "mode"
            ],
            "model_assisted",
        )

        self.assertFalse(
            assessment[
                "derivation"
            ][
                "training_eligible"
            ]
        )

        self.assertEqual(
            len(
                calls
            ),
            1,
        )

        self.assertEqual(
            calls[0][
                "mode"
            ],
            OBSERVATION_SEMANTIC_GEMINI_MODE,
        )

        self.assertEqual(
            calls[0][
                "model"
            ],
            OBSERVATION_SEMANTIC_GEMINI_MODEL,
        )

        self.assertIn(
            "UNTRUSTED_SOURCE_TEXT",
            calls[0][
                "contents"
            ],
        )

    def test_known_reliability_context_is_applied(
        self,
    ):
        def generator(
            **kwargs,
        ):
            payload = (
                self.response_payload()
            )

            payload[
                "reliability_class"
            ] = "unknown"

            return SimpleNamespace(
                text=json.dumps(
                    payload
                )
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={
                    "known_reliability_class": (
                        "established"
                    )
                },
                client=object(),
                client_key="client",
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "assessment"
            ][
                "reliability_class"
            ],
            "established",
        )

    def test_provider_failure_is_best_effort(
        self,
    ):
        def generator(
            **kwargs,
        ):
            raise RuntimeError(
                "provider down"
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={},
                client=object(),
                client_key="client",
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "assessment_failed",
        )

        self.assertEqual(
            result[
                "error_type"
            ],
            "RuntimeError",
        )

        self.assertIsNone(
            result[
                "assessment"
            ]
        )

    def test_parse_failure_is_best_effort(
        self,
    ):
        def generator(
            **kwargs,
        ):
            return SimpleNamespace(
                text="not json"
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={},
                client=object(),
                client_key="client",
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "assessment_failed",
        )

        self.assertEqual(
            result[
                "error_type"
            ],
            "ValueError",
        )

    def test_service_has_no_live_merit_effect(
        self,
    ):
        def generator(
            **kwargs,
        ):
            return SimpleNamespace(
                text=json.dumps(
                    self.response_payload()
                )
            )

        result = (
            assess_claim_observation_semantics_with_gemini(
                claim=self.claim(),
                source=self.source(),
                context={},
                client=object(),
                client_key="client",
                generator=generator,
            )
        )

        forbidden = {
            "merit",
            "merit_score",
            "score_adjustment",
            "live_total",
            "shadow_total",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "no_live_merit_effect"
            ]
        )


if __name__ == "__main__":
    unittest.main()
