"""
Rate limiting and other constants for the users app.
"""

RATE_LIMIT_ONBOARDING_EVENT = "50/h"
# Signed-link email unsubscribe (todo 408), per client IP. The token is the
# credential, so this bounds probing, not a real user clicking twice.
RATE_LIMIT_EMAIL_UNSUBSCRIBE = "30/h"
# The service worker's push re-subscribe (todo 456), per client IP: it has no
# user to key on. A browser replaces its subscription rarely (expiry, or a
# Firefox reset), so this only caps guessing at an endpoint's auth secret.
RATE_LIMIT_PUSH_RESUBSCRIBE = "20/h"
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

# How long a push service holds a message for a browser that is offline or
# closed. pywebpush defaults to 0, which tells the service to drop the message
# unless the browser is connected at that moment (PR #852 review).
WEB_PUSH_TTL_SECONDS = 24 * 60 * 60
# Bound on one push-service POST, so a stalled service cannot hold a worker.
WEB_PUSH_TIMEOUT_SECONDS = 10
# Bound on each OAuth provider call (token exchange, profile, emails) in the web
# callback. uvicorn has no per-request hard kill, so without it a stalled
# provider holds a sync thread indefinitely (live forum replies, slice 1).
OAUTH_PROVIDER_TIMEOUT_SECONDS = 10
# The push service answers these when a subscription is gone for good. 413
# (payload too large) and 429 (rate limited) say nothing about the subscription.
WEB_PUSH_GONE_STATUSES = (404, 410)
# Usernames for accounts the user did not name (OAuth, social and Firebase
# signup): prefix + random suffix, never the email (signup.generate_username).
GENERATED_USERNAME_PREFIX = "member_"
# No 0/o, 1/l/i: the handle is shown publicly and may be read aloud or retyped.
GENERATED_USERNAME_ALPHABET = (
    "abcdefghjkmnpqrstuvwxyz23456789"  # pragma: allowlist secret
)
GENERATED_USERNAME_SUFFIX_LENGTH = 8
GENERATED_USERNAME_ATTEMPTS = 10

# Version of the Privacy Policy and Terms of Service a sign-up accepts. The
# server stamps it; a client never sends a version. Bump it when either text
# changes materially.
LEGAL_POLICY_VERSION = "2026-11-06"
# Sign-up without an explicit boolean ``true`` consent is refused with HTTP 428.
CONSENT_REQUIRED_CODE = "consent_required"
CONSENT_REQUIRED_MESSAGE = (
    "Please accept the Privacy Policy and Terms of Service to create an account."
)

# Web OAuth sign-up that came back without consent waits in the session for the
# user to accept on the web app's /signup/finish page, for this long.
OAUTH_PENDING_SIGNUP_TTL_SECONDS = 900
SIGNUP_EXPIRED_CODE = "signup_expired"
SIGNUP_EXPIRED_MESSAGE = "Your sign-up expired. Please sign in again."
# The finish step could not create or find the account (the provider identity
# is linked elsewhere, or the email now belongs to another account).
SIGNUP_FAILED_CODE = "signup_failed"
SIGNUP_FAILED_MESSAGE = "We couldn't finish your sign-up. Please sign in again."
# POST auth/oauth/finish/, per client IP. Looser than register's 3/h: a 428
# (box not ticked) is a retry, not a new sign-up.
RATE_LIMIT_OAUTH_FINISH = "10/h"
# The only provider-profile keys the pending sign-up keeps: the ones
# oauth_views._find_or_create_user reads. Never a token.
OAUTH_PENDING_SIGNUP_USER_DATA_KEYS = (
    "id",
    "email",
    "given_name",
    "family_name",
    "name",
    "bio",
    "blog",
    "location",
)

