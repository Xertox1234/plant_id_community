"""django-ratelimit wrapper that preserves the rate on the raised exception.

django-ratelimit's ``Ratelimited`` is a bare exception and its decorator discards
the rate string (it keeps only ``request.limited``), so a downstream exception
handler has no way to compute a correct ``Retry-After`` window. This thin wrapper
re-raises ``RatelimitedWithRate`` carrying the configured rate so the handler can.

Usage: import this module's ``ratelimit`` in place of
``django_ratelimit.decorators.ratelimit`` — it is a drop-in with the same
signature, so every decorator that uses the imported name benefits automatically.
"""

from functools import wraps

from django_ratelimit import ALL
from django_ratelimit.decorators import ratelimit as _ratelimit
from django_ratelimit.exceptions import Ratelimited


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
