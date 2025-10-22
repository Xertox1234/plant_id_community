"""
Constants for Plant Identification Services

Centralized configuration values to improve maintainability and make
tuning easier without hunting through service code.
"""

# ============================================================================
# ThreadPoolExecutor Configuration
# ============================================================================

# Maximum number of worker threads for parallel API calls
# Capped to prevent API rate limit issues
MAX_WORKER_THREADS = 10

# Default multiplier for calculating workers based on CPU cores
# For I/O-bound tasks (API calls), use 2x CPU cores
CPU_CORE_MULTIPLIER = 2


# ============================================================================
# API Timeout Configuration (seconds)
# ============================================================================

# Plant.id API timeout (including 5s buffer)
PLANT_ID_API_TIMEOUT = 35
PLANT_ID_API_TIMEOUT_DEFAULT = 30

# PlantNet API timeout (including 5s buffer)
PLANTNET_API_TIMEOUT = 20
PLANTNET_API_REQUEST_TIMEOUT = 60

# Plant Health API timeout
PLANT_HEALTH_API_TIMEOUT = 60
PLANT_HEALTH_HEALTH_CHECK_TIMEOUT = 10

# Trefle API timeout
TREFLE_API_TIMEOUT = 10

# Image service timeouts
IMAGE_DOWNLOAD_TIMEOUT = 30
IMAGE_DOWNLOAD_QUICK_TIMEOUT = 10


# ============================================================================
# Cache Configuration (seconds)
# ============================================================================

# Standard 24-hour cache for API results
CACHE_TIMEOUT_24_HOURS = 86400

# Alternative cache timeouts
CACHE_TIMEOUT_30_MINUTES = 1800
CACHE_TIMEOUT_1_HOUR = 3600
CACHE_TIMEOUT_7_DAYS = 604800

# Specific service cache timeouts
PLANT_ID_CACHE_TIMEOUT = CACHE_TIMEOUT_30_MINUTES
PLANTNET_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS
TREFLE_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS
UNSPLASH_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS
PEXELS_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS
AI_IMAGE_CACHE_TIMEOUT = CACHE_TIMEOUT_7_DAYS
AI_COST_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS

# Rate limit cache durations
RATE_LIMIT_CACHE_DURATION = 300  # 5 minutes
RATE_LIMIT_RETRY_AFTER_MIN = 60  # 1 minute minimum


# ============================================================================
# Confidence Score Thresholds
# ============================================================================

# Species lookup confidence scores
CONFIDENCE_LOCAL_VERIFIED = 0.8  # Expert-verified local species
CONFIDENCE_CACHED_API = 0.6      # Cached API results
CONFIDENCE_LOCAL_FALLBACK = 0.4  # Local fallback when API unavailable

# Plant health confidence thresholds
HEALTH_CONFIDENCE_HIGH = 0.8     # High confidence diagnosis
HEALTH_CONFIDENCE_MEDIUM = 0.6   # Medium confidence diagnosis

# Monitoring thresholds
MONITORING_WARNING_THRESHOLD = 0.8   # 80% of limit
MONITORING_CRITICAL_THRESHOLD = 0.95  # 95% of limit


# ============================================================================
# Performance Thresholds
# ============================================================================

# Cache performance thresholds (percentages)
CACHE_HIT_RATIO_MIN = 30         # Minimum acceptable cache hit rate (%)
LOCAL_DB_RATIO_MIN = 30          # Minimum local database usage (%)
API_DEPENDENCY_RATIO_MAX = 60    # Maximum API dependency (%)


# ============================================================================
# API Limits and Defaults
# ============================================================================

# Default result limits
DEFAULT_SEARCH_LIMIT = 10
DEFAULT_SPECIES_LIMIT = 20
DEFAULT_IMAGE_LIMIT_UNSPLASH = 10
DEFAULT_IMAGE_LIMIT_PEXELS = 15

# API-imposed limits
UNSPLASH_MAX_RESULTS = 30        # Unsplash API limit
PLANT_HEALTH_MAX_IMAGES = 10     # Plant Health API limit


# ============================================================================
# Temperature and Climate Constants
# ============================================================================

# Default temperature ranges (for care instructions)
TEMPERATURE_RANGE_CELSIUS = "18-24°C"
TEMPERATURE_RANGE_FAHRENHEIT = "65-75°F"
HUMIDITY_IDEAL_RANGE = "40-60%"


# ============================================================================
# Geographic Regions (for PlantNet project selection)
# ============================================================================

# Europe boundaries
EUROPE_LAT_MIN, EUROPE_LAT_MAX = 35, 70
EUROPE_LON_MIN, EUROPE_LON_MAX = -25, 45

# South America boundaries
SOUTH_AMERICA_LAT_MIN, SOUTH_AMERICA_LAT_MAX = -55, 15
SOUTH_AMERICA_LON_MIN, SOUTH_AMERICA_LON_MAX = -85, -35

# Africa boundaries
AFRICA_LAT_MIN, AFRICA_LAT_MAX = -35, 40
AFRICA_LON_MIN, AFRICA_LON_MAX = -20, 55

# Asia boundaries
ASIA_LAT_MIN, ASIA_LAT_MAX = -10, 70
ASIA_LON_MIN, ASIA_LON_MAX = 60, 180

# Oceania boundaries
OCEANIA_LAT_MIN, OCEANIA_LAT_MAX = -50, -10
OCEANIA_LON_MIN, OCEANIA_LON_MAX = 110, 180


# ============================================================================
# Time Intervals (days)
# ============================================================================

# Care reminder intervals
CARE_REMINDER_INTERVAL_DAYS = 30


# ============================================================================
# Cache Performance Metrics
# ============================================================================

# Expected cache hit rate after optimization (for documentation)
EXPECTED_CACHE_HIT_RATE = 0.40  # 40% of requests should hit cache

# Performance improvement expectations
PARALLEL_SPEEDUP_FACTOR = 0.60  # 60% faster with parallel execution
