"""DB-backed overrides for ``WAGTAILFORUM_*`` tunables (Wagtail quick wins, item 1).

``ForumSettings`` (models.py) stores the admin-edited values; :func:`provide`
is the override provider this module registers with ``wagtail_forum.conf`` at
``AppConfig.ready()``. The *package* owns the precedence — a non-blank DB
value, then the ``WAGTAILFORUM_<NAME>`` Django setting, then the package
default — so the host never has to re-implement the lookup and the package
never imports the host (``test_reusability``).

Why a memo + shared token instead of one SELECT per read: the mapped names sit
on hot paths (the heuristic spam check reads two per post create, autopublish
one per publish, the experts rail one per request) and the forum suite pins
query counts on those paths, so a per-call SELECT would be both a small
regression and a churn of every pinned count. Steady state here is zero DB
queries and one cache GET. Cross-worker invalidation rides ``CACHE_KEY``: a
save or delete stores a fresh token **once its transaction commits** (the
admin edit view saves inside ``atomic()``; rotating the token earlier would
let another worker reload the still-uncommitted OLD row under the NEW token
and memoise it for good — code-review 2026-09-04), and every worker whose
memo carries a different token reloads on its next read. A *missing* token
(flushed cache, Redis restart, TTL lapse, ``cache.clear()`` in tests)
deliberately keeps the memo — the worst case is "stale until the next admin
save", never a per-read query storm — which is also why the token can carry
a finite TTL without affecting correctness.
"""

import logging
import uuid

from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.db.models.signals import post_delete, post_save
from wagtail_forum.conf import MISSING, register_override_provider

from . import constants

logger = logging.getLogger(__name__)

# WAGTAILFORUM_<NAME> -> ForumSettings field. Only these names ever touch the
# DB; every other get_setting() call short-circuits to MISSING with no I/O.
FIELD_MAP = {
    "REPORT_AUTO_HIDE_THRESHOLD": "report_auto_hide_threshold",
    "TRUST_AUTOPUBLISH_LEVEL": "trust_autopublish_level",
    "SPAM_MAX_LINKS": "spam_max_links",
    "SPAM_BANNED_WORDS": "spam_banned_words",
    "EXPERTS_MIN_TRUST_LEVEL": "experts_min_trust_level",
    "BADGE_BOTANIST_THRESHOLD": "badge_botanist_threshold",
}

# Versioned so a future change to the memo's shape can never be satisfied by a
# token written by older code.
CACHE_KEY = "forum_host:forum_settings:token:v1"

# (token seen at load, {NAME: value}) — or None before the first load / after
# a local invalidate. Assignment of the whole tuple is atomic in CPython; two
# threads racing the first load both compute the same answer.
_memo = None


def _split_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _load_values():
    """One SELECT of the single ForumSettings row -> {NAME: value} for the
    non-blank fields. No row, or a row with every field blank, is ``{}``."""
    from .models import ForumSettings

    # Savepoint: if the table doesn't exist yet (app booted before `migrate`
    # ran), the ProgrammingError must not leave an enclosing transaction —
    # e.g. an atomic post create that is spam-checking — in the aborted state.
    with transaction.atomic():
        row = ForumSettings.objects.values(*FIELD_MAP.values()).first()
    if row is None:
        return {}
    values = {}
    for name, field in FIELD_MAP.items():
        raw = row[field]
        if raw is None:
            continue  # NULL = inherit
        if name == "SPAM_BANNED_WORDS":
            raw = _split_lines(raw)
            if not raw:
                continue  # blank textarea = inherit
        values[name] = raw
    return values


def _values():
    global _memo
    token = cache.get(CACHE_KEY)
    memo = _memo
    if memo is None or (token is not None and token != memo[0]):
        memo = _memo = (token, _load_values())
    return memo[1]


def provide(name):
    """``wagtail_forum.conf`` override provider: the DB value when set, else
    ``MISSING`` so the package falls through to settings/defaults. Never
    raises — a DB outage or a not-yet-migrated table degrades to inherit."""
    if name not in FIELD_MAP:
        return MISSING
    try:
        values = _values()
    except DatabaseError:
        logger.warning(
            "[ERROR] ForumSettings unavailable; %s inherits the settings value",
            name,
            exc_info=True,
        )
        return MISSING
    return values.get(name, MISSING)


def invalidate(**kwargs):
    """Drop this process's memo now and rotate the shared token when the
    surrounding transaction commits (immediately if there is none), so every
    other worker reloads on its next read — of the committed row. Wired to
    ForumSettings post_save and post_delete; ``**kwargs`` swallows the signal
    payload."""
    global _memo
    _memo = None
    token = uuid.uuid4().hex
    transaction.on_commit(
        lambda: cache.set(CACHE_KEY, token, constants.FORUM_SETTINGS_TOKEN_TTL_SECONDS)
    )


def connect():
    """Idempotent — safe to call from ``ready()`` however many times Django
    imports the app config (test runners, autoreload)."""
    register_override_provider(provide)
    post_save.connect(
        invalidate,
        sender="forum_host.ForumSettings",
        dispatch_uid="forum_host.forum_settings.post_save",
    )
    post_delete.connect(
        invalidate,
        sender="forum_host.ForumSettings",
        dispatch_uid="forum_host.forum_settings.post_delete",
    )
