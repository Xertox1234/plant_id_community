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
}


def get_setting(name):
    # deepcopy so a caller that mutates a returned list/dict (e.g. the empty
    # SPAM_BANNED_WORDS default) can't poison the shared DEFAULTS for later reads.
    value = getattr(settings, f"WAGTAILFORUM_{name}", DEFAULTS[name])
    return copy.deepcopy(value)
