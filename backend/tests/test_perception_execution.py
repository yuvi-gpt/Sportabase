from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from app.models import artifacts as artifact_models
from app.models import content
from app.services import (
    artifact_extraction,
    media_execution,
    perception_execution,
)


OBSERVED = "2026-08-16T12:00:00Z"


TSV = """level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext
1\t1\t0\t0\t0\t0\t0\t0\t800\t400\t-1\t
5\t1\t1\t1\t1\t1\t10\t20\t80\t30\t90\tSPORTABASE
5\t1\t1\t1\t1\t2\t100\t20\t50\t30\t80\tLIVE
5\t1\t1\t1\t2\t1\t10\t70\t70\t30\t95\tARSENAL
"""


def provenance():
    return content.ProvenanceRecord(
        source_url=(
            "https://cdn.example/"
            "media"
        ),
        observed_at=OBSERVED,
        extraction_method=(
            "browser_dom"
        ),
    )


def video_manifest():
    item = (
        content
        .UnifiedContentItem(
            item_id="x:video",
            platform="x",
            platform_surface="post",
            container_kind="media",
            canonical_url=(
                "https://x.com/a/status/1"
            ),
            observed_at=OBSERVED,
            text_components=[
                content.TextComponent(
                    component_id=(
                        "caption"
                    ),
                    role="caption",
                    text=(
                        "Sportabase clip"
                    ),
                    provenance=(
                        provenance()
                    ),
                )
            ],
            media_components=[
                content.MediaComponent(
                    component_id=(
                        "video:0"
                    ),
                    media_kind="video",
                    media_url=(
                        "https://cdn.example/"
                        "video.mp4"
                    ),
                    duration_seconds=20,
                    has_audio=True,
                    provenance=(
                        provenance()
                    ),
                )
            ],
        )
    )

    content.validate_unified_content_item(
        item
    )

    return (
        artifact_extraction
        .materialize_item_artifacts(
            item
        )
    )


def image_manifest():
    item = (
        content
        .UnifiedContentItem(
            item_id="x:image",
            platform="x",
            platform_surface="post",
            container_kind="media",
            canonical_url=(
                "https://x.com/a/status/2"
            ),
            observed_at=OBSERVED,
            text_components=[
                content.TextComponent(
                    component_id=(
                        "caption"
                    ),
                    role="caption",
                    text="Image caption",
                    provenance=(
                        provenance()
                    ),
                )
            ],
            media_components=[
                content.MediaComponent(
                    component_id=(
                        "image:0"
                    ),
                    media_kind="image",
                    media_url=(
                        "https://cdn.example/"
                        "image.png"
                    ),
                    provenance=(
                        provenance()
                    ),
                )
            ],
        )
    )

    content.validate_unified_content_item(
        item
    )

    return (
        artifact_extraction
        .materialize_item_artifacts(
            item
        )
    )


class StubWorkspace:
    def __init__(
        self,
        root,
    ):
        self.root = Path(
            root
        )

        self.calls = []

    def path_for(
        self,
        name,
    ):
        path = (
            self.root
            / Path(
                name
            ).name
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return path

    def acquire(
        self,
        url,
        *,
        expected_kind="",
    ):
        self.calls.append(
            (
                url,
                expected_kind,
            )
        )

        extension = {
            "image": ".png",
            "audio": ".wav",
            "video": ".mp4",
        }.get(
            expected_kind,
            ".bin",
        )

        path = (
            self.root
            / (
                expected_kind
                + extension
            )
        )

        data = (
            (
                expected_kind
                or "media"
            )
            .encode(
                "utf-8"
            )
            + b"-bytes"
        )

        path.write_bytes(
            data
        )

        return (
            media_execution
            .LocalMediaAsset(
                source_url=url,
                final_url=url,
                local_path=str(
                    path
                ),
                content_type=(
                    (
                        "image/png"
                    )
                    if expected_kind
                    == "image"
                    else (
                        "audio/wav"
                        if expected_kind
                        == "audio"
                        else "video/mp4"
                    )
                ),
                size_bytes=len(
                    data
                ),
                sha256=(
                    hashlib
                    .sha256(
                        data
                    )
                    .hexdigest()
                ),
                media_kind=(
                    expected_kind
                ),
            )
        )


class TesseractRunner:
    def __init__(
        self,
        *,
        tsv=TSV,
        missing=False,
    ):
        self.tsv = tsv
        self.missing = (
            missing
        )
        self.calls = []

    def __call__(
        self,
        args,
        **kwargs,
    ):
        args = list(
            args
        )

        self.calls.append(
            (
                args,
                dict(
                    kwargs
                ),
            )
        )

        if self.missing:
            raise FileNotFoundError(
                "tesseract"
            )

        if "--version" in args:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "tesseract 5.5.0\n"
                ),
                stderr="",
            )

        return SimpleNamespace(
            returncode=0,
            stdout=self.tsv,
            stderr="",
        )


