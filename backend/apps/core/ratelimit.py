"""django-ratelimit wrapper that preserves the rate on the raised exception.

django-ratelimit's ``Ratelimited`` is a bare exception and its decorator discards
the rate string (it keeps only ``request.limited``), so a downstream exception
handler has no way to compute a correct ``Retry-After`` window. This thin wrapper
re-raises ``RatelimitedWithRate`` carrying the configured rate so the handler can.

Usage: import this module's ``ratelimit`` in place of
``django_ratelimit.decorators.ratelimit`` — it is a drop-in with the same
signature, so every decorator that uses the imported name benefits automatically.
"""

import ipaddress
import logging
from functools import wraps
from typing import Optional

from django.conf import settings
from django.http import HttpRequest
from django_ratelimit import ALL
from django_ratelimit.decorators import ratelimit as _ratelimit
from django_ratelimit.exceptions import Ratelimited

logger = logging.getLogger(__name__)


class RatelimitedWithRate(Ratelimited):
    """``Ratelimited`` that also carries the configured rate string (e.g. '30/m').

    Subclasses django-ratelimit's ``Ratelimited`` so existing
    ``isinstance(exc, Ratelimited)`` checks (and the 429 exception handler) keep
    matching; adds ``.rate`` so handlers can derive the ``Retry-After`` window.
    """

    def __init__(self, rate=None, *args):
        super().__init__(*args)
        self.rate = rate


def ratelimit(group=None, key=None, rate=None, method=ALL, block=True):
    """Drop-in for ``django_ratelimit.decorators.ratelimit`` that attaches the
    rate to the raised exception (see module docstring)."""
    inner = _ratelimit(group=group, key=key, rate=rate, method=method, block=block)

    def decorator(fn):
        wrapped_inner = inner(fn)

        @wraps(fn)
        def _wrapped(request, *args, **kwargs):
            try:
                return wrapped_inner(request, *args, **kwargs)
            except Ratelimited as exc:
                # django-ratelimit already set request.limited before raising; we
                # only re-raise with the rate attached for the Retry-After header.
                # django-ratelimit accepts a callable rate (resolved per request);
                # resolve it the same way so .rate is always the "N/period" string.
                resolved = rate(group, request) if callable(rate) else rate
                raise RatelimitedWithRate(resolved) from exc

        return _wrapped

    return decorator


