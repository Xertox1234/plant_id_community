"""
Garden App Constants

Centralized configuration for the garden planner feature including:
- Cache timeouts and key formats
- File upload limits and allowed types
- Weather thresholds for smart reminders
- Reminder defaults
- Rate limits for API endpoints
"""

# ========================================
# Cache Configuration
# ========================================

# Cache timeouts (seconds)
CACHE_TIMEOUT_WEATHER = 3600  # 1 hour
CACHE_TIMEOUT_CARE_PLAN = 2592000  # 30 days
CACHE_TIMEOUT_PLANT_LIBRARY = 86400  # 24 hours

# Cache key formats (standardized pattern: app:feature:scope:identifier)
CACHE_KEY_WEATHER_CURRENT = "garden:weather:current:{lat}:{lng}"
CACHE_KEY_WEATHER_FORECAST = "garden:weather:forecast:{lat}:{lng}"
CACHE_KEY_CARE_PLAN = "garden:care_plan:{species}:{climate}"
CACHE_KEY_PLANT_LIBRARY = "garden:plant_library:{scientific_name}"


# ========================================
# File Upload Configuration
# ========================================

# File size limits (bytes)
MAX_GARDEN_PLANT_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_PEST_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_JOURNAL_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# Image count limits per entity
MAX_PEST_IMAGES_PER_ISSUE = 6
MAX_JOURNAL_IMAGES_PER_ENTRY = 10

# Allowed file extensions (validated before MIME type)
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']

# Allowed MIME types (defense in depth)
ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp'
]


# ========================================
# Weather Thresholds
# ========================================

# Temperature thresholds (Fahrenheit)
FROST_TEMP_F = 32  # Below this temperature = frost warning
HEATWAVE_TEMP_F = 95  # Above this temperature = heat warning

# Precipitation threshold
HEAVY_RAIN_INCHES = 0.5  # Daily rainfall above this = skip watering


# ========================================
# Reminder Defaults
# ========================================

# Default intervals for recurring reminders (days)
DEFAULT_WATERING_INTERVAL_DAYS = 3
DEFAULT_FERTILIZING_INTERVAL_DAYS = 14
DEFAULT_PRUNING_INTERVAL_DAYS = 30
DEFAULT_PEST_CHECK_INTERVAL_DAYS = 7
DEFAULT_REPOTTING_INTERVAL_DAYS = 365  # Once per year


# ========================================
# Rate Limits (django-ratelimit)
# ========================================

# Format: "count/period" where period is s, m, h, or d
RATE_LIMIT_GARDEN_CREATE = "10/day"  # Prevent spam garden creation
RATE_LIMIT_AI_CARE_PLAN = "5/hour"  # OpenAI API protection
RATE_LIMIT_WEATHER_API = "100/hour"  # OpenWeatherMap API protection
RATE_LIMIT_IMAGE_UPLOAD = "20/hour"  # Prevent image spam


# ========================================
# Garden Dimensions
# ========================================

# Maximum garden dimensions (to prevent performance issues)
MAX_GARDEN_WIDTH_FT = 500
MAX_GARDEN_HEIGHT_FT = 500
MAX_GARDEN_WIDTH_M = 150
MAX_GARDEN_HEIGHT_M = 150

# Canvas grid size (pixels per foot/meter)
DEFAULT_GRID_SIZE = 12


# ========================================
# Task Management
# ========================================

# Maximum active tasks per user
MAX_ACTIVE_TASKS_PER_USER = 100

# Task priority weights (for sorting)
PRIORITY_WEIGHTS = {
    'low': 1,
    'medium': 2,
    'high': 3
}


# ========================================
# Seasonal Templates
# ========================================

# Pre-populated seasonal task templates by climate zone
# This will be expanded in the services layer
SEASONAL_TASK_CATEGORIES = [
    'planting',
    'maintenance',
    'harvesting',
    'preparation',
    'other'
]


# ========================================
# Plant Care Library
# ========================================

# Water need frequency mappings (days)
WATER_NEED_FREQUENCY = {
    'low': 7,  # Once per week
    'medium': 3,  # Every 3 days
    'high': 1  # Daily
}

# Sunlight hours per day requirements
SUNLIGHT_HOURS = {
    'full_sun': 6,  # 6+ hours direct sunlight
    'partial_shade': 3,  # 3-6 hours
    'full_shade': 0  # Less than 3 hours
}


# ========================================
# Notification Settings
# ========================================

# Time before scheduled reminder to send notification (minutes)
REMINDER_NOTIFICATION_LEAD_TIME = 60  # 1 hour before

# Maximum reminders to send in single notification batch
MAX_REMINDERS_PER_NOTIFICATION = 5


# ========================================
# Companion Planting
# ========================================

# Minimum distance between enemy plants (feet)
MIN_DISTANCE_ENEMY_PLANTS_FT = 3
MIN_DISTANCE_ENEMY_PLANTS_M = 1


# ========================================
# Pagination
# ========================================

# API pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
