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
    # How long tombstone rows (TopicDeletedLog) are retained before pruning.
    # A mobile client that hasn't synced in longer than this window will miss
    # some deletions and should fall back to a full resync.
    "SYNC_TOMBSTONE_RETENTION_DAYS": 30,
    # Distinct open reports on a single post before it is auto-unpublished
    # pending moderator review (audit 2026-07-11 C1, todo 254).
    "REPORT_AUTO_HIDE_THRESHOLD": 3,
}


def get_setting(name):
    # deepcopy so a caller that mutates a returned list/dict (e.g. the empty
    # SPAM_BANNED_WORDS default) can't poison the shared DEFAULTS for later reads.
    value = getattr(settings, f"WAGTAILFORUM_{name}", DEFAULTS[name])
    return copy.deepcopy(value)
