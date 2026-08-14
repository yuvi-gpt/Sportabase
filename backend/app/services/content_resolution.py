import html as ihtml
import ipaddress
import re
import socket

from typing import (
    Any,
    Dict,
    List,
)

from urllib.parse import (
    parse_qsl,
    urlencode,
    urljoin,
    urlparse,
)

import requests

from bs4 import BeautifulSoup


TRACKING_QUERY_PARAMETERS = {
    "dclid",
    "fbclid",
    "gclid",
    "gbraid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref_src",
    "s_cid",
    "vero_conv",
    "vero_id",
    "wbraid",
}

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def is_tracking_query_parameter(
    name: str,
) -> bool:
    normalized_name = str(
        name or ""
    ).strip().lower()

    return (
        normalized_name.startswith("utm_")
        or normalized_name
        in TRACKING_QUERY_PARAMETERS
    )


def youtube_video_id_from_url(
    parsed: Any,
) -> str:
    hostname = str(
        parsed.hostname or ""
    ).strip().lower()

    path_parts = [
        part
        for part in str(
            parsed.path or ""
        ).split("/")
        if part
    ]

    query_pairs = parse_qsl(
        parsed.query or "",
        keep_blank_values=True,
    )

    query = {}

    for key, value in query_pairs:
        normalized_key = str(
            key or ""
        ).strip().lower()

        if normalized_key not in query:
            query[normalized_key] = str(
                value or ""
            ).strip()

    candidate = ""

    if hostname in {
        "youtu.be",
        "www.youtu.be",
    }:
        if path_parts:
            candidate = path_parts[0]

    elif hostname in YOUTUBE_HOSTS:
        if (
            path_parts
            and path_parts[0].lower()
            in {
                "embed",
                "live",
                "shorts",
                "v",
            }
            and len(path_parts) >= 2
        ):
            candidate = path_parts[1]

        elif (
            not path_parts
            or path_parts[0].lower()
            == "watch"
        ):
            candidate = query.get(
                "v",
                "",
            )

    candidate = re.sub(
        r"[^A-Za-z0-9_-]",
        "",
        candidate,
    )

    if not re.fullmatch(
        r"[A-Za-z0-9_-]{6,20}",
        candidate,
    ):
        return ""

    return candidate


def _validate_public_ip_address(
    address: str,
) -> None:
    clean_address = str(
        address or ""
    ).split(
        "%",
        1,
    )[0].strip()

    try:
        parsed_address = ipaddress.ip_address(
            clean_address
        )
    except ValueError as error:
        raise ValueError(
            "The remote hostname resolved "
            "to an invalid IP address."
        ) from error

    if not parsed_address.is_global:
        raise ValueError(
            "Private, local, reserved, and "
            "non-public network addresses "
            "are not allowed."
        )


def validate_safe_remote_url(
    url: str,
) -> str:
    candidate = str(
        url or ""
    ).strip()

    if not candidate:
        raise ValueError(
            "A remote URL is required."
        )

    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()

    if scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "Only HTTP and HTTPS URLs "
            "are allowed."
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "URLs containing credentials "
            "are not allowed."
        )

    hostname = str(
        parsed.hostname or ""
    ).strip().rstrip(".").lower()

    if not hostname:
        raise ValueError(
            "The URL must contain a hostname."
        )

    if (
        hostname == "localhost"
        or hostname.endswith(
            ".localhost"
        )
    ):
        raise ValueError(
            "Localhost URLs are not allowed."
        )

    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(
            "The URL contains an invalid port."
        ) from error

    if port is None:
        port = (
            443
            if scheme == "https"
            else 80
        )

    try:
        ipaddress.ip_address(
            hostname.split(
                "%",
                1,
            )[0]
        )
    except ValueError:
        try:
            resolved = socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        except OSError as error:
            raise ValueError(
                "The remote hostname could "
                "not be resolved."
            ) from error

        addresses = {
            str(result[4][0]).split(
                "%",
                1,
            )[0]
            for result in resolved
            if len(result) >= 5
            and result[4]
        }

        if not addresses:
            raise ValueError(
                "The remote hostname did not "
                "resolve to an IP address."
            )

        for address in addresses:
            _validate_public_ip_address(
                address
            )
    else:
        _validate_public_ip_address(
            hostname
        )

    return candidate


