from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)
from urllib.parse import urlparse


from app.services.article_intelligence_shadow import (
    ARTICLE_PRIMARY_CLAIM_TYPES,
)

from app.services.article_rules import (
    detect_article_type,
)


HISTORICAL_ARTICLE_CLAIM_BACKFILL_PLAN_VERSION = (
    "historical-article-claim-backfill-plan-v1"
)

HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION = (
    "historical-article-claim-backfill-report-v1"
)

BACKFILL_DECISIONS = {
    "admit",
    "review",
    "reject",
}


_EXCLUDED_SERVICE_PATTERNS = (
    re.compile(
        r"\bsign[\s-]*up\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsignup\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnewsletter\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bemail\s+sign[\s-]*up\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsubscribe\b",
        re.IGNORECASE,
    ),
)


_SIGNAL_FAMILIES = {
    "transfer_completed": {
        "article_types": {
            "transfer_official",
        },
        "patterns": (
            re.compile(
                r"\b(?:has|have)\s+signed\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsigns\s+(?:for|with)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsigned\s+(?:for|with|by)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bjoins?\s+from\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bjoins?\s+on\s+loan\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bcompletes?\s+(?:(?:a|his|her|their)\s+)?"
                r"(?:move|transfer)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bannounces?\s+(?:the\s+)?signing\b",
                re.IGNORECASE,
            ),
        ),
    },
    "transfer_market": {
        "article_types": {
            "transfer_report",
            "transfer_rumor",
        },
        "patterns": (
            re.compile(
                r"\btransfer\s+(?:rumou?r|news|update|latest|talk)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\blinked\s+(?:with|to)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bkeen\s+on\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\binterested\s+in\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\binterest\s+in\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bbid\s+for\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\boffer\s+for\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bmove\s+for\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bwant(?:s|ed)?\s+to\s+sign\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\beyeing\b",
                re.IGNORECASE,
            ),
        ),
    },
    "injury": {
        "article_types": {
            "injury_confirmed",
            "injury_rumor",
        },
        "patterns": (
            re.compile(
                r"\binjur(?:y|ed|ies)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bfitness\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bruled\s+out\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bdoubtful\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bcould\s+miss\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bmay\s+miss\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bwill\s+miss\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bset\s+to\s+miss\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bout\s+for\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bhamstring\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bankle\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bknee\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bconcussion\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsurgery\b",
                re.IGNORECASE,
            ),
        ),
    },
    "lineup": {
        "article_types": {
            "lineup_confirmed",
            "lineup_predicted",
            "squad_news",
        },
        "patterns": (
            re.compile(
                r"\bconfirmed\s+(?:lineup|line-up|xi)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bpredicted\s+(?:lineup|line-up|xi|team)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bstarting\s+(?:xi|eleven|lineup)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bteam\s+news\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsquad\s+news\b",
                re.IGNORECASE,
            ),
        ),
    },
    "discipline_legal": {
        "article_types": {
            "discipline_legal",
        },
        "patterns": (
            re.compile(
                r"\barrested\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bcharged\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bbanned\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsuspended\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsuspension\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\binvestigat(?:ed|ion|ing)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bcourt\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\blawsuit\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bdisciplinary\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bfined\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bmisconduct\b",
                re.IGNORECASE,
            ),
        ),
    },
    "managerial": {
        "article_types": {
            "managerial_news",
        },
        "patterns": (
            re.compile(
                r"\bappointed\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsacked\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bdismissed\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bresigns?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsteps?\s+down\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bhead\s+coach\s+deal\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bmanager\s+deal\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\boffered\s+(?:the\s+)?"
                r"(?:manager|head\s+coach)\s+(?:job|deal)\b",
                re.IGNORECASE,
            ),
        ),
    },
    "contract": {
        "article_types": {
            "contract_news",
        },
        "patterns": (
            re.compile(
                r"\bnew\s+contract\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bcontract\s+extension\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bnew\s+deal\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bagrees?\s+(?:a\s+)?new\s+deal\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bextension\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\brelease\s+clause\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bwage(?:s)?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bsalary\b",
                re.IGNORECASE,
            ),
        ),
    },
    "fixture_schedule": {
        "article_types": {
            "fixture_schedule",
        },
        "patterns": (
            re.compile(
                r"\bfixtures?\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bschedule\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\brescheduled\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bpostponed\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bkick[\s-]?off\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bdate\s+confirmed\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\btournament\s+draw\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bgroup(?:-stage)?\s+draw\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bfixtures?\s+released\b",
                re.IGNORECASE,
            ),
        ),
    },
    "official_announcement": {
        "article_types": {
            "official_announcement",
        },
        "patterns": (
            re.compile(
                r"\bofficial\s+announcement\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bofficially\s+announces?\b",
                re.IGNORECASE,
            ),
        ),
    },
}



