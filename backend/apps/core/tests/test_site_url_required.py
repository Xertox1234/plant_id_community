"""validate_environment() requires SITE_URL in production (todo 408).

SITE_URL is the web app's origin: every link in our email, the RSS feeds and
the sitemap are built on it. Production ran without it, so all of them pointed
at the settings default — a domain the project does not own — while the
service booted and served normally. Classified by consequence, that is a
critical error, not a warning.
"""

from django.test import SimpleTestCase

from .test_r2_storage import _run_check

PRODUCTION = dict(
    DEBUG="False",
    ALLOWED_HOSTS="example.com",
    CSRF_TRUSTED_ORIGINS="https://example.com",
    PLANT_ID_API_KEY="1" * 32,
    CORS_ALLOWED_ORIGINS="https://example.com",
    REDIS_URL="redis://localhost:6379/1",
)


class SiteUrlRequiredTests(SimpleTestCase):
    def test_missing_site_url_fails_fast_in_production(self):
        # Blank, not absent: an absent key falls through to backend/.env.
        result = _run_check(SITE_URL="", **PRODUCTION)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SITE_URL must be set in production", result.stderr)

    def test_set_site_url_is_not_reported(self):
        result = _run_check(SITE_URL="https://example.com", **PRODUCTION)
        self.assertNotIn("SITE_URL must be set", result.stderr)

    def test_missing_site_url_does_not_block_development(self):
        result = _run_check(SITE_URL="", DEBUG="True")
        self.assertNotIn("SITE_URL must be set", result.stderr)
