from __future__ import annotations

import csv
import io
import math
import os
from pathlib import Path
import re
import subprocess
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
)

from app.models import artifacts as artifact_models
from app.services import (
    artifact_extraction,
    media_execution,
)


PERCEPTION_EXECUTION_VERSION = "perception-execution-v1"

DEFAULT_OCR_LANGUAGE = "eng"
DEFAULT_OCR_TIMEOUT_SECONDS = 20.0

DEFAULT_WHISPER_MODEL = "small"
DEFAULT_WHISPER_DEVICE = "cpu"
DEFAULT_WHISPER_COMPUTE_TYPE = "int8"
DEFAULT_WHISPER_CPU_THREADS = 4
DEFAULT_WHISPER_CHUNK_SECONDS = 30
DEFAULT_MAX_TRANSCRIPTION_SECONDS = 7200.0


class PerceptionExecutionError(RuntimeError):
    pass


class PerceptionToolUnavailable(
    PerceptionExecutionError
):
    pass


class PerceptionProviderError(
    PerceptionExecutionError
):
    pass


class PerceptionLimitError(
    PerceptionExecutionError
):
    pass


def _clamp_probability(
    value: Any,
) -> Optional[float]:
    if value is None:
        return None

    try:
        numeric = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        numeric
    ):
        return None

    return max(
        0.0,
        min(
            1.0,
            numeric,
        ),
    )


