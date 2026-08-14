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


from app.services.benchmark_adapters import (
    BENCHMARK_CORPUS_ADAPTER_VERSION,
    benchmark_expectation,
    build_averitec_request,
    normalize_averitec_rows,
    normalize_fever_rows,
    parse_fever_jsonl,
)
from app.services.corpus_adapters import (
    ingest_normalized_records,
)


class BenchmarkAdapterTests(
    unittest.TestCase
):
    def test_averitec_request_is_deterministic(
        self,
    ):
        request = build_averitec_request(
            split="train"
        )

        self.assertEqual(
            request[
                "provider_key"
            ],
            "averitec",
        )

        self.assertTrue(
            request[
                "url"
            ].endswith(
                "/train.json"
            )
        )

    def test_averitec_request_rejects_unknown_split(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported AVeriTeC split",
        ):
            build_averitec_request(
                split="test-maybe"
            )

    def test_averitec_supported_claim_normalization(
        self,
    ):
        row = normalize_averitec_rows(
            split="dev",
            rows=[
                {
                    "claim": (
                        "Example real-world claim"
                    ),
                    "label": "Supported",
                    "claim_date": (
                        "2024-01-01"
                    ),
                    "original_claim_url": (
                        "https://example.com/claim"
                    ),
                    "questions": [],
                }
            ],
        )[0]

        self.assertEqual(
            row["data_family"],
            "benchmark",
        )

        self.assertEqual(
            row[
                "metadata"
            ][
                "benchmark_label"
            ],
            "supported",
        )

        self.assertEqual(
            row[
                "canonical_url"
            ],
            "https://example.com/claim",
        )

    def test_averitec_conflicting_label_maps_to_contested(
        self,
    ):
        row = normalize_averitec_rows(
            split="dev",
            rows=[
                {
                    "claim": (
                        "Example contested claim"
                    ),
                    "label": (
                        "Conflicting Evidence/"
                        "Cherry-picking"
                    ),
                    "questions": [],
                }
            ],
        )[0]

        expectation = (
            benchmark_expectation(
                row
            )
        )

        self.assertEqual(
            expectation[
                "expected_claim_evidence_state"
            ],
            "contested",
        )

    def test_averitec_evidence_urls_are_deduplicated(
        self,
    ):
        row = normalize_averitec_rows(
            split="train",
            rows=[
                {
                    "claim": "Example",
                    "label": "Refuted",
                    "questions": [
                        {
                            "question": "Q1",
                            "answers": [
                                {
                                    "source_url": (
                                        "https://a.example/x"
                                    )
                                },
                                {
                                    "source_url": (
                                        "https://a.example/x"
                                    )
                                },
                                {
                                    "source_url": (
                                        "https://b.example/y"
                                    )
                                },
                            ],
                        }
                    ],
                }
            ],
        )[0]

        refs = row[
            "metadata"
        ][
            "evidence_references"
        ]

        self.assertEqual(
            refs,
            [
                "https://a.example/x",
                "https://b.example/y",
            ],
        )

    def test_averitec_requires_claim(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "claim is required",
        ):
            normalize_averitec_rows(
                split="train",
                rows=[
                    {
                        "claim": "",
                        "label": "Supported",
                    }
                ],
            )

    def test_fever_jsonl_parser(
        self,
    ):
        rows = parse_fever_jsonl(
            (
                '{"id":1,"claim":"A",'
                '"label":"SUPPORTS",'
                '"evidence":[]}\n'
                '\n'
                '{"id":2,"claim":"B",'
                '"label":"REFUTES",'
                '"evidence":[]}'
            )
        )

        self.assertEqual(
            len(rows),
            2,
        )

        self.assertEqual(
            rows[1]["id"],
            2,
        )

    def test_fever_jsonl_rejects_invalid_json(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "line 2",
        ):
            parse_fever_jsonl(
                (
                    '{"id":1}\n'
                    '{not-json}'
                )
            )

    def test_fever_support_normalization_preserves_evidence_pages(
        self,
    ):
        row = normalize_fever_rows(
            split="train",
            rows=[
                {
                    "id": 62037,
                    "claim": (
                        "Example claim"
                    ),
                    "label": "SUPPORTS",
                    "evidence": [
                        [
                            [
                                1,
                                2,
                                "Example_Page",
                                0,
                            ]
                        ]
                    ],
                }
            ],
        )[0]

        self.assertEqual(
            row[
                "external_record_id"
            ],
            "train|62037",
        )

        self.assertEqual(
            row[
                "metadata"
            ][
                "benchmark_label"
            ],
            "supported",
        )

        self.assertEqual(
            row[
                "metadata"
            ][
                "evidence_references"
            ],
            [
                "Example_Page",
            ],
        )

    def test_fever_nei_maps_to_insufficient(
        self,
    ):
        row = normalize_fever_rows(
            split="dev",
            rows=[
                {
                    "id": 5,
                    "claim": (
                        "Unknown example"
                    ),
                    "label": (
                        "NOT ENOUGH INFO"
                    ),
                    "evidence": [
                        [
                            [
                                1,
                                2,
                                None,
                                None,
                            ]
                        ]
                    ],
                }
            ],
        )[0]

        expectation = (
            benchmark_expectation(
                row
            )
        )

        self.assertEqual(
            expectation[
                "expected_claim_evidence_state"
            ],
            "insufficient",
        )

    def test_benchmark_expectation_never_claims_independence_or_corroboration(
        self,
    ):
        row = normalize_averitec_rows(
            split="dev",
            rows=[
                {
                    "claim": "Example",
                    "label": "Supported",
                    "questions": [
                        {
                            "answers": [
                                {
                                    "source_url": (
                                        "https://one.example"
                                    )
                                },
                                {
                                    "source_url": (
                                        "https://two.example"
                                    )
                                },
                            ]
                        }
                    ],
                }
            ],
        )[0]

        expectation = (
            benchmark_expectation(
                row
            )
        )

        self.assertFalse(
            expectation[
                "independence_ground_truth_available"
            ]
        )

        self.assertFalse(
            expectation[
                "corroboration_ground_truth_available"
            ]
        )

        self.assertFalse(
            expectation[
                "live_merit_authorized"
            ]
        )

    def test_benchmark_records_fit_existing_corpus_ingestion_contract(
        self,
    ):
        row = normalize_fever_rows(
            split="dev",
            rows=[
                {
                    "id": 99,
                    "claim": "Example",
                    "label": "REFUTES",
                    "evidence": [],
                }
            ],
        )[0]

        calls = []

        def recorder(
            **kwargs,
        ):
            calls.append(
                kwargs
            )

            return {
                "created": True,
            }

        result = ingest_normalized_records(
            records=[
                row
            ],
            connection_factory=(
                "fake-db"
            ),
            recorder=recorder,
        )

        self.assertEqual(
            result[
                "counts"
            ][
                "created"
            ],
            1,
        )

        self.assertEqual(
            calls[0][
                "data_family"
            ],
            "benchmark",
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()
