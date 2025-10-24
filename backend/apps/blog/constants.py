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
