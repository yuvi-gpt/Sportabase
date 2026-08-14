import hashlib
import json

from typing import Any, Dict, Iterable, List

from app.intelligence.providers import (
    get_provider,
)
from app.services.corpus_adapters import (
    REMOTE_CORPUS_ADAPTER_VERSION,
)


BENCHMARK_CORPUS_ADAPTER_VERSION = (
    "benchmark-corpus-adapter-v1"
)


AVERITEC_LABELS = {
    "supported": "supported",
    "refuted": "refuted",
    "not enough evidence": (
        "not_enough_evidence"
    ),
    "not enough info": (
        "not_enough_evidence"
    ),
    "conflicting evidence/cherry-picking": (
        "conflicting_evidence"
    ),
    "conflicting evidence/cherrypicking": (
        "conflicting_evidence"
    ),
}


FEVER_LABELS = {
    "supports": "supported",
    "refutes": "refuted",
    "not enough info": (
        "not_enough_evidence"
    ),
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _label_key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _stable_hash(
    value: Any,
) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def build_averitec_request(
    *,
    split: str,
) -> Dict[str, Any]:
    normalized_split = _label_key(
        split
    )

    if normalized_split not in {
        "train",
        "dev",
    }:
        raise ValueError(
            "Unsupported AVeriTeC split."
        )

    provider = get_provider(
        "averitec"
    )

    return {
        "version": (
            REMOTE_CORPUS_ADAPTER_VERSION
        ),
        "provider_key": (
            "averitec"
        ),
        "url": (
            provider[
                "base_url"
            ]
            + "/"
            + normalized_split
            + ".json"
        ),
        "expected_format": (
            "json"
        ),
    }


def parse_fever_jsonl(
    text: str,
) -> List[Dict[str, Any]]:
    raw_text = str(
        text or ""
    )

    rows = []

    for line_number, line in enumerate(
        raw_text.splitlines(),
        start=1,
    ):
        clean_line = line.strip()

        if not clean_line:
            continue

        try:
            row = json.loads(
                clean_line
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid FEVER JSONL at "
                f"line {line_number}."
            ) from exc

        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "FEVER JSONL rows must "
                "be dictionaries."
            )

        rows.append(
            row
        )

    return rows


def _averitec_evidence_urls(
    row: Dict[str, Any],
) -> List[str]:
    urls = set()

    questions = row.get(
        "questions",
        [],
    )

    if not isinstance(
        questions,
        list,
    ):
        return []

    for question in questions:
        if not isinstance(
            question,
            dict,
        ):
            continue

        answers = question.get(
            "answers",
            [],
        )

        if not isinstance(
            answers,
            list,
        ):
            continue

        for answer in answers:
            if not isinstance(
                answer,
                dict,
            ):
                continue

            source_url = _clean(
                answer.get(
                    "source_url"
                )
            )

            if source_url:
                urls.add(
                    source_url
                )

    return sorted(
        urls
    )


def _fever_evidence_pages(
    row: Dict[str, Any],
) -> List[str]:
    pages = set()

    evidence = row.get(
        "evidence",
        [],
    )

    if not isinstance(
        evidence,
        list,
    ):
        return []

    for evidence_set in evidence:
        if not isinstance(
            evidence_set,
            list,
        ):
            continue

        for item in evidence_set:
            if (
                not isinstance(
                    item,
                    list,
                )
                or len(item) < 4
            ):
                continue

            page = _clean(
                item[2]
            )

            if page:
                pages.add(
                    page
                )

    return sorted(
        pages
    )


def _benchmark_metadata(
    *,
    provider_key: str,
    split: str,
    benchmark_label: str,
    evidence_references: List[str],
) -> Dict[str, Any]:
    provider = get_provider(
        provider_key
    )

    capabilities = dict(
        provider.get(
            "benchmark_capabilities",
            {},
        )
        or {}
    )

    return {
        "provider_key": (
            provider_key
        ),
        "split": (
            _label_key(
                split
            )
        ),
        "benchmark_label": (
            benchmark_label
        ),
        "evidence_references": list(
            evidence_references
        ),
        "benchmark_capabilities": (
            capabilities
        ),
        "independence_ground_truth_available": (
            bool(
                capabilities.get(
                    "independence_labels",
                    False,
                )
            )
        ),
        "corroboration_ground_truth_available": (
            bool(
                capabilities.get(
                    "corroboration_labels",
                    False,
                )
            )
        ),
        "live_merit_authority": False,
        "truth_established_by_sportabase": (
            False
        ),
    }