def _planned_type_from_explicit_family(
    *,
    title: str,
    family: str,
) -> str:
    normalized_family = _key(
        family
    )

    if normalized_family == "transfer_completed":
        return "transfer_official"

    if normalized_family == "transfer_market":
        return "transfer_rumor"

    if normalized_family == "injury":
        if re.search(
            (
                r"\b(?:ruled\s+out|"
                r"will\s+miss|"
                r"set\s+to\s+miss|"
                r"out\s+injured|"
                r"surgery)\b"
            ),
            title,
            re.IGNORECASE,
        ):
            return "injury_confirmed"

        return "injury_rumor"

    if normalized_family == "lineup":
        if re.search(
            r"\bconfirmed\s+(?:lineup|line-up|xi)\b",
            title,
            re.IGNORECASE,
        ):
            return "lineup_confirmed"

        if re.search(
            r"\bpredicted\s+(?:lineup|line-up|xi|team)\b",
            title,
            re.IGNORECASE,
        ):
            return "lineup_predicted"

        return "squad_news"

    family_types = {
        "discipline_legal": (
            "discipline_legal"
        ),
        "managerial": (
            "managerial_news"
        ),
        "contract": (
            "contract_news"
        ),
        "fixture_schedule": (
            "fixture_schedule"
        ),
        "official_announcement": (
            "official_announcement"
        ),
    }

    return family_types.get(
        normalized_family,
        "",
    )

def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


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
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _is_https(
    value: Any,
) -> bool:
    text = _clean(
        value
    )

    try:
        parsed = urlparse(
            text
        )

    except Exception:
        return False

    return bool(
        parsed.scheme.lower()
        == "https"
        and parsed.netloc
    )


def _score(
    value: Any,
):
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        result
    ):
        return None

    if not (
        0.0
        <= result
        <= 100.0
    ):
        return None

    return result


def _service_or_subscription_content(
    *,
    title: str,
    url: str,
) -> bool:
    text = (
        title
        + " "
        + url
    )

    return any(
        pattern.search(
            text
        )
        is not None
        for pattern
        in _EXCLUDED_SERVICE_PATTERNS
    )


def _explicit_signal_families(
    title: str,
) -> List[
    str
]:
    matched = []

    for family, config in (
        _SIGNAL_FAMILIES.items()
    ):
        if any(
            pattern.search(
                title
            )
            is not None
            for pattern
            in config[
                "patterns"
            ]
        ):
            matched.append(
                family
            )

    return sorted(
        matched
    )


def _compatible_families(
    article_type: str,
):
    return sorted(
        family
        for family, config
        in _SIGNAL_FAMILIES.items()
        if article_type
        in config[
            "article_types"
        ]
    )