class FakeOcrProvider:
    def __init__(
        self,
        lines=None,
    ):
        self.lines = (
            lines
            if lines is not None
            else [
                {
                    "text": (
                        "SPORTABASE"
                    ),
                    "confidence": (
                        0.91
                    ),
                    "bounding_box": {
                        "left": 1,
                        "top": 2,
                        "width": 3,
                        "height": 4,
                    },
                }
            ]
        )

        self.paths = []

    def extract(
        self,
        path,
    ):
        self.paths.append(
            str(
                path
            )
        )

        return {
            "engine": "fake-ocr",
            "engine_version": "1",
            "language": "eng",
            "lines": list(
                self.lines
            ),
        }


class FakeWhisperModel:
    def __init__(
        self,
    ):
        self.calls = []

    def transcribe(
        self,
        path,
        **kwargs,
    ):
        self.calls.append(
            (
                str(
                    path
                ),
                dict(
                    kwargs
                ),
            )
        )

        words = [
            SimpleNamespace(
                start=0.0,
                end=0.5,
                word="hello",
                probability=0.9,
            ),
            SimpleNamespace(
                start=0.5,
                end=1.0,
                word="world",
                probability=0.7,
            ),
        ]

        segments = [
            SimpleNamespace(
                start=0.0,
                end=1.0,
                text="hello world",
                words=words,
                avg_logprob=-0.2,
                no_speech_prob=0.1,
                compression_ratio=1.2,
            )
        ]

        info = SimpleNamespace(
            language="en",
            language_probability=0.96,
            duration=1.0,
            duration_after_vad=0.9,
        )

        return (
            iter(
                segments
            ),
            info,
        )


class FakeTranscriptionProvider:
    def __init__(
        self,
        *,
        fail=False,
        text="hello world",
    ):
        self.fail = fail
        self.text = text
        self.calls = []

    def transcribe(
        self,
        path,
        *,
        language=None,
    ):
        self.calls.append(
            (
                str(
                    path
                ),
                language,
            )
        )

        if self.fail:
            raise RuntimeError(
                "transcription failed"
            )

        return {
            "engine": (
                "fake-whisper"
            ),
            "model": "test",
            "text": self.text,
            "segments": [],
            "overall_confidence": (
                0.88
            ),
            "language": "en",
            "language_probability": (
                0.99
            ),
        }


def fake_probe(
    _path,
    **_kwargs,
):
    return (
        media_execution
        .MediaProbe(
            duration_seconds=10.0,
            width=None,
            height=None,
            has_video=False,
            has_audio=True,
        )
    )


