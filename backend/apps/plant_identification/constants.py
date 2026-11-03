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
# Reduced from 10 to 4 to prevent API quota exhaustion during burst traffic
# Rationale: I/O-bound tasks (API calls) don't benefit from many threads
# 4 workers still allows parallelism while protecting against quota exhaustion
MAX_WORKER_THREADS = 4

# Default multiplier for calculating workers based on CPU cores
# For I/O-bound tasks (API calls), use 1x CPU cores (reduced from 2x)
CPU_CORE_MULTIPLIER = 1


# ============================================================================
# API Timeout Configuration (seconds)
# ============================================================================

# Plant.id API timeouts
PLANT_ID_API_TIMEOUT = 35  # With 5s buffer
PLANT_ID_API_TIMEOUT_DEFAULT = 30  # Default timeout

# PlantNet API timeouts
PLANTNET_API_TIMEOUT = 20  # With 5s buffer
PLANTNET_API_REQUEST_TIMEOUT = 60  # Request timeout

# Image service timeouts
IMAGE_DOWNLOAD_TIMEOUT = 30  # Standard download
IMAGE_DOWNLOAD_QUICK_TIMEOUT = 10  # Quick download


# ============================================================================
# Cache Configuration (seconds)
# ============================================================================

# Base cache timeouts
CACHE_TIMEOUT_24_HOURS = 86400  # 24 hours
CACHE_TIMEOUT_30_MINUTES = 1800  # 30 minutes

# Service-specific cache timeouts
PLANT_ID_CACHE_TIMEOUT = CACHE_TIMEOUT_30_MINUTES
PLANTNET_CACHE_TIMEOUT = CACHE_TIMEOUT_24_HOURS


# ============================================================================
# API Quota Configuration
# ============================================================================

# Plant.id API Limits (Free Tier)
PLANT_ID_MONTHLY_QUOTA = 100  # 100 identifications per month
PLANT_ID_DAILY_QUOTA = 3  # ~3 per day (100/30)
PLANT_ID_QUOTA_WARNING_THRESHOLD = 0.8  # Warn at 80% usage

# PlantNet API Limits (Free Tier)
PLANTNET_DAILY_QUOTA = 500  # 500 requests per day
PLANTNET_HOURLY_QUOTA = 20  # ~20 per hour (500/24)
PLANTNET_QUOTA_WARNING_THRESHOLD = 0.8  # Warn at 80% usage

# Quota tracking Redis key prefixes
QUOTA_KEY_PREFIX_PLANT_ID_DAILY = "quota:plant_id:daily"
QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY = "quota:plant_id:monthly"
QUOTA_KEY_PREFIX_PLANTNET_DAILY = "quota:plantnet:daily"
QUOTA_KEY_PREFIX_PLANTNET_HOURLY = "quota:plantnet:hourly"


# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

# Plant.id API Circuit Breaker (Paid Tier - Conservative)
PLANT_ID_CIRCUIT_FAIL_MAX = 3  # Open circuit after 3 consecutive failures
PLANT_ID_CIRCUIT_RESET_TIMEOUT = 60  # Wait 60s before testing recovery
PLANT_ID_CIRCUIT_SUCCESS_THRESHOLD = 2  # Require 2 successes to close circuit
PLANT_ID_CIRCUIT_TIMEOUT = PLANT_ID_API_TIMEOUT

# PlantNet API Circuit Breaker (Free Tier - More Tolerant)
PLANTNET_CIRCUIT_FAIL_MAX = 5  # Open circuit after 5 consecutive failures
PLANTNET_CIRCUIT_RESET_TIMEOUT = 30  # Wait 30s before testing recovery
PLANTNET_CIRCUIT_SUCCESS_THRESHOLD = 2  # Require 2 successes to close circuit
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
CACHE_LOCK_ID_PREFIX = "plant_id"  # Will be: "plant_id-{hostname}-{pid}-{thread_id}"


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
    "anonymous": {
        "plant_identification": "100/h",  # Increased for development testing (was 10/h)
        "read_only": "100/h",  # General read operations
        "search": "30/h",  # Search endpoints
    },
    # Authenticated User Limits (user-based)
    "authenticated": {
        "plant_identification": "100/h",  # Plant ID API calls
        "write_operations": "50/h",  # Create/update operations
        "read_only": "1000/h",  # General read operations
        "search": "100/h",  # Search endpoints
        "care_instructions": "30/m",  # Care instruction lookups
        "regenerate": "5/m",  # AI regeneration (expensive)
    },
    # Authentication Endpoints (IP-based, security-focused)
    "auth_endpoints": {
        "login": "5/15m",  # Login attempts
        "register": "3/h",  # Registration
        "token_refresh": "10/h",  # Token refresh
        "password_reset": "3/h",  # Password reset (not implemented)
        "firebase_token_exchange": "10/m",  # Firebase token -> JWT exchange (mobile)
        "verify_email": "20/h",  # Email verification confirm, per user (todo 446)
        "verify_email_resend": "3/h",  # Resend verification email, per user
    },
    # User Feature Endpoints (user-based)
    "user_features": {
        "push_notifications": "10/h",  # Push notification subscriptions
        # Per user, on PATCH auth/user/update/ and DELETE auth/user/avatar/
        # (todo 565): each may carry a 2 MB avatar, and the mobile profile
        # screen PATCHes once per notification toggle.
        "profile_updates": "30/h",
    },
    # Blog/Content Endpoints (user_or_ip-based)
    "blog": {
        "read": "100/h",  # Blog post reads
        "write": "10/h",  # Blog post creation (authenticated)
        "comment": "20/h",  # Comments (when implemented)
    },
}

