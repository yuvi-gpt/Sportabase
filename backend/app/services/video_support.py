import re

from functools import lru_cache

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from lingua import (
    LanguageDetectorBuilder,
)

from app.services.article_rules import (
    clean_html,
)


def prepare_video_transcript(transcript: str) -> Dict[str, Any]:
    raw_transcript = clean_html(transcript)

    cleaned_transcript = re.sub(
        r"\[(music|applause|laughter)\]",
        " ",
        raw_transcript,
        flags=re.IGNORECASE,
    )
    cleaned_transcript = re.sub(
        r"\s+",
        " ",
        cleaned_transcript,
    ).strip()

    return {
        "raw_transcript": raw_transcript,
        "cleaned_transcript": cleaned_transcript,
        "transcript_confidence": None,
        "uncertain_corrections": [],
    }


def split_video_transcript(
    transcript: str,
    chunk_size: int = 4000,
    overlap: int = 400,
) -> List[str]:
    text = clean_html(transcript)

    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    overlap = max(0, min(overlap, chunk_size - 1))
    step = chunk_size - overlap

    chunks: List[str] = []

    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size].strip()

        if chunk:
            chunks.append(chunk)

        if start + chunk_size >= len(text):
            break

    return chunks


@lru_cache(maxsize=1)
def get_language_detector():
    """
    Build one reusable offline detector containing every modern spoken
    language supported by Lingua.
    """
    return (
        LanguageDetectorBuilder
        .from_all_spoken_languages()
        .with_low_accuracy_mode()
        .build()
    )


def lingua_language_name(language: Any) -> str:
    return str(language.name).replace("_", " ").title()


def detect_content_language(text: str) -> Dict[str, Any]:
    """
    Detect article languages locally without using Gemini quota.

    Lingua handles the primary language and substantial multilingual
    sections. A small additional heuristic handles Romanized Hindi and
    Hinglish, which are harder for script-based language detectors.
    """
    cleaned = clean_html(text).strip()

    unknown_result = {
        "detected_language": "unknown",
        "languages": [],
        "mixed_language": False,
        "language_confidence": 0.0,
        "detection_method": "lingua_local",
        "language_candidates": [],
    }

    if not cleaned:
        return unknown_result

    if len(cleaned) <= 12000:
        sample = cleaned
    else:
        sample = (
            cleaned[:6000]
            + "\n\n[END SAMPLE]\n\n"
            + cleaned[-6000:]
        )

    letter_count = sum(
        1
        for character in sample
        if character.isalpha()
    )

    if letter_count < 10:
        return unknown_result

    try:
        detector = get_language_detector()

        primary_language = detector.detect_language_of(
            sample
        )

        if primary_language is None:
            return unknown_result

        primary_name = lingua_language_name(
            primary_language
        )

        confidence_values = (
            detector.compute_language_confidence_values(sample)
        )

        if confidence_values:
            primary_confidence = next(
                (
                    float(candidate.value)
                    for candidate in confidence_values
                    if candidate.language == primary_language
                ),
                float(confidence_values[0].value),
            )

            candidates = [
                {
                    "language": lingua_language_name(
                        candidate.language
                    ),
                    "confidence": round(
                        float(candidate.value),
                        3,
                    ),
                }
                for candidate in confidence_values[:3]
            ]
        else:
            # Lingua's alphabet rule engine identified the
            # language without requiring n-gram probabilities.
            primary_confidence = 1.0
            candidates = [
                {
                    "language": primary_name,
                    "confidence": 1.0,
                }
            ]

        # Detect substantial sections written in different languages.
        segment_weights: Dict[str, int] = {}

        for segment in detector.detect_multiple_languages_of(sample):
            segment_text = sample[
                segment.start_index:segment.end_index
            ]

            segment_letters = sum(
                1
                for character in segment_text
                if character.isalpha()
            )

            if segment_letters <= 0:
                continue

            segment_name = lingua_language_name(
                segment.language
            )

            segment_weights[segment_name] = (
                segment_weights.get(segment_name, 0)
                + segment_letters
            )

        total_segment_letters = sum(
            segment_weights.values()
        )

        major_languages = []

        if total_segment_letters > 0:
            major_languages = [
                (
                    language,
                    weight / total_segment_letters,
                )
                for language, weight in segment_weights.items()
                if (
                    weight >= 80
                    and weight / total_segment_letters >= 0.15
                )
            ]

            major_languages.sort(
                key=lambda item: item[1],
                reverse=True,
            )

        detected_languages = [
            language
            for language, _ratio in major_languages[:3]
        ]

        mixed_language = len(detected_languages) >= 2

        if not mixed_language:
            detected_languages = [primary_name]

        detected_language = (
            " / ".join(detected_languages) + " mixed"
            if mixed_language
            else primary_name
        )

        # Romanized Hindi and Hinglish overlay.
        tokens = re.findall(
            r"[A-Za-z']+",
            sample.lower(),
        )

        romanized_hindi_markers = {
            "hai",
            "hain",
            "nahi",
            "nahin",
            "kya",
            "kyun",
            "kaise",
            "lekin",
            "mein",
            "mera",
            "meri",
            "hum",
            "tum",
            "unka",
            "unki",
            "uska",
            "uski",
            "raha",
            "rahi",
            "rahe",
            "gaya",
            "gayi",
            "karna",
            "kiya",
            "karo",
            "wala",
            "wali",
            "bahut",
            "thoda",
            "abhi",
            "aaj",
            "hoga",
            "hogi",
            "shayad",
            "bilkul",
            "magar",
            "kyunki",
        }

        english_markers = {
            "the",
            "and",
            "that",
            "this",
            "with",
            "from",
            "have",
            "has",
            "was",
            "were",
            "will",
            "would",
            "their",
            "about",
            "after",
            "before",
            "because",
            "during",
            "into",
            "also",
            "club",
            "team",
            "player",
            "match",
        }

        hindi_hits = sum(
            1
            for token in tokens
            if token in romanized_hindi_markers
        )

        english_hits = sum(
            1
            for token in tokens
            if token in english_markers
        )

        token_count = max(1, len(tokens))
        hindi_ratio = hindi_hits / token_count

        looks_romanized_hindi = (
            primary_name in {
                "English",
                "Hindi",
                "Urdu",
            }
            and hindi_hits >= 6
            and hindi_ratio >= 0.015
        )

        if looks_romanized_hindi:
            has_substantial_english = (
                english_hits >= 6
            )

            if has_substantial_english:
                detected_language = (
                    "Hindi-English mixed"
                )
                detected_languages = [
                    "Hindi",
                    "English",
                ]
                mixed_language = True
            else:
                detected_language = (
                    "Hindi (Romanized)"
                )
                detected_languages = ["Hindi"]
                mixed_language = False

            primary_confidence = max(
                primary_confidence,
                0.75,
            )

        return {
            "detected_language": detected_language,
            "languages": detected_languages,
            "mixed_language": mixed_language,
            "language_confidence": round(
                max(
                    0.0,
                    min(1.0, primary_confidence),
                ),
                2,
            ),
            "detection_method": "lingua_local",
            "language_candidates": candidates,
        }

    except Exception as error:
        return {
            **unknown_result,
            "error": (
                f"{type(error).__name__}: "
                f"{str(error)[:160]}"
            ),
        }


