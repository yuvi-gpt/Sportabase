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


class ObservationDependencyPolicyTests(
    unittest.TestCase
):
    def bundle(
        self,
        *relationship_types,
    ):
        return {
            "observation_dependencies": [
                {
                    "id": f"dependency-{index}",
                    "relationship_type":
                        relationship_type,
                }
                for index, relationship_type
                in enumerate(
                    relationship_types
                )
            ]
        }

    def test_current_relationships_are_recognized(
        self,
    ):
        report = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    "attributed_to",
                    "derived_from",
                )
            )
        )

        self.assertEqual(
            report["version"],
            main.OBSERVATION_DEPENDENCY_POLICY_VERSION,
        )

        self.assertEqual(
            report["recognized"],
            [
                "attributed_to",
                "derived_from",
            ],
        )

        self.assertEqual(
            report["unknown"],
            [],
        )

    def test_unknown_relationships_are_exposed(
        self,
    ):
        report = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    "attributed_to",
                    "syndicated_from",
                )
            )
        )

        self.assertEqual(
            report["recognized"],
            [
                "attributed_to",
            ],
        )

        self.assertEqual(
            report["unknown"],
            [
                "syndicated_from",
            ],
        )

    def test_relationships_are_normalized(
        self,
    ):
        report = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    " ATTRIBUTED_TO ",
                    "Derived_From",
                )
            )
        )

        self.assertEqual(
            report["recognized"],
            [
                "attributed_to",
                "derived_from",
            ],
        )

    def test_input_order_is_stable(
        self,
    ):
        first = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    "derived_from",
                    "unknown_relation",
                    "attributed_to",
                )
            )
        )

        second = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    "attributed_to",
                    "unknown_relation",
                    "derived_from",
                )
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_empty_bundle_is_safe(
        self,
    ):
        report = (
            main.inspect_observation_dependency_vocabulary(
                {}
            )
        )

        self.assertEqual(
            report["recognized"],
            [],
        )

        self.assertEqual(
            report["unknown"],
            [],
        )

    def test_bundle_must_be_dictionary(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.inspect_observation_dependency_vocabulary(
                []
            )

    def test_policy_does_not_claim_independence_or_corroboration(
        self,
    ):
        report = (
            main.inspect_observation_dependency_vocabulary(
                self.bundle(
                    "attributed_to",
                    "derived_from",
                )
            )
        )

        forbidden = {
            "independent",
            "independent_sources",
            "corroborated",
            "corroboration",
            "score",
            "weight",
            "penalty",
            "boost",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                report.keys()
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
