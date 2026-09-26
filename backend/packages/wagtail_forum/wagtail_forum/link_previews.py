"""Link preview cards for forum bodies (todo 428) — the package half.

A paragraph whose only content is one ``http(s)`` link (and not a video the
host embeds) is stored as a ``link_preview`` block: a SNAPSHOT of the page's
title, description and site name, taken once at write time. Four rules:

1. **The host fetches, the package decides.** The page is fetched by a host
   callable named in ``WAGTAILFORUM_LINK_PREVIEW_FETCHER`` (a dotted path),
   ``fetcher(url) -> dict | None``. The package never imports the host, and
   never learns how the fetch is secured — SSRF hardening is the host's job
   (``apps.forum_host.link_preview`` here). Unset, nothing converts: links
   stay links.
2. **Network only at WRITE time, bounded.** All of a body's candidate URLs
   are fetched CONCURRENTLY inside ONE ``LINK_PREVIEW_FETCH_TIMEOUT_SECONDS``
   window (the ``warm_embeds`` shape). A URL that fails, raises, answers
   ``None`` or is still running when the window closes stays a paragraph,
   and the post still saves.
3. **Reads never touch the network.** The snapshot lives in the block, so
   ``link_preview_envelope`` is pure data; the card does not change when the
   linked page later does.
4. **Nothing in a card is the client's word.** A resubmitted ``link_preview``
   block is reduced to its URL. Its other fields come from the stored body
   (an edit resending an existing card) or from the fetcher, never from the
   request — otherwise any member could post a card whose title and image
   say one thing while the link goes elsewhere.
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from urllib.parse import urlsplit

from django.core.files.storage import default_storage
from django.utils.module_loading import import_string

from .conf import get_setting

logger = logging.getLogger("wagtail_forum")

# Stored bounds. The block's max_lengths (blocks.py) are these, and every
# fetcher value is truncated to them before it is stored.
URL_MAX_LENGTH = 2048
TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 500
SITE_NAME_MAX_LENGTH = 100
DOMAIN_MAX_LENGTH = 253  # the longest DNS name
IMAGE_MAX_LENGTH = 255

# Concurrent page fetches per process. A body's URLs resolve in parallel
# inside ONE timeout window, so this bounds pool pressure, not wall time.
LINK_PREVIEW_FETCH_WORKERS = 8

_TEXT_FIELDS = (
    ("title", TITLE_MAX_LENGTH),
    ("description", DESCRIPTION_MAX_LENGTH),
    ("site_name", SITE_NAME_MAX_LENGTH),
    ("domain", DOMAIN_MAX_LENGTH),
)

_executor = None
_executor_lock = threading.Lock()


def _get_executor():
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=LINK_PREVIEW_FETCH_WORKERS,
                    thread_name_prefix="wagtail-forum-link-preview",
                )
    return _executor


def is_card_url(url) -> bool:
    """An ``http(s)`` URL with a host, no credentials, no whitespace or
    control characters, within the stored bound. The package's own check:
    it gates what may become a card on write AND what a card may link to
    on read (a CMS edit or an import writes blocks directly)."""
    if not isinstance(url, str) or not url or len(url) > URL_MAX_LENGTH:
        return False
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url):
        return False
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
    except ValueError:
        return False
    return (
        parts.scheme.lower() in {"http", "https"}
        and bool(hostname)
        and parts.username is None
        and parts.password is None
    )


def _image_name_pattern():
    prefix = get_setting("LINK_PREVIEW_IMAGE_PREFIX")
    return re.compile(rf"^{re.escape(prefix)}[0-9a-f]{{64}}\.(?:jpg|webp)$")


def is_cached_image_name(name) -> bool:
    """A storage name the host's image cache could have written: under
    ``LINK_PREVIEW_IMAGE_PREFIX``, a sha256 hex stem, a jpg/webp suffix.
    Anything else (a third-party URL, another media file, a path with
    ``..``) is never served, so a card can only show an image this site
    downloaded, validated and re-encoded itself."""
    return isinstance(name, str) and bool(_image_name_pattern().match(name))


def get_fetcher():
    """The host's fetcher callable, or ``None`` when the host has not opted
    in. A dotted path that does not import is logged and treated as unset:
    a configuration mistake must degrade posts to links, not fail them."""
    path = get_setting("LINK_PREVIEW_FETCHER")
    if not path:
        return None
    try:
        return import_string(path)
    except ImportError:
        logger.exception("[LINK_PREVIEW] fetcher %r does not import", path)
        return None


def _snapshot(url, fetched):
    """The stored block value for ``url`` from the fetcher's answer, bounded,
    or ``None`` when the answer is not a usable dict. ``url`` is always the
    link the author wrote, never whatever URL the fetcher reports."""
    if not isinstance(fetched, dict):
        return None
    value = {"url": url}
    for key, limit in _TEXT_FIELDS:
        text = fetched.get(key)
        value[key] = text.strip()[:limit] if isinstance(text, str) else ""
    image = fetched.get("image")
    value["image"] = image if is_cached_image_name(image) else ""
    return value


def _fetch_and_close(fetcher, url):
    # Runs on a pool thread. The fetcher may touch the DB (a host's cache or
    # storage backend could); close the thread's connection when done so
    # pool threads never hold idle connections (docs/rules/database.md).
    from django.db import connection

    try:
        return fetcher(url)
    finally:
        connection.close()


def _log_late(url, future):
    exc = future.exception()
    if exc is not None:
        logger.warning("[LINK_PREVIEW] late fetch failed for %s: %r", url, exc)


def fetch_snapshots(fetcher, urls) -> dict:
    """``{url: snapshot}`` for every URL in ``urls`` the fetcher answered in
    time. All are fetched concurrently and the author waits at most ONE
    ``LINK_PREVIEW_FETCH_TIMEOUT_SECONDS`` window for the lot; a fetch still
    running then is left to finish in the background and its URL stays a
    link. Nothing here raises."""
    urls = list(dict.fromkeys(urls))
    if not urls:
        return {}
    timeout = get_setting("LINK_PREVIEW_FETCH_TIMEOUT_SECONDS")
    futures = {
        _get_executor().submit(_fetch_and_close, fetcher, url): url for url in urls
    }
    done, pending = wait_futures(futures, timeout=timeout)
    for future in pending:
        url = futures[future]
        logger.warning(
            "[LINK_PREVIEW] fetch still running after %ss, saving as a link: %s",
            timeout,
            url,
        )
        future.add_done_callback(lambda fut, url=url: _log_late(url, fut))
    snapshots = {}
    for future in done:
        url = futures[future]
        exc = future.exception()
        if exc is not None:  # a fetcher bug must never fail the post
            logger.error("[LINK_PREVIEW] fetcher raised for %s", url, exc_info=exc)
            continue
        snapshot = _snapshot(url, future.result())
        if snapshot is not None:
            snapshots[url] = snapshot
    return snapshots


def _stored_text(value) -> dict:
    """The text fields of a stored block value, a non-string read as ""."""
    return {
        key: value.get(key) if isinstance(value.get(key), str) else ""
        for key, _limit in _TEXT_FIELDS
    }


def link_preview_snapshots(raw_data) -> dict:
    """``{url: stored value}`` for every ``link_preview`` block in a body's
    raw StreamField data. The edit path passes this to
    ``validate_forum_body`` so a card the author keeps is reused as stored —
    no fetch, and no change because the linked page changed since."""
    stored = {}
    for block in raw_data:
        if not isinstance(block, dict) or block.get("type") != "link_preview":
            continue
        value = block.get("value")
        url = value.get("url") if isinstance(value, dict) else None
        if is_card_url(url) and url not in stored:
            image = value.get("image")
            stored[url] = {
                "url": url,
                **_stored_text(value),
                "image": image if isinstance(image, str) else "",
            }
    return stored


def link_preview_envelope(raw_value):
    """The API shape of a ``link_preview`` block, or ``None`` when the stored
    value holds no usable link (clients skip a null card). Pure data: no
    fetch, no query. ``image_url`` is our own storage's URL for a cached
    image, else ``None`` — never a third-party address."""
    value = raw_value if isinstance(raw_value, dict) else {}
    url = value.get("url")
    if not is_card_url(url):
        return None
    image = value.get("image")
    return {
        "url": url,
        **_stored_text(value),
        "image_url": (
            default_storage.url(image) if is_cached_image_name(image) else None
        ),
    }
