"""URL safety helpers shared across apps."""

from urllib.parse import urlsplit


def safe_http_url(url):
    """Return `url` if it is an absolute http(s) URL with a host, else `""`.

    Rejects every other scheme (never let a `javascript:`/`data:` value reach
    an `href`), a missing host (`https://`), and embedded credentials
    (a userinfo part before the host), matching the web's `safeExternalUrl`.
    Stored values are not proof of safety: management commands and imports
    write StreamFields directly, past any form validation (todo 376).
    """
    if not isinstance(url, str) or not url:
        return ""
    url = url.strip()
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not hostname:
        return ""
    if parts.username is not None or parts.password is not None:
        return ""
    return url
