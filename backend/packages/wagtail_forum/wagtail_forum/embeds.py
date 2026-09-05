"""Video/oEmbed support for forum bodies (todo 344) — the package half.

Three rules shape this module, all from the security posture the todo set:

1. **Provider allowlist is the host's.** ``is_supported_url`` asks Wagtail's
   configured finders (``WAGTAILEMBEDS_FINDERS``) — the host decides which
   providers exist; the package never hardcodes one. With Wagtail's default
   (every known provider) a host that has not narrowed the list gets all of
   them, which is why the host app here ships youtube + vimeo only.
2. **Network only at WRITE time, bounded.** ``warm_embed`` resolves the
   provider's oEmbed response into Wagtail's ``Embed`` cache table while the
   author waits, inside a hard timeout (``EMBED_FETCH_TIMEOUT_SECONDS``) —
   Wagtail's finder calls ``requests.get`` with no timeout (verified in
   ``wagtail/embeds/finders/oembed.py``), so an unreachable provider must not
   hang a create. Failure of any kind is swallowed: the post still saves with
   the URL, and readers get a link card until a later write refreshes it.
3. **Reads never touch the network.** ``embed_envelope`` reads the ``Embed``
   row that ``warm_embed`` left (no ``get_embed`` — that would fetch on a
   cache miss, inline, on a public cached read path) and derives the player
   URL itself from the ORIGINAL url with a per-provider regex. Provider HTML
   is never delivered to clients: the web renders its own sandboxed iframe
   from ``embed_url`` and every client can fall back to ``thumbnail_url`` +
   ``title`` + a plain link.
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from datetime import timedelta
from urllib.parse import urlsplit

import requests
from django.utils import timezone
from django.utils.html import format_html
from wagtail.embeds.exceptions import EmbedNotFoundException
from wagtail.embeds.finders.oembed import OEmbedFinder

from .conf import get_setting

logger = logging.getLogger("wagtail_forum")

EMBED_URL_MAX_LENGTH = 2048
# RFC 3986 unreserved + reserved + percent: anything else (quotes, angle
# brackets, whitespace) is not a URL and never reaches storage.
_URL_CHARS = re.compile(r"^[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$")
# Concurrent provider fetches per process — a body's URLs are resolved in
# parallel inside ONE timeout window, so this bounds pool pressure, not
# wall time (see warm_embeds).
EMBED_FETCH_WORKERS = 8


class TimeoutOEmbedFinder(OEmbedFinder):
    """Wagtail's oEmbed finder with a REAL socket timeout on the provider
    request (``EMBED_FETCH_TIMEOUT_SECONDS``). The stock finder calls
    ``requests.get`` with none, so a stalled provider hangs whatever thread
    asked — the API's write-time worker (which would then be orphaned past
    the executor's own bound) AND the Wagtail admin's embed chooser, which
    calls ``get_embed`` directly. Hosts register this class in
    ``WAGTAILEMBEDS_FINDERS`` (see the README); it is what makes both write
    surfaces bounded. Body mirrors ``OEmbedFinder.find_embed`` in Wagtail
    7.4 with the one added kwarg — re-check on a Wagtail upgrade.
    """

    def find_embed(self, url, max_width=None, max_height=None):
        endpoint = self._get_endpoint(url)
        if endpoint is None:
            raise EmbedNotFoundException

        params = self.options.copy()
        params["url"] = url
        params["format"] = "json"
        if max_width:
            params["maxwidth"] = max_width
        if max_height:
            params["maxheight"] = max_height

        try:
            r = requests.get(
                endpoint,
                params=params,
                headers={"User-agent": "Mozilla/5.0"},
                timeout=get_setting("EMBED_FETCH_TIMEOUT_SECONDS"),
            )
            r.raise_for_status()
            oembed = r.json()
        except requests.RequestException as e:
            raise EmbedNotFoundException(f"Request failed: {e}") from e

        if "type" not in oembed:
            raise EmbedNotFoundException("Missing 'type' in response")
        if oembed["type"] == "photo":
            html = format_html('<img src="{}" alt="">', oembed["url"])
        else:
            html = oembed.get("html")

        result = {
            "title": oembed.get("title", "") or "",
            "author_name": oembed.get("author_name", "") or "",
            "provider_name": oembed.get("provider_name", "") or "",
            "type": oembed["type"],
            "thumbnail_url": oembed.get("thumbnail_url"),
            "width": oembed.get("width"),
            "height": oembed.get("height"),
            "html": html,
        }
        try:
            cache_age = int(oembed["cache_age"])
        except (KeyError, TypeError, ValueError):
            pass
        else:
            result["cache_until"] = timezone.now() + timedelta(seconds=cache_age)
        return result


# Player URLs derived from the ORIGINAL video url, never from provider HTML.
# youtube-nocookie: the privacy-enhanced host, no tracking cookies until play.
_YOUTUBE_ID = re.compile(
    r"^https?://(?:[-\w]+\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|v/|shorts/|live/|embed/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)
_VIMEO_ID = re.compile(r"^https?://(?:www\.|player\.)?vimeo\.com/(?:video/)?(\d+)")


def derive_embed_url(url: str) -> str | None:
    """A sandbox-safe player URL for the providers we know how to iframe, or
    None (clients then show the thumbnail/link card)."""
    m = _YOUTUBE_ID.match(url)
    if m:
        return f"https://www.youtube-nocookie.com/embed/{m.group(1)}"
    m = _VIMEO_ID.match(url)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return None


def is_supported_url(url: str) -> bool:
    """http(s), bounded length, and accepted by one of the host's finders."""
    if not isinstance(url, str) or len(url) > EMBED_URL_MAX_LENGTH:
        return False
    if not _URL_CHARS.match(url):
        return False
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    from wagtail.embeds.finders import get_finders

    return any(finder.accept(url) for finder in get_finders())


