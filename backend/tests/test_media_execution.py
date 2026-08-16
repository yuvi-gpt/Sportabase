from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from app.models import content
from app.services import (
    artifact_extraction,
    media_execution,
)


PUBLIC_IP = "93.184.216.34"
OBSERVED = "2026-08-16T12:00:00Z"


def public_resolver(
    _host,
    port,
    *_args,
):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (
                PUBLIC_IP,
                port,
            ),
        )
    ]


def private_resolver(
    _host,
    port,
    *_args,
):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (
                "127.0.0.1",
                port,
            ),
        )
    ]


class FakeResponse:
    def __init__(
        self,
        body=b"",
        *,
        status=200,
        headers=None,
    ):
        self.body = bytes(
            body
        )

        self.status = status

        self.headers = {
            str(key).lower(): str(
                value
            )
            for key, value
            in (
                headers
                or {}
            ).items()
        }

        self.offset = 0


    def getheader(
        self,
        name,
    ):
        return self.headers.get(
            str(
                name
            ).lower()
        )


    def read(
        self,
        size=-1,
    ):
        if (
            self.offset
            >= len(
                self.body
            )
        ):
            return b""


        end = (
            len(
                self.body
            )
            if (
                size is None
                or size < 0
            )
            else min(
                len(
                    self.body
                ),
                self.offset
                + size,
            )
        )


        chunk = self.body[
            self.offset:end
        ]

        self.offset = end

        return chunk


class FakeConnection:
    def __init__(
        self,
        response,
    ):
        self.response = (
            response
        )

        self.requests = []

        self.closed = False


    def request(
        self,
        method,
        target,
        headers=None,
    ):
        self.requests.append(
            (
                method,
                target,
                dict(
                    headers
                    or {}
                ),
            )
        )


    def getresponse(
        self,
    ):
        return self.response


    def close(
        self,
    ):
        self.closed = True


class QueueConnectionFactory:
    def __init__(
        self,
        responses,
    ):
        self.responses = list(
            responses
        )

        self.targets = []

        self.connections = []


    def __call__(
        self,
        target,
        _timeout,
    ):
        if not self.responses:
            raise AssertionError(
                "Unexpected connection."
            )


        self.targets.append(
            target
        )


        connection = (
            FakeConnection(
                self.responses.pop(
                    0
                )
            )
        )


        self.connections.append(
            connection
        )


        return connection


class FakeRunner:
    def __init__(
        self,
        *,
        probe_payload=None,
        fail_tool="",
    ):
        self.calls = []


        self.probe_payload = (
            probe_payload
            or {
                "format": {
                    "duration": (
                        "20.0"
                    )
                },

                "streams": [
                    {
                        "index": 0,

                        "codec_type": (
                            "video"
                        ),

                        "width": 320,
                        "height": 180,
                    },

                    {
                        "index": 1,

                        "codec_type": (
                            "audio"
                        ),

                        "sample_rate": (
                            "48000"
                        ),

                        "channels": 2,
                    },
                ],
            }
        )


        self.fail_tool = (
            fail_tool
        )


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


        if (
            self.fail_tool
            and args[0]
            == self.fail_tool
        ):
            raise FileNotFoundError(
                args[0]
            )


        if args[0] == "ffprobe":
            return SimpleNamespace(
                returncode=0,

                stdout=json.dumps(
                    self.probe_payload
                ),

                stderr="",
            )


        if args[0] == "ffmpeg":
            output = Path(
                args[-1]
            )


            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )


            if output.suffix == ".wav":
                output.write_bytes(
                    b"RIFF"
                    + b"a" * 64
                )

            else:
                output.write_bytes(
                    b"\xff\xd8"
                    + b"frame-data"
                    + b"\xff\xd9"
                )


            return SimpleNamespace(
                returncode=0,
                stdout="",
                stderr="",
            )


        raise AssertionError(
            "Unexpected tool."
        )


def fake_fetcher_for(
    body=b"video-bytes",
    content_type="video/mp4",
):
    factory = (
        QueueConnectionFactory(
            [
                FakeResponse(
                    body,
                    headers={
                        "Content-Type": (
                            content_type
                        )
                    },
                )
            ]
        )
    )


    fetcher = (
        media_execution
        .SafeMediaFetcher(
            resolver=(
                public_resolver
            ),

            connection_factory=(
                factory
            ),
        )
    )


    return (
        fetcher,
        factory,
    )


