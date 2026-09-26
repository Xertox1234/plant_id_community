"""Secure external-page metadata previews for the forum composer."""

from __future__ import annotations

import hashlib
import html
import io
import ipaddress
import logging
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from html.parser import HTMLParser
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from PIL import Image, ImageOps
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail_forum.api.versioning import UnversionedForumAPIMixin
from wagtail_forum.api.views import PrivateForumReadCacheMixin
from wagtail_forum.conf import get_setting
from wagtail_forum.link_previews import is_cached_image_name

from . import constants
from .api import _throttled

logger = logging.getLogger(__name__)
_dns_executor: ThreadPoolExecutor | None = None
_dns_executor_lock = threading.Lock()


class InvalidPreviewURL(ValueError):
    """Raised when a preview target is not a public HTTP(S) URL."""


@dataclass(frozen=True)
class _Target:
    url: str
    scheme: str
    host: str
    port: int
    address: str


class _MetadataParser(HTMLParser):
    _META_KEYS = frozenset(
        {
            "og:title",
            "og:description",
            "og:site_name",
            "og:image",
            "twitter:title",
            "twitter:description",
            "twitter:image",
            "description",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
            return
        if tag.lower() != "meta":
            return
        attributes = {name.lower(): value for name, value in attrs if name}
        key = (
            (attributes.get("property") or attributes.get("name") or "").strip().lower()
        )
        value = attributes.get("content")
        if key in self._META_KEYS and value and key not in self.values:
            self.values[key] = value

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def _clean_text(value: str | None, limit: int) -> str:
    if not value:
        return ""
    return " ".join(html.unescape(value).split())[:limit].strip()


def _public_ip(address: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise InvalidPreviewURL from exc
    mapped = getattr(parsed, "ipv4_mapped", None)
    return mapped or parsed


def _get_dns_executor() -> ThreadPoolExecutor:
    global _dns_executor
    if _dns_executor is None:
        with _dns_executor_lock:
            if _dns_executor is None:
                _dns_executor = ThreadPoolExecutor(
                    max_workers=constants.LINK_PREVIEW_DNS_WORKERS,
                    thread_name_prefix="forum-link-dns",
                )
    return _dns_executor


def _resolve_addresses(
    host: str, port: int, timeout: float | None = None
) -> list[tuple]:
    limit = constants.LINK_PREVIEW_DNS_TIMEOUT_SECONDS
    timeout = limit if timeout is None else min(timeout, limit)
    future = _get_dns_executor().submit(
        socket.getaddrinfo,
        host,
        port,
        type=socket.SOCK_STREAM,
    )
    try:
        return future.result(timeout=timeout)
    except FutureTimeoutError as exc:
        future.cancel()
        raise InvalidPreviewURL from exc
    except OSError as exc:
        raise InvalidPreviewURL from exc


def _resolve_public_address(
    host: str, port: int, dns_timeout: float | None = None
) -> tuple[str, str]:
    try:
        literal = _public_ip(host)
    except InvalidPreviewURL:
        try:
            normalized_host = host.encode("idna").decode("ascii").lower().rstrip(".")
        except UnicodeError as exc:
            raise InvalidPreviewURL from exc
        if not normalized_host:
            raise InvalidPreviewURL
        infos = _resolve_addresses(normalized_host, port, dns_timeout)
        addresses = []
        for info in infos:
            try:
                address = _public_ip(info[4][0])
            except (IndexError, InvalidPreviewURL):
                raise InvalidPreviewURL
            addresses.append(address)
        if not addresses or any(not address.is_global for address in addresses):
            raise InvalidPreviewURL
        return normalized_host, str(addresses[0])
    if not literal.is_global:
        raise InvalidPreviewURL
    return host.lower(), str(literal)


def _target_for_url(raw_url: str, *, dns_timeout: float | None = None) -> _Target:
    """``dns_timeout`` caps the resolution below the usual
    ``LINK_PREVIEW_DNS_TIMEOUT_SECONDS``; the image download passes what is
    left of its budget."""
    if not isinstance(raw_url, str):
        raise InvalidPreviewURL
    value = raw_url.strip()
    if (
        not value
        or len(value) > constants.LINK_PREVIEW_MAX_URL_LENGTH
        or any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in value
        )
    ):
        raise InvalidPreviewURL
    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        host = parts.hostname
        explicit_port = parts.port
    except ValueError as exc:
        raise InvalidPreviewURL from exc
    if (
        scheme not in {"http", "https"}
        or not host
        or parts.username is not None
        or parts.password is not None
    ):
        raise InvalidPreviewURL
    port = (
        explicit_port
        if explicit_port is not None
        else (443 if scheme == "https" else 80)
    )
    if port not in constants.LINK_PREVIEW_ALLOWED_PORTS:
        raise InvalidPreviewURL
    normalized_host, address = _resolve_public_address(host, port, dns_timeout)
    netloc = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    if explicit_port is not None:
        netloc = f"{netloc}:{port}"
    normalized_url = urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))
    return _Target(normalized_url, scheme, normalized_host, port, address)


