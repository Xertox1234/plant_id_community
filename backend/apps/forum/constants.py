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
ATTACHMENT_CLEANUP_DAYS = 30  # Days to keep soft-deleted attachments before permanent deletion
ATTACHMENT_CLEANUP_BATCH_SIZE = 100  # Attachments to delete per batch in cleanup job

# Allowed image formats for attachments
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

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

# Trust level daily action limits (posts/threads/reactions per day)
TRUST_LEVEL_LIMITS = {
    TRUST_LEVEL_NEW: {
        'posts_per_day': 10,
        'threads_per_day': 3,
        'reactions_per_day': 50,  # Lighter-weight action, higher limit
    },
    TRUST_LEVEL_BASIC: {
        'posts_per_day': 50,
        'threads_per_day': 10,
        'reactions_per_day': 200,
    },
    TRUST_LEVEL_TRUSTED: {
        'posts_per_day': 100,
        'threads_per_day': 25,
        'reactions_per_day': 500,
    },
    TRUST_LEVEL_VETERAN: {
        'posts_per_day': None,  # Unlimited
        'threads_per_day': None,  # Unlimited
        'reactions_per_day': None,  # Unlimited
    },
    TRUST_LEVEL_EXPERT: {
        'posts_per_day': None,  # Unlimited
        'threads_per_day': None,  # Unlimited
        'reactions_per_day': None,  # Unlimited
    },
}

# Trust level permissions (what actions each level can perform)
TRUST_LEVEL_PERMISSIONS = {
    TRUST_LEVEL_NEW: {
        'can_create_posts': True,
        'can_create_threads': True,
        'can_upload_images': False,
        'can_edit_posts': True,  # Own posts only
        'can_moderate': False,
    },
    TRUST_LEVEL_BASIC: {
        'can_create_posts': True,
        'can_create_threads': True,
        'can_upload_images': True,
        'can_edit_posts': True,
        'can_moderate': False,
    },
    TRUST_LEVEL_TRUSTED: {
        'can_create_posts': True,
        'can_create_threads': True,
        'can_upload_images': True,
        'can_edit_posts': True,
        'can_moderate': False,
    },
    TRUST_LEVEL_VETERAN: {
        'can_create_posts': True,
        'can_create_threads': True,
        'can_upload_images': True,
        'can_edit_posts': True,
        'can_moderate': False,
    },
    TRUST_LEVEL_EXPERT: {
        'can_create_posts': True,
        'can_create_threads': True,
        'can_upload_images': True,
        'can_edit_posts': True,
        'can_moderate': True,  # Only experts can moderate
    },
}

# Cache configuration for trust level service
TRUST_LEVEL_CACHE_TIMEOUT = 3600  # 1 hour (user limits change infrequently)
CACHE_PREFIX_TRUST_LIMITS = 'trust_limits:user:'
CACHE_PREFIX_DAILY_ACTIONS = 'daily_actions:user:'

# Standardized cache key format: "forum:feature:scope:identifier"
# This format ensures consistency across the forum app and makes cache key management easier
CACHE_KEY_SPAM_CHECK = 'forum:spam:{content_type}:{user_id}:{content_hash}'  # Spam detection cache
CACHE_KEY_MOD_DASHBOARD = 'forum:moderation:dashboard'  # Moderation dashboard overview
CACHE_TIMEOUT_SPAM_CHECK = 300  # 5 minutes (prevent spam retry attacks)
CACHE_TIMEOUT_MOD_DASHBOARD = 300  # 5 minutes (balance freshness vs load)

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

# Moderation system (Phase 4.2)
# Flag reasons for content moderation
FLAG_REASON_SPAM = 'spam'
FLAG_REASON_OFFENSIVE = 'offensive'
FLAG_REASON_OFF_TOPIC = 'off_topic'
FLAG_REASON_MISINFORMATION = 'misinformation'
FLAG_REASON_DUPLICATE = 'duplicate'
FLAG_REASON_LOW_QUALITY = 'low_quality'
FLAG_REASON_OTHER = 'other'

