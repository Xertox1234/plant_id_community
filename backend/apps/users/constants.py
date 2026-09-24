"""
Rate limiting and other constants for the users app.
"""

RATE_LIMIT_DEMO_DATA_CREATE = "10/h"
RATE_LIMIT_ONBOARDING_EVENT = "50/h"
# Signed-link email unsubscribe (todo 408), per client IP. The token is the
# credential, so this bounds probing, not a real user clicking twice.
RATE_LIMIT_EMAIL_UNSUBSCRIBE = "30/h"
