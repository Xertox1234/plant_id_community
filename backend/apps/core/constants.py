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

# ============================================================================
# IP Address Constants
# ============================================================================

# Default value for unknown IP addresses
UNKNOWN_IP_ADDRESS = "unknown"

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

ALERT_SEVERITY_CRITICAL = "critical"
ALERT_SEVERITY_HIGH = "high"
ALERT_SEVERITY_MEDIUM = "medium"
ALERT_SEVERITY_LOW = "low"

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

LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"
LOG_LEVEL_CRITICAL = "CRITICAL"

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

# ============================================================================
# Security Middleware Path List (todo 419 moved this here)
# ============================================================================
# Hand-maintained URL literals, pinned route-by-route in
# apps/core/tests/test_legacy_api_mount_removed.py: they named the removed
# /api/auth/ paths and silently matched nothing until todo 405.
#
# Failed logins are no longer matched by path: the login view reports its own
# rejections to SecurityMonitor.track_failed_login (todo 435), whose docstring
# also records why the Firebase token exchange deliberately does not.

# Path prefixes SecurityMetricsMiddleware logs slow requests for.
SECURITY_SENSITIVE_PATHS = (
    "/api/v1/auth/login/",
    "/api/v1/auth/register/",
    "/api/v1/auth/logout/",
    "/api/v1/auth/token/refresh/",
    "/api/v1/auth/firebase-token-exchange/",
)

# ============================================================================
# Push devices (todo 621)
# ============================================================================
# Per account, shared by every device: sign-in, token rotation and the app's
# bounded reconciliation retries all register, so a few devices signing in
# and out must fit with room to spare.
PUSH_DEVICE_RATE_LIMIT = "30/h"
# Model field limits, mirrored by the API serializer.
PUSH_DEVICE_TOKEN_MAX_LENGTH = 255
PUSH_DEVICE_INSTALLATION_ID_MAX_LENGTH = 64
PUSH_DEVICE_PLATFORMS = ("ios", "android")

# ============================================================================
# Delivery outbox (todo 619, apps/core/delivery.py)
# ============================================================================
# A row written with the event waits this long before reconciliation may
# re-drive it: the normal path (an on_commit enqueue) gets there first.
DELIVERY_GRACE_SECONDS = 5 * 60
# A claimed row whose worker has not reported back after this long is taken
# to be interrupted and re-driven (the at-least-once window). Well above the
# per-task hard time limit (CELERY_TASK_TIME_LIMIT, 120 s).
DELIVERY_CLAIM_LEASE_SECONDS = 15 * 60
# Attempts per delivery, counted at each claim. The last failure is terminal.
DELIVERY_MAX_ATTEMPTS = 5
# Transient-failure backoff: 2, 4, 8, 16 minutes after attempts 1-4.
DELIVERY_RETRY_BASE_SECONDS = 2 * 60
# A delivery still undelivered this long after its event is dropped: a stale
# reply email or push is worth less than none.
DELIVERY_MAX_AGE_SECONDS = 24 * 60 * 60
# After re-driving a row, reconciliation leaves it alone this long so a
# re-driven task still waiting in the queue is not enqueued again.
DELIVERY_REDRIVE_INTERVAL_SECONDS = 10 * 60
# Rows re-driven per reconciliation run, oldest due first.
DELIVERY_RECONCILE_BATCH = 200
# Finished rows (sent, suppressed, failed) are deleted after this long.
DELIVERY_RETENTION_DAYS = 14
# Weekly mail (forum digest, blog newsletter) recovery runs: when a run
# reports failed sends, the same command runs again after 30 and then 60
# more minutes, at most this many times. Each run re-claims every member
# still due, so consent is rechecked and an accepted send is never repeated.
WEEKLY_RECOVERY_MAX_RUNS = 2
WEEKLY_RECOVERY_DELAY_SECONDS = 30 * 60

# ============================================================================
# Notification alerts (todo 623, apps/core/notification_ops.py)
# ============================================================================
# A pending outbox row this far past due means reconciliation is not keeping
# up: every pass (5 min) re-drives due rows and moves them 10 min out, so a
# healthy row is never more than one redrive interval overdue.
DELIVERY_QUEUE_LAG_ALERT_SECONDS = 30 * 60
# "Push is not configured" pages at most this often per channel.
PUSH_UNCONFIGURED_ALERT_SECONDS = 60 * 60

# ============================================================================
# Email provider feedback and click attribution (todo 625,
# apps/core/email_feedback.py; policy: docs/operations/notification-baseline.md)
# ============================================================================
# Svix (Resend's webhook signer) refuses a timestamp more than five minutes
# from now: an old, captured request cannot be replayed once its id is pruned.
EMAIL_WEBHOOK_TOLERANCE_SECONDS = 5 * 60
# A Resend event is a few KB. Anything far larger is refused before parsing.
EMAIL_WEBHOOK_MAX_BODY_BYTES = 256 * 1024
# The longest svix-id accepted: the width of EmailProviderEvent.svix_id.
SVIX_ID_MAX_LENGTH = 64
# A click is attributed to its email only this long after the send. A later
# click still redirects; it is just not counted.
EMAIL_CLICK_ATTRIBUTION_DAYS = 7
# Click rows and provider events are deleted after this long (owner decision
# 2026-10-12). Clicks also go with the account (EmailClick.user CASCADE).
EMAIL_FEEDBACK_RETENTION_DAYS = 90
# Rows deleted per DELETE by the feedback prune, so a first run on a large
# table, or one after a long beat outage, never holds one long lock.
EMAIL_FEEDBACK_PRUNE_BATCH = 5000
# The context keys whose links are wrapped in a signed click redirect: the
# content links of the forum notification emails. Never an unsubscribe,
# preferences or account-security link.
EMAIL_TRACKED_LINK_KEYS = ("post_url", "topic_url")
