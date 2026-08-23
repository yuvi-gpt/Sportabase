from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse


NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_BATCH_VERSION = (
    "negative-merit-real-world-candidate-batch-v1"
)

NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_CASE_VERSION = (
    "negative-merit-real-world-candidate-v1"
)


CASES = [
    {
        "candidate_id": (
            "olise-real-madrid-direct-denial-2026"
        ),
        "subject": "Michael Olise",
        "claim_summary": (
            "Real Madrid intended to pursue Michael Olise "
            "and reported club representatives had confirmed "
            "that interest."
        ),
        "claimant_urls": [
            (
                "https://www.goal.com/en/lists/"
                "this-has-been-confirmed-by-representatives-of-real-madrid-"
                "fresh-details-have-emerged-about-the-reported-interest-in-"
                "bayern-munich-superstar-michael-olise/"
                "bltb4af8cd273e845a8"
            ),
            (
                "https://uk.sports.yahoo.com/news/"
                "confirmed-representatives-real-madrid-fresh-072325317.html"
            ),
        ],
        "claimant_domains": {
            "goal.com",
            "sports.yahoo.com",
        },
        "claimant_subject_terms": [
            "michael",
            "olise",
            "real madrid",
        ],
        "claimant_assertion_terms": [
            "intended to pursue michael olise",
            "confirmed by representatives of real madrid",
            "representatives of real madrid have confirmed",
            "real madrid president",
        ],
        "authority_url": (
            "https://www.realmadrid.com/es-ES/noticias/club/comunicados/"
            "comunicado-oficial-real-madrid-20-06-2026"
        ),
        "authority_domains": {
            "realmadrid.com",
        },
        "authority_subject_terms": [
            "michael",
            "olise",
        ],
        "authority_denial_terms": [
            "no ha mantenido ning\u00fan contacto directo ni indirecto",
            "no se corresponden con la realidad",
            "supuesto inter\u00e9s",
        ],
        "authority_entity": "Real Madrid C. F.",
        "candidate_relationship": (
            "direct_authority_denial_candidate"
        ),
    },
    {
        "candidate_id": (
            "enzo-real-madrid-direct-denial-2026"
        ),
        "subject": "Enzo Fernandez",
        "claim_summary": (
            "Real Madrid were preparing a major bid for "
            "Enzo Fernandez and treated him as a priority "
            "midfield target."
        ),
        "claimant_urls": [
            (
                "https://www.teamtalk.com/chelsea/"
                "real-madrid-transfer-news-enzo-fernandez-bid-chelsea-"
                "xabi-alonso"
            ),
            (
                "https://talksport.com/football/4341751/"
                "enzo-fernandez-transfer-news-real-madrid-chelsea/"
            ),
        ],
        "claimant_domains": {
            "teamtalk.com",
            "talksport.com",
        },
        "claimant_subject_terms": [
            "enzo",
            "fernandez",
            "real madrid",
        ],
        "claimant_assertion_terms": [
            "preparing to test chelsea",
            "leading targets",
            "priority midfield target",
            "interest has intensified",
            "personal terms effectively in place",
            "open talks with chelsea",
        ],
        "authority_url": (
            "https://www.realmadrid.com/es-ES/noticias/club/comunicados/"
            "comunicado-oficial-03-07-2026"
        ),
        "authority_domains": {
            "realmadrid.com",
        },
        "authority_subject_terms": [
            "enzo",
            "fernandez",
        ],
        "authority_denial_terms": [
            "no ha realizado gesti\u00f3n alguna",
            "no tiene intenci\u00f3n alguna",
            "desmentir categ\u00f3ricamente",
            "carecen de fundamento",
            "no responden a la realidad",
        ],
        "authority_entity": "Real Madrid C. F.",
        "candidate_relationship": (
            "direct_authority_denial_candidate"
        ),
    },
    {
        "candidate_id": (
            "musiala-galatasaray-direct-denial-2026"
        ),
        "subject": "Jamal Musiala",
        "claim_summary": (
            "Galatasaray were reported to be close to "
            "completing a loan move for Jamal Musiala."
        ),
        "claimant_urls": [
            (
                "https://www.gzt.com/spor/"
                "son-dakika-galatasaray-on-numara-transferini-bitirmek-"
                "uzere-4245038"
            ),
        ],
        "claimant_domains": {
            "gzt.com",
        },
        "claimant_subject_terms": [
            "musiala",
            "galatasaray",
        ],
        "claimant_assertion_terms": [
            "transferinde sona yaklaştı",
            "anlaşma sağlamak üzere",
            "transferini bitirmeye çok yaklaştı",
            "anlaşma yakın",
            "sona yaklaşıldığı",
        ],
        "authority_url": (
            "https://www.galatasaray.org/haber/kulup/"
            "kamuoyuna-duyuru/60690"
        ),
        "authority_domains": {
            "galatasaray.org",
        },
        "authority_subject_terms": [
            "jamal",
            "musiala",
            "galatasaray",
        ],
        "authority_denial_terms": [
            "iddialar gerçek dışıdır",
            "gerçeği yansıtmayan",
            "gerçek dışı",
        ],
        "authority_entity": (
            "Galatasaray Spor Kulübü"
        ),
        "candidate_relationship": (
            "direct_authority_denial_candidate"
        ),
    },
]