FLAG_REASONS = [
    (FLAG_REASON_SPAM, 'Spam or Advertising'),
    (FLAG_REASON_OFFENSIVE, 'Offensive or Inappropriate Content'),
    (FLAG_REASON_OFF_TOPIC, 'Off-Topic'),
    (FLAG_REASON_MISINFORMATION, 'Misinformation'),
    (FLAG_REASON_DUPLICATE, 'Duplicate Content'),
    (FLAG_REASON_LOW_QUALITY, 'Low Quality'),
    (FLAG_REASON_OTHER, 'Other'),
]

# Moderation states
MODERATION_STATUS_PENDING = 'pending'
MODERATION_STATUS_APPROVED = 'approved'
MODERATION_STATUS_REJECTED = 'rejected'
MODERATION_STATUS_REMOVED = 'removed'

MODERATION_STATUSES = [
    (MODERATION_STATUS_PENDING, 'Pending Review'),
    (MODERATION_STATUS_APPROVED, 'Approved (No Action Needed)'),
    (MODERATION_STATUS_REJECTED, 'Rejected (Flag Invalid)'),
    (MODERATION_STATUS_REMOVED, 'Content Removed'),
]

# Content types that can be flagged
FLAGGABLE_CONTENT_TYPE_POST = 'post'
FLAGGABLE_CONTENT_TYPE_THREAD = 'thread'

FLAGGABLE_CONTENT_TYPES = [
    (FLAGGABLE_CONTENT_TYPE_POST, 'Post'),
    (FLAGGABLE_CONTENT_TYPE_THREAD, 'Thread'),
]

# Moderation action types
MODERATION_ACTION_APPROVE = 'approve'
MODERATION_ACTION_REJECT = 'reject'
MODERATION_ACTION_REMOVE_POST = 'remove_post'
MODERATION_ACTION_REMOVE_THREAD = 'remove_thread'
MODERATION_ACTION_LOCK_THREAD = 'lock_thread'
MODERATION_ACTION_WARNING = 'warning'

MODERATION_ACTIONS = [
    (MODERATION_ACTION_APPROVE, 'Approve (No Violation)'),
    (MODERATION_ACTION_REJECT, 'Reject Flag'),
    (MODERATION_ACTION_REMOVE_POST, 'Remove Post'),
    (MODERATION_ACTION_REMOVE_THREAD, 'Remove Thread'),
    (MODERATION_ACTION_LOCK_THREAD, 'Lock Thread'),
    (MODERATION_ACTION_WARNING, 'Issue Warning to User'),
]

# Moderation limits
MAX_FLAGS_PER_USER_PER_DAY = 10  # Prevent flag spam
MAX_EXPLANATION_LENGTH = 1000  # Max length for flag/action explanation
MIN_FLAGS_FOR_AUTO_HIDE = 3  # Auto-hide content after N flags (trust level dependent)

# Spam detection configuration (Phase 4.4)
SPAM_URL_LIMIT_NEW = 2  # NEW users: max 2 URLs per post
SPAM_URL_LIMIT_BASIC = 5  # BASIC users: max 5 URLs per post
SPAM_URL_LIMIT_TRUSTED = 10  # TRUSTED+ users: max 10 URLs per post

SPAM_RAPID_POST_SECONDS = 10  # Minimum seconds between posts (NEW/BASIC users)
SPAM_DUPLICATE_SIMILARITY_THRESHOLD = 0.85  # 85% similarity = duplicate
SPAM_DUPLICATE_CACHE_TIMEOUT = 300  # 5 minutes cache for duplicate checks

# Spam keywords organized by category for better maintenance and future weighting
SPAM_KEYWORDS_COMMERCIAL = [
    'buy now', 'limited time', 'act now', 'special promotion',
    'guaranteed', 'no risk', 'click here', 'order now',
    'limited offer', 'exclusive deal', 'hurry',
]

