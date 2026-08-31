"""
Production /media/ is NOT served by Django (plant_community_backend/urls.py).

PR #539's serve() fallback (a stopgap route reading MEDIA_ROOT directly) was
removed once the R2 cutover (todo 305, PR #591) was verified live — media is
now served from an R2-backed CDN domain, not this app. This pins the
opposite of the old behavior: even a file that physically exists in
MEDIA_ROOT must 404 through Django, since nothing routes /media/ anymore.
Regression guard against silently re-adding a local serve route.
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings


# TestCase (not SimpleTestCase): a 404 response passes through Wagtail's
# redirects middleware, which looks up Redirect rows in the database.
class ProductionMediaServingTests(TestCase):
    """The DEBUG=False branch of urls.py has no /media/ route at all."""

    def test_urlconf_loaded_the_production_branch(self):
        # Load-bearing guard: if DEBUG were True here, the assertion below
        # would 404 via a different mechanism (no static() route registered
        # for a nonexistent file) and prove nothing about production.
        self.assertFalse(settings.DEBUG)

    def test_existing_media_file_still_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "probe.txt").write_bytes(b"media-probe")
            with override_settings(MEDIA_ROOT=tmp):
                response = self.client.get("/media/probe.txt")
                self.assertEqual(response.status_code, 404)

    def test_missing_media_file_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                response = self.client.get("/media/absent.txt")
                self.assertEqual(response.status_code, 404)
