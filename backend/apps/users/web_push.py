"""Web Push helpers (todo 413)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from .constants import WEB_PUSH_ALLOWED_HOST_SUFFIXES, WEB_PUSH_ENDPOINT_MAX_LENGTH


def is_allowed_push_endpoint(endpoint: Any) -> bool:
    """True if ``endpoint`` is an https URL on a known browser push service.

    Sending a push makes the server POST to this URL, so anything else (an
    internal address, cloud metadata, a plain-http host) would be SSRF.
    """
    if not isinstance(endpoint, str) or len(endpoint) > WEB_PUSH_ENDPOINT_MAX_LENGTH:
        return False
    try:
        parts = urlsplit(endpoint)
        # `.port` parses lazily and raises ValueError for ':abc' or an
        # out-of-range number, so it belongs inside the try (PR #852 review).
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    if port not in (None, 443):
        return False
    return any(
        host == suffix or host.endswith("." + suffix)
        for suffix in WEB_PUSH_ALLOWED_HOST_SUFFIXES
    )


def clean_subscription(data: Any) -> Optional[Dict[str, Any]]:
    """The browser's ``PushSubscription.toJSON()`` shape, validated, or None."""
    if not isinstance(data, dict):
        return None
    endpoint = data.get("endpoint")
    keys = data.get("keys")
    if not is_allowed_push_endpoint(endpoint) or not isinstance(keys, dict):
        return None
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not (isinstance(p256dh, str) and p256dh and isinstance(auth, str) and auth):
        return None
    if len(p256dh) > 255 or len(auth) > 255:
        return None
    return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}}