SPAM_KEYWORDS_FINANCIAL = [
    'free money', 'gift card', 'bitcoin', 'wire transfer',
    'claim your prize', 'winner', 'congratulations', 'cash prize',
    'lottery', 'inheritance', 'make money fast',
]

SPAM_KEYWORDS_PHISHING = [
    'verify your account', 'suspended account', 'confirm your password',
    'update payment', 'urgent', 'immediate action required',
    'account locked', 'security alert', 'unusual activity',
]

# Combined list for backward compatibility
SPAM_KEYWORDS = (
    SPAM_KEYWORDS_COMMERCIAL +
    SPAM_KEYWORDS_FINANCIAL +
    SPAM_KEYWORDS_PHISHING
)

# Future enhancement: Weighted scoring by category
# Phishing keywords have higher security risk and could warrant higher scores
SPAM_KEYWORD_WEIGHTS = {
    **{kw: 10 for kw in SPAM_KEYWORDS_COMMERCIAL},   # Lower weight (sales spam)
    **{kw: 20 for kw in SPAM_KEYWORDS_FINANCIAL},    # Medium weight (financial spam)
    **{kw: 30 for kw in SPAM_KEYWORDS_PHISHING},     # Higher weight (security risk)
}

# Spam pattern thresholds
SPAM_CAPS_RATIO_THRESHOLD = 0.7  # >70% caps = likely spam
SPAM_PUNCTUATION_RATIO_THRESHOLD = 0.3  # >30% punctuation = spam
SPAM_REPETITION_PATTERN = r'(.)\1{4,}'  # 5+ repeated characters (e.g., "!!!!!")

# Spam scoring (total >= 50 = SPAM)
# Individual strong signals (50-60 points) trigger blocking alone:
#   - Duplicate content: 60 points → BLOCKED (exact or 85%+ similar)
#   - Rapid posting: 55 points → BLOCKED (NEW/BASIC users <10s between posts)
#   - Link spam: 50 points → BLOCKED (NEW: >2 URLs, BASIC: >5 URLs, TRUSTED: >10 URLs)
#   - Keyword spam: 50 points → BLOCKED (2+ spam keywords detected)
#
# Moderate signals (45 points) require combination:
#   - Pattern spam (45) + Keyword spam (50) = 95 → BLOCKED
#   - Pattern spam (45) + Link spam (50) = 95 → BLOCKED
#
# Examples:
#   1. Obvious spam: "BUY NOW!!! http://spam1.com http://spam2.com http://spam3.com"
#      → Link spam (50) + Keyword spam (50) + Pattern spam (45) = 145 → BLOCKED
#
#   2. Link spam only: "Check out http://link1.com http://link2.com http://link3.com" (NEW user)
#      → Link spam (50) = 50 → BLOCKED
#
#   3. Borderline content: "Check this out: http://example.com" (1 URL, no keywords)
#      → Score: 0 → ALLOWED
#
#   4. ALL CAPS with keywords: "BUY NOW LIMITED TIME OFFER"
#      → Pattern spam (45) + Keyword spam (50) = 95 → BLOCKED
#
SPAM_SCORE_DUPLICATE = 60  # Duplicate content (strong signal - block immediately)
SPAM_SCORE_RAPID_POST = 55  # Rapid posting (strong bot signal - block immediately)
SPAM_SCORE_LINK_SPAM = 50  # Excessive URLs (strong spam signal - block immediately)
SPAM_SCORE_KEYWORD_SPAM = 50  # Multiple spam keywords (strong signal - block immediately)
SPAM_SCORE_PATTERN_SPAM = 45  # Spam patterns (moderate signal - needs combination)
SPAM_SCORE_THRESHOLD = 50  # Threshold for auto-flagging
