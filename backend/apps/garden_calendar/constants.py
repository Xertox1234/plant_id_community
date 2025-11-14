"""
Garden Calendar Constants

Centralized configuration for the garden_calendar app.
Follows pattern from apps/forum/constants.py and apps/plant_identification/constants.py.
All configuration values are defined here to avoid magic numbers.
"""

# =============================================================================
# Cache Configuration
# =============================================================================

# Cache timeouts (in seconds)
CACHE_TIMEOUT_GARDEN_BED_LIST = 1800  # 30 minutes
CACHE_TIMEOUT_GARDEN_BED_DETAIL = 3600  # 1 hour
CACHE_TIMEOUT_PLANT_LIST = 1800  # 30 minutes
CACHE_TIMEOUT_PLANT_DETAIL = 3600  # 1 hour
CACHE_TIMEOUT_CARE_TASK_LIST = 900  # 15 minutes (tasks change frequently)
CACHE_TIMEOUT_ANALYTICS = 3600  # 1 hour
CACHE_TIMEOUT_WEATHER = 1800  # 30 minutes
CACHE_TIMEOUT_GROWING_ZONE = 86400  # 24 hours (rarely changes)
CACHE_TIMEOUT_SEASONAL_TEMPLATE = 86400  # 24 hours
CACHE_TIMEOUT_COMMUNITY_EVENT = 3600  # 1 hour

# Cache key formats (standardized: "app:feature:scope:identifier")
CACHE_KEY_GARDEN_BED_LIST = "garden:beds:user:{user_id}"
CACHE_KEY_GARDEN_BED_DETAIL = "garden:bed:{bed_uuid}"
CACHE_KEY_PLANT_LIST = "garden:plants:bed:{bed_uuid}"
CACHE_KEY_PLANT_DETAIL = "garden:plant:{plant_uuid}"
CACHE_KEY_CARE_TASKS_UPCOMING = "garden:tasks:upcoming:user:{user_id}"
CACHE_KEY_ANALYTICS = "garden:analytics:user:{user_id}"
CACHE_KEY_GARDEN_ANALYTICS = "garden:analytics:{metric}:user:{user_id}"
CACHE_KEY_WEATHER_CURRENT = "garden:weather:current:{lat}:{lng}"
CACHE_KEY_WEATHER_FORECAST = "garden:weather:forecast:{lat}:{lng}"
CACHE_KEY_COMPANION_PLANTS = "garden:companion:{species_id}"

# =============================================================================
# Rate Limiting Configuration (django-ratelimit)
# =============================================================================

# Garden Bed Operations
RATE_LIMIT_GARDEN_BED_CREATE = "10/day"  # Max 10 new beds per day
RATE_LIMIT_GARDEN_BED_UPDATE = "50/hour"  # 50 updates per hour
RATE_LIMIT_GARDEN_BED_DELETE = "5/hour"  # Prevent accidental bulk deletion

# Plant Operations
RATE_LIMIT_PLANT_CREATE = "100/day"  # Max 100 new plants per day
RATE_LIMIT_PLANT_UPDATE = "200/hour"  # Frequent updates expected
RATE_LIMIT_PLANT_DELETE = "50/hour"

# Care Task Operations
RATE_LIMIT_CARE_TASK_CREATE = "100/day"
RATE_LIMIT_CARE_TASK_COMPLETE = "500/hour"  # High limit for task completion
RATE_LIMIT_CARE_TASK_SKIP = "500/hour"

# AI and External API Operations
RATE_LIMIT_AI_CARE_PLAN = "5/hour"  # Expensive AI generation
RATE_LIMIT_WEATHER_API = "100/hour"  # OpenWeatherMap free tier
RATE_LIMIT_COMPANION_SUGGESTIONS = "50/hour"

# Community Event Operations
RATE_LIMIT_EVENT_CREATE = "10/day"
RATE_LIMIT_EVENT_RSVP = "100/hour"

# =============================================================================
# Model Limits
# =============================================================================

