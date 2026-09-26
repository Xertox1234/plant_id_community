"""
Rate limiting and other constants for the users app.
"""

RATE_LIMIT_DEMO_DATA_CREATE = "10/h"
RATE_LIMIT_ONBOARDING_EVENT = "50/h"
# Signed-link email unsubscribe (todo 408), per client IP. The token is the
# credential, so this bounds probing, not a real user clicking twice.
RATE_LIMIT_EMAIL_UNSUBSCRIBE = "30/h"
# Verification mails per account, lifetime, the registration mail included
# (todo 447). Past it, resend answers `limit_reached` and nothing is queued.
VERIFICATION_EMAIL_CAP = 5
# Account mails sent by Celery (todo 447 item 11). A failed send retries
# after 1, 2 and 4 minutes, then is logged and dropped.
ACCOUNT_MAIL_MAX_RETRIES = 3
ACCOUNT_MAIL_RETRY_DELAY = 60
