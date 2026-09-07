"""Secure external-page metadata previews for the forum composer."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import logging
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from html.parser import HTMLParser
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from django.core.cache import cache
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from wagtail_forum.api.versioning import UnversionedForumAPIMixin
from wagtail_forum.api.views import PrivateForumReadCacheMixin

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
        key = (attributes.get("property") or attributes.get("name") or "").strip().lower()
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


def _resolve_addresses(host: str, port: int) -> list[tuple]:
    future = _get_dns_executor().submit(
        socket.getaddrinfo,
        host,
        port,
        type=socket.SOCK_STREAM,
    )
    try:
        return future.result(timeout=constants.LINK_PREVIEW_DNS_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        future.cancel()
        raise InvalidPreviewURL from exc
    except OSError as exc:
        raise InvalidPreviewURL from exc


def _resolve_public_address(host: str, port: int) -> tuple[str, str]:
    try:
        literal = _public_ip(host)
    except InvalidPreviewURL:
        try:
            normalized_host = host.encode("idna").decode("ascii").lower().rstrip(".")
        except UnicodeError as exc:
            raise InvalidPreviewURL from exc
        if not normalized_host:
            raise InvalidPreviewURL
        infos = _resolve_addresses(normalized_host, port)
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


def _target_for_url(raw_url: str) -> _Target:
    if not isinstance(raw_url, str):
        raise InvalidPreviewURL
    value = raw_url.strip()
    if (
        not value
        or len(value) > constants.LINK_PREVIEW_MAX_URL_LENGTH
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise InvalidPreviewURL
    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        host = parts.hostname
        explicit_port = parts.port
    except ValueError as exc:
        raise InvalidPreviewURL from exc
    if scheme not in {"http", "https"} or not host or parts.username is not None or parts.password is not None:
        raise InvalidPreviewURL
    port = explicit_port if explicit_port is not None else (443 if scheme == "https" else 80)
    if port not in constants.LINK_PREVIEW_ALLOWED_PORTS:
        raise InvalidPreviewURL
    normalized_host, address = _resolve_public_address(host, port)
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


def _parse_document(body: bytes, original_url: str, final_url: str) -> dict[str, object]:
    parser = _MetadataParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    final_parts = urlsplit(final_url)
    domain = (final_parts.hostname or "").lower()
    values = parser.values
    title = _clean_text(
        values.get("og:title") or values.get("twitter:title") or "".join(parser.title_parts) or domain,
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


def _open_connection(target: _Target) -> HTTPConnection | HTTPSConnection:
    connection_host = f"[{target.host}]" if ":" in target.host else target.host
    if target.scheme == "https":
        connection: HTTPConnection | HTTPSConnection = HTTPSConnection(
            connection_host,
            target.port,
            timeout=constants.LINK_PREVIEW_TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
        )
    else:
        connection = HTTPConnection(
            connection_host,
            target.port,
            timeout=constants.LINK_PREVIEW_TIMEOUT_SECONDS,
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
    content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        return None
    content_length = response.getheader("Content-Length")
    try:
        if content_length is not None and int(content_length) > constants.LINK_PREVIEW_MAX_BODY_BYTES:
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
            host_header = f"[{current.host}]" if ":" in current.host else current.host
            default_port = 443 if current.scheme == "https" else 80
            if current.port != default_port:
                host_header = f"{host_header}:{current.port}"
            connection.request(
                "GET",
                _request_path(current),
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                    "Host": host_header,
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
