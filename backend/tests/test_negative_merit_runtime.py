import json
import sys
import unittest

from pathlib import Path
from unittest.mock import (
    Mock,
    patch,
)


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)

from app.services.negative_merit_runtime import (
    NEGATIVE_MERIT_RUNTIME_VERSION,
    run_negative_merit_shadow,
)


class NegativeMeritRuntimeTests(
    unittest.TestCase
):
    @staticmethod
    def legacy():
        return {
            "total": 72,
            "badge": "Good",
            "components": {},
            "calculation": {},
            "reasons": [],
        }

    @staticmethod
    def bundle(
        *,
        relationship="contradicts",
        target_type="source_observation",
    ):
        return {
            "claims": [
                {
                    "id": "claim-1",
                    "canonical_key": (
                        "article-primary|"
                        "media-1|transfer"
                    ),
                    "subject_key": (
                        "transfer|test"
                    ),
                }
            ],
            "claim_links": [
                {
                    "id": "link-1",
                    "claim_id": "claim-1",
                    "target_type": target_type,
                    "target_id": "obs-1",
                    "relationship_type": (
                        relationship
                    ),
                }
            ],
        }

    @staticmethod
    def verified_authority_result():
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_direct_stakeholder_"
                "contradiction_lineage"
            ),
            "persisted": True,
            "evidence": {
                "id": "authority-evidence-1",
                "evidence_type": (
                    "direct_stakeholder_"
                    "contradiction_reference"
                ),
                "verification_status": (
                    "verified"
                ),
                "subject_key": (
                    "merit-negative-evidence|"
                    "claim-1"
                ),
                "metadata_json": json.dumps(
                    {
                        "verifier_version": (
                            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
                        ),
                        "machine_verified_authority": True,
                        "recorded_contradiction_relationship": True,
                        "contradiction_semantics_verified": False,
                        "claim_truth_established": False,
                        "live_merit_changed": False,
                    }
                ),
            },
        }

    @staticmethod
    def verified_semantic_result():
        return {
            "version": (
                MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_machine_"
                "contradiction_semantics"
            ),
            "persisted": True,
            "evidence": {
                "id": (
                    "semantic-evidence-1"
                ),
                "evidence_type": (
                    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE
                ),
                "verification_status": (
                    "verified"
                ),
                "subject_key": (
                    "merit-negative-semantic-evidence|"
                    "claim-1"
                ),
                "metadata_json": json.dumps(
                    {
                        "verifier_version": (
                            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
                        ),
                        "claim_id": (
                            "claim-1"
                        ),
                        "stance": (
                            "contradicts"
                        ),
                        "contradiction_semantics_verified": True,
                        "contradiction_semantics_are_source_semantics": True,
                        "claim_truth_established": False,
                        "live_merit_changed": False,
                    }
                ),
            },
        }

    def test_two_verified_gates_become_calibration_eligible(
        self,
    ):
        authority = Mock(
            return_value=(
                self.verified_authority_result()
            )
        )

        semantics = Mock(
            return_value=(
                self.verified_semantic_result()
            )
        )

        with patch(
            (
                "app.services.negative_merit_runtime."
                "persist_direct_stakeholder_"
                "contradiction_verification"
            ),
            authority,
        ), patch(
            (
                "app.services.negative_merit_runtime."
                "persist_machine_verified_"
                "contradiction_semantics_verification"
            ),
            semantics,
        ):
            result = (
                run_negative_merit_shadow(
                    legacy_score=(
                        self.legacy()
                    ),
                    evidence_bundle=(
                        self.bundle()
                    ),
                    media_item_id=(
                        "media-1"
                    ),
                    connection_factory=(
                        object()
                    ),
                )
            )

        self.assertEqual(
            result[
                "version"
            ],
            NEGATIVE_MERIT_RUNTIME_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "negative_evidence_"
                "calibration_eligible"
            ),
        )

        self.assertTrue(
            result[
                "shadow"
            ][
                "evidence_gates"
            ][
                "direct_authority_contradiction_lineage"
            ]
        )

        self.assertTrue(
            result[
                "shadow"
            ][
                "evidence_gates"
            ][
                "machine_verified_contradiction_semantics"
            ]
        )

        self.assertTrue(
            result[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            result[
                "shadow"
            ][
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            72.0,
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )

        authority.assert_called_once()
        semantics.assert_called_once()

    def test_authority_without_machine_semantics_is_not_eligible(
        self,
    ):
        authority = Mock(
            return_value=(
                self.verified_authority_result()
            )
        )

        semantics = Mock(
            return_value={
                "version": (
                    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
                ),
                "status": (
                    "no_machine_verified_stance"
                ),
                "persisted": False,
                "evidence": None,
            }
        )

        with patch(
            (
                "app.services.negative_merit_runtime."
                "persist_direct_stakeholder_"
                "contradiction_verification"
            ),
            authority,
        ), patch(
            (
                "app.services.negative_merit_runtime."
                "persist_machine_verified_"
                "contradiction_semantics_verification"
            ),
            semantics,
        ):
            result = (
                run_negative_merit_shadow(
                    legacy_score=(
                        self.legacy()
                    ),
                    evidence_bundle=(
                        self.bundle()
                    ),
                    media_item_id=(
                        "media-1"
                    ),
                    connection_factory=(
                        object()
                    ),
                )
            )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertEqual(
            result[
                "shadow"
            ][
                "signal"
            ],
            (
                "verified_authority_contradiction_"
                "semantics_unverified"
            ),
        )

        self.assertTrue(
            result[
                "shadow"
            ][
                "evidence_gates"
            ][
                "direct_authority_contradiction_lineage"
            ]
        )

        self.assertFalse(
            result[
                "shadow"
            ][
                "evidence_gates"
            ][
                "machine_verified_contradiction_semantics"
            ]
        )

        self.assertFalse(
            result[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            result[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            72.0,
        )

    def test_no_contradiction_does_not_call_verifiers(
        self,
    ):
        authority = Mock()
        semantics = Mock()

        with patch(
            (
                "app.services.negative_merit_runtime."
                "persist_direct_stakeholder_"
                "contradiction_verification"
            ),
            authority,
        ), patch(
            (
                "app.services.negative_merit_runtime."
                "persist_machine_verified_"
                "contradiction_semantics_verification"
            ),
            semantics,
        ):
            result = (
                run_negative_merit_shadow(
                    legacy_score=(
                        self.legacy()
                    ),
                    evidence_bundle=(
                        self.bundle(
                            relationship="supports"
                        )
                    ),
                    media_item_id=(
                        "media-1"
                    ),
                    connection_factory=(
                        object()
                    ),
                )
            )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertEqual(
            result[
                "contradiction_observation_ids"
            ],
            [],
        )

        authority.assert_not_called()
        semantics.assert_not_called()

    def test_reporter_contradiction_does_not_call_verifiers(
        self,
    ):
        authority = Mock()
        semantics = Mock()

        with patch(
            (
                "app.services.negative_merit_runtime."
                "persist_direct_stakeholder_"
                "contradiction_verification"
            ),
            authority,
        ), patch(
            (
                "app.services.negative_merit_runtime."
                "persist_machine_verified_"
                "contradiction_semantics_verification"
            ),
            semantics,
        ):
            result = (
                run_negative_merit_shadow(
                    legacy_score=(
                        self.legacy()
                    ),
                    evidence_bundle=(
                        self.bundle(
                            target_type=(
                                "reporter_observation"
                            )
                        )
                    ),
                    media_item_id=(
                        "media-1"
                    ),
                    connection_factory=(
                        object()
                    ),
                )
            )

        self.assertEqual(
            result[
                "contradiction_observation_ids"
            ],
            [],
        )

        authority.assert_not_called()
        semantics.assert_not_called()

    def test_duplicate_primary_claim_fails_closed(
        self,
    ):
        bundle = self.bundle()

        bundle[
            "claims"
        ].append(
            {
                "id": "claim-2",
                "canonical_key": (
                    "article-primary|"
                    "media-1|duplicate"
                ),
            }
        )

        result = (
            run_negative_merit_shadow(
                legacy_score=(
                    self.legacy()
                ),
                evidence_bundle=(
                    bundle
                ),
                media_item_id=(
                    "media-1"
                ),
                connection_factory=(
                    object()
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "primary_claim_not_unique"
            ),
        )

        self.assertIsNone(
            result[
                "shadow"
            ]
        )


if __name__ == "__main__":
    unittest.main()