_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _search_text(
    value: Any,
) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        _clean(
            value
        ),
    )

    text = "".join(
        character
        for character
        in normalized
        if not unicodedata.combining(
            character
        )
    )

    return text.casefold()


def _domain(
    value: str,
) -> str:
    try:
        hostname = (
            urlparse(
                value
            ).hostname
            or ""
        ).lower()

    except Exception:
        return ""

    if hostname.startswith(
        "www."
    ):
        hostname = hostname[
            4:
        ]

    if hostname.startswith(
        "uk."
    ):
        hostname = hostname[
            3:
        ]

    return hostname


def _https(
    value: str,
) -> bool:
    try:
        parsed = urlparse(
            value
        )

    except Exception:
        return False

    return (
        parsed.scheme.lower()
        == "https"
        and bool(
            parsed.netloc
        )
    )


def _sha256(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(
    value: Any,
) -> str:
    return _sha256(
        _canonical_json(
            value
        )
    )


def _contains_all(
    text: str,
    terms: List[
        str
    ],
) -> bool:
    haystack = _search_text(
        text
    )

    return all(
        _search_text(
            term
        )
        in haystack
        for term
        in terms
    )


def _contains_any(
    text: str,
    terms: List[
        str
    ],
) -> bool:
    haystack = _search_text(
        text
    )

    return any(
        _search_text(
            term
        )
        in haystack
        for term
        in terms
    )


def _timestamp(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if text.endswith(
        "Z"
    ):
        text = (
            text[
                :-1
            ]
            + "+00:00"
        )

    parsed = datetime.fromisoformat(
        text
    )

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            "Timestamp must include timezone."
        )

    return parsed.isoformat()


def _capture_page(
    *,
    urls: List[
        str
    ],
    allowed_domains,
    subject_terms: List[
        str
    ],
    assertion_terms: List[
        str
    ],
    fetch_article,
    extract_article,
    normalize_url,
) -> Dict[str, Any]:
    failures = []

    for index, requested_url in enumerate(
        urls
    ):
        try:
            canonical_requested = (
                normalize_url(
                    requested_url
                )
            )

            fetched = fetch_article(
                canonical_requested,
                max_bytes=1_500_000,
                timeout_seconds=15.0,
                max_redirects=4,
            )

            final_url = normalize_url(
                _clean(
                    fetched.get(
                        "final_url"
                    )
                )
            )

            domain = _domain(
                final_url
            )

            if (
                domain
                not in allowed_domains
            ):
                raise ValueError(
                    "Unexpected final domain: "
                    + domain
                )

            extraction = extract_article(
                fetched.get(
                    "html",
                    "",
                ),
                max_chars=30_000,
                min_chars=120,
            )

            title = _clean(
                extraction.get(
                    "title"
                )
            )

            body = _clean(
                extraction.get(
                    "text"
                )
            )

            combined = (
                title
                + "\n"
                + body
            )

            if len(
                body
            ) < 120:
                raise ValueError(
                    "Extracted body is too short."
                )

            if not _contains_all(
                combined,
                subject_terms,
            ):
                raise ValueError(
                    "Expected subject identity "
                    "not present."
                )

            if not _contains_any(
                combined,
                assertion_terms,
            ):
                raise ValueError(
                    "Expected claim/denial semantics "
                    "not present."
                )

            captured_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            return {
                "requested_url": (
                    canonical_requested
                ),
                "final_url": (
                    final_url
                ),
                "selected_url_index": (
                    index
                ),
                "domain": (
                    domain
                ),
                "title": (
                    title
                ),
                "content_sha256": (
                    _sha256(
                        body
                    )
                ),
                "character_count": len(
                    body
                ),
                "paragraph_count": int(
                    extraction.get(
                        "paragraph_count",
                        0,
                    )
                    or 0
                ),
                "extraction_method": (
                    _clean(
                        extraction.get(
                            "extraction_method"
                        )
                    )
                ),
                "captured_at": (
                    captured_at
                ),
            }

        except Exception as error:
            failures.append(
                {
                    "url": (
                        requested_url
                    ),
                    "error_type": (
                        type(
                            error
                        ).__name__
                    ),
                    "error": (
                        _clean(
                            str(
                                error
                            )
                        )[
                            :240
                        ]
                    ),
                }
            )

    raise RuntimeError(
        "All candidate source URLs failed: "
        + json.dumps(
            failures,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def validate_candidate_batch(
    manifest: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Candidate batch must be a dictionary."
        )

    if (
        _clean(
            manifest.get(
                "version"
            )
        )
        != (
            NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_BATCH_VERSION
        )
    ):
        raise ValueError(
            "Unsupported candidate batch version."
        )

    cases = manifest.get(
        "cases"
    )

    if (
        not isinstance(
            cases,
            list,
        )
        or len(
            cases
        )
        != 3
    ):
        raise ValueError(
            "Candidate batch must contain "
            "exactly three real-world cases."
        )

    seen = set()

    for case in cases:
        if not isinstance(
            case,
            dict,
        ):
            raise ValueError(
                "Candidate case must be a dictionary."
            )

        if (
            _clean(
                case.get(
                    "version"
                )
            )
            != (
                NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_CASE_VERSION
            )
        ):
            raise ValueError(
                "Candidate case version mismatch."
            )

        candidate_id = _clean(
            case.get(
                "candidate_id"
            )
        )

        if (
            not candidate_id
            or candidate_id
            in seen
        ):
            raise ValueError(
                "Candidate IDs must be unique."
            )

        seen.add(
            candidate_id
        )

        if (
            _clean(
                case.get(
                    "candidate_semantic_status"
                )
            )
            != (
                "unverified_direct_authority_"
                "denial_candidate"
            )
        ):
            raise ValueError(
                "Candidate semantic status "
                "must remain unverified."
            )

        for name in (
            "claimant_capture",
            "authority_capture",
        ):
            capture = case.get(
                name
            )

            if not isinstance(
                capture,
                dict,
            ):
                raise ValueError(
                    name
                    + " is missing."
                )

            url = _clean(
                capture.get(
                    "final_url"
                )
            )

            content_sha = _clean(
                capture.get(
                    "content_sha256"
                )
            ).lower()

            captured_at = _timestamp(
                capture.get(
                    "captured_at"
                )
            )

            if not _https(
                url
            ):
                raise ValueError(
                    name
                    + " requires HTTPS."
                )

            if not _SHA256_RE.fullmatch(
                content_sha
            ):
                raise ValueError(
                    name
                    + " requires SHA-256."
                )

            if not captured_at:
                raise ValueError(
                    name
                    + " capture time is missing."
                )

        score = case.get(
            "claimant_current_merit"
        )

        if not isinstance(
            score,
            dict,
        ):
            raise ValueError(
                "Current claimant Merit "
                "measurement is missing."
            )

        try:
            total = float(
                score.get(
                    "total"
                )
            )

        except (
            TypeError,
            ValueError,
        ) as error:
            raise ValueError(
                "Current claimant Merit "
                "must be numeric."
            ) from error

        if not (
            0.0
            <= total
            <= 100.0
        ):
            raise ValueError(
                "Current claimant Merit "
                "must be between 0 and 100."
            )

        policy = case.get(
            "policy"
        )

        if not isinstance(
            policy,
            dict,
        ):
            raise ValueError(
                "Candidate policy is missing."
            )

        required_false = (
            "claim_truth_established",
            "machine_semantics_verified",
            "direct_authority_gate_verified",
            "numeric_negative_penalty_authorized",
            "live_negative_merit_authorized",
            "provider_call_performed",
            "production_database_written",
        )

        for field in required_false:
            if (
                policy.get(
                    field
                )
                is not False
            ):
                raise ValueError(
                    "Candidate safety field "
                    + field
                    + " must be false."
                )

    core = {
        key: value
        for key, value
        in manifest.items()
        if key
        != "manifest_digest"
    }

    expected_digest = _digest(
        core
    )

    if (
        _clean(
            manifest.get(
                "manifest_digest"
            )
        )
        != expected_digest
    ):
        raise ValueError(
            "Candidate manifest digest mismatch."
        )

    return {
        "status": "valid",
        "case_count": len(
            cases
        ),
        "manifest_digest": (
            expected_digest
        ),
    }


def capture_real_world_candidate_batch(
    *,
    fetch_article,
    extract_article,
    normalize_url,
    detect_article_type,
    merit_score,
) -> Dict[str, Any]:
    captured_cases = []

    for definition in CASES:
        print()
        print(
            "CAPTURING_CANDIDATE|"
            + definition[
                "candidate_id"
            ]
        )

        claimant = _capture_page(
            urls=(
                definition[
                    "claimant_urls"
                ]
            ),
            allowed_domains=(
                definition[
                    "claimant_domains"
                ]
            ),
            subject_terms=(
                definition[
                    "claimant_subject_terms"
                ]
            ),
            assertion_terms=(
                definition[
                    "claimant_assertion_terms"
                ]
            ),
            fetch_article=(
                fetch_article
            ),
            extract_article=(
                extract_article
            ),
            normalize_url=(
                normalize_url
            ),
        )

        authority = _capture_page(
            urls=[
                definition[
                    "authority_url"
                ]
            ],
            allowed_domains=(
                definition[
                    "authority_domains"
                ]
            ),
            subject_terms=(
                definition[
                    "authority_subject_terms"
                ]
            ),
            assertion_terms=(
                definition[
                    "authority_denial_terms"
                ]
            ),
            fetch_article=(
                fetch_article
            ),
            extract_article=(
                extract_article
            ),
            normalize_url=(
                normalize_url
            ),
        )

        claimant_fetch = fetch_article(
            claimant[
                "final_url"
            ],
            max_bytes=1_500_000,
            timeout_seconds=15.0,
            max_redirects=1,
        )

        claimant_extract = extract_article(
            claimant_fetch.get(
                "html",
                "",
            ),
            max_chars=30_000,
            min_chars=120,
        )

        claimant_text = _clean(
            claimant_extract.get(
                "text"
            )
        )

        claimant_title = _clean(
            claimant_extract.get(
                "title"
            )
        )

        claimant_type = detect_article_type(
            claimant_title,
            claimant_text,
            claimant[
                "final_url"
            ],
        )

        claimant_score = merit_score(
            claimant_title,
            claimant_text,
            claimant[
                "final_url"
            ],
            claimant_type,
        )

        current_merit = {
            "total": int(
                claimant_score[
                    "total"
                ]
            ),
            "article_type": (
                _clean(
                    claimant_type.get(
                        "primary_type"
                    )
                )
            ),
            "type_confidence": float(
                claimant_type.get(
                    "confidence",
                    0.0,
                )
                or 0.0
            ),
            "measurement_scope": (
                "current_retrievable_claimant_page"
            ),
            "not_a_truth_probability": True,
        }

        case = {
            "version": (
                NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_CASE_VERSION
            ),
            "candidate_id": (
                definition[
                    "candidate_id"
                ]
            ),
            "origin": (
                "real_world"
            ),
            "subject": (
                definition[
                    "subject"
                ]
            ),
            "claim_summary": (
                definition[
                    "claim_summary"
                ]
            ),
            "candidate_relationship": (
                definition[
                    "candidate_relationship"
                ]
            ),
            "candidate_semantic_status": (
                "unverified_direct_authority_"
                "denial_candidate"
            ),
            "authority_entity": (
                definition[
                    "authority_entity"
                ]
            ),
            "claimant_capture": (
                claimant
            ),
            "authority_capture": (
                authority
            ),
            "claimant_current_merit": (
                current_merit
            ),
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

        captured_cases.append(
            case
        )

        print(
            "CLAIMANT|"
            + claimant[
                "domain"
            ]
            + "|"
            + claimant[
                "content_sha256"
            ]
            + "|merit="
            + str(
                current_merit[
                    "total"
                ]
            )
            + "|type="
            + current_merit[
                "article_type"
            ]
        )

        print(
            "AUTHORITY|"
            + authority[
                "domain"
            ]
            + "|"
            + authority[
                "content_sha256"
            ]
        )

    core = {
        "version": (
            NEGATIVE_MERIT_REAL_WORLD_CANDIDATE_BATCH_VERSION
        ),
        "captured_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "case_count": len(
            captured_cases
        ),
        "cases": (
            captured_cases
        ),
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

    manifest = dict(
        core
    )

    manifest[
        "manifest_digest"
    ] = _digest(
        core
    )

    validate_candidate_batch(
        manifest
    )

    return manifest


def main(
    argv=None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the frozen real-world "
            "Negative Merit candidate batch."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    args = parser.parse_args(
        argv
    )

    from app.services.article_rules import (
        detect_article_type,
        merit_score,
    )

    from app.services.content_resolution import (
        extract_article_content,
        fetch_safe_article_html,
        normalized_analysis_url,
    )

    manifest = (
        capture_real_world_candidate_batch(
            fetch_article=(
                fetch_safe_article_html
            ),
            extract_article=(
                extract_article_content
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            detect_article_type=(
                detect_article_type
            ),
            merit_score=(
                merit_score
            ),
        )
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "CASE_COUNT="
        + str(
            manifest[
                "case_count"
            ]
        )
    )

    print(
        "MANIFEST_DIGEST="
        + manifest[
            "manifest_digest"
        ]
    )

    print(
        "REAL_WORLD_NEGATIVE_CANDIDATE_CAPTURE=PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
