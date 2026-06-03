"""Forum configuration constants (no magic numbers elsewhere)."""

# --- Rate limits (django-ratelimit `rate` strings) ---
# Keyed by authenticated user where possible; IP for anonymous-readable endpoints.
FORUM_RATE_LIMITS = {
    "create_topic": "10/h",
    "create_post": "30/h",
    "update_post": "30/h",
    "delete_post": "30/h",
    "react": "60/m",
    "upload_image": "20/h",
    "search": "30/m",
    "ai_assist": "20/d",  # per-user daily cap — direct cost vector
    # Added with todos 106-109 — mutating endpoints that were previously
    # unthrottled.
    "mark_viewed": "60/m",  # 106 — anonymous view-count inflation (key=ip)
    "update_topic": "30/m",  # 107 — topic pin/lock/solve PATCH
    "image_delete": "30/m",  # 108 — image delete
    "image_update": "60/m",  # 109 — image reorder (one PATCH per image)
}

# --- Pagination ---
FORUM_MAX_PAGE_SIZE = 100
FORUM_DEFAULT_PAGE_SIZE = 25
FORUM_TOPIC_POSTS_PER_PAGE = 10

# --- Topic list ordering ---
# Allowlist mapping the client-facing `ordering` query param (frontend naming,
# see web ThreadListPage sort dropdown) to a safe Topic ORM field. Anything not
# present here falls back to FORUM_TOPIC_DEFAULT_ORDERING. NEVER pass a raw query
# param to .order_by() — that is a sort-key injection / DoS vector.
FORUM_TOPIC_DEFAULT_ORDERING = "-last_post_on"
FORUM_TOPIC_ORDERING_MAP = {
    "-last_activity_at": "-last_post_on",  # "Recent Activity" (default)
    "-created_at": "-created",  # "Newest First"
    "created_at": "created",  # "Oldest First"
    "-view_count": "-views_count",  # "Most Viewed"
    "-post_count": "-posts_count",  # "Most Replies"
}

# --- Image upload validation ---
FORUM_IMAGE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
FORUM_IMAGE_ALLOWED_CONTENT_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
]
FORUM_IMAGE_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
# PIL format names corresponding to the allowed types
FORUM_IMAGE_ALLOWED_PIL_FORMATS = ["JPEG", "PNG", "GIF", "WEBP"]
FORUM_IMAGE_MAX_PER_POST = 6

# --- Caching ---
# forum_stats runs 3 COUNT queries on every anonymous request. The numbers
# tolerate brief staleness, so cache them under a short TTL.
FORUM_STATS_CACHE_KEY = "forum:stats"
FORUM_STATS_CACHE_TTL = 60  # seconds