def normalize_public_url(raw_url: str) -> str:
    return _target_for_url(raw_url).url


def _cache_key(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"{constants.LINK_PREVIEW_CACHE_KEY_PREFIX}:{digest}"


def _empty_preview(url: str) -> dict[str, object]:
    return {
        "url": url,
        "title": "",
        "description": "",
        "image_url": None,
        "site_name": "",
        "domain": "",
        "available": False,
    }


def _safe_image_url(base_url: str, image_value: str | None) -> str | None:
    if not image_value:
        return None
    try:
        image_url = normalize_public_url(urljoin(base_url, image_value))
    except InvalidPreviewURL:
        return None
    if (
        not image_url.startswith("https://")
        or len(image_url) > constants.LINK_PREVIEW_MAX_IMAGE_URL_LENGTH
    ):
        return None
    return image_url


def _parse_document(
    body: bytes, original_url: str, final_url: str
) -> dict[str, object]:
    parser = _MetadataParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    final_parts = urlsplit(final_url)
    domain = (final_parts.hostname or "").lower()
    values = parser.values
    title = _clean_text(
        values.get("og:title")
        or values.get("twitter:title")
        or "".join(parser.title_parts)
        or domain,
        constants.LINK_PREVIEW_MAX_TITLE_CHARS,
    )
    description = _clean_text(
        values.get("og:description")
        or values.get("twitter:description")
        or values.get("description"),
        constants.LINK_PREVIEW_MAX_DESCRIPTION_CHARS,
    )
    site_name = _clean_text(
        values.get("og:site_name") or domain,
        constants.LINK_PREVIEW_MAX_SITE_NAME_CHARS,
    )
    image_url = _safe_image_url(
        final_url,
        values.get("og:image") or values.get("twitter:image"),
    )
    return {
        "url": original_url,
        "title": title,
        "description": description,
        "image_url": image_url,
        "site_name": site_name,
        "domain": domain,
        "available": True,
    }


def _open_connection(
    target: _Target, timeout: float | None = None
) -> HTTPConnection | HTTPSConnection:
    if timeout is None:
        timeout = constants.LINK_PREVIEW_TIMEOUT_SECONDS
    connection_host = f"[{target.host}]" if ":" in target.host else target.host
    if target.scheme == "https":
        connection: HTTPConnection | HTTPSConnection = HTTPSConnection(
            connection_host,
            target.port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        connection = HTTPConnection(
            connection_host,
            target.port,
            timeout=timeout,
        )

    def create_connection(_address, timeout, source_address=None):
        return socket.create_connection(
            (target.address, target.port),
            timeout,
            source_address,
        )

    connection._create_connection = create_connection
    return connection


def _request_path(target: _Target) -> str:
    parts = urlsplit(target.url)
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if not parts.query:
        return path
    query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~[]")
    return f"{path}?{query}"


def _read_document(response) -> bytes | None:
    content_type = (
        (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
    )
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        return None
    content_length = response.getheader("Content-Length")
    try:
        if (
            content_length is not None
            and int(content_length) > constants.LINK_PREVIEW_MAX_BODY_BYTES
        ):
            return None
    except (TypeError, ValueError):
        pass
    chunks: list[bytes] = []
    total = 0
    while total <= constants.LINK_PREVIEW_MAX_BODY_BYTES:
        chunk = response.read(
            min(
                constants.LINK_PREVIEW_READ_CHUNK_BYTES,
                constants.LINK_PREVIEW_MAX_BODY_BYTES - total + 1,
            )
        )
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > constants.LINK_PREVIEW_MAX_BODY_BYTES:
            return None
    return b"".join(chunks)


def _fetch_html(target: _Target) -> tuple[str, bytes] | None:
    current = target
    for request_number in range(constants.LINK_PREVIEW_MAX_REDIRECTS + 1):
        connection = None
        response = None
        try:
            connection = _open_connection(current)
            connection.request(
                "GET",
                _request_path(current),
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                    "Host": _host_header(current),
                    "User-Agent": "PlantCommunityLinkPreview/1.0",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                if request_number >= constants.LINK_PREVIEW_MAX_REDIRECTS:
                    return None
                location = response.getheader("Location")
                if not location:
                    return None
                current = _target_for_url(urljoin(current.url, location))
                continue
            if not 200 <= response.status < 300:
                return None
            body = _read_document(response)
            return (current.url, body) if body is not None else None
        except (HTTPException, OSError, ValueError, UnicodeError):
            return None
        finally:
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
    return None


def fetch_link_preview(raw_url: str) -> dict[str, object]:
    target = _target_for_url(raw_url)
    cache_key = _cache_key(target.url)
    try:
        cached = cache.get(cache_key)
    except Exception:
        logger.warning("[CACHE] link preview read failed")
    else:
        if isinstance(cached, dict):
            return dict(cached)

    preview = _empty_preview(target.url)
    fetched = _fetch_html(target)
    if fetched is not None:
        final_url, body = fetched
        preview = _parse_document(body, target.url, final_url)
    cache_timeout = (
        constants.LINK_PREVIEW_CACHE_TTL_SECONDS
        if preview.get("available") is True
        else constants.LINK_PREVIEW_FAILURE_CACHE_TTL_SECONDS
    )
    try:
        cache.set(cache_key, preview, cache_timeout)
    except Exception:
        logger.warning("[CACHE] link preview write failed")
    return preview


# --- preview-card images (todo 428 slice B) -----------------------------------
#
# A card's image is the page's og:image, downloaded ONCE at write time through
# the same SSRF-pinned path as the page, validated like an upload, re-encoded
# (which drops EXIF and every other metadata chunk) and stored on our own
# media storage. Readers only ever load our copy; the package serves an image
# name only when it matches ``is_cached_image_name``.

# PIL's own plugin list is far wider; only these decoders ever see the bytes.
_IMAGE_FORMATS = ("JPEG", "PNG", "GIF", "WEBP")
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


def _image_name(image_url: str) -> str:
    """Content-addressed by the image's URL, so a second post showing the
    same image reuses the stored file instead of downloading it again."""
    digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    return f"{get_setting('LINK_PREVIEW_IMAGE_PREFIX')}{digest}.webp"


def _image_content_types() -> frozenset[str]:
    # The upload path's allowlist, so the two cannot drift, plus
    # ``image/jpg``: not a registered type, but CDNs send it for JPEGs. The
    # header only decides whether to download; PIL decides what it is.
    return frozenset(get_setting("IMAGE_ALLOWED_MIME_TYPES")) | {"image/jpg"}


def _host_header(target: _Target) -> str:
    host_header = f"[{target.host}]" if ":" in target.host else target.host
    default_port = 443 if target.scheme == "https" else 80
    if target.port != default_port:
        host_header = f"{host_header}:{target.port}"
    return host_header


def _shutdown_socket(sock) -> None:
    """The deadline watchdog. A socket timeout bounds each ``recv``, not a
    request: a server dripping a byte a second keeps ``readline`` (the status
    line, headers, chunk sizes) alive for hours. Shutting the socket down
    ends any read in progress. (The TLS handshake needs no watchdog: CPython
    bounds the whole handshake by the socket timeout, which the caller caps
    at the time left.)"""
    try:
        socket.socket.shutdown(sock, socket.SHUT_RDWR)
    except OSError:
        pass


def _read_image(response, deadline: float) -> bytes | None:
    content_type = (
        (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
    )
    if content_type not in _image_content_types():
        return None
    limit = constants.LINK_PREVIEW_IMAGE_MAX_BYTES
    content_length = response.getheader("Content-Length")
    try:
        if content_length is not None and int(content_length) > limit:
            return None
    except (TypeError, ValueError):
        pass
    chunks: list[bytes] = []
    total = 0
    while True:
        if time.monotonic() >= deadline:
            return None
        # read1: at most ONE underlying recv. read(n) blocks until n bytes
        # arrive, which a slow-drip server can stretch far past the deadline.
        chunk = response.read1(
            min(constants.LINK_PREVIEW_READ_CHUNK_BYTES, limit - total + 1)
        )
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            return None
    # An empty read also ends a body the watchdog cut off, or one the server
    # closed before its Content-Length: neither raises, so check both.
    if time.monotonic() >= deadline or getattr(response, "length", None):
        return None
    return b"".join(chunks)


def _fetch_image(target: _Target, deadline: float) -> bytes | None:
    """The image's bytes, or ``None``. Every hop is re-validated by
    ``_target_for_url`` (public address, pinned) and must stay HTTPS; at most
    ``LINK_PREVIEW_MAX_REDIRECTS`` redirects; nothing runs past
    ``deadline``."""
    current = target
    for request_number in range(constants.LINK_PREVIEW_MAX_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        connection = None
        response = None
        watchdog = None
        try:
            connection = _open_connection(
                current, timeout=min(constants.LINK_PREVIEW_TIMEOUT_SECONDS, remaining)
            )
            connection.connect()
            watchdog = threading.Timer(
                max(deadline - time.monotonic(), 0),
                _shutdown_socket,
                args=(connection.sock,),
            )
            watchdog.daemon = True
            watchdog.start()
            connection.request(
                "GET",
                _request_path(current),
                headers={
                    "Accept": "image/webp,image/png,image/jpeg,image/gif",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                    "Host": _host_header(current),
                    "User-Agent": "PlantCommunityLinkPreview/1.0",
                },
            )
            response = connection.getresponse()
            if response.status in _REDIRECT_STATUSES:
                if request_number >= constants.LINK_PREVIEW_MAX_REDIRECTS:
                    return None
                location = response.getheader("Location")
                if not location:
                    return None
                current = _target_for_url(
                    urljoin(current.url, location),
                    dns_timeout=max(deadline - time.monotonic(), 0.01),
                )
                if current.scheme != "https":
                    return None
                continue
            if not 200 <= response.status < 300:
                return None
            return _read_image(response, deadline)
        except (HTTPException, OSError, ValueError, UnicodeError):
            return None
        finally:
            if watchdog is not None:
                watchdog.cancel()
            if response is not None:
                response.close()
            if connection is not None:
                connection.close()
    return None


def _reencode_image(data: bytes) -> bytes | None:
    """WebP bytes of the first frame, or ``None`` when ``data`` is not an
    allowed, decodable image within the size limits. The size is read from
    the header and checked BEFORE decoding, so a small file declaring a huge
    canvas (a decompression bomb) is refused without allocating it."""
    try:
        with Image.open(io.BytesIO(data), formats=_IMAGE_FORMATS) as source:
            width, height = source.size
            if (
                width > constants.LINK_PREVIEW_IMAGE_MAX_SIDE
                or height > constants.LINK_PREVIEW_IMAGE_MAX_SIDE
            ):
                return None
            if width * height > constants.LINK_PREVIEW_IMAGE_MAX_PIXELS:
                return None
            source.load()
            image = ImageOps.exif_transpose(source)
    except Exception as exc:  # not a decodable image of an allowed format
        logger.info("[LINK_PREVIEW] preview image refused: %r", exc)
        return None
    has_alpha = image.mode in {"RGBA", "LA", "PA"} or "transparency" in image.info
    mode = "RGBA" if has_alpha else "RGB"
    image = image.convert(mode)
    side = constants.LINK_PREVIEW_IMAGE_STORED_MAX_SIDE
    image.thumbnail((side, side))
    # Rebuilt from pixels alone, so EXIF (GPS, camera serials), XMP and ICC
    # chunks still in ``info`` cannot reach the file. Pillow 12's WebP encoder
    # copies none of them unless asked; this keeps that true if one ever does.
    clean = Image.frombytes(mode, image.size, image.tobytes())
    output = io.BytesIO()
    clean.save(output, "WEBP", quality=constants.LINK_PREVIEW_IMAGE_WEBP_QUALITY)
    return output.getvalue()


def _store_image(name: str, data: bytes) -> str:
    saved = default_storage.save(name, ContentFile(data))
    if saved == name:
        return name
    # Another post stored the same image first, so ours got a suffixed name
    # (R2 runs with file_overwrite=False, and FileSystemStorage renames too).
    # A suffixed name never passes is_cached_image_name: drop our copy and
    # use the canonical one.
    try:
        default_storage.delete(saved)
    except Exception:
        logger.warning("[LINK_PREVIEW] could not delete duplicate %s", saved)
    return name if default_storage.exists(name) else ""


def _cache_preview_image(image_url: str, deadline: float) -> str:
    """The stored image's name for the card, or ``""`` for a card without an
    image. ``image_url`` is the page's og:image as ``_safe_image_url``
    accepted it (HTTPS, public)."""
    name = _image_name(image_url)
    if default_storage.exists(name):
        return name
    remaining = deadline - time.monotonic()
    if remaining < constants.LINK_PREVIEW_IMAGE_MIN_SECONDS:
        logger.info("[LINK_PREVIEW] no time left to download %s", image_url)
        return ""
    target = _target_for_url(image_url, dns_timeout=remaining)
    if target.scheme != "https":
        return ""
    data = _fetch_image(target, deadline)
    if data is None:
        logger.info("[LINK_PREVIEW] preview image not downloaded: %s", image_url)
        return ""
    encoded = _reencode_image(data)
    if encoded is None:
        return ""
    stored = _store_image(name, encoded)
    return stored if is_cached_image_name(stored) else ""


def link_preview_snapshot(
    raw_url: str, *, deadline: float | None = None
) -> dict[str, str] | None:
    """The forum package's ``WAGTAILFORUM_LINK_PREVIEW_FETCHER`` hook (todo 428).

    Called once per link at write time, when a post stores a link as a card.
    Returns the card's fields, or ``None`` for "no card" (not a public
    HTTP(S) URL, unreachable, not HTML), so the link stays a link. Goes
    through the same SSRF-pinned, cached ``fetch_link_preview`` as the
    composer endpoint, so a composer preview and the card agree.

    ``image`` is the name of OUR copy of the page's og:image, or ``""``: a
    reader's device must never load the linked site's image (owner decision
    2026-09-24). Any image failure still returns the card, without an image.
    The page and the image share one budget that ends
    ``LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS`` before the package's window.
    ``deadline`` is that window's end as the package passes it, counted from
    when it SUBMITTED the job (todo 448 item 9): a job that waited in a busy
    pool gets only what is left, not a fresh budget. ``None`` (a direct
    call) starts the window now.
    """
    if deadline is None:
        deadline = time.monotonic() + get_setting("LINK_PREVIEW_FETCH_TIMEOUT_SECONDS")
    deadline -= constants.LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS
    try:
        preview = fetch_link_preview(raw_url)
    except InvalidPreviewURL:
        return None
    if preview.get("available") is not True:
        return None
    image = ""
    image_url = preview.get("image_url")
    if isinstance(image_url, str) and image_url:
        try:
            image = _cache_preview_image(image_url, deadline)
        except Exception:
            logger.warning(
                "[LINK_PREVIEW] preview image failed for %s", image_url, exc_info=True
            )
    return {
        "title": str(preview.get("title") or ""),
        "description": str(preview.get("description") or ""),
        "site_name": str(preview.get("site_name") or ""),
        "domain": str(preview.get("domain") or ""),
        "image": image,
    }


@_throttled("link_preview", "GET")
class LinkPreviewView(
    UnversionedForumAPIMixin,
    PrivateForumReadCacheMixin,
    APIView,
):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "url",
                OpenApiTypes.URI,
                OpenApiParameter.QUERY,
                required=True,
            )
        ],
        responses={200: dict, 400: dict, 401: dict, 429: dict},
        description=(
            "Fetches safe title, description, image, and domain metadata for a "
            "public HTTP(S) URL. The endpoint never returns external page HTML."
        ),
    )
    def get(self, request) -> Response:
        raw_url = request.query_params.get("url", "")
        if not isinstance(raw_url, str) or not raw_url.strip():
            return Response(
                {"detail": "A public HTTP(S) URL is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            preview = fetch_link_preview(raw_url)
        except InvalidPreviewURL:
            return Response(
                {"detail": "A public HTTP(S) URL is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(preview)