def _safe_int(
    value: Any,
) -> int:
    try:
        return int(
            float(
                value
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


def _value(
    obj: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(
        obj,
        Mapping,
    ):
        return obj.get(
            name,
            default,
        )

    return getattr(
        obj,
        name,
        default,
    )


def _run_process(
    args: Sequence[str],
    *,
    timeout_seconds: float,
    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
) -> Any:
    try:
        result = runner(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    except FileNotFoundError as error:
        raise PerceptionToolUnavailable(
            "Required perception tool "
            "is unavailable: "
            + str(
                args[0]
            )
        ) from error

    except subprocess.TimeoutExpired as error:
        raise PerceptionProviderError(
            "Perception command timed out."
        ) from error

    if int(
        getattr(
            result,
            "returncode",
            0,
        )
    ) != 0:
        stderr = str(
            getattr(
                result,
                "stderr",
                "",
            )
            or ""
        ).strip()

        if len(stderr) > 1200:
            stderr = (
                stderr[:1200]
                + "..."
            )

        raise PerceptionProviderError(
            "Perception command failed"
            + (
                ": " + stderr
                if stderr
                else "."
            )
        )

    return result


def parse_tesseract_tsv(
    raw_tsv: str,
) -> List[
    Dict[
        str,
        Any,
    ]
]:
    reader = csv.DictReader(
        io.StringIO(
            str(
                raw_tsv
                or ""
            )
        ),
        delimiter="\t",
    )

    groups: Dict[
        tuple,
        Dict[
            str,
            Any,
        ],
    ] = {}

    for row in reader:
        if str(
            row.get(
                "level",
                ""
            )
        ).strip() != "5":
            continue

        text = str(
            row.get(
                "text",
                ""
            )
            or ""
        ).strip()

        if not text:
            continue

        raw_confidence = (
            row.get(
                "conf"
            )
        )

        confidence = None

        try:
            numeric_confidence = float(
                raw_confidence
            )

            if (
                math.isfinite(
                    numeric_confidence
                )
                and numeric_confidence
                >= 0
            ):
                confidence = max(
                    0.0,
                    min(
                        1.0,
                        numeric_confidence
                        / 100.0,
                    ),
                )

        except (
            TypeError,
            ValueError,
        ):
            confidence = None

        key = (
            _safe_int(
                row.get(
                    "page_num"
                )
            ),
            _safe_int(
                row.get(
                    "block_num"
                )
            ),
            _safe_int(
                row.get(
                    "par_num"
                )
            ),
            _safe_int(
                row.get(
                    "line_num"
                )
            ),
        )

        left = _safe_int(
            row.get(
                "left"
            )
        )

        top = _safe_int(
            row.get(
                "top"
            )
        )

        width = max(
            0,
            _safe_int(
                row.get(
                    "width"
                )
            ),
        )

        height = max(
            0,
            _safe_int(
                row.get(
                    "height"
                )
            ),
        )

        group = groups.setdefault(
            key,
            {
                "words": [],
                "left": left,
                "top": top,
                "right": (
                    left + width
                ),
                "bottom": (
                    top + height
                ),
            },
        )

        group[
            "left"
        ] = min(
            group["left"],
            left,
        )

        group[
            "top"
        ] = min(
            group["top"],
            top,
        )

        group[
            "right"
        ] = max(
            group["right"],
            left + width,
        )

        group[
            "bottom"
        ] = max(
            group["bottom"],
            top + height,
        )

        group[
            "words"
        ].append(
            {
                "text": text,
                "confidence": (
                    confidence
                ),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
        )

    lines: List[
        Dict[
            str,
            Any,
        ]
    ] = []

    for (
        page_num,
        block_num,
        par_num,
        line_num,
    ), group in sorted(
        groups.items()
    ):
        words = group[
            "words"
        ]

        text = " ".join(
            word["text"]
            for word
            in words
        ).strip()

        if not text:
            continue

        weighted_total = 0.0
        total_weight = 0

        for word in words:
            confidence = (
                word[
                    "confidence"
                ]
            )

            if confidence is None:
                continue

            weight = max(
                1,
                len(
                    word[
                        "text"
                    ]
                ),
            )

            weighted_total += (
                confidence
                * weight
            )

            total_weight += (
                weight
            )

        confidence = (
            weighted_total
            / total_weight
            if total_weight
            else None
        )

        lines.append(
            {
                "text": text,
                "confidence": (
                    confidence
                ),
                "page_num": (
                    page_num
                ),
                "block_num": (
                    block_num
                ),
                "paragraph_num": (
                    par_num
                ),
                "line_num": (
                    line_num
                ),
                "bounding_box": {
                    "left": (
                        group[
                            "left"
                        ]
                    ),
                    "top": (
                        group[
                            "top"
                        ]
                    ),
                    "width": (
                        group[
                            "right"
                        ]
                        - group[
                            "left"
                        ]
                    ),
                    "height": (
                        group[
                            "bottom"
                        ]
                        - group[
                            "top"
                        ]
                    ),
                },
                "words": words,
            }
        )

    return lines


class TesseractOcrProvider:
    def __init__(
        self,
        *,
        language: str = (
            DEFAULT_OCR_LANGUAGE
        ),
        psm: int = 6,
        oem: int = 1,
        timeout_seconds: float = (
            DEFAULT_OCR_TIMEOUT_SECONDS
        ),
        runner: Callable[
            ...,
            Any,
        ] = subprocess.run,
    ):
        self.language = (
            str(
                language
                or DEFAULT_OCR_LANGUAGE
            ).strip()
        )

        self.psm = int(
            psm
        )

        self.oem = int(
            oem
        )

        self.timeout_seconds = float(
            timeout_seconds
        )

        self.runner = (
            runner
        )

        self._version: Optional[
            str
        ] = None

    def version(
        self,
    ) -> str:
        if self._version is not None:
            return self._version

        result = _run_process(
            [
                "tesseract",
                "--version",
            ],
            timeout_seconds=(
                self.timeout_seconds
            ),
            runner=self.runner,
        )

        first_line = str(
            getattr(
                result,
                "stdout",
                "",
            )
            or ""
        ).splitlines()

        self._version = (
            first_line[0].strip()
            if first_line
            else "tesseract"
        )

        return self._version

    def extract(
        self,
        image_path: str,
    ) -> Dict[
        str,
        Any,
    ]:
        path = Path(
            image_path
        )

        if not path.exists():
            raise PerceptionProviderError(
                "OCR image does not exist."
            )

        result = _run_process(
            [
                "tesseract",
                str(
                    path
                ),
                "stdout",
                "-l",
                self.language,
                "--oem",
                str(
                    self.oem
                ),
                "--psm",
                str(
                    self.psm
                ),
                "tsv",
            ],
            timeout_seconds=(
                self.timeout_seconds
            ),
            runner=self.runner,
        )

        return {
            "engine": "tesseract",
            "engine_version": (
                self.version()
            ),
            "language": (
                self.language
            ),
            "lines": (
                parse_tesseract_tsv(
                    str(
                        getattr(
                            result,
                            "stdout",
                            "",
                        )
                        or ""
                    )
                )
            ),
        }


def _normalized_ocr_key(
    value: str,
) -> str:
    return re.sub(
        r"[^\w]+",
        " ",
        str(
            value
            or ""
        ).casefold(),
        flags=re.UNICODE,
    ).strip()


def _flatten_dependency_artifacts(
    dependency_outputs: Mapping[
        str,
        Sequence[
            artifact_models
            .ExtractionArtifact
        ],
    ],
) -> List[
    artifact_models
    .ExtractionArtifact
]:
    output: List[
        artifact_models
        .ExtractionArtifact
    ] = []

    for artifacts in (
        dependency_outputs
        .values()
    ):
        output.extend(
            list(
                artifacts
                or ()
            )
        )

    return output


def _deduplicate_ocr_results(
    sources: Sequence[
        Mapping[
            str,
            Any,
        ]
    ],
    provider: Any,
) -> Dict[
    str,
    Any,
]:
    entries: Dict[
        str,
        Dict[
            str,
            Any,
        ],
    ] = {}

    engine = "tesseract"
    engine_version = ""
    language = ""

    for source in sources:
        result = provider.extract(
            str(
                source[
                    "local_path"
                ]
            )
        )

        engine = str(
            result.get(
                "engine",
                engine,
            )
            or engine
        )

        engine_version = str(
            result.get(
                "engine_version",
                engine_version,
            )
            or engine_version
        )

        language = str(
            result.get(
                "language",
                language,
            )
            or language
        )

        for line in (
            result.get(
                "lines",
                []
            )
            or []
        ):
            text = str(
                line.get(
                    "text",
                    ""
                )
                or ""
            ).strip()

            if not text:
                continue

            key = (
                _normalized_ocr_key(
                    text
                )
            )

            if not key:
                continue

            confidence = (
                _clamp_probability(
                    line.get(
                        "confidence"
                    )
                )
            )

            occurrence = {
                "source_artifact_id": (
                    str(
                        source.get(
                            "source_artifact_id",
                            "",
                        )
                        or ""
                    )
                ),
                "timestamp_seconds": (
                    source.get(
                        "timestamp_seconds"
                    )
                ),
                "confidence": (
                    confidence
                ),
                "bounding_box": (
                    line.get(
                        "bounding_box"
                    )
                    or {}
                ),
            }

            existing = (
                entries.get(
                    key
                )
            )

            if existing is None:
                entries[
                    key
                ] = {
                    "text": text,
                    "confidence": (
                        confidence
                    ),
                    "occurrence_count": (
                        1
                    ),
                    "occurrences": [
                        occurrence
                    ],
                }

                continue

            existing[
                "occurrence_count"
            ] += 1

            existing[
                "occurrences"
            ].append(
                occurrence
            )

            old_confidence = (
                existing.get(
                    "confidence"
                )
            )

            if (
                confidence is not None
                and (
                    old_confidence
                    is None
                    or confidence
                    > old_confidence
                )
            ):
                existing[
                    "text"
                ] = text

                existing[
                    "confidence"
                ] = confidence

    ordered = list(
        entries.values()
    )

    confidence_values = [
        float(
            entry[
                "confidence"
            ]
        )
        for entry
        in ordered
        if entry.get(
            "confidence"
        )
        is not None
    ]

    return {
        "engine": engine,
        "engine_version": (
            engine_version
        ),
        "language": language,
        "text": "\n".join(
            entry[
                "text"
            ]
            for entry
            in ordered
        ),
        "entries": ordered,
        "mean_confidence": (
            (
                sum(
                    confidence_values
                )
                / len(
                    confidence_values
                )
            )
            if confidence_values
            else None
        ),
        "source_count": len(
            sources
        ),
        "deduplicated_line_count": (
            len(
                ordered
            )
        ),
    }


class FasterWhisperProvider:
    def __init__(
        self,
        *,
        model_size: Optional[
            str
        ] = None,
        device: Optional[
            str
        ] = None,
        compute_type: Optional[
            str
        ] = None,
        cpu_threads: Optional[
            int
        ] = None,
        chunk_length_seconds: Optional[
            int
        ] = None,
        download_root: Optional[
            str
        ] = None,
        revision: Optional[
            str
        ] = None,
        local_files_only: bool = False,
        model_factory: Optional[
            Callable[
                ...,
                Any,
            ]
        ] = None,
    ):
        self.model_size = str(
            model_size
            or os.getenv(
                "SPORTABASE_WHISPER_MODEL",
                DEFAULT_WHISPER_MODEL,
            )
        ).strip()

        self.device = str(
            device
            or os.getenv(
                "SPORTABASE_WHISPER_DEVICE",
                DEFAULT_WHISPER_DEVICE,
            )
        ).strip()

        self.compute_type = str(
            compute_type
            or os.getenv(
                "SPORTABASE_WHISPER_COMPUTE_TYPE",
                DEFAULT_WHISPER_COMPUTE_TYPE,
            )
        ).strip()

        self.cpu_threads = int(
            cpu_threads
            if cpu_threads is not None
            else os.getenv(
                "SPORTABASE_WHISPER_CPU_THREADS",
                str(
                    DEFAULT_WHISPER_CPU_THREADS
                ),
            )
        )

        self.chunk_length_seconds = int(
            chunk_length_seconds
            if (
                chunk_length_seconds
                is not None
            )
            else os.getenv(
                "SPORTABASE_WHISPER_CHUNK_SECONDS",
                str(
                    DEFAULT_WHISPER_CHUNK_SECONDS
                ),
            )
        )

        self.download_root = (
            download_root
            or os.getenv(
                "SPORTABASE_WHISPER_CACHE_DIR",
                "",
            )
            or None
        )

        self.revision = (
            revision
            or os.getenv(
                "SPORTABASE_WHISPER_REVISION",
                "",
            )
            or None
        )

        self.local_files_only = bool(
            local_files_only
        )

        self._model_factory = (
            model_factory
        )

        self._model = None

    def _get_model(
        self,
    ) -> Any:
        if self._model is not None:
            return self._model

        factory = (
            self._model_factory
        )

        if factory is None:
            try:
                from faster_whisper import (
                    WhisperModel,
                )

            except ImportError as error:
                raise PerceptionToolUnavailable(
                    "faster-whisper is "
                    "not installed."
                ) from error

            factory = (
                WhisperModel
            )

        kwargs: Dict[
            str,
            Any,
        ] = {
            "device": (
                self.device
            ),
            "compute_type": (
                self.compute_type
            ),
            "cpu_threads": (
                self.cpu_threads
            ),
            "num_workers": 1,
            "local_files_only": (
                self.local_files_only
            ),
        }

        if self.download_root:
            kwargs[
                "download_root"
            ] = (
                self.download_root
            )

        if self.revision:
            kwargs[
                "revision"
            ] = self.revision

        try:
            self._model = factory(
                self.model_size,
                **kwargs,
            )

        except ImportError as error:
            raise PerceptionToolUnavailable(
                "Whisper runtime dependency "
                "is unavailable."
            ) from error

        return self._model

    def transcribe(
        self,
        audio_path: str,
        *,
        language: Optional[
            str
        ] = None,
    ) -> Dict[
        str,
        Any,
    ]:
        path = Path(
            audio_path
        )

        if not path.exists():
            raise PerceptionProviderError(
                "Transcription audio "
                "does not exist."
            )

        model = (
            self._get_model()
        )

        segments_iterable, info = (
            model.transcribe(
                str(
                    path
                ),
                language=(
                    language
                    or None
                ),
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                chunk_length=(
                    self.chunk_length_seconds
                ),
                condition_on_previous_text=(
                    False
                ),
                temperature=0.0,
            )
        )

        segments = []

        confidence_total = 0.0
        confidence_weight = 0.0

        for raw_segment in list(
            segments_iterable
        ):
            start = float(
                _value(
                    raw_segment,
                    "start",
                    0.0,
                )
                or 0.0
            )

            end = float(
                _value(
                    raw_segment,
                    "end",
                    start,
                )
                or start
            )

            text = str(
                _value(
                    raw_segment,
                    "text",
                    "",
                )
                or ""
            ).strip()

            words_payload = []

            word_confidence_total = 0.0
            word_confidence_weight = 0

            for raw_word in (
                _value(
                    raw_segment,
                    "words",
                    None,
                )
                or []
            ):
                word_text = str(
                    _value(
                        raw_word,
                        "word",
                        "",
                    )
                    or ""
                )

                probability = (
                    _clamp_probability(
                        _value(
                            raw_word,
                            "probability",
                            None,
                        )
                    )
                )

                words_payload.append(
                    {
                        "start_seconds": (
                            float(
                                _value(
                                    raw_word,
                                    "start",
                                    0.0,
                                )
                                or 0.0
                            )
                        ),
                        "end_seconds": (
                            float(
                                _value(
                                    raw_word,
                                    "end",
                                    0.0,
                                )
                                or 0.0
                            )
                        ),
                        "text": (
                            word_text
                        ),
                        "probability": (
                            probability
                        ),
                    }
                )

                if probability is not None:
                    weight = max(
                        1,
                        len(
                            word_text.strip()
                        ),
                    )

                    word_confidence_total += (
                        probability
                        * weight
                    )

                    word_confidence_weight += (
                        weight
                    )

            if word_confidence_weight:
                confidence = (
                    word_confidence_total
                    / word_confidence_weight
                )

            else:
                avg_logprob = _value(
                    raw_segment,
                    "avg_logprob",
                    None,
                )

                no_speech_prob = (
                    _clamp_probability(
                        _value(
                            raw_segment,
                            "no_speech_prob",
                            0.0,
                        )
                    )
                    or 0.0
                )

                try:
                    confidence = (
                        math.exp(
                            float(
                                avg_logprob
                            )
                        )
                        * (
                            1.0
                            - no_speech_prob
                        )
                    )

                    confidence = (
                        _clamp_probability(
                            confidence
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                ):
                    confidence = None

            if confidence is not None:
                weight = max(
                    0.001,
                    end - start,
                )

                confidence_total += (
                    confidence
                    * weight
                )

                confidence_weight += (
                    weight
                )

            segments.append(
                {
                    "start_seconds": (
                        start
                    ),
                    "end_seconds": (
                        end
                    ),
                    "text": text,
                    "confidence": (
                        confidence
                    ),
                    "avg_logprob": (
                        _value(
                            raw_segment,
                            "avg_logprob",
                            None,
                        )
                    ),
                    (
                        "no_speech_"
                        "probability"
                    ): (
                        _clamp_probability(
                            _value(
                                raw_segment,
                                "no_speech_prob",
                                None,
                            )
                        )
                    ),
                    "compression_ratio": (
                        _value(
                            raw_segment,
                            "compression_ratio",
                            None,
                        )
                    ),
                    "words": (
                        words_payload
                    ),
                }
            )

        transcript = " ".join(
            segment[
                "text"
            ]
            for segment
            in segments
            if segment[
                "text"
            ]
        ).strip()

        return {
            "engine": (
                "faster-whisper"
            ),
            "model": (
                self.model_size
            ),
            "device": (
                self.device
            ),
            "compute_type": (
                self.compute_type
            ),
            "chunk_length_seconds": (
                self.chunk_length_seconds
            ),
            "text": transcript,
            "segments": segments,
            "overall_confidence": (
                (
                    confidence_total
                    / confidence_weight
                )
                if confidence_weight
                else None
            ),
            "confidence_kind": (
                "word_probability_"
                "weighted_mean_with_"
                "segment_logprob_fallback"
            ),
            "language": str(
                _value(
                    info,
                    "language",
                    "",
                )
                or ""
            ),
            "language_probability": (
                _clamp_probability(
                    _value(
                        info,
                        "language_probability",
                        None,
                    )
                )
            ),
            "duration_seconds": (
                _value(
                    info,
                    "duration",
                    None,
                )
            ),
            (
                "duration_after_"
                "vad_seconds"
            ): (
                _value(
                    info,
                    "duration_after_vad",
                    None,
                )
            ),
        }


def build_perception_executors(
    workspace: (
        media_execution
        .MediaWorkspace
    ),
    *,
    ocr_provider: Optional[
        Any
    ] = None,
    transcription_provider: Optional[
        Any
    ] = None,
    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
    command_timeout_seconds: float = (
        media_execution
        .DEFAULT_COMMAND_TIMEOUT_SECONDS
    ),
    max_transcription_seconds: float = (
        DEFAULT_MAX_TRANSCRIPTION_SECONDS
    ),
    media_executor_builder: Optional[
        Callable[
            ...,
            Dict[
                str,
                Callable[
                    ...,
                    Any,
                ],
            ],
        ]
    ] = None,
    audio_extract_fn: Optional[
        Callable[
            ...,
            Dict[
                str,
                Any,
            ],
        ]
    ] = None,
    probe_fn: Optional[
        Callable[
            ...,
            Any,
        ]
    ] = None,
) -> Dict[
    str,
    Callable[
        ...,
        Any,
    ],
]:
    actual_ocr_provider = (
        ocr_provider
        or TesseractOcrProvider(
            language=(
                os.getenv(
                    "SPORTABASE_OCR_LANGUAGE",
                    DEFAULT_OCR_LANGUAGE,
                )
            ),
            runner=runner,
        )
    )

    actual_transcription_provider = (
        transcription_provider
        or FasterWhisperProvider()
    )

    build_media = (
        media_executor_builder
        or (
            media_execution
            .build_concrete_media_executors
        )
    )

    extract_audio = (
        audio_extract_fn
        or (
            media_execution
            .extract_audio_track
        )
    )

    probe_media = (
        probe_fn
        or (
            media_execution
            .probe_local_media
        )
    )

    executors = dict(
        build_media(
            workspace,
            runner=runner,
            timeout_seconds=(
                command_timeout_seconds
            ),
        )
    )

    def ocr_executor(
        work,
        _available_artifacts,
        dependency_outputs,
    ):
        media_kind = str(
            work.parameters.get(
                "media_kind",
                ""
            )
            or ""
        ).strip()

        sources = []

        if media_kind == "video":
            dependency_artifacts = (
                _flatten_dependency_artifacts(
                    dependency_outputs
                )
            )

            for artifact in (
                dependency_artifacts
            ):
                if (
                    artifact.artifact_kind
                    != "video_frame"
                ):
                    continue

                local_path = str(
                    artifact.payload.get(
                        "local_path",
                        ""
                    )
                    or ""
                ).strip()

                if not local_path:
                    continue

                sources.append(
                    {
                        "local_path": (
                            local_path
                        ),
                        (
                            "source_"
                            "artifact_id"
                        ): (
                            artifact
                            .artifact_id
                        ),
                        (
                            "timestamp_"
                            "seconds"
                        ): (
                            artifact
                            .payload
                            .get(
                                "timestamp_seconds"
                            )
                        ),
                    }
                )

        elif media_kind == "image":
            media_url = str(
                work.parameters.get(
                    "media_url",
                    ""
                )
                or ""
            ).strip()

            if not media_url:
                raise PerceptionExecutionError(
                    "Image OCR requires "
                    "media_url."
                )

            asset = (
                workspace.acquire(
                    media_url,
                    expected_kind="image",
                )
            )

            sources.append(
                {
                    "local_path": (
                        asset.local_path
                    ),
                    (
                        "source_"
                        "artifact_id"
                    ): (
                        "media:"
                        + asset.sha256[:24]
                    ),
                    (
                        "timestamp_"
                        "seconds"
                    ): None,
                }
            )

        else:
            raise PerceptionExecutionError(
                "OCR work requires image "
                "or video media."
            )

        if not sources:
            raise PerceptionExecutionError(
                "OCR work has no usable "
                "image sources."
            )

        result = (
            _deduplicate_ocr_results(
                sources,
                actual_ocr_provider,
            )
        )

        return {
            "artifact_kind": (
                "ocr_text"
            ),
            "modality": "text",
            "payload": {
                **result,
                "confidence_kind": (
                    "tesseract_word_"
                    "confidence_weighted_mean"
                ),
            },
            "metadata": {
                (
                    "perception_execution_"
                    "version"
                ): (
                    PERCEPTION_EXECUTION_VERSION
                ),
                "text_detected": bool(
                    result[
                        "text"
                    ]
                ),
            },
        }

    def transcription_executor(
        work,
        _available_artifacts,
        _dependency_outputs,
    ):
        media_kind = str(
            work.parameters.get(
                "media_kind",
                ""
            )
            or ""
        ).strip()

        media_url = str(
            work.parameters.get(
                "media_url",
                ""
            )
            or ""
        ).strip()

        if (
            media_kind
            not in {
                "video",
                "audio",
            }
        ):
            raise PerceptionExecutionError(
                "Transcription requires "
                "video or audio media."
            )

        if not media_url:
            raise PerceptionExecutionError(
                "Transcription requires "
                "media_url."
            )

        asset = workspace.acquire(
            media_url,
            expected_kind=(
                media_kind
            ),
        )

        outputs = []

        if media_kind == "video":
            audio_output = (
                extract_audio(
                    asset,
                    workspace=workspace,
                    timeout_seconds=(
                        command_timeout_seconds
                    ),
                    runner=runner,
                )
            )

            outputs.append(
                audio_output
            )

            audio_path = str(
                audio_output[
                    "payload"
                ][
                    "local_path"
                ]
            )

        else:
            audio_path = (
                asset.local_path
            )

            outputs.append(
                {
                    "artifact_kind": (
                        "audio_source"
                    ),
                    "modality": (
                        "audio"
                    ),
                    "payload": {
                        "local_path": (
                            asset.local_path
                        ),
                        "content_type": (
                            asset.content_type
                        ),
                        "size_bytes": (
                            asset.size_bytes
                        ),
                        "sha256": (
                            asset.sha256
                        ),
                        (
                            "source_"
                            "media_url"
                        ): (
                            asset.final_url
                        ),
                    },
                    "metadata": {
                        (
                            "perception_"
                            "execution_version"
                        ): (
                            PERCEPTION_EXECUTION_VERSION
                        ),
                        (
                            "ephemeral_"
                            "local_file"
                        ): True,
                    },
                }
            )

        probe = probe_media(
            audio_path,
            timeout_seconds=(
                command_timeout_seconds
            ),
            runner=runner,
        )

        if (
            probe.duration_seconds
            is not None
            and probe.duration_seconds
            > max_transcription_seconds
        ):
            raise PerceptionLimitError(
                "Audio exceeds maximum "
                "transcription duration."
            )

        language_hint = str(
            work.parameters.get(
                "language",
                ""
            )
            or ""
        ).strip()

        transcript = (
            actual_transcription_provider
            .transcribe(
                audio_path,
                language=(
                    language_hint
                    or None
                ),
            )
        )

        outputs.append(
            {
                "artifact_kind": (
                    "transcript"
                ),
                "modality": "text",
                "payload": (
                    transcript
                ),
                "metadata": {
                    (
                        "perception_"
                        "execution_version"
                    ): (
                        PERCEPTION_EXECUTION_VERSION
                    ),
                    "text_detected": bool(
                        transcript.get(
                            "text"
                        )
                    ),
                },
            }
        )

        return outputs

    def alignment_input_executor(
        work,
        available_artifacts,
        dependency_outputs,
    ):
        if len(
            work.source_component_ids
        ) < 2:
            raise PerceptionExecutionError(
                "Caption/media alignment "
                "work requires caption "
                "and media components."
            )

        caption_component_id = (
            work
            .source_component_ids[0]
        )

        media_component_id = (
            work
            .source_component_ids[1]
        )

        caption_artifact = next(
            (
                artifact
                for artifact
                in available_artifacts
                if (
                    artifact.artifact_kind
                    == "text_component"
                    and caption_component_id
                    in (
                        artifact
                        .source_component_ids
                    )
                )
            ),
            None,
        )

        if caption_artifact is None:
            raise PerceptionExecutionError(
                "Caption artifact is "
                "unavailable."
            )

        dependency_artifacts = (
            _flatten_dependency_artifacts(
                dependency_outputs
            )
        )

        return {
            "artifact_kind": (
                "caption_media_"
                "alignment_input"
            ),
            "modality": (
                "multimodal"
            ),
            "payload": {
                "caption_component_id": (
                    caption_component_id
                ),
                "media_component_id": (
                    media_component_id
                ),
                "caption_text": (
                    caption_artifact
                    .payload
                    .get(
                        "text",
                        ""
                    )
                ),
                "caption_artifact_id": (
                    caption_artifact
                    .artifact_id
                ),
                (
                    "dependency_"
                    "artifact_ids"
                ): [
                    artifact.artifact_id
                    for artifact
                    in dependency_artifacts
                ],
                (
                    "dependency_"
                    "artifact_kinds"
                ): [
                    artifact.artifact_kind
                    for artifact
                    in dependency_artifacts
                ],
                (
                    "alignment_"
                    "assessment"
                ): None,
            },
            "metadata": {
                (
                    "perception_execution_"
                    "version"
                ): (
                    PERCEPTION_EXECUTION_VERSION
                ),
                (
                    "interpretation_"
                    "performed"
                ): False,
            },
        }

    executors.update(
        {
            "ocr": (
                ocr_executor
            ),
            "transcription": (
                transcription_executor
            ),
            (
                "caption_media_"
                "alignment"
            ): (
                alignment_input_executor
            ),
        }
    )

    return executors


def execute_perception_manifest(
    manifest: (
        artifact_models
        .ItemArtifactManifest
    ),
    *,
    workspace: (
        media_execution
        .MediaWorkspace
    ),
    **executor_options: Any,
) -> (
    artifact_models
    .ItemArtifactManifest
):
    return (
        artifact_extraction
        .execute_item_artifact_manifest(
            manifest,
            executors=(
                build_perception_executors(
                    workspace,
                    **executor_options,
                )
            ),
        )
    )