def _video_context_tokens(
    value: str,
) -> set[str]:
    tokens = set(
        re.findall(
            r"[^\W_]{3,}",
            str(value or "").lower(),
            flags=re.UNICODE,
        )
    )

    stopwords = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "have",
        "has",
        "was",
        "were",
        "will",
        "would",
        "about",
        "into",
        "their",
        "they",
        "them",
        "then",
        "than",
        "but",
        "for",
        "you",
        "your",
        "video",
    }

    return {
        token
        for token in tokens
        if token not in stopwords
    }


COVERAGE_BUDGET_RATIO = 60
MAX_CANDIDATE_CHARS = 360
COVERAGE_SLOT_CHARS = 440


def _video_context_candidate_spans(
    text: str,
    max_candidate_chars: int = MAX_CANDIDATE_CHARS,
) -> List[Dict[str, Any]]:
    """Return bounded, contiguous verbatim spans with source offsets."""
    if not text:
        return []

    rough_spans: List[tuple[int, int]] = []
    start = 0

    for match in re.finditer(
        r"[.!?\u2026]+(?=\s+|$)",
        text,
    ):
        end = match.end()
        if text[start:end].strip():
            rough_spans.append((start, end))
        start = end

    if start < len(text) and text[start:].strip():
        rough_spans.append((start, len(text)))

    if not rough_spans and text.strip():
        rough_spans = [(0, len(text))]

    # Combine tiny adjacent sentence fragments while retaining the exact
    # contiguous source slice between them.
    combined: List[tuple[int, int]] = []
    for span_start, span_end in rough_spans:
        while span_start < span_end and text[span_start].isspace():
            span_start += 1
        while span_end > span_start and text[span_end - 1].isspace():
            span_end -= 1
        if span_start >= span_end:
            continue

        if (
            combined
            and combined[-1][1] <= span_start
            and combined[-1][1] - combined[-1][0] < 80
            and span_end - combined[-1][0] <= max_candidate_chars
        ):
            combined[-1] = (combined[-1][0], span_end)
        else:
            combined.append((span_start, span_end))

    candidates: List[Dict[str, Any]] = []
    ordinal = 0

    for span_start, span_end in combined:
        cursor = span_start
        while cursor < span_end:
            while cursor < span_end and text[cursor].isspace():
                cursor += 1
            if cursor >= span_end:
                break

            limit = min(span_end, cursor + max_candidate_chars)
            cut = limit
            if limit < span_end:
                whitespace = max(
                    text.rfind(" ", cursor, limit + 1),
                    text.rfind("\t", cursor, limit + 1),
                    text.rfind("\n", cursor, limit + 1),
                )
                if whitespace > cursor:
                    cut = whitespace

            if cut <= cursor:
                cut = min(span_end, cursor + max_candidate_chars)

            candidate_start = cursor
            candidate_end = cut
            while (
                candidate_end > candidate_start
                and text[candidate_end - 1].isspace()
            ):
                candidate_end -= 1

            if candidate_end > candidate_start:
                candidates.append(
                    {
                        "text": text[candidate_start:candidate_end],
                        "start_offset": candidate_start,
                        "end_offset": candidate_end,
                        "ordinal": ordinal,
                    }
                )
                ordinal += 1

            cursor = max(cut, cursor + 1)

    return candidates


def _video_context_sentences(
    text: str,
    max_sentence_chars: int = 420,
) -> List[str]:
    """Compatibility wrapper for callers that need text-only candidates."""
    return [
        candidate["text"]
        for candidate in _video_context_candidate_spans(
            re.sub(r"\s+", " ", clean_html(text)).strip(),
            max_candidate_chars=max_sentence_chars,
        )
    ]


