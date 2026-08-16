"""
Production /media/ serving (plant_community_backend/urls.py).

Django's static() URL helper is a deliberate no-op when DEBUG=False, so
before the explicit production route existed every uploaded file 404'd on
Railway even though the files were on disk (found live 2026-08-16 during
the forum demo seed). The test runner forces DEBUG=False, which means the
URLconf here loads the production branch — exactly the route under test.
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings


# TestCase (not SimpleTestCase): a 404 response passes through Wagtail's
# redirects middleware, which looks up Redirect rows in the database.
class ProductionMediaServingTests(TestCase):
    """The DEBUG=False branch of urls.py serves MEDIA_ROOT at /media/."""

    def test_urlconf_loaded_the_production_branch(self):
        # Load-bearing guard: if DEBUG were True here, the assertions below
        # would pass via the development static() route and prove nothing
        # about the production one.
        self.assertFalse(settings.DEBUG)

    def test_media_file_is_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "probe.txt").write_bytes(b"media-probe")
            with override_settings(MEDIA_ROOT=tmp):
                response = self.client.get("/media/probe.txt")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"media-probe")

    def test_missing_media_file_returns_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                response = self.client.get("/media/absent.txt")
                self.assertEqual(response.status_code, 404)