# PlantDiseaseRequest.status. A named constant so SPECTACULAR_SETTINGS
# ["ENUM_NAME_OVERRIDES"] can pin its OpenAPI enum name (todo 581).
DISEASE_REQUEST_STATUS_CHOICES = [
    ("pending", "Pending Diagnosis"),
    ("processing", "Processing with AI"),
    ("diagnosed", "Disease Diagnosed"),
    ("needs_help", "Needs Community Help"),
    ("failed", "Diagnosis Failed"),
]


# Name of the case-insensitive unique constraint on
# PlantDiseaseDatabase.disease_name (todo 613). The diagnosis service matches
# an IntegrityError against it to tell a name collision from any other.
DISEASE_NAME_LOWER_UNIQUE = "plant_disease_name_lower_unique"


# ============================================================================
# Scan 2.0 background scan jobs (Phase B3)
# ============================================================================

# PlantNet organ for each scan photo role, in the fixed order photos are sent.
# The "problem" close-up goes to PlantNet only when it is the sole photo, as a
# leaf (PlantNet has no organ for a symptom close-up).
SCAN_PLANTNET_ORGANS = {"leaf": "leaf", "whole": "habit", "flower": "flower"}
SCAN_PROBLEM_ROLE = "problem"
SCAN_PROBLEM_FALLBACK_ORGAN = "leaf"

# run_scan_job: a scan makes at most two provider round trips (PlantNet then
# Plant.id identify + health), each bounded by its executor timeout.
SCAN_JOB_SOFT_TIME_LIMIT = 150
SCAN_JOB_TIME_LIMIT = 180
SCAN_JOB_RETRY_COUNTDOWN = 5  # seconds before the one automatic retry
# Claims per job, retry and redeliveries included: a job whose worker keeps
# dying is not re-run forever.
SCAN_JOB_MAX_ATTEMPTS = 3

# ScanJob.failure_reason tokens
SCAN_FAILURE_NO_RESULT = "no_result"  # neither provider named the plant
SCAN_FAILURE_ERROR = "error"  # unexpected exception in the task
SCAN_FAILURE_TIMEOUT = "timeout"  # the soft time limit fired
SCAN_FAILURE_STALE = "stale"  # still active past SCAN_JOB_STALE_MINUTES

# Push for a finished job. The event key is "event" (not "type"); the collapse
# key is per EVENT TYPE, never per job (docs/rules/celery.md).
SCAN_JOB_EVENT = "scan_job_finished"
SCAN_JOB_COLLAPSE_KEY = "scan-job-finished"
SCAN_PUSH_READY = ("Your plant check is ready", "Tap to see what we found.")
SCAN_PUSH_FAILED = (
    "We couldn't check your plant",
    "Tap to try again. Your check wasn't used.",
)
SCAN_PUSH_MAX_RETRIES = 3
SCAN_PUSH_RETRY_DELAY = 30  # seconds; doubles per retry (30, 60, 120)
SCAN_SUMMARY_MAX_SUGGESTIONS = 5

# ============================================================================
# Scan 2.0 job API (Phase B4)
# ============================================================================

# A scan's mode, which is also what a finished scan is charged as. Named in
# SPECTACULAR_SETTINGS ENUM_NAME_OVERRIDES as ScanModeEnum.
SCAN_MODE_CHOICES = [("diagnose", "Diagnose"), ("identify", "Identify")]

# Photo roles each mode accepts, and the one it requires.
SCAN_MODE_ROLES = {
    "diagnose": ("problem", "leaf", "whole", "flower"),
    "identify": ("leaf", "whole", "flower"),
}
SCAN_REQUIRED_ROLE = {"diagnose": "problem", "identify": "leaf"}
SCAN_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # per photo, before re-encoding
SCAN_CREATE_RATE = "100/h"  # per-user burst limit on POST scans/
SCAN_PHOTO_CACHE_CONTROL = "private, max-age=86400"
