from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import http.client
import ipaddress
import json
import mimetypes
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from app.models import content
from app.services import artifact_extraction


MEDIA_EXECUTION_VERSION = "media-execution-v1"

DEFAULT_FETCH_TIMEOUT_SECONDS = 12.0
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_MEDIA_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_FRAME_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_AUDIO_BYTES = 96 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 3

_ALLOWED_CONTENT_TYPE_PREFIXES = (
    "image/",
    "video/",
    "audio/",
)

_ALLOWED_BINARY_CONTENT_TYPES = {
    "application/octet-stream",
    "binary/octet-stream",
}


class MediaExecutionError(RuntimeError):
    pass


class UnsafeMediaUrlError(MediaExecutionError):
    pass


class MediaFetchError(MediaExecutionError):
    pass


class MediaLimitError(MediaExecutionError):
    pass


class MediaToolUnavailable(MediaExecutionError):
    pass


class MediaCommandError(MediaExecutionError):
    pass


@dataclass(frozen=True)
class ResolvedMediaTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    resolved_ip: str
    request_target: str
    host_header: str


@dataclass(frozen=True)
class LocalMediaAsset:
    source_url: str
    final_url: str
    local_path: str
    content_type: str
    size_bytes: int
    sha256: str
    media_kind: str = ""
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    has_video: bool
    has_audio: bool

    streams: Tuple[
        Dict[str, Any],
        ...
    ] = ()


def _clean_content_type(
    value: Any,
) -> str:
    return (
        str(value or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )


def _media_kind_from_content_type(
    content_type: str,
) -> str:
    for kind in (
        "image",
        "video",
        "audio",
    ):
        if content_type.startswith(
            kind + "/"
        ):
            return kind

    return ""


def _is_allowed_content_type(
    content_type: str,
    *,
    expected_kind: str = "",
) -> bool:
    clean = _clean_content_type(
        content_type
    )

    allowed = (
        clean
        in _ALLOWED_BINARY_CONTENT_TYPES

        or any(
            clean.startswith(
                prefix
            )
            for prefix
            in _ALLOWED_CONTENT_TYPE_PREFIXES
        )
    )

    if not allowed:
        return False

    if (
        not expected_kind
        or clean
        in _ALLOWED_BINARY_CONTENT_TYPES
    ):
        return True

    return clean.startswith(
        expected_kind + "/"
    )


def _is_public_ip(
    value: str,
) -> bool:
    try:
        return bool(
            ipaddress
            .ip_address(
                value
            )
            .is_global
        )

    except ValueError:
        return False


def _resolve_addresses(
    hostname: str,
    port: int,
    *,
    resolver: Callable[
        ...,
        Any,
    ],
) -> Tuple[
    str,
    ...,
]:
    try:
        literal = (
            ipaddress
            .ip_address(
                hostname
            )
        )

    except ValueError:
        literal = None


    if literal is not None:
        addresses = (
            str(
                literal
            ),
        )

    else:
        try:
            infos = resolver(
                hostname,
                port,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            )

        except OSError as error:
            raise UnsafeMediaUrlError(
                "Media hostname could "
                "not be resolved."
            ) from error


        addresses = tuple(
            sorted(
                {
                    str(
                        info[4][0]
                    )
                    for info
                    in infos
                    if (
                        info
                        and len(info)
                        >= 5
                        and info[4]
                    )
                }
            )
        )


    if not addresses:
        raise UnsafeMediaUrlError(
            "Media hostname did not resolve."
        )


    # Fail closed if DNS returns even one
    # non-public address.
    if not all(
        _is_public_ip(
            address
        )
        for address
        in addresses
    ):
        raise UnsafeMediaUrlError(
            "Media URL resolved to "
            "a non-public address."
        )


    return addresses


def resolve_media_target(
    url: str,
    *,
    resolver: Callable[
        ...,
        Any,
    ] = socket.getaddrinfo,
) -> ResolvedMediaTarget:
    raw = str(
        url or ""
    ).strip()


    if (
        not raw
        or len(raw) > 8192
    ):
        raise UnsafeMediaUrlError(
            "Media URL is missing "
            "or too long."
        )


    try:
        parsed = urlparse(
            raw
        )

    except ValueError as error:
        raise UnsafeMediaUrlError(
            "Media URL is invalid."
        ) from error


    scheme = (
        parsed.scheme
        .lower()
    )


    if scheme not in {
        "http",
        "https",
    }:
        raise UnsafeMediaUrlError(
            "Media URL must use "
            "HTTP or HTTPS."
        )


    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise UnsafeMediaUrlError(
            "Media URL credentials "
            "are not allowed."
        )


    hostname = str(
        parsed.hostname or ""
    ).strip().lower()


    if not hostname:
        raise UnsafeMediaUrlError(
            "Media URL hostname "
            "is required."
        )


    try:
        port = (
            parsed.port
            or (
                443
                if scheme == "https"
                else 80
            )
        )

    except ValueError as error:
        raise UnsafeMediaUrlError(
            "Media URL port is invalid."
        ) from error


    expected_port = (
        443
        if scheme == "https"
        else 80
    )


    if port != expected_port:
        raise UnsafeMediaUrlError(
            "Media URL must use "
            "the standard HTTP "
            "or HTTPS port."
        )


    addresses = _resolve_addresses(
        hostname,
        port,
        resolver=resolver,
    )


    resolved_ip = (
        addresses[0]
    )


    request_target = (
        parsed.path
        or "/"
    )


    if parsed.params:
        request_target += (
            ";"
            + parsed.params
        )


    if parsed.query:
        request_target += (
            "?"
            + parsed.query
        )


    host_header = hostname


    try:
        literal = (
            ipaddress
            .ip_address(
                hostname
            )
        )

    except ValueError:
        literal = None


    if (
        literal is not None
        and literal.version == 6
    ):
        host_header = (
            "["
            + hostname
            + "]"
        )


    clean_url = urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",
        )
    )


    return ResolvedMediaTarget(
        url=clean_url,
        scheme=scheme,
        hostname=hostname,
        port=port,
        resolved_ip=resolved_ip,
        request_target=request_target,
        host_header=host_header,
    )


