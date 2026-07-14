"""Host-level configuration for the mounted wagtail_forum API."""

# Default rate limits for the forum API (audit 2026-06-10 H1). The package is
# host-agnostic and leaves throttling to the host (plan 1C/1D); these are the
# host's choices. Override per-deployment via settings.FORUM_RATELIMITS.
# Write rates are per-user; the anonymous read endpoints are per-IP.
DEFAULT_FORUM_RATELIMITS = {
    "topic_create": "10/h",
    "reply_create": "30/h",
    "post_update": "30/h",
    "post_delete": "20/h",
    "reaction_toggle": "60/m",
    "report_create": "10/h",
    "profile_update": "10/h",
    "image_upload": "30/h",
    "search": "30/m",
    "sync": "60/m",
    # Generous — the bell polls this on an interval; the limit exists only to
    # bound a runaway/malicious client, not to constrain normal polling cadence.
    "notification_unread_count": "120/m",
    "notification_mark_read": "60/m",
}