# Garden Bed Limits
MAX_GARDEN_BEDS_PER_USER = 50  # Reasonable limit for personal use
MAX_BED_NAME_LENGTH = 200
MAX_BED_DESCRIPTION_LENGTH = 2000
MAX_BED_NOTES_LENGTH = 5000

# Plant Limits
MAX_PLANTS_PER_GARDEN_BED = 500  # Large beds can have many plants
MAX_PLANT_NAME_LENGTH = 200
MAX_PLANT_NOTES_LENGTH = 5000
MAX_PLANT_VARIETY_LENGTH = 200

# Care Task Limits
MAX_CARE_TASKS_PER_PLANT = 100  # Prevent task spam
MAX_CARE_TASKS_PENDING_PER_USER = 1000  # Total pending tasks
MAX_TASK_TITLE_LENGTH = 200
MAX_TASK_NOTES_LENGTH = 2000

# Journal/Log Limits
MAX_CARE_LOG_ENTRIES_PER_PLANT = 500
MAX_HARVESTS_PER_PLANT = 200
MAX_LOG_CONTENT_LENGTH = 5000

# =============================================================================
# File Upload Configuration
# =============================================================================

# Allowed image formats (4-layer security validation)
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp'
]

# File size limits
MAX_PLANT_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_GARDEN_BED_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_CARE_LOG_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

# Image count limits
MAX_IMAGES_PER_PLANT = 10
MAX_IMAGES_PER_GARDEN_BED = 20
MAX_IMAGES_PER_CARE_LOG = 5

# Image dimension limits (decompression bomb protection)
MAX_IMAGE_PIXELS = 100_000_000  # 100 megapixels (PIL decompression bomb threshold)
MAX_IMAGE_WIDTH = 5000  # Max width in pixels
MAX_IMAGE_HEIGHT = 5000  # Max height in pixels

# =============================================================================
# Health Status Configuration
# =============================================================================

HEALTH_STATUS_CHOICES = [
    ('thriving', 'Thriving'),
    ('healthy', 'Healthy'),
    ('fair', 'Fair/OK'),
    ('struggling', 'Struggling'),
    ('diseased', 'Diseased'),
    ('pest_damage', 'Pest Damage'),
    ('dying', 'Dying'),
    ('dead', 'Dead/Removed'),
]

HEALTH_STATUS_DEFAULT = 'healthy'

# Health status colors for UI (hex codes)
HEALTH_STATUS_COLORS = {
    'thriving': '#10B981',      # Green
    'healthy': '#34D399',       # Light Green
    'fair': '#FBBF24',          # Yellow
    'struggling': '#F59E0B',    # Amber
    'diseased': '#EF4444',      # Red
    'pest_damage': '#DC2626',   # Dark Red
    'dying': '#991B1B',         # Very Dark Red
    'dead': '#6B7280',          # Gray
}

# =============================================================================
# Care Task Configuration
# =============================================================================

CARE_TASK_TYPES = [
    ('watering', 'Watering'),
    ('fertilizing', 'Fertilizing'),
    ('pruning', 'Pruning'),
    ('deadheading', 'Deadheading'),
    ('repotting', 'Repotting/Transplanting'),
    ('pest_check', 'Pest Inspection'),
    ('disease_check', 'Disease Check'),
    ('soil_amendment', 'Soil Amendment'),
    ('mulching', 'Mulching'),
    ('staking', 'Staking/Support'),
    ('harvesting', 'Harvesting'),
    ('winterization', 'Winter Preparation'),
    ('spring_cleanup', 'Spring Cleanup'),
    ('custom', 'Custom Task'),
]

CARE_TASK_PRIORITY = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('urgent', 'Urgent'),
]

# Default care intervals (in days)
DEFAULT_WATERING_INTERVAL_DAYS = 3
DEFAULT_FERTILIZING_INTERVAL_DAYS = 14
DEFAULT_PRUNING_INTERVAL_DAYS = 30
DEFAULT_PEST_CHECK_INTERVAL_DAYS = 7
DEFAULT_DISEASE_CHECK_INTERVAL_DAYS = 7

# =============================================================================
# Growing Zone Configuration
# =============================================================================