class _PinnedHttpsConnection(
    http.client.HTTPConnection
):
    def __init__(
        self,
        *,
        resolved_ip: str,
        server_hostname: str,
        port: int,
        timeout: float,
        context: Optional[
            ssl.SSLContext
        ] = None,
    ):
        super().__init__(
            resolved_ip,
            port=port,
            timeout=timeout,
        )

        self._server_hostname = (
            server_hostname
        )

        self._ssl_context = (
            context
            or ssl.create_default_context()
        )


    def connect(
        self,
    ) -> None:
        raw_socket = (
            socket
            .create_connection(
                (
                    self.host,
                    self.port,
                ),
                self.timeout,
            )
        )


        self.sock = (
            self._ssl_context
            .wrap_socket(
                raw_socket,
                server_hostname=(
                    self._server_hostname
                ),
            )
        )


def _default_connection_factory(
    target: ResolvedMediaTarget,
    timeout: float,
):
    if target.scheme == "https":
        return _PinnedHttpsConnection(
            resolved_ip=(
                target.resolved_ip
            ),
            server_hostname=(
                target.hostname
            ),
            port=target.port,
            timeout=timeout,
        )


    return (
        http.client
        .HTTPConnection(
            target.resolved_ip,
            port=target.port,
            timeout=timeout,
        )
    )


def _safe_suffix(
    *,
    url: str,
    content_type: str,
) -> str:
    suffix = (
        Path(
            urlparse(
                url
            ).path
        )
        .suffix
        .lower()
    )


    if (
        suffix
        and len(suffix) <= 10
        and suffix[1:].isalnum()
    ):
        return suffix


    guessed = (
        mimetypes
        .guess_extension(
            content_type,
            strict=False,
        )
    )


    if (
        guessed
        and len(guessed) <= 10
    ):
        return guessed


    return ".bin"


