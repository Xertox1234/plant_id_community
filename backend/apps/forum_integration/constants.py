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
}

# --- Pagination ---
FORUM_MAX_PAGE_SIZE = 100
FORUM_DEFAULT_PAGE_SIZE = 25

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
