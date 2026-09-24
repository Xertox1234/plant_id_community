"""Stock-photo credit link (todo 376).

`PlantImageService.get_attribution_url` supplies the link stored beside the
credit text in the blog `plant_spotlight` block. Unsplash's API guidelines
require referral UTM parameters on links back to Unsplash; a non-http(s)
provider value must never be stored as a link.
"""

from unittest import mock

from apps.plant_identification.services.plant_image_service import PlantImageService
from apps.plant_identification.services.unsplash_service import (
    UnsplashImageService,
    with_unsplash_utm,
)
from django.test import SimpleTestCase

UTM = "utm_source=plant_community&utm_medium=referral"


class GetAttributionUrlTest(SimpleTestCase):
    def test_unsplash_links_photographer_profile_with_utm(self):
        url = PlantImageService.get_attribution_url(
            "unsplash",
            {"photographer": {"profile_url": "https://unsplash.com/@janedoe"}},
        )
        self.assertEqual(url, f"https://unsplash.com/@janedoe?{UTM}")

    def test_unsplash_profile_with_query_string_appends_utm(self):
        url = PlantImageService.get_attribution_url(
            "unsplash",
            {"photographer": {"profile_url": "https://unsplash.com/@janedoe?a=1"}},
        )
        self.assertEqual(url, f"https://unsplash.com/@janedoe?a=1&{UTM}")

    def test_pexels_links_photographer_page(self):
        url = PlantImageService.get_attribution_url(
            "pexels", {"photographer": {"url": "https://www.pexels.com/@samroe"}}
        )
        self.assertEqual(url, "https://www.pexels.com/@samroe")

    def test_no_link_for_ai_or_unknown_source(self):
        self.assertEqual(PlantImageService.get_attribution_url("ai", {}), "")
        self.assertEqual(PlantImageService.get_attribution_url("other", {}), "")

    def test_missing_or_non_http_provider_url_yields_no_link(self):
        for source, image_data in [
            ("unsplash", {}),
            ("unsplash", {"photographer": None}),
            ("unsplash", {"photographer": {"profile_url": "javascript:alert(1)"}}),
            ("pexels", {"photographer": {"url": "data:text/html,x"}}),
            ("pexels", {"photographer": {"url": None}}),
        ]:
            with self.subTest(source=source, image_data=image_data):
                self.assertEqual(
                    PlantImageService.get_attribution_url(source, image_data), ""
                )


class AttributionRobustnessTest(SimpleTestCase):
    def test_text_survives_a_null_photographer(self):
        service = PlantImageService.__new__(PlantImageService)
        self.assertEqual(
            service.get_attribution_text("pexels", {"photographer": None}),
            "Photo by Unknown from Pexels",
        )

    def test_url_rejects_hostless_or_credentialed_provider_links(self):
        for bad in ("https://", "https:///x", "https://u:p@host.example/"):
            with self.subTest(url=bad):
                self.assertEqual(
                    PlantImageService.get_attribution_url(
                        "pexels", {"photographer": {"url": bad}}
                    ),
                    "",
                )


class UnsplashUtmTest(SimpleTestCase):
    def test_with_unsplash_utm(self):
        self.assertEqual(
            with_unsplash_utm("https://x.example/a"), f"https://x.example/a?{UTM}"
        )
        self.assertEqual(
            with_unsplash_utm("https://x.example/a?b=1"),
            f"https://x.example/a?b=1&{UTM}",
        )

    def test_trigger_download_still_sends_utm(self):
        service = UnsplashImageService(access_key="k")
        with mock.patch(
            "apps.plant_identification.services.unsplash_service.requests.get"
        ) as get:
            service.trigger_download(
                {
                    "id": "abc",
                    "download_url": "https://unsplash.com/photos/abc/download",
                }
            )
        get.assert_called_once_with(
            f"https://unsplash.com/photos/abc/download?{UTM}", timeout=10
        )
