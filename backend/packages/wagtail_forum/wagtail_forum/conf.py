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
    # SearchView bounds (todo 290) — an anonymous many-term query recurses
    # Wagtail's search-query AND-tree construction (one nesting level per
    # term) into a RecursionError/500 before SEARCH_MAX_QUERY_CHARS alone
    # would ever bite; both caps apply, term count first. Truncate rather
    # than 400 — matches the semantic path's existing behaviour
    # (SIMILAR_QUERY_MAX_CHARS) and keeps a pasted-paragraph query usable.
    "SEARCH_MAX_TERMS": 50,
    "SEARCH_MAX_QUERY_CHARS": 500,
}


def get_setting(name):
    # deepcopy so a caller that mutates a returned list/dict (e.g. the empty
    # SPAM_BANNED_WORDS default) can't poison the shared DEFAULTS for later reads.
    value = getattr(settings, f"WAGTAILFORUM_{name}", DEFAULTS[name])
    return copy.deepcopy(value)
