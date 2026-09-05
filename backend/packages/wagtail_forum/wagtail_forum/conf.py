import copy

from django.conf import settings

DEFAULTS = {
    "SPAM_BACKEND": "wagtail_forum.spam.heuristic.HeuristicSpamBackend",
    "TRUST_AUTOPUBLISH_LEVEL": 2,  # TrustLevel.MEMBER
    "SPAM_MAX_LINKS": 3,
    "SPAM_BANNED_WORDS": [],
    "TRUST_THRESHOLDS": {1: 1, 2: 5, 3: 50, 4: 200},  # trust_level -> min post_count
    # Inline-image upload (Spec 2 PR-3). 4-layer validation limits + the
    # forum-scoped Wagtail collection uploads land in; a post body may only
    # reference images in this collection (membership-checked on write — closes
    # the audit-L5 IDOR-by-reference).
    "IMAGE_ALLOWED_EXTENSIONS": ["jpg", "jpeg", "png", "gif", "webp"],
    "IMAGE_ALLOWED_MIME_TYPES": [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
    ],
    "IMAGE_MAX_SIZE_BYTES": 10 * 1024 * 1024,  # 10MB — DoS guard
    "IMAGE_MAX_PIXELS": 100_000_000,  # PIL decompression-bomb threshold
    "IMAGE_MAX_WIDTH": 5000,
    "IMAGE_MAX_HEIGHT": 5000,
    "IMAGE_COLLECTION_NAME": "Forum Images",
    # view_count deduplication window (seconds). A topic detail GET from the same
    # user (or anonymous IP) within this window counts as one view, not many.
    "VIEW_COUNT_DEDUP_SECONDS": 15 * 60,  # 15 minutes
    # Shared-cache TTL (seconds) for ANONYMOUS hot public reads — board list,
    # topic list, and search ONLY (audit 2026-07-11 M42). Only applied to
    # anonymous success responses (which sit at the constant anon baseline for
    # every per-user field), so a CDN like Cloudflare can offload read-heavy
    # public traffic. Authenticated responses are always `private, no-store`.
    # Topic detail and post list are deliberately NOT cached (they use
    # PrivateForumReadCacheMixin): topic detail increments view_count per hit,
    # and a moderated-away (unpublished/report-hidden) post must stop serving
    # immediately — there is no CDN purge wired. Accepted tradeoff for the
    # cached list/search endpoints: a just-removed topic can linger in the
    # anon-cached LIST (title + counts, never body) for up to this TTL; the
    # origin is correct on the next cache miss. Short by design.
    "PUBLIC_READ_CACHE_SECONDS": 60,
    # How long tombstone rows (TopicDeletedLog) are retained before pruning.
    # A mobile client that hasn't synced in longer than this window will miss
    # some deletions and should fall back to a full resync.
    "SYNC_TOMBSTONE_RETENTION_DAYS": 30,
    # Distinct open reports on a single post before it is auto-unpublished
    # pending moderator review (audit 2026-07-11 C1, todo 254).
    "REPORT_AUTO_HIDE_THRESHOLD": 3,
    # Max distinct @mentions resolved per post (todo 253 slice 4, H4) — bounds
    # both parse cost and notification fan-out on a mass-mention post.
    "MENTION_MAX_PER_POST": 10,
    # Fixed launch-day cutover for "unread" (todo 253 slice 5, H10) — the
    # last-resort fallback baseline when a user has no TopicRead row AND no
    # ForumProfile row at all (never opened a topic, never hit /me/profile/,
    # never received a push). Bounds the flood to "unread only for topics
    # active since launch" rather than the entire back-catalog. A real
    # ForumProfile row (created lazily on first qualifying action) always
    # takes priority once one exists — see the read_watermark_at field on
    # wagtail_forum/models/profiles.py's ForumProfile. ISO 8601, parsed once
    # per query via django.utils.dateparse.parse_datetime.
    "UNREAD_LAUNCH_AT": "2026-07-16T00:00:00Z",
    # Read-marker dedup window (seconds) for TopicDetailView.retrieve's
    # TopicRead.mark_read on_commit hook (todo 253 slice 5, H10). Deliberately
    # its OWN setting, not a reuse of VIEW_COUNT_DEDUP_SECONDS above — the two
    # gate unrelated concerns (view-count throttling vs. read-marking dedup)
    # that only happen to share a default; a host tuning one must not
    # silently retune the other.
    "TOPIC_READ_DEDUP_SECONDS": 15 * 60,  # 15 minutes
    # Topic tags (audit M5) — the species/genus/symptom discovery axis beside
    # the primary board taxonomy. Bounded on write so a single create can't
    # spray the shared Tag table: taggit creates a Tag row per unseen name, so
    # an unbounded list is a cheap write-amplification vector.
    "TOPIC_MAX_TAGS": 5,
    "TOPIC_TAG_MAX_LENGTH": 50,  # <= taggit's Tag.name max_length (100)
    # Identification attachment (audit M6) — the plant-ID snapshot a topic may
    # carry. Every field is caller-supplied (see models/identifications.py), so
    # these are the write bounds, not display preferences: they cap how much
    # unverified text one create request can park on a topic.
    "TOPIC_IDENTIFICATION_MAX_CANDIDATES": 3,
    # Matches PlantSpecies.scientific_name's max_length in the host app, which
    # is the longest name a real provider sends.
    "TOPIC_IDENTIFICATION_NAME_MAX_LENGTH": 200,
    # <= the provider column's max_length (models/identifications.py).
    "TOPIC_IDENTIFICATION_PROVIDER_MAX_LENGTH": 50,
    # topics/recent/ ("Active now" rail): default and cap for ?limit=. Capped
    # because each row may resolve a thumbnail rendition.
    "RECENT_TOPICS_DEFAULT_LIMIT": 5,
    "RECENT_TOPICS_MAX_LIMIT": 20,
    # users/experts/ ("Community experts" rail): row cap and minimum trust.
    "EXPERTS_LIMIT": 4,
    "EXPERTS_MIN_TRUST_LEVEL": 3,  # TrustLevel.REGULAR
    # Presence (todo 301) — two distinct tunables, deliberately not shared
    # (same reasoning as VIEW_COUNT_DEDUP_SECONDS vs TOPIC_READ_DEDUP_SECONDS
    # above: they gate unrelated concerns that only happen to default close
    # together). PRESENCE_TOUCH_THROTTLE_SECONDS bounds how often a
    # ForumProfile.last_seen UPDATE can fire per user (write-amplification
    # guard, api/presence.py). PRESENCE_ONLINE_WINDOW_SECONDS is the
    # freshness a `last_seen` must be within for ExpertsView to report
    # `online: true`. Read via `effective_online_window_seconds()`
    # (api/presence.py), NOT this raw value directly — it is clamped up to
    # at least the throttle interval there, so setting this narrower than
    # PRESENCE_TOUCH_THROTTLE_SECONDS degrades safely instead of making a
    # continuously-active user blink offline between touches.
    "PRESENCE_TOUCH_THROTTLE_SECONDS": 5 * 60,  # 5 minutes
    "PRESENCE_ONLINE_WINDOW_SECONDS": 15 * 60,  # 15 minutes
    # SearchView bounds (todo 290) — an anonymous many-term query recurses
    # Wagtail's search-query AND-tree construction (one nesting level per
    # term) into a RecursionError/500 before SEARCH_MAX_QUERY_CHARS alone
    # would ever bite; both caps apply, term count first. Truncate rather
    # than 400 — matches the semantic path's existing behaviour
    # (SIMILAR_QUERY_MAX_CHARS) and keeps a pasted-paragraph query usable.
    "SEARCH_MAX_TERMS": 50,
    "SEARCH_MAX_QUERY_CHARS": 500,
    # "Your season" badge (todo 300) — a single badge for now (AC only
    # requires one with visible progress); a multi-badge system is
    # speculative until a second one is actually needed. Threshold is on
    # `identifications_shared` (MeStatsView), an already-populated count —
    # deliberately NOT on raw PlantIdentificationResult, which todo 273
    # established has zero writers.
    "BADGE_BOTANIST_NAME": "Botanist",
    "BADGE_BOTANIST_THRESHOLD": 20,
    # Bounds ForumActivityDate.streak_for_user's ORDER BY ... LIMIT scan.
    # One row per active day, so this is already tiny for any real user
    # (~13 months of daily activity) — pure defense against a pathological
    # case, not a realistic limit.
    "STREAK_LOOKBACK_ROWS": 400,
    # Poll (audit M8) — write bounds on the poll a topic may carry. A poll is
    # created once, at compose time, and never edited, so these bound the whole
    # feature's write surface.
    "POLL_MAX_OPTIONS": 10,
    # A poll needs a real choice; one option is a statement, not a question.
    "POLL_MIN_OPTIONS": 2,
    # <= the matching column max_lengths in models/polls.py.
    "POLL_QUESTION_MAX_LENGTH": 300,
    "POLL_OPTION_MAX_LENGTH": 200,
    # Video/oEmbed blocks (todo 344). Off by default: a reusable package
    # cannot assume a host wants external provider lookups and third-party
    # iframes; the block exists in the schema regardless (blocks.py) but the
    # API refuses it and reads carry no player URL until this is True. The
    # provider allowlist is Wagtail's own WAGTAILEMBEDS_FINDERS.
    "ALLOW_EMBED_BLOCKS": False,
    # Hard bound on the ONE network call embeds make — at write time, while
    # the author waits (wagtail_forum/embeds.py::warm_embed). Wagtail's
    # oEmbed finder has no timeout of its own; a slow provider degrades the
    # post to a link card rather than hanging the create.
    "EMBED_FETCH_TIMEOUT_SECONDS": 5,
    # Distinct embed URLs one body may carry. They are fetched concurrently
    # inside ONE timeout window at write time, so this bounds worker-pool
    # pressure per write (and reader-side iframes per post), not wall time.
    "MAX_EMBED_URLS_PER_BODY": 5,
    # Structured post quotes (todo 342): distinct quoted posts per body, and
    # the quoted text's length — the API rejects, never truncates.
    "QUOTES_MAX_PER_POST": 3,
    "QUOTE_MAX_CHARS": 1000,
    # Digest email (todo 340) — an opt-in package feature; the host only
    # schedules `manage.py send_forum_digest` and may override the templates.
    "DIGEST_DEFAULT_FREQUENCY": "off",  # applied to NEW profiles only
    "DIGEST_WINDOW_DAYS": 7,  # activity window per weekly digest
    "DIGEST_MAX_WATCHED_TOPICS": 10,  # "new replies on topics you follow" rows
    "DIGEST_MAX_TRENDING_TOPICS": 10,  # "active topics you have not seen" rows
    "DIGEST_SETTINGS_PATH": "/settings",  # where the email's manage link points
    "EMAIL_SITE_URL": None,  # absolute origin for email links; None = settings.SITE_URL
}


