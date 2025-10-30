"""
Centralized configuration for the forum app.

Follows pattern from apps/blog/constants.py and apps/plant_identification/constants.py
All configuration values are defined here to avoid magic numbers and ensure consistency.
"""

# Cache timeouts (in seconds)
CACHE_TIMEOUT_1_HOUR = 3600  # Thread details (frequent updates)
CACHE_TIMEOUT_6_HOURS = 21600  # Thread lists (less critical)
CACHE_TIMEOUT_24_HOURS = 86400  # Categories (rarely change)

# Cache key prefixes
CACHE_PREFIX_FORUM_THREAD = "forum:thread"
CACHE_PREFIX_FORUM_LIST = "forum:list"
CACHE_PREFIX_FORUM_CATEGORY = "forum:category"
CACHE_PREFIX_FORUM_POST = "forum:post"

# Pagination limits
DEFAULT_THREADS_PER_PAGE = 25
DEFAULT_POSTS_PER_PAGE = 20
MAX_THREADS_PER_PAGE = 100
MAX_POSTS_PER_PAGE = 50

# Content limits
MAX_THREAD_TITLE_LENGTH = 200
MAX_THREAD_EXCERPT_LENGTH = 500
MAX_POST_CONTENT_LENGTH = 50000  # ~50KB
MAX_ATTACHMENTS_PER_POST = 6
MAX_ATTACHMENT_SIZE_MB = 10
MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024  # 10MB in bytes

# Trust levels
TRUST_LEVEL_NEW = 'new'
TRUST_LEVEL_BASIC = 'basic'
TRUST_LEVEL_TRUSTED = 'trusted'
TRUST_LEVEL_VETERAN = 'veteran'
TRUST_LEVEL_EXPERT = 'expert'

TRUST_LEVELS = [
    (TRUST_LEVEL_NEW, 'New Member'),
    (TRUST_LEVEL_BASIC, 'Basic Member'),
    (TRUST_LEVEL_TRUSTED, 'Trusted Member'),
    (TRUST_LEVEL_VETERAN, 'Veteran'),
    (TRUST_LEVEL_EXPERT, 'Expert'),
]

# Trust level requirements (days active, posts created)
TRUST_LEVEL_REQUIREMENTS = {
    TRUST_LEVEL_NEW: {'days': 0, 'posts': 0},
    TRUST_LEVEL_BASIC: {'days': 7, 'posts': 5},
    TRUST_LEVEL_TRUSTED: {'days': 30, 'posts': 25},
    TRUST_LEVEL_VETERAN: {'days': 90, 'posts': 100},
    TRUST_LEVEL_EXPERT: {'verified_by_admin': True},
}

# Performance targets (for monitoring and testing)
TARGET_CACHE_HIT_RATE = 0.30  # 30% (lower than blog's 40% due to higher update frequency)
TARGET_THREAD_LIST_QUERIES = 12  # Max DB queries for list view
TARGET_THREAD_DETAIL_QUERIES = 8  # Max DB queries for detail view
TARGET_RESPONSE_TIME_CACHED_MS = 50  # Cached response target
TARGET_RESPONSE_TIME_LIST_MS = 500  # Uncached list view target
TARGET_RESPONSE_TIME_DETAIL_MS = 300  # Uncached detail view target

# Content formats
CONTENT_FORMAT_PLAIN = 'plain'
CONTENT_FORMAT_MARKDOWN = 'markdown'
CONTENT_FORMAT_RICH = 'rich'  # Draft.js JSON format

CONTENT_FORMATS = [
    (CONTENT_FORMAT_PLAIN, 'Plain Text'),
    (CONTENT_FORMAT_MARKDOWN, 'Markdown'),
    (CONTENT_FORMAT_RICH, 'Rich Content (Draft.js)'),
]

# Reaction types (from existing_implementation reference)
REACTION_LIKE = 'like'
REACTION_LOVE = 'love'
REACTION_HELPFUL = 'helpful'
REACTION_THANKS = 'thanks'

REACTION_TYPES = [
    (REACTION_LIKE, 'Like'),
    (REACTION_LOVE, 'Love'),
    (REACTION_HELPFUL, 'Helpful'),
    (REACTION_THANKS, 'Thanks'),
]

# Default values
DEFAULT_VIEW_COUNT = 0
DEFAULT_POST_COUNT = 0
DEFAULT_REACTION_COUNT = 0
DEFAULT_DISPLAY_ORDER = 0

# Query limits for prefetching (memory-safe)
MAX_PREFETCH_POSTS = 50  # Limit posts prefetched in thread detail
MAX_PREFETCH_REACTIONS = 100  # Limit reactions prefetched per post
MAX_RELATED_THREADS = 5  # Limit related threads shown