def build_video_transcript_context(
    title: str,
    transcript: str,
    max_chars: int = 9000,
    chunk_size: int = 3000,
) -> Dict[str, Any]:
    cleaned = re.sub(
        r"\s+",
        " ",
        clean_html(transcript),
    ).strip()

    if not cleaned:
        return {
            "text": "",
            "strategy": "empty",
            "compression_applied": False,
            "source_chars": 0,
            "context_chars": 0,
            "source_chunk_count": 0,
            "represented_chunk_count": 0,
            "selected_sentence_count": 0,
            "chunk_coverage": 0.0,
            "coverage_window_count": 0,
            "represented_window_count": 0,
            "coverage_anchor_count": 0,
            "global_salience_count": 0,
            "window_coverage": 0.0,
        }

    chunks = split_video_transcript(
        cleaned,
        chunk_size=max(
            500,
            chunk_size,
        ),
        overlap=0,
    )

    if not chunks:
        chunks = [cleaned]

    if len(cleaned) <= max_chars:
        return {
            "text": cleaned,
            "strategy": "full_transcript",
            "compression_applied": False,
            "source_chars": len(cleaned),
            "context_chars": len(cleaned),
            "source_chunk_count": len(chunks),
            "represented_chunk_count": (
                len(chunks)
            ),
            "selected_sentence_count": sum(
                len(
                    _video_context_sentences(
                        chunk
                    )
                )
                for chunk in chunks
            ),
            "chunk_coverage": 1.0,
            "coverage_window_count": 1,
            "represented_window_count": 1,
            "coverage_anchor_count": 0,
            "global_salience_count": 0,
            "window_coverage": 1.0,
        }

    source_chars = len(cleaned)
    legacy_chunk_size = max(500, chunk_size)
    legacy_source_chunk_count = max(
        1,
        (source_chars + legacy_chunk_size - 1)
        // legacy_chunk_size,
    )
    coverage_budget = (
        max_chars * COVERAGE_BUDGET_RATIO // 100
    )
    raw_window_capacity = max(
        1,
        coverage_budget // COVERAGE_SLOT_CHARS,
    )
    window_count = min(
        raw_window_capacity,
        legacy_source_chunk_count,
    )

    title_tokens = _video_context_tokens(title)
    marker_groups = {
        "attribution": (
            "according to", "reported by", "reports", "reported",
            "said", "says", "statement", "official", "confirmed",
            "announced", "seg\u00fan", "inform\u00f3", "confirm\u00f3",
            "selon", "rapport\u00e9", "confirm\u00e9", "ke mutabik",
            "kaha",
        ),
        "transfer": (
            "transfer", "signed", "signing", "bid", "offer", "fee",
            "contract", "loan", "release clause", "fichaje", "transfert",
        ),
        "injury": (
            "injury", "injured", "fitness", "ruled out", "available",
            "suspended", "returned", "lesi\u00f3n", "blessure", "chot",
        ),
        "event": (
            "goal", "scored", "wicket", "dismissed", "penalty",
            "red card", "lap", "pit stop", "result", "won", "lost",
            "draw", "gol", "resultado", "r\u00e9sultat",
        ),
        "argument": (
            "because", "therefore", "however", "although", "means",
            "suggests", "shows", "porque", "sin embargo", "parce que",
            "cependant", "kyunki", "lekin",
        ),
    }

    candidates = _video_context_candidate_spans(cleaned)

    # This is defensive: non-empty text normally always creates candidates.
    # Distributed window slices avoid reverting to first-only truncation.
    if not candidates:
        for window_index in range(window_count):
            window_start = window_index * source_chars // window_count
            window_end = (window_index + 1) * source_chars // window_count
            excerpt_end = min(window_end, window_start + MAX_CANDIDATE_CHARS)
            while (
                excerpt_end < window_end
                and excerpt_end > window_start
                and not cleaned[excerpt_end].isspace()
            ):
                excerpt_end -= 1
            if excerpt_end <= window_start:
                excerpt_end = min(window_end, window_start + MAX_CANDIDATE_CHARS)
            excerpt = cleaned[window_start:excerpt_end].strip()
            if excerpt:
                adjusted_start = cleaned.find(excerpt, window_start, excerpt_end)
                candidates.append(
                    {
                        "text": excerpt,
                        "start_offset": adjusted_start,
                        "end_offset": adjusted_start + len(excerpt),
                        "ordinal": len(candidates),
                    }
                )

    prepared_candidates: List[Dict[str, Any]] = []
    seen_by_window: Dict[int, set[str]] = {}

    def contains_marker(
        value: str,
        markers: tuple[str, ...],
    ) -> bool:
        return any(
            re.search(
                rf"(?<!\w){re.escape(marker)}(?!\w)",
                value,
            )
            is not None
            for marker in markers
        )

    for candidate in candidates:
        text = candidate["text"]
        start_offset = int(candidate["start_offset"])
        end_offset = int(candidate["end_offset"])
        midpoint = start_offset + (end_offset - start_offset) // 2
        window_index = min(
            window_count - 1,
            midpoint * window_count // source_chars,
        )
        normalized_key = re.sub(r"\s+", " ", text).strip().casefold()
        window_seen = seen_by_window.setdefault(window_index, set())
        if not normalized_key or normalized_key in window_seen:
            continue
        window_seen.add(normalized_key)

        lower_text = text.casefold()
        text_tokens = _video_context_tokens(text)
        title_overlap = min(3, len(title_tokens & text_tokens))
        number_hits = min(
            3,
            len(re.findall(r"\b\d+(?:[.,]\d+)?\b", text)),
        )
        score_result = bool(
            re.search(r"\b\d{1,3}\s*[-:]\s*\d{1,3}\b", text)
        )
        date_hit = bool(
            re.search(r"\b(?:19|20)\d{2}\b", text)
            or re.search(
                r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
                text,
            )
        )
        statistic_hit = bool(
            re.search(r"\b\d+(?:[.,]\d+)?\s*%", text)
            or re.search(r"\b(?:statistic|statistics|average|rate)\b", lower_text)
        )
        money_duration_hit = bool(
            re.search(r"(?:[$\u20ac\u00a3\u20b9]\s*\d|\b\d+\s*(?:million|m|crore)\b)", lower_text)
            or re.search(r"\b\d+[- ]year\b", lower_text)
        )
        quotation_hit = bool(
            re.search(r"[\"\u201c\u201d\u2018\u2019][^\"\u201c\u201d\u2018\u2019]{8,}[\"\u201c\u201d\u2018\u2019]", text)
        )
        entity_hits = min(
            5,
            len(re.findall(r"\b[A-Z][\w'-]{2,}\b", text)),
        )
        preferred_length = 80 <= len(text) <= 320
        window_start = window_index * source_chars // window_count
        window_end = (window_index + 1) * source_chars // window_count
        boundary_distance = min(
            max(0, midpoint - window_start),
            max(0, window_end - midpoint),
        )
        boundary_bonus = 0.25 if boundary_distance <= MAX_CANDIDATE_CHARS else 0.0

        score = (
            (4.0 if contains_marker(lower_text, marker_groups["attribution"]) else 0.0)
            + (3.5 if score_result else 0.0)
            + (3.0 if date_hit else 0.0)
            + (3.0 if statistic_hit else 0.0)
            + (3.0 if money_duration_hit else 0.0)
            + (3.0 if contains_marker(lower_text, marker_groups["transfer"]) else 0.0)
            + (3.0 if contains_marker(lower_text, marker_groups["injury"]) else 0.0)
            + (2.5 if contains_marker(lower_text, marker_groups["event"]) else 0.0)
            + (2.0 if quotation_hit else 0.0)
            + (2.0 if contains_marker(lower_text, marker_groups["argument"]) else 0.0)
            + title_overlap * 1.5
            + number_hits * 1.0
            + entity_hits * 0.4
            + (1.0 if preferred_length else 0.0)
            + boundary_bonus
        )
        prepared_candidates.append(
            {
                **candidate,
                "window_index": window_index,
                "normalized_key": normalized_key,
                "preferred_length": preferred_length,
                "score": score,
            }
        )

    selected: Dict[
        int,
        Dict[str, Any],
    ] = {}
    rendered_length = 0
    selected_normalized = set()

    def add_candidate(
        candidate: Dict[str, Any],
        *,
        allow_selected_duplicate: bool = False,
    ) -> bool:
        nonlocal rendered_length
        key = int(candidate["ordinal"])
        normalized_key = candidate["normalized_key"]
        if key in selected:
            return False
        if normalized_key in selected_normalized and not allow_selected_duplicate:
            return False

        marker = (
            f"[SOURCE WINDOW "
            f"{candidate['window_index'] + 1} "
            f"OF {window_count}]"
        )
        part = f"{marker}\n{candidate['text']}"
        separator = "\n\n" if selected else ""
        incremental_cost = len(separator) + len(part)
        if rendered_length + incremental_cost > max_chars:
            return False

        selected[key] = candidate
        selected_normalized.add(normalized_key)
        rendered_length += incremental_cost
        return True

    candidates_by_window: Dict[int, List[Dict[str, Any]]] = {}
    for candidate in prepared_candidates:
        candidates_by_window.setdefault(
            int(candidate["window_index"]),
            [],
        ).append(candidate)

    anchor_count = 0
    represented_windows = set()
    for window_index in range(window_count):
        ranked_window = sorted(
            candidates_by_window.get(window_index, []),
            key=lambda candidate: (
                -candidate["score"],
                -int(candidate["preferred_length"]),
                -len(candidate["text"]),
                candidate["start_offset"],
                candidate["ordinal"],
            ),
        )
        for candidate in ranked_window:
            if add_candidate(
                candidate,
                allow_selected_duplicate=True,
            ):
                anchor_count += 1
                represented_windows.add(window_index)
                break

    ranked_candidates = sorted(
        prepared_candidates,
        key=lambda candidate: (
            -candidate["score"],
            candidate["window_index"],
            candidate["start_offset"],
            candidate["ordinal"],
        ),
    )

    global_salience_count = 0
    for candidate in ranked_candidates:
        if add_candidate(candidate):
            global_salience_count += 1
            represented_windows.add(
                int(candidate["window_index"])
            )

    selected_in_order = sorted(
        selected.values(),
        key=lambda candidate: (
            candidate["start_offset"],
            candidate["end_offset"],
            candidate["ordinal"],
        ),
    )

    context_parts: List[str] = []
    represented_chunks = set()

    for candidate in selected_in_order:
        window_index = int(candidate["window_index"])
        first_chunk_index = min(
            len(chunks) - 1,
            max(
                0,
                int(candidate["start_offset"])
                // legacy_chunk_size,
            ),
        )
        last_chunk_index = min(
            len(chunks) - 1,
            max(
                first_chunk_index,
                (int(candidate["end_offset"]) - 1)
                // legacy_chunk_size,
            ),
        )
        represented_chunks.update(
            range(
                first_chunk_index,
                last_chunk_index + 1,
            )
        )
        context_parts.append(
            (
                f"[SOURCE WINDOW "
                f"{window_index + 1} "
                f"OF {window_count}]\n"
                f"{candidate['text']}"
            )
        )

    context_text = "\n\n".join(
        context_parts
    ).strip()
    if len(context_text) > max_chars:
        raise AssertionError(
            "Video transcript context exceeded its character budget."
        )

    return {
        "text": context_text,
        "strategy": (
            "all_chunk_extractive_compression"
        ),
        "compression_applied": True,
        "source_chars": source_chars,
        "context_chars": len(
            context_text
        ),
        "source_chunk_count": len(chunks),
        "represented_chunk_count": len(
            represented_chunks
        ),
        "selected_sentence_count": len(
            selected_in_order
        ),
        "chunk_coverage": round(
            len(represented_chunks)
            / max(1, len(chunks)),
            3,
        ),
        "coverage_window_count": window_count,
        "represented_window_count": len(represented_windows),
        "coverage_anchor_count": anchor_count,
        "global_salience_count": global_salience_count,
        "window_coverage": round(
            len(represented_windows) / max(1, window_count),
            3,
        ),
    }