def local_asset(
    workspace,
    *,
    name="source.mp4",
):
    source = (
        workspace
        .path_for(
            name
        )
    )


    source.write_bytes(
        b"video"
    )


    data = (
        source
        .read_bytes()
    )


    return (
        media_execution
        .LocalMediaAsset(
            source_url=(
                "https://cdn.example/a.mp4"
            ),

            final_url=(
                "https://cdn.example/a.mp4"
            ),

            local_path=str(
                source
            ),

            content_type=(
                "video/mp4"
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

            media_kind="video",
        )
    )


def video_item(
    *,
    duration_seconds=20.0,
    has_audio=False,
):
    provenance = (
        content
        .ProvenanceRecord(
            source_url=(
                "https://cdn.example/video.mp4"
            ),

            observed_at=(
                OBSERVED
            ),

            extraction_method=(
                "browser_dom"
            ),
        )
    )


    item = (
        content
        .UnifiedContentItem(
            item_id="x:video",

            platform="x",

            platform_surface=(
                "post"
            ),

            container_kind=(
                "media"
            ),

            canonical_url=(
                "https://x.com/a/status/1"
            ),

            observed_at=(
                OBSERVED
            ),

            text_components=[
                content.TextComponent(
                    component_id=(
                        "title"
                    ),

                    role="title",

                    text="Video",

                    provenance=(
                        provenance
                    ),
                )
            ],

            media_components=[
                content.MediaComponent(
                    component_id=(
                        "video:0"
                    ),

                    media_kind=(
                        "video"
                    ),

                    media_url=(
                        "https://cdn.example/video.mp4"
                    ),

                    duration_seconds=(
                        duration_seconds
                    ),

                    has_audio=(
                        has_audio
                    ),

                    provenance=(
                        provenance
                    ),
                )
            ],
        )
    )


    content.validate_unified_content_item(
        item
    )


    return item


class MediaExecutionTests(
    unittest.TestCase
):
    def test_resolve_public_https_target_pins_public_address(
        self,
    ):
        target = (
            media_execution
            .resolve_media_target(
                (
                    "https://cdn.example/"
                    "a.mp4?x=1"
                ),

                resolver=(
                    public_resolver
                ),
            )
        )


        self.assertEqual(
            target.scheme,
            "https",
        )

        self.assertEqual(
            target.port,
            443,
        )

        self.assertEqual(
            target.resolved_ip,
            PUBLIC_IP,
        )

        self.assertEqual(
            target.request_target,
            "/a.mp4?x=1",
        )


    def test_rejects_loopback_literal(
        self,
    ):
        with self.assertRaises(
            media_execution
            .UnsafeMediaUrlError
        ):
            (
                media_execution
                .resolve_media_target(
                    (
                        "http://127.0.0.1/"
                        "a.mp4"
                    )
                )
            )


    def test_rejects_private_dns_resolution(
        self,
    ):
        with self.assertRaises(
            media_execution
            .UnsafeMediaUrlError
        ):
            (
                media_execution
                .resolve_media_target(
                    (
                        "https://cdn.example/"
                        "a.mp4"
                    ),

                    resolver=(
                        private_resolver
                    ),
                )
            )


    def test_rejects_credentials_and_nonstandard_ports(
        self,
    ):
        for url in (
            (
                "https://user:pass@"
                "cdn.example/a.mp4"
            ),

            (
                "https://cdn.example:"
                "8443/a.mp4"
            ),
        ):
            with self.subTest(
                url=url
            ):
                with self.assertRaises(
                    media_execution
                    .UnsafeMediaUrlError
                ):
                    (
                        media_execution
                        .resolve_media_target(
                            url,

                            resolver=(
                                public_resolver
                            ),
                        )
                    )


    def test_fetch_writes_bounded_hashed_media(
        self,
    ):
        body = (
            b"image-bytes"
        )


        factory = (
            QueueConnectionFactory(
                [
                    FakeResponse(
                        body,

                        headers={
                            "Content-Type": (
                                "image/jpeg"
                            ),

                            "Content-Length": (
                                str(
                                    len(
                                        body
                                    )
                                )
                            ),
                        },
                    )
                ]
            )
        )


        fetcher = (
            media_execution
            .SafeMediaFetcher(
                resolver=(
                    public_resolver
                ),

                connection_factory=(
                    factory
                ),

                max_bytes=1024,
            )
        )


        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            asset = (
                fetcher
                .fetch(
                    (
                        "https://cdn.example/"
                        "a.jpg"
                    ),

                    output_directory=(
                        root
                    ),

                    expected_kind=(
                        "image"
                    ),
                )
            )


            self.assertTrue(
                Path(
                    asset.local_path
                ).exists()
            )


            self.assertEqual(
                Path(
                    asset.local_path
                ).read_bytes(),

                body,
            )


            self.assertEqual(
                asset.size_bytes,
                len(body),
            )


            self.assertEqual(
                asset.media_kind,
                "image",
            )


            self.assertEqual(
                len(
                    asset.sha256
                ),
                64,
            )


    def test_redirect_is_revalidated_and_private_redirect_fails_closed(
        self,
    ):
        factory = (
            QueueConnectionFactory(
                [
                    FakeResponse(
                        status=302,

                        headers={
                            "Location": (
                                "http://127.0.0.1/"
                                "private"
                            )
                        },
                    )
                ]
            )
        )


        fetcher = (
            media_execution
            .SafeMediaFetcher(
                resolver=(
                    public_resolver
                ),

                connection_factory=(
                    factory
                ),
            )
        )


        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            with self.assertRaises(
                media_execution
                .UnsafeMediaUrlError
            ):
                (
                    fetcher
                    .fetch(
                        (
                            "https://cdn.example/"
                            "a.mp4"
                        ),

                        output_directory=(
                            root
                        ),

                        expected_kind=(
                            "video"
                        ),
                    )
                )


        self.assertEqual(
            len(
                factory.targets
            ),
            1,
        )


    def test_fetch_rejects_declared_oversize_payload(
        self,
    ):
        factory = (
            QueueConnectionFactory(
                [
                    FakeResponse(
                        b"x",

                        headers={
                            "Content-Type": (
                                "video/mp4"
                            ),

                            "Content-Length": (
                                "1000"
                            ),
                        },
                    )
                ]
            )
        )


        fetcher = (
            media_execution
            .SafeMediaFetcher(
                resolver=(
                    public_resolver
                ),

                connection_factory=(
                    factory
                ),

                max_bytes=100,
            )
        )


        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            with self.assertRaises(
                media_execution
                .MediaLimitError
            ):
                (
                    fetcher
                    .fetch(
                        (
                            "https://cdn.example/"
                            "a.mp4"
                        ),

                        output_directory=(
                            root
                        ),

                        expected_kind=(
                            "video"
                        ),
                    )
                )


    def test_fetch_rejects_stream_that_exceeds_limit(
        self,
    ):
        factory = (
            QueueConnectionFactory(
                [
                    FakeResponse(
                        b"x" * 101,

                        headers={
                            "Content-Type": (
                                "video/mp4"
                            ),
                        },
                    )
                ]
            )
        )


        fetcher = (
            media_execution
            .SafeMediaFetcher(
                resolver=(
                    public_resolver
                ),

                connection_factory=(
                    factory
                ),

                max_bytes=100,
            )
        )


        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            with self.assertRaises(
                media_execution
                .MediaLimitError
            ):
                (
                    fetcher
                    .fetch(
                        (
                            "https://cdn.example/"
                            "a.mp4"
                        ),

                        output_directory=(
                            root
                        ),

                        expected_kind=(
                            "video"
                        ),
                    )
                )


    def test_fetch_rejects_wrong_content_type(
        self,
    ):
        factory = (
            QueueConnectionFactory(
                [
                    FakeResponse(
                        b"<html></html>",

                        headers={
                            "Content-Type": (
                                "text/html"
                            ),
                        },
                    )
                ]
            )
        )


        fetcher = (
            media_execution
            .SafeMediaFetcher(
                resolver=(
                    public_resolver
                ),

                connection_factory=(
                    factory
                ),
            )
        )


        with (
            tempfile
            .TemporaryDirectory()
        ) as root:
            with self.assertRaises(
                media_execution
                .MediaFetchError
            ):
                (
                    fetcher
                    .fetch(
                        (
                            "https://cdn.example/"
                            "a.mp4"
                        ),

                        output_directory=(
                            root
                        ),

                        expected_kind=(
                            "video"
                        ),
                    )
                )


    def test_workspace_caches_same_media_fetch(
        self,
    ):
        (
            fetcher,
            factory,
        ) = fake_fetcher_for()


        with (
            media_execution
            .MediaWorkspace(
                fetcher=fetcher
            )
        ) as workspace:
            first = (
                workspace
                .acquire(
                    (
                        "https://cdn.example/"
                        "a.mp4"
                    ),

                    expected_kind=(
                        "video"
                    ),
                )
            )


            second = (
                workspace
                .acquire(
                    (
                        "https://cdn.example/"
                        "a.mp4"
                    ),

                    expected_kind=(
                        "video"
                    ),
                )
            )


            self.assertEqual(
                first.local_path,
                second.local_path,
            )


            self.assertEqual(
                len(
                    factory.targets
                ),
                1,
            )


    def test_probe_parses_video_audio_and_dimensions(
        self,
    ):
        runner = (
            FakeRunner()
        )


        probe = (
            media_execution
            .probe_local_media(
                "fixture.mp4",

                runner=runner,
            )
        )


        self.assertEqual(
            probe.duration_seconds,
            20.0,
        )

        self.assertEqual(
            probe.width,
            320,
        )

        self.assertEqual(
            probe.height,
            180,
        )

        self.assertTrue(
            probe.has_video
        )

        self.assertTrue(
            probe.has_audio
        )


        (
            args,
            kwargs,
        ) = runner.calls[0]


        self.assertEqual(
            args[0],
            "ffprobe",
        )


        self.assertFalse(
            kwargs.get(
                "shell",
                False,
            )
        )


    def test_missing_ffprobe_fails_closed(
        self,
    ):
        runner = (
            FakeRunner(
                fail_tool=(
                    "ffprobe"
                )
            )
        )


        with self.assertRaises(
            media_execution
            .MediaToolUnavailable
        ):
            (
                media_execution
                .probe_local_media(
                    "fixture.mp4",

                    runner=runner,
                )
            )


    def test_frame_extraction_materializes_hashed_jpegs(
        self,
    ):
        runner = (
            FakeRunner()
        )


        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            outputs = (
                media_execution
                .extract_video_frames(
                    local_asset(
                        workspace
                    ),

                    [
                        0,
                        10,
                        19.6,
                    ],

                    workspace=(
                        workspace
                    ),

                    runner=runner,
                )
            )


            self.assertEqual(
                len(outputs),
                3,
            )


            self.assertTrue(
                all(
                    output[
                        "artifact_kind"
                    ]
                    == "video_frame"

                    for output
                    in outputs
                )
            )


            self.assertTrue(
                all(
                    Path(
                        output[
                            "payload"
                        ][
                            "local_path"
                        ]
                    ).exists()

                    for output
                    in outputs
                )
            )


            self.assertTrue(
                all(
                    len(
                        output[
                            "payload"
                        ][
                            "sha256"
                        ]
                    )
                    == 64

                    for output
                    in outputs
                )
            )


    def test_frame_commands_use_bounded_single_frame_output(
        self,
    ):
        runner = (
            FakeRunner()
        )


        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            (
                media_execution
                .extract_video_frames(
                    local_asset(
                        workspace
                    ),

                    [5],

                    workspace=(
                        workspace
                    ),

                    runner=runner,
                )
            )


        (
            args,
            kwargs,
        ) = runner.calls[0]


        self.assertIn(
            "-nostdin",
            args,
        )


        frame_index = (
            args.index(
                "-frames:v"
            )
        )


        self.assertEqual(
            args[
                frame_index + 1
            ],
            "1",
        )


        filter_index = (
            args.index(
                "-vf"
            )
        )

        self.assertIn(
            (
                "force_original_"
                "aspect_ratio=decrease"
            ),

            args[
                filter_index + 1
            ],
        )


        self.assertFalse(
            kwargs.get(
                "shell",
                False,
            )
        )


    def test_audio_extraction_materializes_mono_16khz_wav(
        self,
    ):
        runner = (
            FakeRunner()
        )


        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            output = (
                media_execution
                .extract_audio_track(
                    local_asset(
                        workspace
                    ),

                    workspace=(
                        workspace
                    ),

                    runner=runner,
                )
            )


            self.assertEqual(
                output[
                    "artifact_kind"
                ],
                "audio_track",
            )


            self.assertEqual(
                output[
                    "payload"
                ][
                    "sample_rate_hz"
                ],
                16000,
            )


            self.assertEqual(
                output[
                    "payload"
                ][
                    "channels"
                ],
                1,
            )


            ffmpeg_args = next(
                args
                for (
                    args,
                    _,
                ) in runner.calls
                if args[0]
                == "ffmpeg"
            )


            self.assertIn(
                "-vn",
                ffmpeg_args,
            )


            self.assertEqual(
                ffmpeg_args[
                    ffmpeg_args
                    .index(
                        "-ac"
                    )
                    + 1
                ],
                "1",
            )


            self.assertEqual(
                ffmpeg_args[
                    ffmpeg_args
                    .index(
                        "-ar"
                    )
                    + 1
                ],
                "16000",
            )


    def test_audio_extraction_rejects_media_without_audio(
        self,
    ):
        runner = (
            FakeRunner(
                probe_payload={
                    "format": {
                        "duration": (
                            "20.0"
                        )
                    },

                    "streams": [
                        {
                            "index": 0,

                            "codec_type": (
                                "video"
                            ),

                            "width": 320,

                            "height": 180,
                        }
                    ],
                }
            )
        )


        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            with self.assertRaises(
                media_execution
                .MediaExecutionError
            ):
                (
                    media_execution
                    .extract_audio_track(
                        local_asset(
                            workspace
                        ),

                        workspace=(
                            workspace
                        ),

                        runner=runner,
                    )
                )


    def test_executor_registry_only_claims_concrete_frame_operation(
        self,
    ):
        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            executors = (
                media_execution
                .build_concrete_media_executors(
                    workspace,

                    runner=(
                        FakeRunner()
                    ),
                )
            )


            self.assertEqual(
                set(
                    executors
                ),
                {
                    (
                        "video_"
                        "frame_extract"
                    )
                },
            )


            for absent in (
                "ocr",
                "transcription",
                "image_visual",
            ):
                self.assertNotIn(
                    absent,
                    executors,
                )


    def test_concrete_executor_completes_frames_but_leaves_semantics_pending(
        self,
    ):
        (
            fetcher,
            _factory,
        ) = fake_fetcher_for()


        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                video_item(
                    duration_seconds=(
                        20
                    ),

                    has_audio=False,
                )
            )
        )


        with (
            media_execution
            .MediaWorkspace(
                fetcher=fetcher
            )
        ) as workspace:
            result = (
                artifact_extraction
                .execute_item_artifact_manifest(
                    manifest,

                    executors=(
                        media_execution
                        .build_concrete_media_executors(
                            workspace,

                            runner=(
                                FakeRunner()
                            ),
                        )
                    ),
                )
            )


            frame_work = next(
                work
                for work
                in result.work_units
                if (
                    work.operation
                    == (
                        "video_"
                        "frame_extract"
                    )
                )
            )


            ocr_work = next(
                work
                for work
                in result.work_units
                if work.operation
                == "ocr"
            )


            self.assertEqual(
                frame_work.status,
                "completed",
            )


            self.assertEqual(
                ocr_work.status,
                "pending",
            )


            frames = [
                artifact
                for artifact
                in result.artifacts
                if (
                    artifact
                    .artifact_kind
                    == "video_frame"
                )
            ]


            self.assertEqual(
                len(frames),
                6,
            )


    def test_unknown_duration_executor_probes_before_sampling(
        self,
    ):
        (
            fetcher,
            _factory,
        ) = fake_fetcher_for()


        runner = (
            FakeRunner(
                probe_payload={
                    "format": {
                        "duration": (
                            "44.0"
                        )
                    },

                    "streams": [
                        {
                            "index": 0,

                            "codec_type": (
                                "video"
                            ),

                            "width": 320,

                            "height": 180,
                        }
                    ],
                }
            )
        )


        manifest = (
            artifact_extraction
            .materialize_item_artifacts(
                video_item(
                    duration_seconds=None,

                    has_audio=False,
                )
            )
        )


        with (
            media_execution
            .MediaWorkspace(
                fetcher=fetcher
            )
        ) as workspace:
            result = (
                artifact_extraction
                .execute_item_artifact_manifest(
                    manifest,

                    executors=(
                        media_execution
                        .build_concrete_media_executors(
                            workspace,

                            runner=runner,
                        )
                    ),
                )
            )


            frame_work = next(
                work
                for work
                in result.work_units
                if (
                    work.operation
                    == (
                        "video_"
                        "frame_extract"
                    )
                )
            )


            self.assertEqual(
                frame_work.status,
                "completed",
            )


            self.assertTrue(
                any(
                    args[0]
                    == "ffprobe"

                    for (
                        args,
                        _,
                    ) in runner.calls
                )
            )


            frames = [
                artifact
                for artifact
                in result.artifacts
                if (
                    artifact
                    .artifact_kind
                    == "video_frame"
                )
            ]


            self.assertEqual(
                len(frames),
                6,
            )


    def test_workspace_cleanup_removes_owned_directory(
        self,
    ):
        workspace = (
            media_execution
            .MediaWorkspace()
        )


        root = (
            workspace.root
        )


        workspace.path_for(
            "temporary.bin"
        ).write_bytes(
            b"x"
        )


        self.assertTrue(
            root.exists()
        )


        workspace.close()


        self.assertFalse(
            root.exists()
        )


    def test_dockerfile_declares_ffmpeg_runtime_dependency(
        self,
    ):
        dockerfile = (
            Path(__file__)
            .resolve()
            .parents[1]
            / "Dockerfile"
        )


        text = (
            dockerfile
            .read_text(
                encoding=(
                    "utf-8-sig"
                )
            )
        )


        self.assertIn(
            "apt-get install",
            text,
        )


        self.assertIn(
            "ffmpeg",
            text,
        )


        self.assertIn(
            "ffprobe -version",
            text,
        )


class RealFfmpegSmokeTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        if (
            shutil.which(
                "ffmpeg"
            ) is None
            or shutil.which(
                "ffprobe"
            ) is None
        ):
            self.skipTest(
                "Local ffmpeg/ffprobe "
                "not installed."
            )


        self.temp = (
            tempfile
            .TemporaryDirectory()
        )


        self.root = Path(
            self.temp.name
        )


        self.fixture = (
            self.root
            / "fixture.mp4"
        )


        result = (
            subprocess
            .run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    (
                        "color=c=black:"
                        "s=64x64:"
                        "r=2:d=2"
                    ),
                    "-f",
                    "lavfi",
                    "-i",
                    (
                        "sine=frequency=440:"
                        "duration=2"
                    ),
                    "-shortest",
                    "-c:v",
                    "mpeg4",
                    "-c:a",
                    "aac",
                    str(
                        self.fixture
                    ),
                ],

                capture_output=True,

                text=True,

                timeout=30,

                check=False,
            )
        )


        if result.returncode != 0:
            self.temp.cleanup()

            self.skipTest(
                "Local ffmpeg fixture "
                "generation unavailable."
            )


    def tearDown(
        self,
    ):
        if hasattr(
            self,
            "temp",
        ):
            self.temp.cleanup()


    def asset(
        self,
    ):
        data = (
            self.fixture
            .read_bytes()
        )


        return (
            media_execution
            .LocalMediaAsset(
                source_url="fixture",
                final_url="fixture",

                local_path=str(
                    self.fixture
                ),

                content_type=(
                    "video/mp4"
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
                    "video"
                ),
            )
        )


    def test_real_ffmpeg_probe_and_frame_extraction(
        self,
    ):
        probe = (
            media_execution
            .probe_local_media(
                str(
                    self.fixture
                )
            )
        )


        self.assertTrue(
            probe.has_video
        )


        self.assertTrue(
            probe.has_audio
        )


        self.assertGreater(
            probe.duration_seconds
            or 0,
            1.0,
        )


        with (
            media_execution
            .MediaWorkspace(
                root=str(
                    self.root
                )
            )
        ) as workspace:
            frames = (
                media_execution
                .extract_video_frames(
                    self.asset(),

                    [
                        0.5,
                        1.5,
                    ],

                    workspace=(
                        workspace
                    ),
                )
            )


            self.assertEqual(
                len(frames),
                2,
            )


            self.assertTrue(
                all(
                    Path(
                        frame[
                            "payload"
                        ][
                            "local_path"
                        ]
                    ).exists()

                    for frame
                    in frames
                )
            )


    def test_real_ffmpeg_audio_demux(
        self,
    ):
        with (
            media_execution
            .MediaWorkspace(
                root=str(
                    self.root
                )
            )
        ) as workspace:
            output = (
                media_execution
                .extract_audio_track(
                    self.asset(),

                    workspace=(
                        workspace
                    ),
                )
            )


            self.assertTrue(
                Path(
                    output[
                        "payload"
                    ][
                        "local_path"
                    ]
                ).exists()
            )


            self.assertGreater(
                output[
                    "payload"
                ][
                    "size_bytes"
                ],
                0,
            )


if __name__ == "__main__":
    unittest.main()