def fake_audio_extract(
    asset,
    *,
    workspace,
    **_kwargs,
):
    path = (
        workspace
        .path_for(
            "audio-test.wav"
        )
    )

    data = b"RIFFaudio"

    path.write_bytes(
        data
    )

    return {
        "artifact_kind": (
            "audio_track"
        ),
        "modality": "audio",
        "payload": {
            "local_path": str(
                path
            ),
            "content_type": (
                "audio/wav"
            ),
            "sample_rate_hz": (
                16000
            ),
            "channels": 1,
            "size_bytes": len(
                data
            ),
            "sha256": (
                hashlib
                .sha256(
                    data
                )
                .hexdigest()
            ),
            (
                "source_"
                "media_sha256"
            ): (
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
            "ephemeral_local_file": (
                True
            )
        },
    }


def fake_media_executor_builder(
    workspace,
    **_kwargs,
):
    def frames(
        _work,
        _artifacts,
        _dependencies,
    ):
        path = (
            workspace
            .path_for(
                "frame.jpg"
            )
        )

        path.write_bytes(
            b"frame"
        )

        return {
            "artifact_kind": (
                "video_frame"
            ),
            "modality": "image",
            "payload": {
                "local_path": str(
                    path
                ),
                "timestamp_seconds": (
                    5.0
                ),
                "sha256": (
                    "f" * 64
                ),
            },
        }

    return {
        "video_frame_extract": (
            frames
        )
    }


def recursive_keys(
    value,
):
    keys = set()

    if isinstance(
        value,
        dict,
    ):
        for key, child in (
            value.items()
        ):
            keys.add(
                str(
                    key
                ).lower()
            )

            keys.update(
                recursive_keys(
                    child
                )
            )

    elif isinstance(
        value,
        (list, tuple),
    ):
        for child in value:
            keys.update(
                recursive_keys(
                    child
                )
            )

    return keys


class PerceptionExecutionTests(
    unittest.TestCase
):
    def test_parse_tsv_groups_words_into_lines(
        self,
    ):
        lines = (
            perception_execution
            .parse_tesseract_tsv(
                TSV
            )
        )

        self.assertEqual(
            len(lines),
            2,
        )

        self.assertEqual(
            lines[0][
                "text"
            ],
            "SPORTABASE LIVE",
        )

        expected = (
            (
                0.9 * 10
                + 0.8 * 4
            )
            / 14
        )

        self.assertAlmostEqual(
            lines[0][
                "confidence"
            ],
            expected,
            places=6,
        )

        self.assertEqual(
            lines[0][
                "bounding_box"
            ][
                "width"
            ],
            140,
        )


    def test_parse_tsv_ignores_empty_words_and_negative_confidence(
        self,
    ):
        raw = """level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext
5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t-1\tWORD
5\t1\t1\t1\t1\t2\t20\t0\t10\t10\t90\t
"""

        lines = (
            perception_execution
            .parse_tesseract_tsv(
                raw
            )
        )

        self.assertEqual(
            len(lines),
            1,
        )

        self.assertEqual(
            lines[0][
                "text"
            ],
            "WORD",
        )

        self.assertIsNone(
            lines[0][
                "confidence"
            ]
        )


    def test_tesseract_provider_uses_tsv_cli_contract(
        self,
    ):
        runner = (
            TesseractRunner()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            image = (
                Path(root)
                / "image.png"
            )

            image.write_bytes(
                b"image"
            )

            provider = (
                perception_execution
                .TesseractOcrProvider(
                    runner=runner
                )
            )

            result = (
                provider.extract(
                    str(
                        image
                    )
                )
            )

        command = runner.calls[
            0
        ][0]

        kwargs = runner.calls[
            0
        ][1]

        self.assertEqual(
            command[0],
            "tesseract",
        )

        self.assertIn(
            "stdout",
            command,
        )

        self.assertEqual(
            command[-1],
            "tsv",
        )

        self.assertFalse(
            kwargs.get(
                "shell",
                False,
            )
        )

        self.assertEqual(
            result[
                "engine"
            ],
            "tesseract",
        )


    def test_tesseract_provider_empty_page_is_valid(
        self,
    ):
        header = (
            TSV.splitlines()[0]
            + "\n"
        )

        runner = (
            TesseractRunner(
                tsv=header
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            image = (
                Path(root)
                / "image.png"
            )

            image.write_bytes(
                b"image"
            )

            result = (
                perception_execution
                .TesseractOcrProvider(
                    runner=runner
                )
                .extract(
                    str(
                        image
                    )
                )
            )

        self.assertEqual(
            result[
                "lines"
            ],
            [],
        )


    def test_tesseract_missing_binary_fails_closed(
        self,
    ):
        runner = (
            TesseractRunner(
                missing=True
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            image = (
                Path(root)
                / "image.png"
            )

            image.write_bytes(
                b"image"
            )

            with self.assertRaises(
                perception_execution
                .PerceptionToolUnavailable
            ):
                (
                    perception_execution
                    .TesseractOcrProvider(
                        runner=runner
                    )
                    .extract(
                        str(
                            image
                        )
                    )
                )


    def test_tesseract_version_is_cached(
        self,
    ):
        runner = (
            TesseractRunner()
        )

        provider = (
            perception_execution
            .TesseractOcrProvider(
                runner=runner
            )
        )

        first = (
            provider.version()
        )

        second = (
            provider.version()
        )

        self.assertEqual(
            first,
            second,
        )

        version_calls = [
            call
            for call
            in runner.calls
            if "--version"
            in call[0]
        ]

        self.assertEqual(
            len(
                version_calls
            ),
            1,
        )


    def test_whisper_model_is_lazy_configured_and_cached(
        self,
    ):
        created = []

        model = (
            FakeWhisperModel()
        )

        def factory(
            model_size,
            **kwargs,
        ):
            created.append(
                (
                    model_size,
                    kwargs,
                )
            )

            return model

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_size="small",
                device="cpu",
                compute_type="int8",
                cpu_threads=3,
                model_factory=factory,
            )
        )

        self.assertEqual(
            created,
            [],
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            provider.transcribe(
                str(
                    audio
                )
            )

            provider.transcribe(
                str(
                    audio
                )
            )

        self.assertEqual(
            len(created),
            1,
        )

        self.assertEqual(
            created[0][0],
            "small",
        )

        self.assertEqual(
            created[0][1][
                "compute_type"
            ],
            "int8",
        )

        self.assertEqual(
            created[0][1][
                "cpu_threads"
            ],
            3,
        )


    def test_whisper_transcript_preserves_timed_words(
        self,
    ):
        model = (
            FakeWhisperModel()
        )

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs: model
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            result = (
                provider.transcribe(
                    str(
                        audio
                    )
                )
            )

        self.assertEqual(
            result[
                "text"
            ],
            "hello world",
        )

        words = result[
            "segments"
        ][0][
            "words"
        ]

        self.assertEqual(
            len(words),
            2,
        )

        self.assertEqual(
            words[0][
                "start_seconds"
            ],
            0.0,
        )

        self.assertEqual(
            words[1][
                "end_seconds"
            ],
            1.0,
        )

        options = model.calls[
            0
        ][1]

        self.assertTrue(
            options[
                "word_timestamps"
            ]
        )

        self.assertTrue(
            options[
                "vad_filter"
            ]
        )

        self.assertFalse(
            options[
                "condition_on_previous_text"
            ]
        )

        self.assertEqual(
            options[
                "chunk_length"
            ],
            30,
        )


    def test_whisper_confidence_uses_word_probabilities(
        self,
    ):
        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs:
                    FakeWhisperModel()
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            result = (
                provider.transcribe(
                    str(
                        audio
                    )
                )
            )

        self.assertAlmostEqual(
            result[
                "segments"
            ][0][
                "confidence"
            ],
            0.8,
            places=6,
        )

        self.assertAlmostEqual(
            result[
                "overall_confidence"
            ],
            0.8,
            places=6,
        )


    def test_whisper_language_metadata_preserved(
        self,
    ):
        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs:
                    FakeWhisperModel()
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            result = (
                provider.transcribe(
                    str(
                        audio
                    )
                )
            )

        self.assertEqual(
            result[
                "language"
            ],
            "en",
        )

        self.assertEqual(
            result[
                "language_probability"
            ],
            0.96,
        )

        self.assertEqual(
            result[
                "duration_seconds"
            ],
            1.0,
        )


    def test_whisper_empty_audio_result_is_valid(
        self,
    ):
        class EmptyModel:
            def transcribe(
                self,
                _path,
                **_kwargs,
            ):
                return (
                    iter(
                        []
                    ),
                    SimpleNamespace(
                        language="en",
                        language_probability=(
                            1.0
                        ),
                        duration=1.0,
                        duration_after_vad=(
                            0.0
                        ),
                    ),
                )

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs:
                    EmptyModel()
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            result = (
                provider.transcribe(
                    str(
                        audio
                    )
                )
            )

        self.assertEqual(
            result[
                "text"
            ],
            "",
        )

        self.assertEqual(
            result[
                "segments"
            ],
            [],
        )

        self.assertIsNone(
            result[
                "overall_confidence"
            ]
        )


    def test_whisper_import_failure_fails_closed(
        self,
    ):
        def failing_factory(
            *_args,
            **_kwargs,
        ):
            raise ImportError(
                "missing"
            )

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    failing_factory
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            with self.assertRaises(
                perception_execution
                .PerceptionToolUnavailable
            ):
                provider.transcribe(
                    str(
                        audio
                    )
                )


    def test_video_ocr_uses_frame_dependencies_and_deduplicates(
        self,
    ):
        provider = (
            FakeOcrProvider()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=provider,
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            first_path = (
                workspace
                .path_for(
                    "one.jpg"
                )
            )

            second_path = (
                workspace
                .path_for(
                    "two.jpg"
                )
            )

            first_path.write_bytes(
                b"one"
            )

            second_path.write_bytes(
                b"two"
            )

            first = (
                artifact_models
                .ExtractionArtifact(
                    artifact_id="a:1",
                    artifact_kind=(
                        "video_frame"
                    ),
                    modality="image",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    content_hash="1",
                    payload={
                        "local_path": str(
                            first_path
                        ),
                        (
                            "timestamp_"
                            "seconds"
                        ): 1.0,
                    },
                )
            )

            second = (
                artifact_models
                .ExtractionArtifact(
                    artifact_id="a:2",
                    artifact_kind=(
                        "video_frame"
                    ),
                    modality="image",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    content_hash="2",
                    payload={
                        "local_path": str(
                            second_path
                        ),
                        (
                            "timestamp_"
                            "seconds"
                        ): 2.0,
                    },
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:ocr",
                    operation="ocr",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    parameters={
                        "media_kind": (
                            "video"
                        )
                    },
                )
            )

            output = executors[
                "ocr"
            ](
                work,
                (),
                {
                    "frames": (
                        first,
                        second,
                    )
                },
            )

        self.assertEqual(
            output[
                "payload"
            ][
                "deduplicated_line_count"
            ],
            1,
        )

        self.assertEqual(
            output[
                "payload"
            ][
                "entries"
            ][0][
                "occurrence_count"
            ],
            2,
        )

        self.assertEqual(
            len(
                provider.paths
            ),
            2,
        )


    def test_image_ocr_acquires_direct_image(
        self,
    ):
        provider = (
            FakeOcrProvider()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=provider,
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:ocr",
                    operation="ocr",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "image:0"
                    ],
                    parameters={
                        "media_kind": (
                            "image"
                        ),
                        "media_url": (
                            "https://cdn.example/"
                            "image.png"
                        ),
                    },
                )
            )

            output = (
                executors[
                    "ocr"
                ](
                    work,
                    (),
                    {},
                )
            )

        self.assertEqual(
            workspace.calls,
            [
                (
                    (
                        "https://cdn.example/"
                        "image.png"
                    ),
                    "image",
                )
            ],
        )

        self.assertEqual(
            output[
                "artifact_kind"
            ],
            "ocr_text",
        )


    def test_empty_ocr_completes_work(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            manifest = (
                image_manifest()
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider(
                            lines=[]
                        )
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            result = (
                artifact_extraction
                .execute_item_artifact_manifest(
                    manifest,
                    executors=(
                        executors
                    ),
                )
            )

        ocr = next(
            work
            for work
            in result.work_units
            if work.operation
            == "ocr"
        )

        self.assertEqual(
            ocr.status,
            "completed",
        )

        artifact = next(
            artifact
            for artifact
            in result.artifacts
            if artifact.artifact_kind
            == "ocr_text"
        )

        self.assertEqual(
            artifact.payload[
                "text"
            ],
            "",
        )


    def test_video_transcription_demuxes_audio(
        self,
    ):
        transcriber = (
            FakeTranscriptionProvider()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        transcriber
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:t",
                    operation=(
                        "transcription"
                    ),
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    parameters={
                        "media_kind": (
                            "video"
                        ),
                        "media_url": (
                            "https://cdn.example/"
                            "video.mp4"
                        ),
                    },
                )
            )

            outputs = (
                executors[
                    "transcription"
                ](
                    work,
                    (),
                    {},
                )
            )

        self.assertEqual(
            [
                output[
                    "artifact_kind"
                ]
                for output
                in outputs
            ],
            [
                "audio_track",
                "transcript",
            ],
        )

        self.assertEqual(
            len(
                transcriber.calls
            ),
            1,
        )

        self.assertTrue(
            transcriber.calls[
                0
            ][0].endswith(
                ".wav"
            )
        )


    def test_audio_transcription_uses_direct_source(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:t",
                    operation=(
                        "transcription"
                    ),
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "audio:0"
                    ],
                    parameters={
                        "media_kind": (
                            "audio"
                        ),
                        "media_url": (
                            "https://cdn.example/"
                            "audio.wav"
                        ),
                    },
                )
            )

            outputs = (
                executors[
                    "transcription"
                ](
                    work,
                    (),
                    {},
                )
            )

        self.assertEqual(
            [
                output[
                    "artifact_kind"
                ]
                for output
                in outputs
            ],
            [
                "audio_source",
                "transcript",
            ],
        )

        self.assertEqual(
            workspace.calls[0][1],
            "audio",
        )


    def test_transcription_duration_limit_fails_closed(
        self,
    ):
        def long_probe(
            _path,
            **_kwargs,
        ):
            return (
                media_execution
                .MediaProbe(
                    duration_seconds=(
                        9000
                    ),
                    width=None,
                    height=None,
                    has_video=False,
                    has_audio=True,
                )
            )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        long_probe
                    ),
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:t",
                    operation=(
                        "transcription"
                    ),
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "audio:0"
                    ],
                    parameters={
                        "media_kind": (
                            "audio"
                        ),
                        "media_url": (
                            "https://cdn.example/"
                            "audio.wav"
                        ),
                    },
                )
            )

            with self.assertRaises(
                perception_execution
                .PerceptionLimitError
            ):
                executors[
                    "transcription"
                ](
                    work,
                    (),
                    {},
                )


    def test_registry_claims_concrete_perception_operations_only(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        self.assertEqual(
            set(
                executors
            ),
            {
                "video_frame_extract",
                "ocr",
                "transcription",
                (
                    "caption_media_"
                    "alignment"
                ),
            },
        )

        self.assertNotIn(
            "image_visual",
            executors,
        )


    def test_alignment_executor_packages_inputs_without_deciding_alignment(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            caption = (
                artifact_models
                .ExtractionArtifact(
                    artifact_id="caption:a",
                    artifact_kind=(
                        "text_component"
                    ),
                    modality="text",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "caption"
                    ],
                    content_hash="c",
                    payload={
                        "text": (
                            "Caption"
                        )
                    },
                )
            )

            ocr = (
                artifact_models
                .ExtractionArtifact(
                    artifact_id="ocr:a",
                    artifact_kind=(
                        "ocr_text"
                    ),
                    modality="text",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    content_hash="o",
                    payload={
                        "text": (
                            "Score"
                        )
                    },
                )
            )

            transcript = (
                artifact_models
                .ExtractionArtifact(
                    artifact_id="t:a",
                    artifact_kind=(
                        "transcript"
                    ),
                    modality="text",
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    content_hash="t",
                    payload={
                        "text": (
                            "Speech"
                        )
                    },
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:a",
                    operation=(
                        "caption_media_alignment"
                    ),
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "caption",
                        "video:0",
                    ],
                )
            )

            output = executors[
                "caption_media_alignment"
            ](
                work,
                (
                    caption,
                    ocr,
                    transcript,
                ),
                {
                    "ocr": (
                        ocr,
                    ),
                    "transcript": (
                        transcript,
                    ),
                },
            )

        self.assertEqual(
            output[
                "artifact_kind"
            ],
            (
                "caption_media_"
                "alignment_input"
            ),
        )

        self.assertIsNone(
            output[
                "payload"
            ][
                "alignment_assessment"
            ]
        )

        self.assertFalse(
            output[
                "metadata"
            ][
                "interpretation_performed"
            ]
        )


    def test_end_to_end_video_perception_completes(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        status = {
            work.operation: (
                work.status
            )
            for work
            in result.work_units
        }

        self.assertEqual(
            status[
                "video_frame_extract"
            ],
            "completed",
        )

        self.assertEqual(
            status[
                "ocr"
            ],
            "completed",
        )

        self.assertEqual(
            status[
                "transcription"
            ],
            "completed",
        )

        self.assertEqual(
            status[
                "caption_media_alignment"
            ],
            "completed",
        )

        kinds = {
            artifact.artifact_kind
            for artifact
            in result.artifacts
        }

        self.assertTrue(
            {
                "video_frame",
                "ocr_text",
                "audio_track",
                "transcript",
                (
                    "caption_media_"
                    "alignment_input"
                ),
            }.issubset(
                kinds
            )
        )


    def test_transcription_failure_marks_unavailable_and_skips_alignment(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider(
                            fail=True
                        )
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        transcription = next(
            work
            for work
            in result.work_units
            if work.operation
            == "transcription"
        )

        alignment = next(
            work
            for work
            in result.work_units
            if work.operation
            == "caption_media_alignment"
        )

        self.assertEqual(
            transcription.status,
            "unavailable",
        )

        self.assertEqual(
            alignment.status,
            "skipped",
        )


    def test_image_alignment_waits_for_image_semantics(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    image_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        visual = next(
            work
            for work
            in result.work_units
            if work.operation
            == "image_visual"
        )

        ocr = next(
            work
            for work
            in result.work_units
            if work.operation
            == "ocr"
        )

        alignment = next(
            work
            for work
            in result.work_units
            if work.operation
            == "caption_media_alignment"
        )

        self.assertEqual(
            visual.status,
            "pending",
        )

        self.assertEqual(
            ocr.status,
            "completed",
        )

        self.assertEqual(
            alignment.status,
            "pending",
        )


    def test_execute_helper_uses_registry(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        self.assertIsInstance(
            result,
            artifact_models
            .ItemArtifactManifest,
        )

        self.assertTrue(
            any(
                artifact
                .artifact_kind
                == "transcript"
                for artifact
                in result.artifacts
            )
        )


    def test_deployment_declares_tesseract_and_faster_whisper(
        self,
    ):
        backend = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        docker = (
            backend
            / "Dockerfile"
        ).read_text(
            encoding="utf-8-sig"
        )

        requirements = (
            backend
            / "requirements.txt"
        ).read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "tesseract-ocr",
            docker,
        )

        self.assertIn(
            "tesseract-ocr-eng",
            docker,
        )

        self.assertIn(
            "tesseract --version",
            docker,
        )

        self.assertIn(
            (
                "faster-whisper"
                "==1.2.1"
            ),
            requirements,
        )


    def test_perception_artifacts_never_create_truth_authority_or_merit_fields(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        payload = (
            result.model_dump(
                mode="json"
            )
            if hasattr(
                result,
                "model_dump",
            )
            else result.dict()
        )

        keys = recursive_keys(
            payload
        )

        for forbidden in (
            "merit_score",
            "truth_status",
            "authority",
            "authority_score",
            "reliability_score",
            "training_eligible",
            "independence_status",
            "affects_merit_score",
        ):
            self.assertNotIn(
                forbidden,
                keys,
            )


    def test_whisper_segment_logprob_fallback_is_bounded(
        self,
    ):
        class Model:
            def transcribe(
                self,
                _path,
                **_kwargs,
            ):
                return (
                    iter(
                        [
                            SimpleNamespace(
                                start=0.0,
                                end=1.0,
                                text="speech",
                                words=[],
                                avg_logprob=(
                                    -0.5
                                ),
                                no_speech_prob=(
                                    0.2
                                ),
                                compression_ratio=(
                                    1.0
                                ),
                            )
                        ]
                    ),
                    SimpleNamespace(
                        language="en",
                        language_probability=(
                            1.0
                        ),
                        duration=1.0,
                        duration_after_vad=(
                            1.0
                        ),
                    ),
                )

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs:
                    Model()
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            result = (
                provider.transcribe(
                    str(
                        audio
                    )
                )
            )

        expected = (
            math.exp(
                -0.5
            )
            * 0.8
        )

        self.assertAlmostEqual(
            result[
                "overall_confidence"
            ],
            expected,
            places=6,
        )


    def test_ocr_confidence_is_extraction_metadata_not_alignment_status(
        self,
    ):
        provider = (
            FakeOcrProvider()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    image_manifest(),
                    workspace=workspace,
                    ocr_provider=provider,
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        artifact = next(
            artifact
            for artifact
            in result.artifacts
            if artifact.artifact_kind
            == "ocr_text"
        )

        self.assertEqual(
            artifact.payload[
                "mean_confidence"
            ],
            0.91,
        )

        self.assertNotIn(
            "alignment_status",
            artifact.payload,
        )


    def test_transcript_confidence_remains_explicit(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        transcript = next(
            artifact
            for artifact
            in result.artifacts
            if artifact.artifact_kind
            == "transcript"
        )

        self.assertEqual(
            transcript.payload[
                "overall_confidence"
            ],
            0.88,
        )


    def test_alignment_dependencies_include_completed_ocr_and_transcript_artifacts(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            result = (
                perception_execution
                .execute_perception_manifest(
                    video_manifest(),
                    workspace=workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        fake_media_executor_builder
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

        alignment = next(
            artifact
            for artifact
            in result.artifacts
            if artifact.artifact_kind
            == (
                "caption_media_"
                "alignment_input"
            )
        )

        kinds = set(
            alignment.payload[
                "dependency_artifact_kinds"
            ]
        )

        self.assertIn(
            "ocr_text",
            kinds,
        )

        self.assertIn(
            "transcript",
            kinds,
        )

        self.assertIn(
            "video_frame",
            kinds,
        )


    def test_whisper_language_hint_is_forwarded(
        self,
    ):
        model = (
            FakeWhisperModel()
        )

        provider = (
            perception_execution
            .FasterWhisperProvider(
                model_factory=(
                    lambda *_args, **_kwargs:
                    model
                )
            )
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            audio = (
                Path(root)
                / "a.wav"
            )

            audio.write_bytes(
                b"audio"
            )

            provider.transcribe(
                str(
                    audio
                ),
                language="fr",
            )

        self.assertEqual(
            model.calls[
                0
            ][1][
                "language"
            ],
            "fr",
        )


    def test_ocr_deduplication_keeps_best_confidence(
        self,
    ):
        class Provider:
            def __init__(
                self,
            ):
                self.index = 0

            def extract(
                self,
                _path,
            ):
                confidence = [
                    0.5,
                    0.95,
                ][
                    self.index
                ]

                self.index += 1

                return {
                    "engine": "fake",
                    "engine_version": "1",
                    "language": "eng",
                    "lines": [
                        {
                            "text": (
                                "Same Text"
                            ),
                            "confidence": (
                                confidence
                            ),
                            "bounding_box": {},
                        }
                    ],
                }

        provider = (
            Provider()
        )

        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            first = (
                Path(root)
                / "1.png"
            )

            second = (
                Path(root)
                / "2.png"
            )

            first.write_bytes(
                b"1"
            )

            second.write_bytes(
                b"2"
            )

            result = (
                perception_execution
                ._deduplicate_ocr_results(
                    [
                        {
                            "local_path": str(
                                first
                            ),
                            (
                                "source_"
                                "artifact_id"
                            ): "a",
                            (
                                "timestamp_"
                                "seconds"
                            ): 1,
                        },
                        {
                            "local_path": str(
                                second
                            ),
                            (
                                "source_"
                                "artifact_id"
                            ): "b",
                            (
                                "timestamp_"
                                "seconds"
                            ): 2,
                        },
                    ],
                    provider,
                )
            )

        self.assertEqual(
            result[
                "entries"
            ][0][
                "confidence"
            ],
            0.95,
        )

        self.assertEqual(
            result[
                "entries"
            ][0][
                "occurrence_count"
            ],
            2,
        )


    def test_video_transcription_reuses_workspace_media_acquisition(
        self,
    ):
        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            workspace = (
                StubWorkspace(
                    root
                )
            )

            executors = (
                perception_execution
                .build_perception_executors(
                    workspace,
                    ocr_provider=(
                        FakeOcrProvider()
                    ),
                    transcription_provider=(
                        FakeTranscriptionProvider()
                    ),
                    media_executor_builder=(
                        lambda *_args, **_kwargs: {}
                    ),
                    audio_extract_fn=(
                        fake_audio_extract
                    ),
                    probe_fn=(
                        fake_probe
                    ),
                )
            )

            work = (
                artifact_models
                .ArtifactWorkUnit(
                    work_id="w:t",
                    operation=(
                        "transcription"
                    ),
                    source_item_ids=[
                        "x:1"
                    ],
                    source_component_ids=[
                        "video:0"
                    ],
                    parameters={
                        "media_kind": (
                            "video"
                        ),
                        "media_url": (
                            "https://cdn.example/"
                            "video.mp4"
                        ),
                    },
                )
            )

            executors[
                "transcription"
            ](
                work,
                (),
                {},
            )

        self.assertEqual(
            workspace.calls,
            [
                (
                    (
                        "https://cdn.example/"
                        "video.mp4"
                    ),
                    "video",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()