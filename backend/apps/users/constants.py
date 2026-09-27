"""
Rate limiting and other constants for the users app.
"""

RATE_LIMIT_ONBOARDING_EVENT = "50/h"
# Signed-link email unsubscribe (todo 408), per client IP. The token is the
# credential, so this bounds probing, not a real user clicking twice.
RATE_LIMIT_EMAIL_UNSUBSCRIBE = "30/h"
# Verification mails per account per window, the registration mail included
# (todo 447). Past it, resend answers `limit_reached` and nothing is queued
# until the window, which starts at the first mail, has passed.
VERIFICATION_EMAIL_CAP = 5
VERIFICATION_EMAIL_WINDOW_DAYS = 30
# Account mails sent by Celery (todo 447 item 11). A failed send retries
# after 1, 2 and 4 minutes, then is logged and dropped.
ACCOUNT_MAIL_MAX_RETRIES = 3
ACCOUNT_MAIL_RETRY_DELAY = 60
# Unverified-account expiry (todo 447 slice C, `expire_unverified_accounts`).
# A password account that never verified its email and never came back is
# deleted once it is this old.
UNVERIFIED_ACCOUNT_EXPIRY_DAYS = 7
# Registration itself issues a refresh token and may stamp last_login. Anything
# later than date_joined plus this margin counts as a sign-in. The registration
# token lands a fraction of a second after the row.
UNVERIFIED_ACCOUNT_SIGNUP_MARGIN_SECONDS = 60

# Web Push (todo 413). Sending a push makes THIS server POST to the
# subscription's endpoint, so a client-supplied endpoint is an SSRF vector
# unless it is https and on a known browser push service. Suffix match on the
# host (a dot boundary is enforced in code).
WEB_PUSH_ALLOWED_HOST_SUFFIXES = (
    "fcm.googleapis.com",  # Chrome, Edge (Chromium), Opera, Samsung
    "push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari (web.push.apple.com)
    "notify.windows.com",  # legacy Edge / Windows (wns2-*.notify.windows.com)
)
WEB_PUSH_ENDPOINT_MAX_LENGTH = 500  # PushSubscription.endpoint max_length
