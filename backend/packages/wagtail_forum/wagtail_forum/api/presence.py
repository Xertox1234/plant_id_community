"""Throttled `ForumProfile.last_seen` touch (todo 301).

Wired via `TouchLastSeenMixin.initial()` below, composed into
`UnversionedForumAPIMixin` (versioning.py) — the one base every forum API
view already inherits, structurally guarded by
`apps/forum_host/tests/test_forum_versioning_optout.py`. Composing here means
every current and future forum view gets presence-touching for free, with no
second per-view mixin to remember and no second guard test to keep in sync.

**Authenticated-only, deliberately.** `request.user.is_authenticated` gates
the touch before anything else runs. This is not just "no data for anon
users" — it is what keeps the write off `PublicForumReadCacheMixin`'s
anon-cached GET path. Per `docs/rules/caching.md`, a `public`-cached read may
never carry a per-request side effect; those views only shared-cache the
ANONYMOUS response (an authenticated hit to the same view is already
`private, no-store` — see `_apply_forum_read_cache_headers` in views.py), so
gating on `is_authenticated` means the touch and the cached response path
never overlap.
"""

import logging

from django.core.cache import cache
from django.utils import timezone

from ..conf import get_setting

logger = logging.getLogger("wagtail_forum")


def touch_last_seen(request):
    """At most one `last_seen` UPDATE per user per
    `PRESENCE_TOUCH_THROTTLE_SECONDS` (default 5 min, todo 301 AC2).

    `cache.add()` is the throttle: it is a single atomic add-if-absent op, so
    two concurrent requests from the same user race on one cache write and
    only one wins — no read-then-write window where both see "stale" and both
    issue an UPDATE. The DB write itself is a plain `.filter().update()`, not
    wrapped in `transaction.on_commit()` like the view_count/read-marking
    touches elsewhere in this package: those defer specifically because they
    ride along on a response the caller is about to build; this one is the
    entire point of the request-lifecycle hook (there is no response to build
    around) and immediate is simpler to test.

    `.filter(user=user)` — not `get_or_create` — so a user with no
    `ForumProfile` row yet gets no write and no row is created here. The only
    consumer of `last_seen` (`ExpertsView`'s `online` field) is scoped to
    `EXPERTS_MIN_TRUST_LEVEL`+ users, and reaching that trust level already
    requires a `ForumProfile` row (trust_level lives nowhere else) — so the
    one case that matters is never affected by skipping row-creation here.

    The write is deliberately fail-open, matching `cache.add()` above (prod's
    `IGNORE_EXCEPTIONS=True` already makes the throttle fail open on a cache
    outage). This mixin is composed into `UnversionedForumAPIMixin` — the
    base every forum view inherits — so an unguarded exception here would put
    incidental presence telemetry in the failure path of every authenticated
    forum request, a blast radius the feature doesn't justify (code review).
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return

    throttle_key = f"forum:presence:{user.pk}"
    throttle_seconds = get_setting("PRESENCE_TOUCH_THROTTLE_SECONDS")
    if not cache.add(throttle_key, True, throttle_seconds):
        return  # touched within the throttle window — skip the write

    from ..models import ForumProfile

    try:
        ForumProfile.objects.filter(user=user).update(last_seen=timezone.now())
    except Exception:
        logger.exception(
            "[ERROR] presence touch failed for user %s; last_seen not updated",
            user.pk,
        )


def effective_online_window_seconds():
    """`PRESENCE_ONLINE_WINDOW_SECONDS`, clamped up to at least
    `PRESENCE_TOUCH_THROTTLE_SECONDS` (code review).

    A window narrower than the throttle is a footgun: `last_seen` only
    advances once per throttle period, so a continuously-active user reads
    online right after each touch and flips to offline for the rest of the
    window before the next one — a majority-false blink, not a meaningful
    "was this user recently active" signal. Clamping here means a host that
    sets the pair inconsistently gets the SAFE degraded behavior (a wider
    window than requested) instead of a systematically-wrong online reading.
    """
    return max(
        get_setting("PRESENCE_ONLINE_WINDOW_SECONDS"),
        get_setting("PRESENCE_TOUCH_THROTTLE_SECONDS"),
    )


class TouchLastSeenMixin:
    """DRF `initial()` hook: touch presence once auth is resolved.

    `super().initial()` runs first — DRF's own `APIView.initial()` calls
    `perform_authentication()` before permissions/throttles, so `request.user`
    is populated by the time `touch_last_seen()` reads it.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        touch_last_seen(request)