# USDA Hardiness Zones (common ranges)
USDA_HARDINESS_ZONES = [
    '1a', '1b', '2a', '2b', '3a', '3b', '4a', '4b',
    '5a', '5b', '6a', '6b', '7a', '7b', '8a', '8b',
    '9a', '9b', '10a', '10b', '11a', '11b', '12a', '12b', '13a', '13b'
]

# Temperature ranges for zones (Fahrenheit)
ZONE_TEMP_RANGES = {
    '1a': (-60, -55), '1b': (-55, -50),
    '2a': (-50, -45), '2b': (-45, -40),
    '3a': (-40, -35), '3b': (-35, -30),
    '4a': (-30, -25), '4b': (-25, -20),
    '5a': (-20, -15), '5b': (-15, -10),
    '6a': (-10, -5), '6b': (-5, 0),
    '7a': (0, 5), '7b': (5, 10),
    '8a': (10, 15), '8b': (15, 20),
    '9a': (20, 25), '9b': (25, 30),
    '10a': (30, 35), '10b': (35, 40),
    '11a': (40, 45), '11b': (45, 50),
    '12a': (50, 55), '12b': (55, 60),
    '13a': (60, 65), '13b': (65, 70),
}

# =============================================================================
# Weather Configuration
# =============================================================================

# OpenWeatherMap API Configuration
WEATHER_API_TIMEOUT = 10  # seconds
WEATHER_API_MAX_RETRIES = 2

# Weather thresholds
FROST_TEMP_F = 32
FREEZE_TEMP_F = 28
HEATWAVE_TEMP_F = 95
HIGH_WIND_MPH = 25
HEAVY_RAIN_INCHES = 0.5

# Weather-based care task adjustments
SKIP_WATERING_IF_RAIN_INCHES = 0.25  # Skip if >= 0.25" rain expected
SKIP_FERTILIZING_IF_RAIN_INCHES = 0.5  # Skip if heavy rain expected

# =============================================================================
# Companion Planting Configuration
# =============================================================================

# Companion planting relationship types
COMPANION_RELATIONSHIP = [
    ('excellent', 'Excellent Companions'),
    ('good', 'Good Companions'),
    ('neutral', 'Neutral'),
    ('avoid', 'Avoid Planting Together'),
    ('harmful', 'Harmful/Allelopathic'),
]

# =============================================================================
# Analytics Configuration
# =============================================================================

# Analytics time windows
ANALYTICS_WINDOW_DAYS = 90  # 3 months of data for trends
ANALYTICS_MIN_DATA_POINTS = 5  # Minimum entries for meaningful analytics

# Garden bed utilization thresholds
BED_UTILIZATION_LOW = 0.25  # <25% planted
BED_UTILIZATION_MEDIUM = 0.60  # 25-60% planted
BED_UTILIZATION_HIGH = 0.85  # 60-85% planted
BED_UTILIZATION_FULL = 1.0  # >85% planted

# =============================================================================
# Seasonal Configuration
# =============================================================================

SEASONS = [
    ('spring', 'Spring'),
    ('summer', 'Summer'),
    ('fall', 'Fall/Autumn'),
    ('winter', 'Winter'),
]

# Season month mappings (Northern Hemisphere)
SEASON_MONTHS = {
    'spring': [3, 4, 5],  # March, April, May
    'summer': [6, 7, 8],  # June, July, August
    'fall': [9, 10, 11],  # September, October, November
    'winter': [12, 1, 2],  # December, January, February
}

# =============================================================================
# Pagination Configuration
# =============================================================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# =============================================================================
# Logging Prefixes (for filtering)
# =============================================================================

LOG_PREFIX_GARDEN = "[GARDEN]"
LOG_PREFIX_PLANT = "[PLANT]"
LOG_PREFIX_CARE_TASK = "[CARE_TASK]"
LOG_PREFIX_WEATHER = "[WEATHER]"
LOG_PREFIX_ANALYTICS = "[ANALYTICS]"
LOG_PREFIX_CACHE = "[CACHE]"
LOG_PREFIX_PERF = "[PERF]"
LOG_PREFIX_ERROR = "[ERROR]"