class SafeMediaFetcher:
    def __init__(
        self,
        *,
        resolver: Callable[
            ...,
            Any,
        ] = socket.getaddrinfo,

        connection_factory: Optional[
            Callable[
                [
                    ResolvedMediaTarget,
                    float,
                ],
                Any,
            ]
        ] = None,

        timeout_seconds: float = (
            DEFAULT_FETCH_TIMEOUT_SECONDS
        ),

        max_bytes: int = (
            DEFAULT_MAX_MEDIA_BYTES
        ),

        max_redirects: int = (
            DEFAULT_MAX_REDIRECTS
        ),
    ):
        if timeout_seconds <= 0:
            raise ValueError(
                "Fetch timeout must "
                "be positive."
            )


        if max_bytes <= 0:
            raise ValueError(
                "Media byte limit must "
                "be positive."
            )


        if max_redirects < 0:
            raise ValueError(
                "Redirect limit cannot "
                "be negative."
            )


        self._resolver = (
            resolver
        )

        self._connection_factory = (
            connection_factory
            or _default_connection_factory
        )

        self.timeout_seconds = float(
            timeout_seconds
        )

        self.max_bytes = int(
            max_bytes
        )

        self.max_redirects = int(
            max_redirects
        )


    def fetch(
        self,
        url: str,
        *,
        output_directory: str,
        expected_kind: str = "",
    ) -> LocalMediaAsset:
        original_url = str(
            url or ""
        ).strip()

        current_url = (
            original_url
        )

        redirects = 0


        while True:
            target = (
                resolve_media_target(
                    current_url,
                    resolver=(
                        self._resolver
                    ),
                )
            )


            connection = (
                self
                ._connection_factory(
                    target,
                    self.timeout_seconds,
                )
            )


            try:
                connection.request(
                    "GET",
                    target.request_target,
                    headers={
                        "Host": (
                            target.host_header
                        ),

                        "User-Agent": (
                            "Sportabase-Media/"
                            + MEDIA_EXECUTION_VERSION
                        ),

                        "Accept": (
                            "image/*,"
                            "video/*,"
                            "audio/*,"
                            "application/octet-stream"
                        ),

                        "Connection": (
                            "close"
                        ),
                    },
                )


                response = (
                    connection
                    .getresponse()
                )


                status = int(
                    response.status
                )


                if status in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    location = (
                        response
                        .getheader(
                            "Location"
                        )
                    )


                    if not location:
                        raise MediaFetchError(
                            "Media redirect did "
                            "not include Location."
                        )


                    if (
                        redirects
                        >= self.max_redirects
                    ):
                        raise MediaFetchError(
                            "Media redirect "
                            "limit exceeded."
                        )


                    current_url = (
                        urljoin(
                            target.url,
                            location,
                        )
                    )

                    redirects += 1

                    continue


                if (
                    status < 200
                    or status >= 300
                ):
                    raise MediaFetchError(
                        "Media request returned "
                        f"HTTP {status}."
                    )


                content_type = (
                    _clean_content_type(
                        response
                        .getheader(
                            "Content-Type"
                        )
                    )
                )


                if not (
                    _is_allowed_content_type(
                        content_type,
                        expected_kind=(
                            expected_kind
                        ),
                    )
                ):
                    raise MediaFetchError(
                        "Media response content "
                        "type is not allowed."
                    )


                content_length = (
                    response
                    .getheader(
                        "Content-Length"
                    )
                )


                if content_length:
                    try:
                        declared_size = int(
                            content_length
                        )

                    except (
                        TypeError,
                        ValueError,
                    ) as error:
                        raise MediaFetchError(
                            "Media Content-Length "
                            "is invalid."
                        ) from error


                    if declared_size < 0:
                        raise MediaFetchError(
                            "Media Content-Length "
                            "cannot be negative."
                        )


                    if (
                        declared_size
                        > self.max_bytes
                    ):
                        raise MediaLimitError(
                            "Media exceeds "
                            "byte limit."
                        )


                output_root = Path(
                    output_directory
                )

                output_root.mkdir(
                    parents=True,
                    exist_ok=True,
                )


                suffix = _safe_suffix(
                    url=target.url,
                    content_type=(
                        content_type
                    ),
                )


                part_path = (
                    output_root
                    / (
                        "download-"
                        + uuid.uuid4().hex
                        + ".part"
                    )
                )


                digest = (
                    hashlib
                    .sha256()
                )

                size = 0


                try:
                    with part_path.open(
                        "wb"
                    ) as handle:
                        while True:
                            chunk = (
                                response
                                .read(
                                    64 * 1024
                                )
                            )


                            if not chunk:
                                break


                            size += len(
                                chunk
                            )


                            if (
                                size
                                > self.max_bytes
                            ):
                                raise MediaLimitError(
                                    "Media exceeded byte "
                                    "limit while streaming."
                                )


                            digest.update(
                                chunk
                            )

                            handle.write(
                                chunk
                            )


                    sha256 = (
                        digest
                        .hexdigest()
                    )


                    final_path = (
                        output_root
                        / (
                            sha256[:24]
                            + suffix
                        )
                    )


                    if final_path.exists():
                        part_path.unlink(
                            missing_ok=True
                        )

                    else:
                        part_path.replace(
                            final_path
                        )


                except Exception:
                    part_path.unlink(
                        missing_ok=True
                    )

                    raise


                return LocalMediaAsset(
                    source_url=(
                        original_url
                    ),

                    final_url=(
                        target.url
                    ),

                    local_path=str(
                        final_path
                    ),

                    content_type=(
                        content_type
                    ),

                    size_bytes=size,

                    sha256=sha256,

                    media_kind=(
                        _media_kind_from_content_type(
                            content_type
                        )
                        or expected_kind
                    ),

                    metadata={
                        "redirect_count": (
                            redirects
                        ),

                        "resolved_ip": (
                            target
                            .resolved_ip
                        ),
                    },
                )


            finally:
                try:
                    connection.close()

                except Exception:
                    pass


