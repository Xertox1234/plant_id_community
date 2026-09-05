"""
Blog application constants.

Following project pattern from apps/plant_identification/constants.py.
All configuration values extracted here to avoid magic numbers.
"""

# Cache timeout constants (in seconds)
BLOG_LIST_CACHE_TIMEOUT = 86400  # 24 hours - blog lists change infrequently
BLOG_POST_CACHE_TIMEOUT = 86400  # 24 hours - individual blog posts rarely change
BLOG_CATEGORY_CACHE_TIMEOUT = 86400  # 24 hours - category pages change infrequently
IMAGE_RENDITION_CACHE_TIMEOUT = 31536000  # 1 year - image renditions are immutable

# Cache key prefixes (for easy identification and pattern matching)
CACHE_PREFIX_BLOG_POST = "blog:post"
CACHE_PREFIX_BLOG_LIST = "blog:list"
CACHE_PREFIX_BLOG_CATEGORY = "blog:category"
CACHE_PREFIX_RENDITION = "wagtail:rendition"

# Query optimization constants
MAX_RELATED_PLANT_SPECIES = 10  # Maximum related plants to prefetch per post
MAX_TAGS_PREFETCH = 50  # Maximum tags to prefetch per query
MAX_CATEGORIES_PREFETCH = 20  # Maximum categories to prefetch per query
DEFAULT_PAGE_SIZE = 10  # Default pagination size
MAX_PAGE_SIZE = 100  # Maximum allowed pagination size

# Performance targets (from plan.md)
TARGET_CACHE_HIT_RATE = 0.35  # 35% minimum cache hit rate
TARGET_BLOG_LIST_QUERIES = 15  # Maximum database queries for blog list
TARGET_BLOG_DETAIL_QUERIES = 10  # Maximum database queries for blog detail
TARGET_CACHED_RESPONSE_MS = 50  # Target response time for cached requests (ms)
TARGET_COLD_LIST_RESPONSE_MS = 500  # Target response time for uncached list (ms)
TARGET_COLD_DETAIL_RESPONSE_MS = 300  # Target response time for uncached detail (ms)

# ============================================================================
# Phase 6.2: Analytics Integration Constants (BLOCKER 3 fix)
# ============================================================================

# View tracking constants
VIEW_DEDUPLICATION_TIMEOUT = (
    900  # 15 minutes (prevents view inflation from page refreshes)
)
VIEW_TRACKING_CACHE_PREFIX = "view:blog"  # Cache key prefix for deduplication

# Bot detection keywords (comprehensive list for user agent filtering)
VIEW_TRACKING_BOT_KEYWORDS = [
    "bot",
    "crawler",
    "spider",
    "scraper",
    "curl",
    "wget",
    "python-requests",
    "http-client",
    "httpie",
    "axios",
    "googlebot",
    "bingbot",
    "slurp",
    "duckduckbot",
    "baiduspider",
    "yandexbot",
    "facebookexternalhit",
    "twitterbot",
    "linkedinbot",
    "whatsapp",
    "telegram",
    "applebot",
    "semrushbot",
    "ahrefsbot",
    "dotbot",
]

# Popular posts API constants
POPULAR_POSTS_DEFAULT_LIMIT = 10  # Default number of popular posts to return
POPULAR_POSTS_MAX_LIMIT = 50  # Maximum allowed limit (prevent abuse)
POPULAR_POSTS_DEFAULT_DAYS = 30  # Default time period (last 30 days)
POPULAR_POSTS_CACHE_TIMEOUT = (
    1800  # 30 minutes (updates less frequently than regular content)
)
CACHE_PREFIX_POPULAR_POSTS = "blog:popular"  # Cache key prefix for popular posts

# Recent posts API constants
RECENT_POSTS_DEFAULT_LIMIT = (
    10  # Default number of recent posts returned when ?limit is not specified
)
RECENT_POSTS_MAX_LIMIT = 50  # Cap to prevent abuse / expensive slices

# Featured/related posts API constants
FEATURED_POSTS_LIMIT = 6  # Number of posts returned by the featured action
RELATED_POSTS_LIMIT = 6  # Number of posts returned by the related action

# Analytics dashboard constants
ANALYTICS_MIN_VIEWS_FOR_BADGE = 100  # Minimum views to show "popular" badge
ANALYTICS_MIN_VIEWS_FOR_VIRAL_BADGE = 1000  # Minimum views to show "viral" badge

# Max items in the public blog RSS/Atom feeds (todo 322).
BLOG_RSS_MAX_ITEMS = 50

# Comment endpoints (todo 352). Overridable per name via settings.BLOG_RATELIMITS,
# same shape as FORUM_RATELIMITS; keys are per authenticated user.
DEFAULT_BLOG_RATELIMITS = {
    "comment_create": "10/h",
    "comment_flag": "20/h",
}
# A comment auto-approves only when its author's FORUM trust level reaches
# this (wagtail_forum.models.TrustLevel value; MEMBER = 2). Below it — and
# always when the spam backend flags the text — the comment is held for the
# existing admin moderation queue. Override with BLOG_COMMENT_AUTO_APPROVE_TRUST_LEVEL.
DEFAULT_COMMENT_AUTO_APPROVE_TRUST_LEVEL = 2
# One user's repeat flags on the same comment count once (cache-deduped).
COMMENT_FLAG_DEDUP_SECONDS = 24 * 60 * 60
COMMENT_AUTO_FLAG_THRESHOLD = 5