def normalize_averitec_rows(
    *,
    rows: Iterable[
        Dict[str, Any]
    ],
    split: str,
) -> List[Dict[str, Any]]:
    normalized_split = _label_key(
        split
    )

    if normalized_split not in {
        "train",
        "dev",
    }:
        raise ValueError(
            "Unsupported AVeriTeC split."
        )

    normalized = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "AVeriTeC rows must be "
                "dictionaries."
            )

        claim = _clean(
            row.get(
                "claim"
            )
        )

        if not claim:
            raise ValueError(
                "AVeriTeC claim is required."
            )

        raw_label = _label_key(
            row.get(
                "label"
            )
        )

        if raw_label not in AVERITEC_LABELS:
            raise ValueError(
                "Unsupported AVeriTeC label."
            )

        benchmark_label = (
            AVERITEC_LABELS[
                raw_label
            ]
        )

        explicit_id = (
            _clean(
                row.get(
                    "claim_id"
                )
            )
            or _clean(
                row.get(
                    "id"
                )
            )
        )

        if explicit_id:
            external_id = (
                normalized_split
                + "|"
                + explicit_id
            )
        else:
            external_id = (
                normalized_split
                + "|hash|"
                + _stable_hash(
                    {
                        "claim": claim,
                        "claim_date": (
                            _clean(
                                row.get(
                                    "claim_date"
                                )
                            )
                        ),
                        "fact_checking_article": (
                            _clean(
                                row.get(
                                    "fact_checking_article"
                                )
                            )
                        ),
                    }
                )
            )

        evidence_urls = (
            _averitec_evidence_urls(
                row
            )
        )

        normalized.append(
            {
                "origin_type": (
                    "external_dataset"
                ),
                "data_family": (
                    "benchmark"
                ),
                "dataset_name": (
                    "averitec"
                ),
                "external_record_id": (
                    external_id
                ),
                "adapter_version": (
                    BENCHMARK_CORPUS_ADAPTER_VERSION
                ),
                "sport_key": "",
                "competition_key": "",
                "season_key": "",
                "event_type": (
                    "benchmark_claim"
                ),
                "granularity": (
                    "claim"
                ),
                "measurement_kind": (
                    "direct"
                ),
                "canonical_url": (
                    _clean(
                        row.get(
                            "original_claim_url"
                        )
                    )
                ),
                "published_at": (
                    _clean(
                        row.get(
                            "claim_date"
                        )
                    )
                    or None
                ),
                "payload": dict(
                    row
                ),
                "metadata": (
                    _benchmark_metadata(
                        provider_key=(
                            "averitec"
                        ),
                        split=(
                            normalized_split
                        ),
                        benchmark_label=(
                            benchmark_label
                        ),
                        evidence_references=(
                            evidence_urls
                        ),
                    )
                ),
            }
        )

    return normalized


def normalize_fever_rows(
    *,
    rows: Iterable[
        Dict[str, Any]
    ],
    split: str,
) -> List[Dict[str, Any]]:
    normalized_split = _label_key(
        split
    )

    if not normalized_split:
        raise ValueError(
            "FEVER split is required."
        )

    normalized = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "FEVER rows must be "
                "dictionaries."
            )

        external_id = _clean(
            row.get(
                "id"
            )
        )

        if not external_id:
            raise ValueError(
                "FEVER claim ID is required."
            )

        claim = _clean(
            row.get(
                "claim"
            )
        )

        if not claim:
            raise ValueError(
                "FEVER claim is required."
            )

        raw_label = _label_key(
            row.get(
                "label"
            )
        )

        if raw_label not in FEVER_LABELS:
            raise ValueError(
                "Unsupported FEVER label."
            )

        benchmark_label = (
            FEVER_LABELS[
                raw_label
            ]
        )

        evidence_pages = (
            _fever_evidence_pages(
                row
            )
        )

        normalized.append(
            {
                "origin_type": (
                    "external_dataset"
                ),
                "data_family": (
                    "benchmark"
                ),
                "dataset_name": (
                    "fever"
                ),
                "external_record_id": (
                    normalized_split
                    + "|"
                    + external_id
                ),
                "adapter_version": (
                    BENCHMARK_CORPUS_ADAPTER_VERSION
                ),
                "sport_key": "",
                "competition_key": "",
                "season_key": "",
                "event_type": (
                    "benchmark_claim"
                ),
                "granularity": (
                    "claim"
                ),
                "measurement_kind": (
                    "direct"
                ),
                "payload": dict(
                    row
                ),
                "metadata": (
                    _benchmark_metadata(
                        provider_key=(
                            "fever"
                        ),
                        split=(
                            normalized_split
                        ),
                        benchmark_label=(
                            benchmark_label
                        ),
                        evidence_references=(
                            evidence_pages
                        ),
                    )
                ),
            }
        )

    return normalized


def benchmark_expectation(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        record,
        dict,
    ):
        raise ValueError(
            "Benchmark record must be "
            "a dictionary."
        )

    if (
        record.get(
            "data_family"
        )
        != "benchmark"
    ):
        raise ValueError(
            "Record is not a benchmark "
            "corpus record."
        )

    metadata = record.get(
        "metadata",
        {},
    )

    if not isinstance(
        metadata,
        dict,
    ):
        raise ValueError(
            "Benchmark metadata must be "
            "a dictionary."
        )

    label = _clean(
        metadata.get(
            "benchmark_label"
        )
    )

    if label not in {
        "supported",
        "refuted",
        "not_enough_evidence",
        "conflicting_evidence",
    }:
        raise ValueError(
            "Benchmark label is missing "
            "or unsupported."
        )

    return {
        "version": (
            BENCHMARK_CORPUS_ADAPTER_VERSION
        ),
        "benchmark_label": label,
        "expected_claim_evidence_state": {
            "supported": (
                "supporting"
            ),
            "refuted": (
                "contradicting"
            ),
            "not_enough_evidence": (
                "insufficient"
            ),
            "conflicting_evidence": (
                "contested"
            ),
        }[
            label
        ],
        "independence_ground_truth_available": (
            bool(
                metadata.get(
                    "independence_ground_truth_available",
                    False,
                )
            )
        ),
        "corroboration_ground_truth_available": (
            bool(
                metadata.get(
                    "corroboration_ground_truth_available",
                    False,
                )
            )
        ),
        "live_merit_authorized": False,
        "truth_established_by_sportabase": (
            False
        ),
    }
