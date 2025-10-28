"""
Constants for Plant Identification Services

Centralized configuration values to improve maintainability and make
tuning easier without hunting through service code.

NOTE: This file has been cleaned up to remove unused constants (80% were unused).
Only actively used constants from the three service files are retained.
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

# Plant.id API timeouts
PLANT_ID_API_TIMEOUT = 35              # With 5s buffer
PLANT_ID_API_TIMEOUT_DEFAULT = 30      # Default timeout

# PlantNet API timeouts
PLANTNET_API_TIMEOUT = 20              # With 5s buffer
PLANTNET_API_REQUEST_TIMEOUT = 60      # Request timeout

# Image service timeouts
IMAGE_DOWNLOAD_TIMEOUT = 30            # Standard download
IMAGE_DOWNLOAD_QUICK_TIMEOUT = 10      # Quick download


# ============================================================================
# Cache Configuration (seconds)
# ============================================================================

# Base cache timeouts
CACHE_TIMEOUT_24_HOURS = 86400         # 24 hours
CACHE_TIMEOUT_30_MINUTES = 1800        # 30 minutes

# Service-specific cache timeouts
PLANT_ID_CACHE_TIMEOUT = CACHE_TIMEOUT_30_MINUTES
PLANTNET_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS


# ============================================================================
# Temperature Constants
# ============================================================================

# Default temperature range for care instructions
TEMPERATURE_RANGE_CELSIUS = "18-24°C"


# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

# Plant.id API Circuit Breaker (Paid Tier - Conservative)
PLANT_ID_CIRCUIT_FAIL_MAX = 3            # Open circuit after 3 consecutive failures
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60      # Wait 60s before testing recovery
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2   # Require 2 successes to close circuit
PLANT_ID_CIRCUIT_TIMEOUT = PLANT_ID_API_TIMEOUT

# PlantNet API Circuit Breaker (Free Tier - More Tolerant)
PLANTNET_CIRCUIT_FAIL_MAX = 5            # Open circuit after 5 consecutive failures
PLANTNET_CIRCUIT_RESET_TIMEOUT = 30      # Wait 30s before testing recovery
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2   # Require 2 successes to close circuit
PLANTNET_CIRCUIT_TIMEOUT = PLANTNET_API_TIMEOUT


# ============================================================================
# Distributed Lock Configuration (Cache Stampede Prevention)
# ============================================================================

# Lock Acquisition Timeout
CACHE_LOCK_TIMEOUT = 15  # Wait max 15s for another process to finish

# Lock Expiry (Auto-Release)
CACHE_LOCK_EXPIRE = 30  # Auto-release after 30s (prevents deadlock on crash)

# Lock Auto-Renewal
CACHE_LOCK_AUTO_RENEWAL = True  # Recommended for API calls with unpredictable duration

# Lock Blocking Mode
CACHE_LOCK_BLOCKING = True  # Wait for lock (better UX than immediate failure)

# Lock ID Prefix
CACHE_LOCK_ID_PREFIX = 'plant_id'  # Will be: "plant_id-{hostname}-{pid}-{thread_id}"


# ============================================================================
# Rate Limiting Configuration
# ============================================================================
# Centralized rate limit policy for consistent enforcement across endpoints.
# See: docs/api/RATE_LIMITING_POLICY.md for detailed documentation.
#
# Format: '{count}/{period}' where period is: s (second), m (minute), h (hour), d (day)
# Key types:
#   - 'ip': Based on client IP address (for anonymous/auth endpoints)
#   - 'user': Based on authenticated user ID
#   - 'user_or_ip': User ID if authenticated, IP otherwise
#
# Rate Limit Tiers:
#   - Anonymous: Strict limits for abuse prevention
#   - Authenticated: Higher limits for legitimate users
#   - Write Operations: Lower limits to prevent spam
#   - Read Operations: Higher limits for better UX

RATE_LIMITS = {
    # Anonymous User Limits (IP-based)
    'anonymous': {
        'plant_identification': '10/h',     # Plant ID API calls (expensive)
        'read_only': '100/h',               # General read operations
        'search': '30/h',                   # Search endpoints
    },

    # Authenticated User Limits (user-based)
    'authenticated': {
        'plant_identification': '100/h',    # Plant ID API calls
        'write_operations': '50/h',         # Create/update operations
        'read_only': '1000/h',              # General read operations
        'search': '100/h',                  # Search endpoints
        'care_instructions': '30/m',        # Care instruction lookups
        'regenerate': '5/m',                # AI regeneration (expensive)
    },

    # Authentication Endpoints (IP-based, security-focused)
    'auth_endpoints': {
        'login': '5/15m',                   # Login attempts
        'register': '3/h',                  # Registration
        'token_refresh': '10/h',            # Token refresh
        'password_reset': '3/h',            # Password reset (not implemented)
    },

    # User Feature Endpoints (user-based)
    'user_features': {
        'push_notifications': '10/h',       # Push notification subscriptions
        'care_reminders': '20/h',           # Care reminder actions
        'profile_updates': '10/h',          # Profile modifications
    },

    # Blog/Content Endpoints (user_or_ip-based)
    'blog': {
        'read': '100/h',                    # Blog post reads
        'write': '10/h',                    # Blog post creation (authenticated)
        'comment': '20/h',                  # Comments (when implemented)
    },
}
