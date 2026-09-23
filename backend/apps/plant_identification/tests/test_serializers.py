"""Serializer helper tests.

The TreatmentAttemptSerializer regression test (todo 092) was removed with the
serializer in todo 405 slice 2: the treatment-attempts endpoint had no client.
"""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from ..serializers import serialize_image_urls

User = get_user_model()


class SerializeImageUrlsTest(TestCase):
    """Contract for the shared image-URL helper (todo 221 / finding M4).

    The four ``get_images``/``get_image_thumbnails`` copies had drifted to two
    URL shapes (one relative, three absolute). This pins the single shape:
    absolute when a request is in context, relative fallback otherwise, and
    falsy entries skipped (images are never silently dropped).
    """

    def setUp(self):
        self.request = RequestFactory().get("/api/v1/plant-id/")

    def test_absolute_urls_when_request_present(self):
        images = [
            SimpleNamespace(url="/media/a.jpg"),
            SimpleNamespace(url="/media/b.jpg"),
        ]
        self.assertEqual(
            serialize_image_urls(images, self.request),
            ["http://testserver/media/a.jpg", "http://testserver/media/b.jpg"],
        )

    def test_relative_urls_when_request_absent(self):
        # Without a request the absolute copies used to return [] (dropping the
        # images); the helper falls back to the relative URL instead.
        images = [SimpleNamespace(url="/media/a.jpg")]
        self.assertEqual(serialize_image_urls(images, None), ["/media/a.jpg"])

    def test_falsy_images_skipped(self):
        images = [None, SimpleNamespace(url="/media/a.jpg"), None]
        self.assertEqual(
            serialize_image_urls(images, self.request),
            ["http://testserver/media/a.jpg"],
        )