def fetch_safe_article_html(
    url: str,
    *,
    max_bytes: int = 1_500_000,
    timeout_seconds: float = 10.0,
    max_redirects: int = 3,
) -> Dict[str, Any]:
    if max_bytes <= 0:
        raise ValueError(
            "The article response limit must "
            "be greater than zero."
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "The article timeout must be "
            "greater than zero."
        )

    if max_redirects < 0:
        raise ValueError(
            "The redirect limit cannot "
            "be negative."
        )

    current_url = validate_safe_remote_url(
        url
    )

    redirect_count = 0

    while True:
        response = None

        try:
            response = requests.get(
                current_url,
                headers={
                    "Accept": (
                        "text/html,"
                        "application/xhtml+xml"
                    ),
                    "User-Agent": (
                        "Sportabase/0.2 "
                        "(article resolver)"
                    ),
                },
                timeout=(
                    3.05,
                    timeout_seconds,
                ),
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout as error:
            raise ValueError(
                "The article request timed out."
            ) from error
        except requests.RequestException as error:
            raise ValueError(
                "The article could not be fetched."
            ) from error

        try:
            status_code = int(
                response.status_code
            )

            if status_code in {
                301,
                302,
                303,
                307,
                308,
            }:
                if redirect_count >= max_redirects:
                    raise ValueError(
                        "The article exceeded the "
                        "redirect limit."
                    )

                location = str(
                    response.headers.get(
                        "Location",
                        "",
                    )
                ).strip()

                if not location:
                    raise ValueError(
                        "The article redirect did "
                        "not include a destination."
                    )

                redirect_url = urljoin(
                    current_url,
                    location,
                )

                current_url = (
                    validate_safe_remote_url(
                        redirect_url
                    )
                )

                redirect_count += 1
                continue

            if (
                status_code < 200
                or status_code >= 300
            ):
                raise ValueError(
                    "The article request returned "
                    f"HTTP {status_code}."
                )

            content_type = str(
                response.headers.get(
                    "Content-Type",
                    "",
                )
            ).strip().lower()

            media_type = content_type.split(
                ";",
                1,
            )[0].strip()

            if media_type not in {
                "text/html",
                "application/xhtml+xml",
            }:
                raise ValueError(
                    "The remote response is not "
                    "an HTML article."
                )

            declared_length = str(
                response.headers.get(
                    "Content-Length",
                    "",
                )
            ).strip()

            if declared_length:
                try:
                    declared_bytes = int(
                        declared_length
                    )
                except ValueError as error:
                    raise ValueError(
                        "The article response has "
                        "an invalid content length."
                    ) from error

                if declared_bytes < 0:
                    raise ValueError(
                        "The article response has "
                        "an invalid content length."
                    )

                if declared_bytes > max_bytes:
                    raise ValueError(
                        "The article response is "
                        "too large."
                    )

            body = bytearray()

            for chunk in response.iter_content(
                chunk_size=65_536
            ):
                if not chunk:
                    continue

                if isinstance(
                    chunk,
                    str,
                ):
                    chunk = chunk.encode(
                        "utf-8"
                    )

                body.extend(chunk)

                if len(body) > max_bytes:
                    raise ValueError(
                        "The article response is "
                        "too large."
                    )

            charset = ""

            for parameter in content_type.split(
                ";"
            )[1:]:
                name, separator, value = (
                    parameter.partition("=")
                )

                if (
                    separator
                    and name.strip() == "charset"
                ):
                    charset = (
                        value.strip()
                        .strip('"')
                        .strip("'")
                    )
                    break

            raw_body = bytes(body)

            if charset:
                try:
                    html = raw_body.decode(
                        charset,
                        errors="replace",
                    )
                except LookupError:
                    html = raw_body.decode(
                        "utf-8",
                        errors="replace",
                    )
            else:
                try:
                    html = raw_body.decode(
                        "utf-8"
                    )
                except UnicodeDecodeError:
                    fallback_encoding = str(
                        getattr(
                            response,
                            "encoding",
                            "",
                        )
                        or "utf-8"
                    ).strip()

                    try:
                        html = raw_body.decode(
                            fallback_encoding,
                            errors="replace",
                        )
                    except LookupError:
                        html = raw_body.decode(
                            "utf-8",
                            errors="replace",
                        )

            return {
                "html": html,
                "final_url": current_url,
                "redirect_count": (
                    redirect_count
                ),
                "content_type": media_type,
                "byte_count": len(body),
            }
        finally:
            response.close()


def _normalize_extracted_text(
    value: Any,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        ihtml.unescape(
            str(value or "")
        ),
    ).strip()


def extract_article_content(
    html: str,
    *,
    max_chars: int = 12_000,
    min_chars: int = 80,
) -> Dict[str, Any]:
    raw_html = str(
        html or ""
    )

    if not raw_html.strip():
        raise ValueError(
            "The article page is empty."
        )

    if max_chars <= 0:
        raise ValueError(
            "The article text limit must "
            "be greater than zero."
        )

    if min_chars < 0:
        raise ValueError(
            "The article minimum length "
            "cannot be negative."
        )

    if min_chars > max_chars:
        raise ValueError(
            "The article minimum length "
            "cannot exceed its text limit."
        )

    soup = BeautifulSoup(
        raw_html,
        "lxml",
    )

    title = ""

    metadata_titles: Dict[
        str,
        str,
    ] = {}

    for tag in soup.find_all("meta"):
        key = _normalize_extracted_text(
            tag.get("property")
            or tag.get("name")
            or ""
        ).lower()

        content = _normalize_extracted_text(
            tag.get("content")
            or ""
        )

        if (
            key
            and content
            and key not in metadata_titles
        ):
            metadata_titles[key] = content

    for key in (
        "og:title",
        "twitter:title",
    ):
        candidate = metadata_titles.get(
            key,
            "",
        )

        if candidate:
            title = candidate
            break

    if not title:
        heading = soup.find("h1")

        if heading is not None:
            title = _normalize_extracted_text(
                heading.get_text(
                    " ",
                    strip=True,
                )
            )

    if (
        not title
        and soup.title is not None
    ):
        title = _normalize_extracted_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    title = title[:300].strip()

    for tag_name in (
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "canvas",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "button",
    ):
        for tag in soup.find_all(
            tag_name
        ):
            tag.decompose()

    def content_root_score(
        node: Any,
    ):
        paragraph_characters = sum(
            len(
                _normalize_extracted_text(
                    paragraph.get_text(
                        " ",
                        strip=True,
                    )
                )
            )
            for paragraph in node.find_all("p")
        )

        total_characters = len(
            _normalize_extracted_text(
                node.get_text(
                    " ",
                    strip=True,
                )
            )
        )

        return (
            paragraph_characters,
            total_characters,
        )

    candidate_roots = []

    for article_candidate in soup.find_all(
        "article"
    ):
        candidate_roots.append(
            (
                "article",
                article_candidate,
            )
        )

    for main_candidate in soup.find_all(
        "main"
    ):
        candidate_roots.append(
            (
                "main",
                main_candidate,
            )
        )

    if candidate_roots:
        (
            extraction_method,
            content_root,
        ) = max(
            candidate_roots,
            key=lambda item: (
                content_root_score(
                    item[1]
                )
            ),
        )

        if content_root_score(
            content_root
        ) == (0, 0):
            if soup.body is not None:
                content_root = soup.body
                extraction_method = "body"
            else:
                content_root = soup
                extraction_method = "document"

    elif soup.body is not None:
        content_root = soup.body
        extraction_method = "body"

    else:
        content_root = soup
        extraction_method = "document"

    paragraphs: List[str] = []
    seen_paragraphs = set()

    for paragraph_tag in (
        content_root.find_all("p")
    ):
        paragraph = (
            _normalize_extracted_text(
                paragraph_tag.get_text(
                    " ",
                    strip=True,
                )
            )
        )

        if not paragraph:
            continue

        duplicate_key = paragraph.lower()

        if duplicate_key in seen_paragraphs:
            continue

        seen_paragraphs.add(
            duplicate_key
        )

        paragraphs.append(
            paragraph
        )

    if paragraphs:
        article_text = "\n\n".join(
            paragraphs
        )
    else:
        article_text = (
            _normalize_extracted_text(
                content_root.get_text(
                    " ",
                    strip=True,
                )
            )
        )

        paragraphs = (
            [article_text]
            if article_text
            else []
        )

    if len(article_text) > max_chars:
        clipped_text = article_text[
            :max_chars
        ].rstrip()

        final_space = (
            clipped_text.rfind(" ")
        )

        safe_boundary = int(
            max_chars * 0.75
        )

        if final_space >= safe_boundary:
            clipped_text = clipped_text[
                :final_space
            ].rstrip()

        article_text = clipped_text

    if len(article_text) < min_chars:
        raise ValueError(
            "The page does not contain enough "
            "meaningful article text."
        )

    if not title:
        title = (
            article_text[:120].rstrip()
        )

    return {
        "title": title,
        "text": article_text,
        "extraction_method": (
            extraction_method
        ),
        "paragraph_count": len(
            paragraphs
        ),
        "character_count": len(
            article_text
        ),
    }


def detect_content_source(
    url: str,
) -> Dict[str, str]:
    raw_url = str(url or "").strip()

    if not raw_url:
        raise ValueError(
            "A content URL is required."
        )

    normalized_url = normalized_analysis_url(
        raw_url
    )

    try:
        parsed = urlparse(normalized_url)
    except ValueError as error:
        raise ValueError(
            "The content URL is invalid."
        ) from error

    scheme = str(
        parsed.scheme or ""
    ).strip().lower()

    hostname = str(
        parsed.hostname or ""
    ).strip().lower()

    if (
        scheme not in {"http", "https"}
        or not hostname
    ):
        raise ValueError(
            "The content URL must use HTTP or HTTPS."
        )

    canonical_hostname = hostname.removeprefix(
        "www."
    )

    youtube_hosts = {
        host.removeprefix("www.")
        for host in YOUTUBE_HOSTS
    }

    is_youtube_host = (
        canonical_hostname in youtube_hosts
    )

    youtube_video_id = (
        youtube_video_id_from_url(parsed)
    )

    if (
        is_youtube_host
        and not youtube_video_id
    ):
        raise ValueError(
            "The YouTube URL does not contain "
            "a valid video ID."
        )

    if youtube_video_id:
        return {
            "source": "youtube",
            "mode": "video",
            "normalized_url": normalized_url,
        }

    return {
        "source": "article",
        "mode": "article",
        "normalized_url": normalized_url,
    }


def normalized_analysis_url(url: str) -> str:
    raw_url = str(url or "").strip()

    if not raw_url:
        return ""

    raw_url = raw_url.split(
        "#",
        1,
    )[0].strip()

    try:
        parsed = urlparse(raw_url)

        if not parsed.scheme and parsed.netloc:
            parsed = urlparse(
                f"https:{raw_url}"
            )

        elif (
            not parsed.scheme
            and not parsed.netloc
            and re.match(
                r"^[A-Za-z0-9.-]+/",
                raw_url,
            )
        ):
            parsed = urlparse(
                f"https://{raw_url}"
            )

        scheme = str(
            parsed.scheme or ""
        ).strip().lower()

        hostname = str(
            parsed.hostname or ""
        ).strip().lower()

        if not scheme or not hostname:
            return raw_url

        canonical_hostname = hostname

        youtube_video_id = (
            youtube_video_id_from_url(
                parsed
            )
        )

        if youtube_video_id:
            return (
                "https://youtube.com/watch?v="
                f"{youtube_video_id}"
            )

        port = parsed.port

        include_port = (
            port is not None
            and not (
                scheme == "http"
                and port == 80
            )
            and not (
                scheme == "https"
                and port == 443
            )
        )

        authority = canonical_hostname

        if include_port:
            authority = (
                f"{authority}:{port}"
            )

        path = re.sub(
            r"/{2,}",
            "/",
            parsed.path or "/",
        )

        if path != "/":
            path = path.rstrip("/")

        retained_query_pairs = []

        for key, value in parse_qsl(
            parsed.query or "",
            keep_blank_values=True,
        ):
            if is_tracking_query_parameter(
                key
            ):
                continue

            retained_query_pairs.append(
                (
                    str(key),
                    str(value),
                )
            )

        retained_query_pairs.sort(
            key=lambda item: (
                item[0].lower(),
                item[1],
            )
        )

        canonical_query = urlencode(
            retained_query_pairs,
            doseq=True,
        )

        result = (
            f"{scheme}://{authority}{path}"
        )

        if canonical_query:
            result = (
                f"{result}?{canonical_query}"
            )

        return result

    except Exception:
        return raw_url
