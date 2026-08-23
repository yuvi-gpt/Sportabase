import copy
import hashlib
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


from evals.negative_merit_real_world_candidate_batch import (
    NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_BATCH_VERSION,
    NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_CASE_VERSION,
    _contains_all,
    validate_candidate_batch,
)


def digest(
    value,
):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()


class NegativeMeritRealWorldCandidateBatchTests(
    unittest.TestCase
):
    def manifest(
        self,
    ):
        cases = []

        for index in range(
            3
        ):
            cases.append(
                {
                    "version": (
                        NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_CASE_VERSION
                    ),
                    "candidate_id": (
                        "case-"
                        + str(
                            index
                        )
                    ),
                    "origin": "real_world",
                    "subject": (
                        "Player "
                        + str(
                            index
                        )
                    ),
                    "claim_summary": (
                        "Reported sports claim."
                    ),
                    "candidate_relationship": (
                        "direct_authority_denial_candidate"
                    ),
                    "candidate_semantic_status": (
                        "unverified_direct_authority_"
                        "denial_candidate"
                    ),
                    "authority_entity": (
                        "Official Club"
                    ),
                    "claimant_capture": {
                        "requested_url": (
                            "https://news.example/"
                            + str(
                                index
                            )
                        ),
                        "final_url": (
                            "https://news.example/"
                            + str(
                                index
                            )
                        ),
                        "selected_url_index": 0,
                        "domain": (
                            "news.example"
                        ),
                        "title": (
                            "Claim article"
                        ),
                        "content_sha256": (
                            str(
                                index + 1
                            )
                            * 64
                        ),
                        "character_count": 1000,
                        "paragraph_count": 5,
                        "extraction_method": (
                            "test"
                        ),
                        "captured_at": (
                            "2026-08-23T16:30:00+00:00"
                        ),
                    },
                    "authority_capture": {
                        "requested_url": (
                            "https://club.example/"
                            + str(
                                index
                            )
                        ),
                        "final_url": (
                            "https://club.example/"
                            + str(
                                index
                            )
                        ),
                        "selected_url_index": 0,
                        "domain": (
                            "club.example"
                        ),
                        "title": (
                            "Official statement"
                        ),
                        "content_sha256": (
                            "a"
                            * 64
                        ),
                        "character_count": 700,
                        "paragraph_count": 3,
                        "extraction_method": (
                            "test"
                        ),
                        "captured_at": (
                            "2026-08-23T16:31:00+00:00"
                        ),
                    },
                    "claimant_current_merit": {
                        "total": 64,
                        "article_type": (
                            "transfer_rumor"
                        ),
                        "type_confidence": 0.9,
                        "measurement_scope": (
                            "current_retrievable_claimant_page"
                        ),
                        "not_a_truth_probability": True,
                    },
                    "policy": {
                        "claim_truth_established": False,
                        "machine_semantics_verified": False,
                        "direct_authority_gate_verified": False,
                        "numeric_negative_penalty_authorized": False,
                        "live_negative_merit_authorized": False,
                        "provider_call_performed": False,
                        "production_database_written": False,
                        "absence_of_corroboration_is_not_falsehood": True,
                        "capture_is_candidate_evidence_only": True,
                    },
                }
            )

        core = {
            "version": (
                NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_BATCH_VERSION
            ),
            "captured_at": (
                "2026-08-23T16:32:00+00:00"
            ),
            "case_count": 3,
            "cases": cases,
            "policy": {
                "real_world_sources_only": True,
                "immutable_capture_hashes_recorded": True,
                "article_bodies_stored_in_repository": False,
                "provider_call_performed": False,
                "production_database_written": False,
                "machine_semantics_verified": False,
                "claim_truth_established": False,
                "numeric_negative_penalty_authorized": False,
                "live_negative_merit_authorized": False,
                "next_step_requires_existing_verifier_contracts": True,
            },
        }

        return {
            **core,
            "manifest_digest": (
                digest(
                    core
                )
            ),
        }

    def test_subject_matching_folds_diacritics(
        self,
    ):
        self.assertTrue(
            _contains_all(
                "Real Madrid statement regarding Enzo Fern\u00e1ndez.",
                [
                    "enzo",
                    "fernandez",
                ],
            )
        )

    def test_valid_manifest_passes(
        self,
    ):
        report = (
            validate_candidate_batch(
                self.manifest()
            )
        )

        self.assertEqual(
            report[
                "status"
            ],
            "valid",
        )

        self.assertEqual(
            report[
                "case_count"
            ],
            3,
        )

    def test_numeric_penalty_cannot_be_authorized(
        self,
    ):
        manifest = self.manifest()

        manifest[
            "cases"
        ][
            0
        ][
            "policy"
        ][
            "numeric_negative_penalty_authorized"
        ] = True

        core = {
            key: value
            for key, value
            in manifest.items()
            if key
            != "manifest_digest"
        }

        manifest[
            "manifest_digest"
        ] = digest(
            core
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be false",
        ):
            validate_candidate_batch(
                manifest
            )

    def test_truth_cannot_be_established(
        self,
    ):
        manifest = self.manifest()

        manifest[
            "cases"
        ][
            1
        ][
            "policy"
        ][
            "claim_truth_established"
        ] = True

        core = {
            key: value
            for key, value
            in manifest.items()
            if key
            != "manifest_digest"
        }

        manifest[
            "manifest_digest"
        ] = digest(
            core
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be false",
        ):
            validate_candidate_batch(
                manifest
            )

    def test_manifest_tampering_is_detected(
        self,
    ):
        manifest = self.manifest()

        manifest[
            "cases"
        ][
            0
        ][
            "subject"
        ] = "Tampered subject"

        with self.assertRaisesRegex(
            ValueError,
            "digest mismatch",
        ):
            validate_candidate_batch(
                manifest
            )


if __name__ == "__main__":
    unittest.main()