class MediaWorkspace:
    def __init__(
        self,
        *,
        root: Optional[str] = None,
        fetcher: Optional[
            SafeMediaFetcher
        ] = None,
    ):
        if root:
            self.root = Path(
                root
            )

            self.root.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._owns_root = (
                False
            )

        else:
            self.root = Path(
                tempfile
                .mkdtemp(
                    prefix=(
                        "sportabase-media-"
                    )
                )
            )

            self._owns_root = (
                True
            )


        self.fetcher = (
            fetcher
            or SafeMediaFetcher()
        )


        self._asset_cache: Dict[
            Tuple[str, str],
            LocalMediaAsset,
        ] = {}


        self._closed = False


    def __enter__(
        self,
    ) -> "MediaWorkspace":
        return self


    def __exit__(
        self,
        _exc_type,
        _exc,
        _traceback,
    ) -> None:
        self.close()


    def _ensure_open(
        self,
    ) -> None:
        if self._closed:
            raise MediaExecutionError(
                "Media workspace is closed."
            )


    def acquire(
        self,
        url: str,
        *,
        expected_kind: str = "",
    ) -> LocalMediaAsset:
        self._ensure_open()


        key = (
            str(
                url or ""
            ).strip(),

            str(
                expected_kind
                or ""
            ).strip(),
        )


        cached = (
            self
            ._asset_cache
            .get(
                key
            )
        )


        if cached is not None:
            return cached


        asset = (
            self.fetcher
            .fetch(
                key[0],
                output_directory=str(
                    self.root
                ),
                expected_kind=(
                    key[1]
                ),
            )
        )


        self._asset_cache[
            key
        ] = asset


        return asset


    def path_for(
        self,
        name: str,
    ) -> Path:
        self._ensure_open()


        clean_name = (
            Path(name).name
        )


        if not clean_name:
            raise ValueError(
                "Workspace file name "
                "is required."
            )


        return (
            self.root
            / clean_name
        )


    def close(
        self,
    ) -> None:
        if self._closed:
            return


        self._closed = True

        self._asset_cache.clear()


        if self._owns_root:
            shutil.rmtree(
                self.root,
                ignore_errors=True,
            )