def normalize_video_transcript_metadata(
    metadata: Any,
) -> Dict[str, Any]:
    raw = (
        metadata
        if isinstance(metadata, dict)
        else {}
    )

    provided = bool(
        raw.get(
            "provided",
            bool(raw),
        )
    )

    def bounded_float(
        key: str,
        default: float = 0.0,
        maximum: float = 1.0,
    ) -> float:
        try:
            value = float(
                raw.get(key, default)
            )
        except Exception:
            value = default

        return max(
            0.0,
            min(maximum, value),
        )

    def bounded_int(
        key: str,
        maximum: int = 5_000_000,
    ) -> int:
        try:
            value = int(
                float(
                    raw.get(key, 0)
                )
            )
        except Exception:
            value = 0

        return max(
            0,
            min(maximum, value),
        )

    raw_warnings = raw.get(
        "extraction_warnings",
        [],
    )

    if not isinstance(
        raw_warnings,
        list,
    ):
        raw_warnings = [
            raw_warnings
        ]

    warnings: List[str] = []

    for warning in raw_warnings:
        cleaned_warning = re.sub(
            r"[^a-z0-9_:-]+",
            "_",
            str(warning or "")
            .strip()
            .lower(),
        ).strip("_")[:64]

        if (
            cleaned_warning
            and cleaned_warning
            not in warnings
        ):
            warnings.append(
                cleaned_warning
            )

        if len(warnings) >= 8:
            break

    confidence_default = (
        1.0
        if not provided
        else 0.0
    )

    return {
        "provided": provided,
        "extraction_confidence": round(
            bounded_float(
                "extraction_confidence",
                confidence_default,
            ),
            2,
        ),
        "extraction_warnings": warnings,
        "segment_count": bounded_int(
            "segment_count",
            100_000,
        ),
        "character_count": bounded_int(
            "character_count",
        ),
        "duplicate_segment_count": (
            bounded_int(
                "duplicate_segment_count",
                100_000,
            )
        ),
        "duplicate_ratio": round(
            bounded_float(
                "duplicate_ratio",
                0.0,
            ),
            3,
        ),
        "average_segment_length": round(
            bounded_float(
                "average_segment_length",
                0.0,
                100_000.0,
            ),
            1,
        ),
        "timestamps_available": bool(
            raw.get(
                "timestamps_available",
                False,
            )
        ),
    }


