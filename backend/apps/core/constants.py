"""
Security constants for the Plant Community application.

This module centralizes all security-related configuration values to ensure
consistency and make it easy to adjust security policies.
"""

# ============================================================================
# Account Lockout Configuration
# ============================================================================

# Maximum failed login attempts before account lockout
ACCOUNT_LOCKOUT_THRESHOLD = 10

# Account lockout duration in seconds (1 hour)
ACCOUNT_LOCKOUT_DURATION = 3600

# Time window for counting failed login attempts in seconds (15 minutes)
ACCOUNT_LOCKOUT_TIME_WINDOW = 900

# ============================================================================
# Rate Limiting Configuration
# ============================================================================

# Failed login tracking
MAX_FAILED_LOGINS = 5
MAX_FAILED_LOGINS_TIME = 900  # 15 minutes

# Suspicious activity detection
SUSPICIOUS_ACTIVITY_THRESHOLD = 10
SUSPICIOUS_ACTIVITY_TIME = 600  # 10 minutes

# API rate limiting
API_RATE_LIMIT_WINDOW = 60  # 1 minute
API_RATE_LIMIT_MAX_REQUESTS = 30

# File upload rate limiting
MAX_UPLOAD_FAILURES_PER_HOUR = 20
UPLOAD_FAILURE_WINDOW = 3600  # 1 hour

# Validation failure tracking
MAX_VALIDATION_FAILURES_PER_HOUR = 50
VALIDATION_FAILURE_WINDOW = 3600  # 1 hour

# ============================================================================
# IP Address Constants
# ============================================================================

# Default value for unknown IP addresses
UNKNOWN_IP_ADDRESS = 'unknown'

# ============================================================================
# Cache Keys
# ============================================================================

# Account lockout cache keys
LOCKOUT_ATTEMPTS_KEY = "security:lockout_attempts:{username}"
LOCKOUT_STATUS_KEY = "security:lockout_status:{username}"

# Failed login tracking
FAILED_LOGIN_KEY = "security:failed_login:{ip}"

# Rate limiting
RATE_LIMIT_KEY = "security:rate_limit:{user_id}:{endpoint}"

# Suspicious activity
SUSPICIOUS_ACTIVITY_KEY = "security:suspicious:{user_id}"

# ============================================================================
# Security Alert Severities
# ============================================================================

ALERT_SEVERITY_CRITICAL = 'critical'
ALERT_SEVERITY_HIGH = 'high'
ALERT_SEVERITY_MEDIUM = 'medium'
ALERT_SEVERITY_LOW = 'low'

# ============================================================================
# Logging Prefixes
# ============================================================================

LOG_PREFIX_SECURITY = "[SECURITY]"
LOG_PREFIX_AUTH = "[AUTH]"
LOG_PREFIX_RATELIMIT = "[RATELIMIT]"
LOG_PREFIX_LOCKOUT = "[LOCKOUT]"
LOG_PREFIX_ALERT = "[ALERT]"
LOG_PREFIX_CACHE = "[CACHE]"
LOG_PREFIX_PERF = "[PERF]"
LOG_PREFIX_ERROR = "[ERROR]"
LOG_PREFIX_API = "[API]"
LOG_PREFIX_DB = "[DB]"
LOG_PREFIX_CIRCUIT = "[CIRCUIT]"
LOG_PREFIX_PARALLEL = "[PARALLEL]"

# ============================================================================
# Log Levels
# ============================================================================

LOG_LEVEL_DEBUG = 'DEBUG'
LOG_LEVEL_INFO = 'INFO'
LOG_LEVEL_WARNING = 'WARNING'
LOG_LEVEL_ERROR = 'ERROR'
LOG_LEVEL_CRITICAL = 'CRITICAL'

# ============================================================================
# Email Configuration
# ============================================================================

# Email notification settings for account lockout
LOCKOUT_EMAIL_ENABLED = True
LOCKOUT_EMAIL_SUBJECT = "Security Alert: Account Locked"

# ============================================================================
# Rate Limit Violation Thresholds
# ============================================================================

# Number of rate limit violations before triggering alert
RATE_LIMIT_VIOLATION_THRESHOLD = 5

# Time window for tracking rate limit violations (1 hour)
RATE_LIMIT_VIOLATION_WINDOW = 3600