_executor = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """Shared, bounded, lazily created — the singleton shape from
    ``docs/patterns/architecture/services.md`` (one pool per process, never
    a pool per call)."""
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=EMBED_FETCH_WORKERS, thread_name_prefix="wf-embed"
                )
    return _executor


def _fetch_and_close(url: str):
    # The worker has its OWN Django DB connection (thread-local); close it
    # when done so a burst of embeds cannot pile up idle connections
    # (docs/rules/database.md — Postgres max_connections is finite).
    from django.db import connection
    from wagtail.embeds.embeds import get_embed

    try:
        return get_embed(url)
    finally:
        connection.close()


def _log_late(url: str, future) -> None:
    # A fetch that outlived the caller's window still finishes here — surface
    # its outcome rather than dropping an exception nobody retrieves.
    exc = future.exception()
    if exc is None:
        logger.info("[EMBED] late provider fetch cached %s", url)
    else:
        logger.warning("[EMBED] late provider fetch failed for %s: %r", url, exc)


def warm_embeds(urls) -> None:
    """Populate Wagtail's Embed cache for every URL in ``urls`` at write
    time, or give up. All of a body's URLs are fetched CONCURRENTLY on the
    shared pool and the author waits at most ONE ``EMBED_FETCH_TIMEOUT_SECONDS``
    window for the lot — so a body with the maximum number of embeds costs
    the same wait as one. Whatever has not resolved by then is left to
    finish in the background (its row still lands, a later read benefits)
    and the post saves with a link card; nothing is retried here.
    """
    from wagtail.embeds.exceptions import EmbedException

    urls = list(dict.fromkeys(u for u in urls if u))
    if not urls:
        return
    timeout = get_setting("EMBED_FETCH_TIMEOUT_SECONDS")
    futures = {_get_executor().submit(_fetch_and_close, url): url for url in urls}
    done, pending = wait_futures(futures, timeout=timeout)
    for future in pending:
        url = futures[future]
        logger.warning(
            "[EMBED] provider fetch still running after %ss, saving as a link card: %s",
            timeout,
            url,
        )
        future.add_done_callback(lambda fut, url=url: _log_late(url, fut))
    for future in done:
        exc = future.exception()
        if exc is None:
            continue
        if isinstance(exc, EmbedException):
            logger.info(
                "[EMBED] provider fetch failed for %s: %s", futures[future], exc
            )
        else:  # a finder bug must never fail the post create
            logger.error(
                "[EMBED] unexpected finder failure for %s",
                futures[future],
                exc_info=exc,
            )


def warm_embed(url: str) -> None:
    """Single-URL convenience over ``warm_embeds``."""
    warm_embeds([url])


def cached_embeds_for(urls) -> dict:
    """``{url: Embed}`` for every fresh cache row among ``urls`` — ONE query,
    or none at all when there is nothing to look up or the host has embeds
    off. The per-page batch every body serializer should use (mirrors
    ``build_forum_image_map``): a page of posts with an embed each must not
    cost a query per post."""
    from wagtail.embeds.embeds import get_embed_hash
    from wagtail.embeds.models import Embed

    urls = {u for u in urls if isinstance(u, str) and u}
    if not urls or not get_setting("ALLOW_EMBED_BLOCKS"):
        return {}
    by_hash = {get_embed_hash(url): url for url in urls}
    rows = (
        Embed.objects.filter(hash__in=by_hash)
        .exclude(cache_until__lte=timezone.now())
        .only("hash", "provider_name", "title", "thumbnail_url")
    )
    return {by_hash[row.hash]: row for row in rows}


_UNSET = object()


def embed_envelope(url: str, cached=_UNSET) -> dict:
    """The API shape of an ``embed`` block. DB-only: reads the cached
    ``Embed`` row if one is fresh, never fetches. Pass ``cached`` (a row or
    None) from a page-level ``cached_embeds_for`` map to make this
    query-free; left unset, it looks its own row up (single-object callers).
    When the host has embeds switched off, ``embed_url`` is None so no client
    renders a player for legacy data, and only the link remains."""
    enabled = get_setting("ALLOW_EMBED_BLOCKS")
    if cached is _UNSET:
        cached = cached_embeds_for({url}).get(url)
    if not enabled:
        cached = None
    return {
        "url": url,
        "provider_name": cached.provider_name if cached else "",
        "title": cached.title if cached else "",
        "thumbnail_url": cached.thumbnail_url if cached else "",
        "embed_url": derive_embed_url(url) if enabled else None,
    }