# Sentinel an override provider returns for "no opinion on this name" — distinct
# from None, which is a legitimate value for some settings (and the DB-blank
# marker on the host side). Compare by identity.
MISSING = object()

# Host-registered override providers, consulted in registration order BEFORE
# the ``WAGTAILFORUM_<NAME>`` Django setting (Wagtail quick wins, item 1). This
# is how a host exposes tunables as admin-editable Wagtail settings without the
# package importing the host: the package owns the lookup order, the host owns
# the storage. A provider is ``provider(name) -> value | MISSING``; it must be
# cheap and must not raise (a DB-backed one handles its own outages and
# answers MISSING). Registration lives here rather than in Django settings so
# the hook is explicit and testable (``test_conf``), and so an unregistered
# host is byte-for-byte the pre-hook behaviour.
_override_providers = []


def register_override_provider(provider):
    """Consult ``provider(name)`` before the Django setting. Idempotent."""
    if provider not in _override_providers:
        _override_providers.append(provider)


def unregister_override_provider(provider):
    """Stop consulting ``provider``; unknown providers are ignored."""
    try:
        _override_providers.remove(provider)
    except ValueError:
        pass


def get_setting(name):
    """Resolve a tunable: host override provider, then the
    ``WAGTAILFORUM_<name>`` Django setting, then the package default.

    Unknown names raise ``KeyError`` before any provider is consulted, so a
    typo can never be masked by a provider that answers anything."""
    default = DEFAULTS[name]
    for provider in _override_providers:
        value = provider(name)
        if value is not MISSING:
            return copy.deepcopy(value)
    # deepcopy so a caller that mutates a returned list/dict (e.g. the empty
    # SPAM_BANNED_WORDS default) can't poison the shared DEFAULTS for later reads.
    value = getattr(settings, f"WAGTAILFORUM_{name}", default)
    return copy.deepcopy(value)