def _run_command(
    args: Sequence[str],
    *,
    timeout_seconds: float,
    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
) -> Any:
    if not args:
        raise ValueError(
            "Media command "
            "cannot be empty."
        )


    try:
        result = runner(
            list(
                args
            ),
            capture_output=True,
            text=True,
            timeout=(
                timeout_seconds
            ),
            check=False,
        )


    except FileNotFoundError as error:
        raise MediaToolUnavailable(
            "Required media tool "
            "is unavailable: "
            + str(
                args[0]
            )
        ) from error


    except subprocess.TimeoutExpired as error:
        raise MediaCommandError(
            "Media command timed out."
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


        if len(stderr) > 1000:
            stderr = (
                stderr[:1000]
                + "..."
            )


        raise MediaCommandError(
            "Media command failed"
            + (
                ": " + stderr
                if stderr
                else "."
            )
        )


    return result


def probe_local_media(
    path: str,
    *,
    timeout_seconds: float = (
        DEFAULT_COMMAND_TIMEOUT_SECONDS
    ),
    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
) -> MediaProbe:
    result = _run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:"
                "stream=index,"
                "codec_type,"
                "width,"
                "height,"
                "sample_rate,"
                "channels"
            ),
            "-of",
            "json",
            str(
                path
            ),
        ],
        timeout_seconds=(
            timeout_seconds
        ),
        runner=runner,
    )


    try:
        payload = (
            json.loads(
                str(
                    getattr(
                        result,
                        "stdout",
                        "",
                    )
                    or "{}"
                )
            )
        )

    except json.JSONDecodeError as error:
        raise MediaCommandError(
            "ffprobe returned "
            "invalid JSON."
        ) from error


    streams = tuple(
        dict(
            stream
        )
        for stream
        in payload.get(
            "streams",
            [],
        )
        if isinstance(
            stream,
            Mapping,
        )
    )


    duration_value = (
        (
            payload.get(
                "format"
            )
            or {}
        )
        .get(
            "duration"
        )
    )


    try:
        duration_seconds = (
            float(
                duration_value
            )
            if (
                duration_value
                not in {
                    None,
                    "",
                    "N/A",
                }
            )
            else None
        )

    except (
        TypeError,
        ValueError,
    ):
        duration_seconds = None


    video_stream = next(
        (
            stream
            for stream
            in streams
            if (
                stream.get(
                    "codec_type"
                )
                == "video"
            )
        ),
        None,
    )


    has_audio = any(
        stream.get(
            "codec_type"
        )
        == "audio"
        for stream
        in streams
    )


    width = None
    height = None


    if video_stream:
        try:
            width = int(
                video_stream.get(
                    "width"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            width = None


        try:
            height = int(
                video_stream.get(
                    "height"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            height = None


    return MediaProbe(
        duration_seconds=(
            duration_seconds
        ),
        width=width,
        height=height,
        has_video=(
            video_stream
            is not None
        ),
        has_audio=(
            has_audio
        ),
        streams=streams,
    )


def _hash_local_file(
    path: Path,
    *,
    max_bytes: int,
) -> Tuple[
    int,
    str,
]:
    size = 0

    digest = (
        hashlib
        .sha256()
    )


    with path.open(
        "rb"
    ) as handle:
        while True:
            chunk = handle.read(
                64 * 1024
            )


            if not chunk:
                break


            size += len(
                chunk
            )


            if (
                size
                > max_bytes
            ):
                raise MediaLimitError(
                    "Generated media "
                    "artifact exceeded "
                    "byte limit."
                )


            digest.update(
                chunk
            )


    if size <= 0:
        raise MediaCommandError(
            "Generated media "
            "artifact is empty."
        )


    return (
        size,
        digest.hexdigest(),
    )


def extract_video_frames(
    asset: LocalMediaAsset,
    timestamps_seconds: Sequence[
        float
    ],
    *,
    workspace: MediaWorkspace,

    timeout_seconds: float = (
        DEFAULT_COMMAND_TIMEOUT_SECONDS
    ),

    max_frame_bytes: int = (
        DEFAULT_MAX_FRAME_BYTES
    ),

    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
) -> List[
    Dict[str, Any]
]:
    timestamps: List[
        float
    ] = []

    seen = set()


    for raw in (
        timestamps_seconds
    ):
        timestamp = round(
            max(
                0.0,
                float(
                    raw
                ),
            ),
            3,
        )


        if timestamp in seen:
            continue


        seen.add(
            timestamp
        )

        timestamps.append(
            timestamp
        )


    if not timestamps:
        raise MediaExecutionError(
            "Frame extraction requires "
            "at least one timestamp."
        )


    outputs: List[
        Dict[str, Any]
    ] = []


    for (
        index,
        timestamp,
    ) in enumerate(
        timestamps
    ):
        milliseconds = int(
            round(
                timestamp
                * 1000
            )
        )


        output_path = (
            workspace
            .path_for(
                (
                    "frame-"
                    + asset.sha256[:12]
                    + "-"
                    + str(
                        index
                    )
                    + "-"
                    + str(
                        milliseconds
                    )
                    + ".jpg"
                )
            )
        )


        _run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                asset.local_path,
                "-frames:v",
                "1",
                "-vf",
                (
                    "scale=1280:1280:"
                    "force_original_aspect_ratio=decrease"
                ),
                "-q:v",
                "3",
                str(
                    output_path
                ),
            ],
            timeout_seconds=(
                timeout_seconds
            ),
            runner=runner,
        )


        if not (
            output_path
            .exists()
        ):
            raise MediaCommandError(
                "ffmpeg did not "
                "produce the "
                "requested frame."
            )


        (
            size,
            sha256,
        ) = _hash_local_file(
            output_path,
            max_bytes=(
                max_frame_bytes
            ),
        )


        outputs.append(
            {
                "artifact_kind": (
                    "video_frame"
                ),

                "modality": (
                    "image"
                ),

                "payload": {
                    "timestamp_seconds": (
                        timestamp
                    ),

                    "local_path": str(
                        output_path
                    ),

                    "content_type": (
                        "image/jpeg"
                    ),

                    "size_bytes": (
                        size
                    ),

                    "sha256": (
                        sha256
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
                    (
                        "media_execution_"
                        "version"
                    ): (
                        MEDIA_EXECUTION_VERSION
                    ),

                    (
                        "ephemeral_"
                        "local_file"
                    ): True,
                },
            }
        )


    return outputs


def extract_audio_track(
    asset: LocalMediaAsset,
    *,
    workspace: MediaWorkspace,

    probe: Optional[
        MediaProbe
    ] = None,

    timeout_seconds: float = (
        DEFAULT_COMMAND_TIMEOUT_SECONDS
    ),

    max_audio_bytes: int = (
        DEFAULT_MAX_AUDIO_BYTES
    ),

    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,
) -> Dict[
    str,
    Any,
]:
    media_probe = (
        probe
        or probe_local_media(
            asset.local_path,
            timeout_seconds=(
                timeout_seconds
            ),
            runner=runner,
        )
    )


    if not media_probe.has_audio:
        raise MediaExecutionError(
            "Media does not contain "
            "an audio stream."
        )


    output_path = (
        workspace
        .path_for(
            (
                "audio-"
                + asset.sha256[:12]
                + ".wav"
            )
        )
    )


    _run_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            asset.local_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(
                output_path
            ),
        ],
        timeout_seconds=(
            timeout_seconds
        ),
        runner=runner,
    )


    if not (
        output_path
        .exists()
    ):
        raise MediaCommandError(
            "ffmpeg did not produce "
            "an audio track."
        )


    (
        size,
        sha256,
    ) = _hash_local_file(
        output_path,
        max_bytes=(
            max_audio_bytes
        ),
    )


    return {
        "artifact_kind": (
            "audio_track"
        ),

        "modality": "audio",

        "payload": {
            "local_path": str(
                output_path
            ),

            "content_type": (
                "audio/wav"
            ),

            "sample_rate_hz": (
                16000
            ),

            "channels": 1,

            "size_bytes": size,

            "sha256": sha256,

            (
                "source_"
                "media_sha256"
            ): asset.sha256,

            (
                "source_"
                "media_url"
            ): asset.final_url,
        },

        "metadata": {
            (
                "media_execution_"
                "version"
            ): (
                MEDIA_EXECUTION_VERSION
            ),

            (
                "ephemeral_"
                "local_file"
            ): True,
        },
    }


def build_concrete_media_executors(
    workspace: MediaWorkspace,
    *,
    runner: Callable[
        ...,
        Any,
    ] = subprocess.run,

    timeout_seconds: float = (
        DEFAULT_COMMAND_TIMEOUT_SECONDS
    ),
) -> Dict[
    str,
    Callable[..., Any],
]:
    def video_frame_extract(
        work,
        _available_artifacts,
        _dependency_outputs,
    ):
        media_url = str(
            work.parameters.get(
                "media_url"
            )
            or ""
        ).strip()


        if not media_url:
            raise MediaExecutionError(
                "Frame work requires "
                "media_url."
            )


        asset = (
            workspace
            .acquire(
                media_url,
                expected_kind="video",
            )
        )


        timestamps = list(
            work.parameters.get(
                "timestamps_seconds"
            )
            or []
        )


        if not timestamps:
            if not bool(
                work.parameters.get(
                    "requires_duration_probe"
                )
            ):
                raise MediaExecutionError(
                    "Frame work did not "
                    "include sampling "
                    "timestamps."
                )


            probe = probe_local_media(
                asset.local_path,
                timeout_seconds=(
                    timeout_seconds
                ),
                runner=runner,
            )


            if (
                probe.duration_seconds
                is None
            ):
                raise MediaExecutionError(
                    "Video duration could "
                    "not be determined."
                )


            component_id = (
                work
                .source_component_ids[0]
                if (
                    work
                    .source_component_ids
                )
                else "video"
            )


            media = (
                content
                .MediaComponent(
                    component_id=(
                        component_id
                    ),
                    media_kind="video",
                    duration_seconds=(
                        probe
                        .duration_seconds
                    ),
                )
            )


            schedule = (
                artifact_extraction
                .frame_sampling_schedule(
                    media
                )
            )


            timestamps = list(
                schedule[
                    "timestamps_seconds"
                ]
            )


        return extract_video_frames(
            asset,
            timestamps,
            workspace=workspace,
            timeout_seconds=(
                timeout_seconds
            ),
            runner=runner,
        )


    # Deliberately register only
    # operations that are genuinely
    # implemented here.
    #
    # OCR, transcription, image semantics
    # and alignment remain pending until
    # their real providers are added.
    return {
        "video_frame_extract": (
            video_frame_extract
        ),
    }