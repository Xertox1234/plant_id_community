"""The optional-integration keys whose `.env.example` placeholder must not boot.

Single source for ``settings.validate_environment()`` and the tests that seed
or assert on these keys (todos 436 and 561). Importing this module has no side
effects, unlike importing settings.
"""

# Every key here is read with a default, so unset leaves that integration off
# and is never an error (todo 436).
OPTIONAL_INTEGRATION_KEYS = (
    "OPENWEATHER_API_KEY",
    "TREFLE_API_KEY",
    "PLANT_HEALTH_API_KEY",
    "OPENAI_API_KEY",
    "UNSPLASH_ACCESS_KEY",
    "PEXELS_API_KEY",
    "GOOGLE_OAUTH2_CLIENT_ID",
    "GOOGLE_OAUTH2_CLIENT_SECRET",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "FIREBASE_PROJECT_ID",
    "FIREBASE_CREDENTIALS_PATH",
)

# The values these keys carried in `.env.example` before todo 436 replaced them
# with REQUIRED__ placeholders (git show 826d700e:backend/.env.example). An
# environment built from that older template still holds them, and they are
# truthy, so each one switched its integration ON with a value published in a
# public repository. Refused by exact literal (todo 561, owner decision
# 2026-10-11), matched anywhere in the value for the same paste-padding reason
# as ``is_required_placeholder``: no real key contains one of these strings.
# Each line carries a detect-secrets pragma: these are the published
# placeholders themselves, not secrets.
LEGACY_PLACEHOLDERS = {
    "OPENWEATHER_API_KEY": "your-openweathermap-api-key-here",  # pragma: allowlist secret
    "TREFLE_API_KEY": "your-trefle-api-key-here",  # pragma: allowlist secret
    "PLANT_HEALTH_API_KEY": "your-plant-health-api-key-here",  # pragma: allowlist secret
    "OPENAI_API_KEY": "your-openai-api-key-here",  # pragma: allowlist secret
    "UNSPLASH_ACCESS_KEY": "your-unsplash-access-key",  # pragma: allowlist secret
    "PEXELS_API_KEY": "your-pexels-api-key",  # pragma: allowlist secret
    "GOOGLE_OAUTH2_CLIENT_ID": "your-google-client-id.apps.googleusercontent.com",  # pragma: allowlist secret
    "GOOGLE_OAUTH2_CLIENT_SECRET": "your-google-client-secret",  # pragma: allowlist secret
    "GITHUB_CLIENT_ID": "your-github-client-id",  # pragma: allowlist secret
    "GITHUB_CLIENT_SECRET": "your-github-client-secret",  # pragma: allowlist secret
    "FIREBASE_PROJECT_ID": "your-firebase-project-id",  # pragma: allowlist secret
    "FIREBASE_CREDENTIALS_PATH": "path/to/firebase-service-account.json",  # pragma: allowlist secret
}


def is_legacy_placeholder(key_name, value):
    """True if ``value`` is the pre-todo-436 `.env.example` value of
    ``key_name``."""
    literal = LEGACY_PLACEHOLDERS.get(key_name)
    return bool(value) and literal is not None and literal in value