def _is_valid_ip(value: str) -> bool:
    """True if ``value`` parses as a valid IPv4/IPv6 address."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def get_trusted_client_ip(request: HttpRequest) -> Optional[str]:
    """Resolve the real client IP for per-IP rate limiting behind a reverse proxy.

    django-ratelimit's ``key="ip"`` keys on ``REMOTE_ADDR``, which behind a proxy
    (Railway) is the *proxy's* address — so every client shares one bucket and the
    per-IP limit never accumulates per real client (todo 218).

    ``X-Forwarded-For`` is ``client, proxy1, proxy2, ...``: the left side is
    attacker-controllable (a client may pre-set the header), the right side is
    appended by trusted infrastructure. We therefore count
    ``settings.RATELIMIT_TRUSTED_PROXY_COUNT`` hops from the RIGHT and take the
    entry at that position — the address the outermost trusted proxy actually
    observed. Indexing from the right means any extra left-prepended (spoofed)
    entries cannot shift the result, so a forged header cannot rotate the key.

    Two resolution strategies (use whichever fits the live proxy):

    1. ``RATELIMIT_CLIENT_IP_META_KEY`` — a single trusted META key that already
       holds the real client (e.g. Railway/Envoy's ``HTTP_X_ENVOY_EXTERNAL_ADDRESS``).
       Positional XFF counting is unreliable on proxies that vary the chain, so a
       deployment that exposes a clean header should point at it directly. Only
       honored when it parses as an IP; the proxy MUST set it authoritatively
       (overwrite any client-sent value) or it is spoofable.
    2. ``RATELIMIT_TRUSTED_PROXY_COUNT`` — count this many hops from the RIGHT of
       ``X-Forwarded-For`` and take that entry. Indexing from the right means
       left-prepended (spoofed) entries cannot shift the result. The count MUST
       equal the number of proxies that actually append to XFF.

    Default (neither set) → ``REMOTE_ADDR``, which keeps local/dev/test correct.
    Set ``RATELIMIT_LOG_RESOLUTION=True`` to log how each request resolved (a
    one-time diagnostic for confirming a proxy's real shape, then turn it off).

    Returns the validated client IP, or ``None`` when it cannot be determined.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "")
    meta_key = getattr(settings, "RATELIMIT_CLIENT_IP_META_KEY", "")
    proxy_count = getattr(settings, "RATELIMIT_TRUSTED_PROXY_COUNT", 0)

    result = remote_addr or None

    if meta_key:
        # (1) Trusted single real-client header (e.g. Railway's Envoy header).
        candidate = request.META.get(meta_key, "").strip()
        if _is_valid_ip(candidate):
            result = candidate
    elif proxy_count > 0:
        # (2) Positional X-Forwarded-For. The trusted position only exists if XFF
        # carries at least proxy_count entries; fewer means a missing expected hop.
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [part.strip() for part in xff.split(",") if part.strip()]
        if len(parts) >= proxy_count:
            candidate = parts[-proxy_count]
            if _is_valid_ip(candidate):
                result = candidate
            # A non-IP in the trusted position is malformed/forged: keep REMOTE_ADDR
            # rather than key on an attacker-supplied value.

    if getattr(settings, "RATELIMIT_LOG_RESOLUTION", False):
        # Diagnostic only (off by default). Dumps the candidate forwarding headers
        # so the real client-IP shape of an unknown proxy can be confirmed once.
        logger.warning(
            "[RATELIMIT-RESOLVE] remote_addr=%s x_forwarded_for=%r "
            "x_envoy_external_address=%r x_real_ip=%r meta_key=%r proxy_count=%s "
            "-> resolved=%s",
            remote_addr,
            request.META.get("HTTP_X_FORWARDED_FOR"),
            request.META.get("HTTP_X_ENVOY_EXTERNAL_ADDRESS"),
            request.META.get("HTTP_X_REAL_IP"),
            meta_key,
            proxy_count,
            result,
        )

    return result


def _mask_ip(ip: str) -> str:
    """Collapse ``ip`` to its rate-limit network — IPv4 /32, IPv6 /64 by default.

    Mirrors django-ratelimit's own ``key="ip"`` masking (``RATELIMIT_IPV4_MASK`` /
    ``RATELIMIT_IPV6_MASK``, same defaults) so this stays a true drop-in. The IPv6
    mask is essential: without it a client controlling a /64 could rotate the low
    64 bits to a fresh address per request and evade the per-IP limit. Returns
    ``ip`` unchanged if it cannot be parsed (REMOTE_ADDR is server-set, so this is
    a defensive guard, not an attacker path).
    """
    try:
        version = ipaddress.ip_address(ip).version
    except ValueError:
        return ip
    mask = (
        getattr(settings, "RATELIMIT_IPV6_MASK", 64)
        if version == 6
        else getattr(settings, "RATELIMIT_IPV4_MASK", 32)
    )
    return str(ipaddress.ip_network(f"{ip}/{mask}", strict=False).network_address)


def client_ip_key(group: Optional[str], request: HttpRequest) -> str:
    """django-ratelimit key function: throttle on the trusted client IP.

    Drop-in replacement for ``key="ip"`` that resolves the real client behind our
    reverse proxy (see :func:`get_trusted_client_ip`) and masks it to the same
    network django-ratelimit would (see :func:`_mask_ip`). Returns a stable string
    so all requests from one client share a bucket; falls back to a single
    ``"unknown"`` bucket when no IP can be resolved — failing closed (those
    requests are throttled together rather than each bypassing the limit).
    """
    ip = get_trusted_client_ip(request)
    return _mask_ip(ip) if ip else "unknown"