def evaluate_historical_story_for_backfill(
    *,
    story: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        story,
        dict,
    ):
        raise ValueError(
            "Historical story must be a dictionary."
        )

    story_id = _clean(
        story.get(
            "id"
        )
    )

    title = _clean(
        story.get(
            "title"
        )
    )

    summary = _clean(
        story.get(
            "summary"
        )
    )

    url = _clean(
        story.get(
            "link"
        )
    )

    source = _clean(
        story.get(
            "source"
        )
    )

    sport = _clean(
        story.get(
            "sport"
        )
    )

    published = _clean(
        story.get(
            "published"
        )
    )

    created_at = _clean(
        story.get(
            "created_at"
        )
    )

    observed_at = (
        published
        or created_at
    )

    blockers = []

    if not story_id:
        blockers.append(
            "story_id_missing"
        )

    if not title:
        blockers.append(
            "title_missing"
        )

    if not _is_https(
        url
    ):
        blockers.append(
            "https_url_required"
        )

    if not observed_at:
        blockers.append(
            "observed_at_missing"
        )

    if blockers:
        return {
            "story_id": story_id,
            "decision": "reject",
            "reason": (
                "required_historical_identity_missing"
            ),
            "blockers": blockers,
            "title": title,
            "url": url,
            "source": source,
            "sport": sport,
            "observed_at": observed_at,
            "current_rule_type": "",
            "current_rule_confidence": 0.0,
            "explicit_signal_families": [],
            "historical_merit_score": (
                _score(
                    story.get(
                        "merit_score"
                    )
                )
            ),
            "calibration_baseline_eligible": False,
        }

    classification = detect_article_type(
        title,
        summary,
        url,
    )

    article_type = _key(
        classification.get(
            "primary_type"
        )
    )

    try:
        confidence = float(
            classification.get(
                "confidence"
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):
        confidence = 0.0

    current_claim_bearing = (
        article_type
        in ARTICLE_PRIMARY_CLAIM_TYPES
    )

    explicit_families = (
        _explicit_signal_families(
            title
        )
    )

    compatible_families = (
        _compatible_families(
            article_type
        )
    )

    matching_families = sorted(
        set(
            explicit_families
        ).intersection(
            compatible_families
        )
    )

    service_content = (
        _service_or_subscription_content(
            title=title,
            url=url,
        )
    )

    planned_article_type = ""
    planned_article_type_source = ""

    if service_content:
        decision = "reject"
        reason = (
            "subscription_or_service_content"
        )

    elif current_claim_bearing:
        if len(
            explicit_families
        ) == 0:
            decision = "review"
            reason = (
                "claim_bearing_rule_without_"
                "explicit_headline_claim_signal"
            )

        elif len(
            matching_families
        ) == 1:
            decision = "admit"
            reason = (
                "current_rule_confirmed_by_"
                "explicit_headline_claim_signal"
            )
            planned_article_type = (
                article_type
            )
            planned_article_type_source = (
                "current_rule_confirmed_by_headline"
            )

        elif len(
            matching_families
        ) == 0:
            decision = "review"
            reason = (
                "headline_signal_conflicts_with_"
                "current_rule_type"
            )

        else:
            decision = "review"
            reason = (
                "multiple_compatible_headline_"
                "claim_signals"
            )

    elif len(
        explicit_families
    ) == 1:
        recovered_type = (
            _planned_type_from_explicit_family(
                title=title,
                family=(
                    explicit_families[
                        0
                    ]
                ),
            )
        )

        if (
            recovered_type
            in ARTICLE_PRIMARY_CLAIM_TYPES
        ):
            decision = "admit"
            reason = (
                "explicit_headline_claim_signal_"
                "recovers_classifier_miss"
            )
            planned_article_type = (
                recovered_type
            )
            planned_article_type_source = (
                "explicit_headline_signal"
            )

        else:
            decision = "review"
            reason = (
                "explicit_headline_signal_"
                "has_no_safe_seed_type"
            )

    elif len(
        explicit_families
    ) > 1:
        decision = "review"
        reason = (
            "multiple_headline_claim_signals_"
            "with_non_claim_classifier"
        )

    else:
        decision = "reject"
        reason = (
            "current_rule_not_claim_bearing"
        )

    return {
        "story_id": story_id,
        "decision": decision,
        "reason": reason,
        "blockers": [],
        "title": title,
        "summary_chars": len(
            summary
        ),
        "url": url,
        "source": source,
        "sport": sport,
        "observed_at": observed_at,
        "current_rule_type": (
            article_type
        ),
        "current_rule_confidence": round(
            confidence,
            3,
        ),
        "planned_article_type": (
            planned_article_type
        ),
        "planned_article_type_source": (
            planned_article_type_source
        ),
        "explicit_signal_families": (
            explicit_families
        ),
        "matching_signal_families": (
            matching_families
        ),
        "historical_merit_score": (
            _score(
                story.get(
                    "merit_score"
                )
            )
        ),
        "calibration_baseline_eligible": False,
        "policy": {
            "historical_score_is_archival_only": True,
            "headline_seed_does_not_establish_truth": True,
            "planner_does_not_write_database": True,
            "planner_does_not_call_provider": True,
            "admit_means_seed_candidate_only": True,
            "review_requires_separate_curation": True,
        },
    }


def _connect_read_only(
    db_path: Path,
):
    resolved = Path(
        db_path
    ).resolve()

    if not resolved.is_file():
        raise FileNotFoundError(
            "Sportabase database not found: "
            + str(
                resolved
            )
        )

    conn = sqlite3.connect(
        resolved.as_uri()
        + "?mode=ro",
        uri=True,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA query_only=ON;"
    )

    return conn


def build_historical_article_claim_backfill_plan(
    *,
    db_path: Path,
) -> Dict[str, Any]:
    path = Path(
        db_path
    ).resolve()

    conn = _connect_read_only(
        path
    )

    try:
        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'stories'
            """
        ).fetchone()

        if row is None:
            raise ValueError(
                "Historical stories table "
                "does not exist."
            )

        stories = [
            dict(
                item
            )
            for item
            in conn.execute(
                """
                SELECT *
                FROM stories
                ORDER BY
                  created_at,
                  id
                """
            ).fetchall()
        ]

        cases = [
            evaluate_historical_story_for_backfill(
                story=story
            )
            for story
            in stories
        ]

        decision_counts = {
            decision: 0
            for decision
            in sorted(
                BACKFILL_DECISIONS
            )
        }

        reason_counts = {}

        for case in cases:
            decision_counts[
                case[
                    "decision"
                ]
            ] += 1

            reason = case[
                "reason"
            ]

            reason_counts[
                reason
            ] = (
                reason_counts.get(
                    reason,
                    0,
                )
                + 1
            )

        admitted = [
            case
            for case
            in cases
            if case[
                "decision"
            ]
            == "admit"
        ]

        review = [
            case
            for case
            in cases
            if case[
                "decision"
            ]
            == "review"
        ]

        rejected = [
            case
            for case
            in cases
            if case[
                "decision"
            ]
            == "reject"
        ]

        report_core = {
            "version": (
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION
            ),
            "planner_version": (
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_PLAN_VERSION
            ),
            "status": (
                "ready"
            ),
            "database": {
                "path": str(
                    path
                ),
                "read_only": True,
            },
            "metrics": {
                "historical_story_count": len(
                    cases
                ),
                "admit_count": len(
                    admitted
                ),
                "review_count": len(
                    review
                ),
                "reject_count": len(
                    rejected
                ),
                "calibration_baseline_eligible_count": 0,
            },
            "decision_counts": (
                decision_counts
            ),
            "reason_counts": dict(
                sorted(
                    reason_counts.items()
                )
            ),
            "admit": admitted,
            "review": review,
            "reject": rejected,
            "policy": {
                "database_opened_read_only": True,
                "provider_call_performed": False,
                "database_write_performed": False,
                "current_classifier_confidence_is_not_backfill_authority": True,
                "explicit_headline_claim_signal_required_for_admission": True,
            "single_unambiguous_headline_signal_may_recover_classifier_miss": True,
            "recovered_article_type_is_seed_only_not_truth": True,
                "subscription_content_is_rejected": True,
                "classifier_signal_mismatch_requires_review": True,
                "historical_merit_score_is_not_current_calibration_baseline": True,
                "admission_does_not_establish_truth": True,
                "admission_does_not_enable_live_merit": True,
            },
        }

        digest_payload = {
            "version": report_core[
                "version"
            ],
            "planner_version": (
                report_core[
                    "planner_version"
                ]
            ),
            "metrics": report_core[
                "metrics"
            ],
            "decision_counts": (
                decision_counts
            ),
            "reason_counts": (
                report_core[
                    "reason_counts"
                ]
            ),
            "admit": admitted,
            "review": review,
            "reject": rejected,
        }

        return {
            **report_core,
            "report_digest": (
                _digest(
                    digest_payload
                )
            ),
        }

    finally:
        conn.close()


def write_backfill_plan(
    path: Path,
    report: Dict[str, Any],
) -> None:
    destination = Path(
        path
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