# Account deletion (Plan B). An address deleted for abuse or under-13 cannot
# sign up again: every create path answers 403 with this code BEFORE it asks
# for sign-up consent, so a blocked address is never shown the terms.
SIGNUP_BLOCKED_CODE = "signup_blocked"
SIGNUP_BLOCKED_MESSAGE = "This email address can't be used to create an account."
DELETED_ACCOUNT_REASON_SELF = "self"
DELETED_ACCOUNT_REASON_STAFF = "staff"
DELETED_ACCOUNT_REASON_ABUSE = "abuse"
DELETED_ACCOUNT_REASON_UNDER_13 = "under_13"
DELETED_ACCOUNT_STATUS_PENDING = "pending"
DELETED_ACCOUNT_STATUS_DONE = "done"
# Reasons that keep an address from signing up again.
SIGNUP_BLOCKING_REASONS = (
    DELETED_ACCOUNT_REASON_ABUSE,
    DELETED_ACCOUNT_REASON_UNDER_13,
)
# Erasing a deleted account's data (Plan B task 3). A post of theirs with a
# report still in the moderation queue keeps its content this long, so a
# moderator can still review it; the scheduled erase then removes it.
FORUM_HELD_POST_DAYS = 30
# What an erased account's topics are titled. The same sentinel the forum
# shows for a deleted author.
DELETED_TOPIC_TITLE = "[deleted]"
# Erase steps, in the order they run and are recorded in steps_done.
ERASE_STEP_FORUM = "forum"
ERASE_STEP_EMAIL = "email"
ERASE_STEP_DJANGO = "django"
ERASE_STEP_FIRESTORE = "firestore"
ERASE_STEP_FIREBASE_AUTH = "firebase_auth"
# Recorded once the "your account has been deleted" email is sent, so a retry
# never sends a second one.
ERASE_STEP_NOTIFIED = "notified"
# delete_account_task's retries (Plan B task 5). retry_backoff=True is
# Celery's backoff factor 1: about 1 s, 2 s, 4 s ... jittered, capped below.
ACCOUNT_DELETE_MAX_RETRIES = 8
ACCOUNT_DELETE_RETRY_BACKOFF_MAX = 3600
ACCOUNT_DELETED_EMAIL_SUBJECT = "Your Houseplant MD account has been deleted"
# Audit-log rows deleted per statement while erasing.
ERASE_LOGENTRY_CHUNK_SIZE = 500

# Deletion endpoints (Plan B task 6). The mobile app proves a fresh sign-in:
# the Firebase ID token's auth_time may be at most this old.
ACCOUNT_DELETE_REAUTH_MAX_AGE_SECONDS = 300
# How far in the future auth_time may be (clock skew) before it is refused.
ACCOUNT_DELETE_AUTH_TIME_SKEW_SECONDS = 60
ACCOUNT_DELETE_REAUTH_CODE = "reauth_required"
ACCOUNT_DELETE_REAUTH_MESSAGE = "Please sign in again to delete your account."
ACCOUNT_DELETE_SCHEDULED_STATUS = "scheduled"
# Staff and blog authors (DeletionRefused). [[CONTACT_EMAIL]] is the policy
# placeholder the owner fills in later; keep it literal until then.
ACCOUNT_DELETE_CONTACT_SUPPORT_CODE = "contact_support"
ACCOUNT_DELETE_CONTACT_SUPPORT_MESSAGE = (
    "This account can't be deleted from the app. Email [[CONTACT_EMAIL]] "
    "and we'll help."
)
# The emailed link (web). POST account/delete/request/ is limited per client
# IP and per normalised address.
ACCOUNT_DELETE_REQUEST_RATE_IP = "5/h"
ACCOUNT_DELETE_REQUEST_RATE_EMAIL = "3/h"
ACCOUNT_DELETE_REQUEST_SENT_STATUS = "sent"
ACCOUNT_DELETE_LINK_TTL_SECONDS = 3600
ACCOUNT_DELETE_LINK_SALT = "account-delete"
# The link's one-time nonce lives in the cache under this prefix + user pk; a
# new request replaces it, so only the newest link works.
ACCOUNT_DELETE_LINK_CACHE_PREFIX = "account-delete:"
ACCOUNT_DELETE_LINK_NONCE_BYTES = 32
ACCOUNT_DELETE_LINK_PATH = "/delete-account/confirm"
ACCOUNT_DELETE_LINK_SUBJECT = "Confirm you want to delete your Houseplant MD account"
ACCOUNT_DELETE_LINK_INVALID_CODE = "link_invalid"
ACCOUNT_DELETE_LINK_INVALID_MESSAGE = (
    "This link has expired or was already used. Request a new one."
)

# Nightly privacy prune (Plan B task 8, beat entry ``privacy-retention-prune``).
# Email records, blog page views and audit-log rows are kept this long.
PRIVACY_RETENTION_DAYS = 90
# Rows deleted per statement by the retention prune.
PRIVACY_PRUNE_BATCH = 5000
# The prune's own Celery limits: a first run over a large audit-log table
# outlasts the request-shaped global 90 s. Each batch commits on its own, so a
# kill loses nothing and the next night carries on.
PRIVACY_PRUNE_SOFT_TIME_LIMIT = 900
PRIVACY_PRUNE_TIME_LIMIT = 960
# A Firebase login with no account behind it is removed once it is this old.
# The margin covers a sign-up whose Django account is created after its login.
ORPHAN_FIREBASE_USER_DAYS = 7
# More orphans than this in one run is treated as a bug (a wrong project, an
# emptied users table), not cleanup: nothing is deleted and Sentry is told.
ORPHAN_FIREBASE_DELETE_CAP = 50
# A deletion still pending this long after it was requested is queued again:
# delete_account_task's retries span only minutes, and a .delay() that failed
# at commit leaves the record with no job at all.
ACCOUNT_DELETE_STALE_HOURS = 1