def apply_video_extraction_confidence_policy(
    payload: Dict[str, Any],
    transcript_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply the provider-free transcript extraction confidence policy."""
    data = dict(payload or {})
    transcript_extraction = normalize_video_transcript_metadata(
        transcript_metadata
    )
    limiting_warnings = {
        "very_few_segments",
        "very_short_transcript",
    }
    transcript_extraction_limited = bool(
        transcript_extraction.get("provided", False)
        and (
            float(transcript_extraction.get("extraction_confidence", 0.0))
            < 0.55
            or any(
                warning in limiting_warnings
                for warning in transcript_extraction.get(
                    "extraction_warnings", []
                )
            )
        )
    )

    try:
        model_transcript_confidence = float(
            data.get("transcript_confidence", 0.0)
        )
    except Exception:
        model_transcript_confidence = 0.0
    model_transcript_confidence = round(
        max(0.0, min(1.0, model_transcript_confidence)),
        2,
    )

    extraction_confidence = float(
        transcript_extraction.get("extraction_confidence", 1.0)
    )
    if transcript_extraction.get("provided", False):
        effective_transcript_confidence = min(
            model_transcript_confidence,
            extraction_confidence,
        )
    else:
        effective_transcript_confidence = model_transcript_confidence
    effective_transcript_confidence = round(
        effective_transcript_confidence,
        2,
    )

    evidence_score = int(float(data.get("evidence_score", 0)))
    logic_score = int(float(data.get("logic_score", 0)))
    evidence_score = max(0, min(100, evidence_score))
    logic_score = max(0, min(100, logic_score))

    evidence_used = data.get("evidence_used", [])
    if not isinstance(evidence_used, list):
        evidence_used = [str(evidence_used)]
    evidence_used = [
        clean_html(str(item)).strip()
        for item in evidence_used
        if str(item).strip()
    ][:8]

    allowed_content_types = {
        "confirmed_news",
        "sports_report",
        "rumor",
        "sports_analysis",
        "sports_opinion",
        "engagement_bait",
        "not_sports_content",
    }
    content_type = str(data.get("content_type", "unknown")).strip().lower()
    if content_type not in allowed_content_types:
        content_type = "unknown"

    allowed_verdicts = {
        "confirmed",
        "well_supported_report",
        "well_supported_analysis",
        "reasonable_opinion",
        "plausible_rumor",
        "weakly_supported",
        "misleading",
        "engagement_bait",
        "not_sports_content",
    }
    verdict = str(data.get("verdict", "weakly_supported")).strip().lower()
    if verdict not in allowed_verdicts:
        verdict = "weakly_supported"
    if content_type == "unknown":
        content_type = {
            "confirmed": "confirmed_news",
            "well_supported_report": "sports_report",
            "well_supported_analysis": "sports_analysis",
            "reasonable_opinion": "sports_opinion",
            "plausible_rumor": "rumor",
            "engagement_bait": "engagement_bait",
            "not_sports_content": "not_sports_content",
        }.get(verdict, "unknown")

    strong_verdicts = {
        "confirmed",
        "well_supported_report",
        "well_supported_analysis",
    }
    if not evidence_used:
        evidence_score = min(evidence_score, 35)
        if verdict in strong_verdicts:
            verdict = "weakly_supported"
    if transcript_extraction_limited:
        evidence_score = min(evidence_score, 55)
        if verdict in strong_verdicts:
            verdict = "weakly_supported"
            data["localized_verdict"] = ""

    data.update(
        {
            "content_type": content_type,
            "evidence_used": evidence_used,
            "evidence_score": evidence_score,
            "logic_score": logic_score,
            "verdict": verdict,
            "transcript_confidence": effective_transcript_confidence,
        }
    )
    return {
        "data": data,
        "transcript_extraction": transcript_extraction,
        "transcript_extraction_limited": transcript_extraction_limited,
        "model_transcript_confidence": model_transcript_confidence,
        "transcript_confidence": effective_transcript_confidence,
        "evidence_score": evidence_score,
        "logic_score": logic_score,
        "verdict": verdict,
        "localized_verdict": data.get("localized_verdict"),
        "evidence_used": evidence_used,
    }


VIDEO_MODEL_UI_LABEL_KEYS = {
    "video_intelligence",
    "main_claim",
    "evidence_used",
    "logic_check",
    "hype_check",
    "evidence_score",
    "logic_score",
    "verdict",
    "analyze_again",
    "transcript_analyzed",
}


def clean_video_model_text(
    value: Any,
    max_chars: int,
) -> str:
    cleaned = re.sub(
        r"\s+",
        " ",
        clean_html(str(value or "")),
    ).strip()

    return cleaned[:max_chars].rstrip()


def sanitize_video_model_payload(
    payload: Any,
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(
            "Video analysis JSON must be an object."
        )

    def number(
        key: str,
        maximum: float = 1.0,
    ) -> float:
        try:
            value = float(
                payload.get(key, 0)
            )
        except Exception:
            value = 0.0

        return max(
            0.0,
            min(maximum, value),
        )

    raw_evidence = payload.get(
        "evidence_used",
        [],
    )

    if not isinstance(raw_evidence, list):
        raw_evidence = [raw_evidence]

    evidence = []
    seen = set()

    for item in raw_evidence:
        cleaned = clean_video_model_text(
            item,
            600,
        )

        key = cleaned.casefold()

        if not cleaned or key in seen:
            continue

        seen.add(key)
        evidence.append(cleaned)

        if len(evidence) >= 8:
            break

    raw_labels = payload.get(
        "ui_labels",
        {},
    )

    labels = {}

    if isinstance(raw_labels, dict):
        for key in VIDEO_MODEL_UI_LABEL_KEYS:
            value = clean_video_model_text(
                raw_labels.get(key, ""),
                80,
            )

            if value:
                labels[key] = value

    raw_corrections = payload.get(
        "uncertain_corrections",
        [],
    )

    if not isinstance(raw_corrections, list):
        raw_corrections = []

    corrections = []

    for item in raw_corrections:
        if not isinstance(item, dict):
            continue

        original = clean_video_model_text(
            item.get("original", ""),
            240,
        )

        suggested = clean_video_model_text(
            item.get("suggested", ""),
            240,
        )

        reason = clean_video_model_text(
            item.get("reason", ""),
            500,
        )

        if not (
            original
            and suggested
            and reason
        ):
            continue

        try:
            confidence = float(
                item.get("confidence", 0)
            )
        except Exception:
            confidence = 0.0

        corrections.append(
            {
                "original": original,
                "suggested": suggested,
                "reason": reason,
                "confidence": round(
                    max(
                        0.0,
                        min(1.0, confidence),
                    ),
                    2,
                ),
            }
        )

        if len(corrections) >= 5:
            break

    raw_languages = payload.get(
        "languages",
        [],
    )

    if not isinstance(raw_languages, list):
        raw_languages = [raw_languages]

    languages = []

    for item in raw_languages:
        cleaned = clean_video_model_text(
            item,
            80,
        )

        if (
            cleaned
            and cleaned not in languages
        ):
            languages.append(cleaned)

        if len(languages) >= 5:
            break

    return {
        "detected_language": clean_video_model_text(
            payload.get(
                "detected_language",
                "",
            ),
            80,
        ),
        "languages": languages,
        "mixed_language": bool(
            payload.get(
                "mixed_language",
                False,
            )
        ),
        "language_confidence": round(
            number("language_confidence"),
            2,
        ),
        "transcript_confidence": round(
            number("transcript_confidence"),
            2,
        ),
        "uncertain_corrections": corrections,
        "content_type": clean_video_model_text(
            payload.get(
                "content_type",
                "",
            ),
            80,
        ).lower(),
        "localized_content_type":
            clean_video_model_text(
                payload.get(
                    "localized_content_type",
                    "",
                ),
                120,
            ),
        "localized_verdict":
            clean_video_model_text(
                payload.get(
                    "localized_verdict",
                    "",
                ),
                120,
            ),
        "ui_labels": labels,
        "claim": clean_video_model_text(
            payload.get("claim", ""),
            1200,
        ),
        "evidence_used": evidence,
        "logic_check": clean_video_model_text(
            payload.get(
                "logic_check",
                "",
            ),
            1600,
        ),
        "hype_check": clean_video_model_text(
            payload.get(
                "hype_check",
                "",
            ),
            1600,
        ),
        "evidence_score": int(
            number(
                "evidence_score",
                100.0,
            )
        ),
        "logic_score": int(
            number(
                "logic_score",
                100.0,
            )
        ),
        "verdict": clean_video_model_text(
            payload.get("verdict", ""),
            80,
        ).lower(),
    }


def classify_video_provider_error(
    error: Exception,
) -> Dict[str, str]:
    raw_error = (
        f"{type(error).__name__}: "
        f"{str(error)}"
    )[:500]

    normalized = raw_error.lower()

    if (
        "503" in normalized
        or "unavailable" in normalized
        or "high demand" in normalized
        or "overloaded" in normalized
    ):
        return {
            "code": "provider_capacity",
            "message": (
                "Gemini is temporarily busy. "
                "Please wait a few minutes and "
                "try the analysis again."
            ),
            "raw": raw_error,
        }

    if (
        "429" in normalized
        or "resource_exhausted" in normalized
        or "rate limit" in normalized
        or "quota" in normalized
    ):
        return {
            "code": "provider_rate_limited",
            "message": (
                "Gemini is temporarily rate-limited. "
                "Please wait before trying again."
            ),
            "raw": raw_error,
        }

    if (
        "timeout" in normalized
        or "timed out" in normalized
        or "deadline_exceeded" in normalized
    ):
        return {
            "code": "provider_timeout",
            "message": (
                "The AI provider took too long to "
                "respond. Please try again shortly."
            ),
            "raw": raw_error,
        }

    return {
        "code": "provider_error",
        "message": (
            "The AI provider could not complete "
            "this analysis right now. Please try "
            "again later."
        ),
        "raw": raw_error,
    }


VIDEO_CONTENT_TYPES = {
    "unknown",
    "confirmed_news",
    "sports_report",
    "rumor",
    "sports_analysis",
    "sports_opinion",
    "engagement_bait",
    "not_sports_content",
}


VIDEO_VERDICTS = {
    "confirmed",
    "well_supported_report",
    "well_supported_analysis",
    "reasonable_opinion",
    "plausible_rumor",
    "weakly_supported",
    "misleading",
    "engagement_bait",
    "not_sports_content",
    "analysis_failed",
    "ai_unavailable",
}


VIDEO_ALLOWED_VERDICTS_BY_TYPE = {
    "confirmed_news": {
        "confirmed",
        "well_supported_report",
        "weakly_supported",
        "misleading",
    },
    "sports_report": {
        "well_supported_report",
        "weakly_supported",
        "misleading",
    },
    "rumor": {
        "plausible_rumor",
        "weakly_supported",
        "misleading",
        "engagement_bait",
    },
    "sports_analysis": {
        "well_supported_analysis",
        "weakly_supported",
        "misleading",
        "engagement_bait",
    },
    "sports_opinion": {
        "reasonable_opinion",
        "weakly_supported",
        "misleading",
        "engagement_bait",
    },
    "engagement_bait": {
        "engagement_bait",
        "misleading",
        "weakly_supported",
    },
    "not_sports_content": {
        "not_sports_content",
    },
}


VIDEO_VERDICT_REQUIREMENTS = {
    "confirmed": {
        "minimum_evidence_score": 85,
        "minimum_logic_score": 70,
        "minimum_evidence_items": 2,
    },
    "well_supported_report": {
        "minimum_evidence_score": 70,
        "minimum_logic_score": 65,
        "minimum_evidence_items": 2,
    },
    "well_supported_analysis": {
        "minimum_evidence_score": 60,
        "minimum_logic_score": 65,
        "minimum_evidence_items": 1,
    },
    "reasonable_opinion": {
        "minimum_evidence_score": 0,
        "minimum_logic_score": 60,
        "minimum_evidence_items": 0,
    },
    "plausible_rumor": {
        "minimum_evidence_score": 35,
        "minimum_logic_score": 50,
        "minimum_evidence_items": 1,
    },
}


VIDEO_VERDICT_LABELS = {
    "confirmed": "Confirmed",
    "well_supported_report": (
        "Well-Supported Report"
    ),
    "well_supported_analysis": (
        "Well-Supported Analysis"
    ),
    "reasonable_opinion": (
        "Reasonable Opinion"
    ),
    "plausible_rumor": "Plausible Rumor",
    "weakly_supported": "Weakly Supported",
    "misleading": "Misleading",
    "engagement_bait": "Engagement Bait",
    "not_sports_content": (
        "Not Sports Content"
    ),
    "analysis_failed": "Analysis Failed",
    "ai_unavailable": "AI Unavailable",
}


def bounded_video_score(
    value: Any,
) -> int:
    try:
        numeric_value = int(
            float(value)
        )
    except Exception:
        numeric_value = 0

    return max(
        0,
        min(100, numeric_value),
    )


def validate_video_analysis_consistency(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        result = {}

    validated = dict(result)

    debug = validated.get(
        "debug",
        {},
    )

    if not isinstance(debug, dict):
        debug = {}

    issues: List[str] = []
    rewrites: List[str] = []

    content_type = str(
        validated.get(
            "content_type",
            "",
        )
    ).strip().lower()

    original_content_type = content_type

    if content_type not in VIDEO_CONTENT_TYPES:
        issues.append(
            "invalid_content_type"
        )
        rewrites.append(
            "content_type_to_unknown"
        )
        content_type = "unknown"

    verdict = str(
        validated.get(
            "verdict",
            "",
        )
    ).strip().lower()

    original_verdict = verdict

    if verdict not in VIDEO_VERDICTS:
        issues.append(
            "invalid_verdict"
        )
        rewrites.append(
            "verdict_to_weakly_supported"
        )
        verdict = "weakly_supported"

    evidence_score = bounded_video_score(
        validated.get(
            "evidence_score",
            0,
        )
    )

    logic_score = bounded_video_score(
        validated.get(
            "logic_score",
            0,
        )
    )

    raw_evidence = validated.get(
        "evidence_used",
        [],
    )

    if not isinstance(raw_evidence, list):
        raw_evidence = [
            raw_evidence
        ]
        issues.append(
            "evidence_not_list"
        )
        rewrites.append(
            "normalized_evidence_list"
        )

    evidence_used: List[str] = []
    seen_evidence = set()

    for item in raw_evidence:
        cleaned_item = clean_html(
            str(item or "")
        ).strip()

        if not cleaned_item:
            continue

        evidence_key = (
            cleaned_item.lower()
        )

        if evidence_key in seen_evidence:
            continue

        seen_evidence.add(
            evidence_key
        )
        evidence_used.append(
            cleaned_item
        )

    if len(evidence_used) != len(
        raw_evidence
    ):
        issues.append(
            "empty_or_duplicate_evidence"
        )
        rewrites.append(
            "cleaned_evidence"
        )

    claim = clean_html(
        str(
            validated.get(
                "claim",
                "",
            )
        )
    ).strip()

    logic_check = clean_html(
        str(
            validated.get(
                "logic_check",
                "",
            )
        )
    ).strip()

    hype_check = clean_html(
        str(
            validated.get(
                "hype_check",
                "",
            )
        )
    ).strip()

    missing_core_analysis = False

    if not claim:
        missing_core_analysis = True
        issues.append(
            "missing_claim"
        )
        rewrites.append(
            "safe_missing_claim_message"
        )
        claim = (
            "Sportabase could not determine "
            "a reliable central claim from "
            "the available transcript."
        )

    if not logic_check:
        missing_core_analysis = True
        issues.append(
            "missing_logic_check"
        )
        rewrites.append(
            "safe_missing_logic_message"
        )
        logic_check = (
            "The reasoning could not be "
            "evaluated reliably from the "
            "available transcript."
        )

    if not hype_check:
        issues.append(
            "missing_hype_check"
        )
        rewrites.append(
            "safe_missing_hype_message"
        )
        hype_check = (
            "The presentation style could "
            "not be evaluated reliably from "
            "the available transcript."
        )

    if content_type == "not_sports_content":
        if verdict != "not_sports_content":
            issues.append(
                "not_sports_verdict_mismatch"
            )
            rewrites.append(
                "verdict_to_not_sports_content"
            )

        verdict = "not_sports_content"
        evidence_score = 0
        logic_score = 0

    elif content_type == "unknown":
        if verdict not in {
            "analysis_failed",
            "ai_unavailable",
        }:
            issues.append(
                "unknown_type_with_verdict"
            )
            rewrites.append(
                "unknown_type_to_weak_verdict"
            )
            verdict = "weakly_supported"

            evidence_score = min(
                evidence_score,
                40,
            )
            logic_score = min(
                logic_score,
                40,
            )

    else:
        allowed_verdicts = (
            VIDEO_ALLOWED_VERDICTS_BY_TYPE.get(
                content_type,
                {"weakly_supported"},
            )
        )

        if verdict not in allowed_verdicts:
            issues.append(
                "content_type_verdict_mismatch"
            )
            rewrites.append(
                "verdict_to_weakly_supported"
            )
            verdict = "weakly_supported"

    requirements = (
        VIDEO_VERDICT_REQUIREMENTS.get(
            verdict
        )
    )

    if requirements:
        threshold_failures = []

        if (
            evidence_score
            < requirements[
                "minimum_evidence_score"
            ]
        ):
            threshold_failures.append(
                "evidence_score"
            )

        if (
            logic_score
            < requirements[
                "minimum_logic_score"
            ]
        ):
            threshold_failures.append(
                "logic_score"
            )

        if (
            len(evidence_used)
            < requirements[
                "minimum_evidence_items"
            ]
        ):
            threshold_failures.append(
                "evidence_items"
            )

        if threshold_failures:
            issues.append(
                "verdict_threshold_failure:"
                + ",".join(
                    threshold_failures
                )
            )
            rewrites.append(
                "verdict_to_weakly_supported"
            )
            verdict = "weakly_supported"

    if verdict == "confirmed":
        confirmation_text = " ".join(
            evidence_used
        ).lower()

        confirmation_markers = (
            "official statement",
            "official announcement",
            "official result",
            "official timing",
            "official classification",
            "press release",
            "confirmed by",
            "announced by",
            "club statement",
            "team statement",
            "league statement",
            "governing body",
            "federation statement",
            "final score",
            "match result",
            "race result",
            "published standings",
            "fia document",
            "fia decision",
        )

        if not any(
            marker in confirmation_text
            for marker in confirmation_markers
        ):
            issues.append(
                "confirmed_without_"
                "primary_source_signal"
            )

            rewrites.append(
                "confirmed_to_"
                "well_supported_report"
            )

            verdict = (
                "well_supported_report"
            )

    if (
        verdict
        in {
            "misleading",
            "engagement_bait",
        }
        and evidence_score >= 70
        and logic_score >= 70
    ):
        issues.append(
            "negative_verdict_high_scores"
        )
        rewrites.append(
            "negative_verdict_to_uncertain"
        )
        verdict = "weakly_supported"

    if missing_core_analysis:
        verdict = "weakly_supported"
        evidence_score = min(
            evidence_score,
            40,
        )
        logic_score = min(
            logic_score,
            40,
        )

    validated["content_type"] = (
        content_type
    )
    validated["verdict"] = verdict
    validated["claim"] = claim
    validated["logic_check"] = (
        logic_check
    )
    validated["hype_check"] = (
        hype_check
    )
    validated["evidence_used"] = (
        evidence_used
    )
    validated["evidence_score"] = (
        evidence_score
    )
    validated["logic_score"] = (
        logic_score
    )

    if (
        content_type
        != original_content_type
    ):
        validated[
            "localized_content_type"
        ] = ""

    if verdict != original_verdict:
        validated[
            "localized_verdict"
        ] = ""

    debug[
        "consistency_validation"
    ] = {
        "valid": not bool(issues),
        "adjusted": bool(rewrites),
        "issues": issues,
        "rewrites": rewrites,
        "final_content_type": (
            content_type
        ),
        "final_verdict": verdict,
        "final_evidence_score": (
            evidence_score
        ),
        "final_logic_score": (
            logic_score
        ),
        "evidence_items": len(
            evidence_used
        ),
    }

    debug[
        "consistency_adjusted"
    ] = bool(rewrites)

    validated["debug"] = debug

    return validated


def video_analysis_cache_decision(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {
            "allowed": False,
            "reason": "invalid_result",
        }

    debug = result.get("debug", {})

    if not isinstance(debug, dict):
        debug = {}

    if bool(
        debug.get(
            "temporal_guard_triggered",
            False,
        )
    ):
        return {
            "allowed": False,
            "reason": "temporal_guard_triggered",
        }

    if bool(
        debug.get(
            "consistency_adjusted",
            False,
        )
    ):
        return {
            "allowed": False,
            "reason": (
                "consistency_adjusted"
            ),
        }

    if bool(
        debug.get(
            "transcript_extraction_limited",
            False,
        )
    ):
        return {
            "allowed": False,
            "reason": (
                "transcript_extraction_limited"
            ),
        }

    verdict = str(
        result.get("verdict", "")
    ).strip().lower()

    if verdict in {
        "analysis_failed",
        "ai_unavailable",
    }:
        return {
            "allowed": False,
            "reason": verdict,
        }

    content_type = str(
        result.get("content_type", "")
    ).strip().lower()

    if content_type in {
        "",
        "unknown",
    }:
        return {
            "allowed": False,
            "reason": "unknown_content_type",
        }

    claim = clean_html(
        str(result.get("claim", ""))
    ).strip()

    if not claim:
        return {
            "allowed": False,
            "reason": "missing_claim",
        }

    evidence_used = result.get(
        "evidence_used",
        [],
    )

    if not isinstance(
        evidence_used,
        list,
    ):
        evidence_used = []

    if (
        verdict
        in {
            "confirmed",
            "well_supported_report",
            "well_supported_analysis",
        }
        and not evidence_used
    ):
        return {
            "allowed": False,
            "reason": (
                "strong_verdict_without_evidence"
            ),
        }

    return {
        "allowed": True,
        "reason": "eligible",
    }
