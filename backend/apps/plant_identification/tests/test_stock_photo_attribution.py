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
from django.core.cache import cache
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


class AttributionFromImageTagsTest(SimpleTestCase):
    """Todo 438: rebuild a credit from the tags the download path writes."""

    def rebuild(self, *tags):
        return PlantImageService.attribution_from_image_tags(list(tags))

    def test_unsplash_tags_give_username_credit_and_utm_profile_link(self):
        self.assertEqual(
            self.rebuild(
                "unsplash", "botanical", "photographer:janedoe", "unsplash_id:abc"
            ),
            ("Photo by janedoe on Unsplash", f"https://unsplash.com/@janedoe?{UTM}"),
        )

    def test_pexels_tags_give_text_only_credit_with_spaces_restored(self):
        self.assertEqual(
            self.rebuild("pexels", "botanical", "photographer:Sam_Roe", "pexels_id:7"),
            ("Photo by Sam Roe from Pexels", ""),
        )

    def test_ai_tag_gives_the_disclosure_text(self):
        self.assertEqual(
            self.rebuild("ai_generated", "dall_e_3", "botanical"),
            ("AI-generated botanical image (DALL-E 3)", ""),
        )

    def test_unsplash_username_that_is_not_a_username_gets_no_link(self):
        self.assertEqual(
            self.rebuild("unsplash", "photographer:jane/../x?y"),
            ("Photo by jane/../x?y on Unsplash", ""),
        )

    def test_unrecoverable_tag_sets_return_none(self):
        for tags in [
            (),
            ("botanical",),
            ("unsplash",),  # no photographer tag
            ("unsplash", "photographer:unknown"),  # the services' fallback
            ("pexels", "photographer:"),
            ("unsplash", "pexels", "photographer:x"),  # ambiguous provider
            ("unsplash", "photographer:a", "photographer:b"),
        ]:
            with self.subTest(tags=tags):
                self.assertIsNone(self.rebuild(*tags))

    def test_attribution_text_is_callable_without_an_instance(self):
        # The tag-only fallback builds credits without a provider instance (no
        # API keys needed); the Unsplash lookup is the instance method
        # rebuild_attribution below (todo 442).
        self.assertEqual(
            PlantImageService.get_attribution_text(
                "unsplash", {"photographer": {"name": "Jane Doe"}}
            ),
            "Photo by Jane Doe on Unsplash",
        )


class UnsplashGetPhotoTest(SimpleTestCase):
    """Todo 442: `GET /photos/:id`, for the backfill's real-name credit."""

    PHOTO = {
        "id": "abc123",
        "description": "Monstera",
        "urls": {"raw": "r", "full": "f", "regular": "g", "small": "s", "thumb": "t"},
        "width": 4000,
        "height": 3000,
        "user": {
            "name": "Jane Doe",
            "username": "janedoe",
            "links": {"html": "https://unsplash.com/@janedoe"},
        },
        "links": {
            "download": "https://unsplash.com/photos/abc123/download",
            "html": "https://unsplash.com/photos/abc123",
        },
        "created_at": "2024-01-01T00:00:00Z",
        "likes": 3,
    }

    def setUp(self):
        cache.clear()

    def test_fetches_the_photo_and_shapes_it_like_a_search_result(self):
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(
            service, "_make_request", return_value=self.PHOTO
        ) as request:
            image_data = service.get_photo("abc123")
        request.assert_called_once_with("photos/abc123")
        self.assertEqual(
            image_data["photographer"],
            {
                "name": "Jane Doe",
                "username": "janedoe",
                "profile_url": "https://unsplash.com/@janedoe",
            },
        )
        self.assertEqual(image_data["source"], "unsplash")

    def test_a_looked_up_photo_is_cached(self):
        # A --dry-run followed by the real run costs one request per image.
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(
            service, "_make_request", return_value=self.PHOTO
        ) as request:
            service.get_photo("cached1")
            service.get_photo("cached1")
        request.assert_called_once()

    def test_no_request_without_a_key_or_for_a_malformed_id(self):
        # The id comes from an image tag editors can change in the CMS, so it
        # must never reach the URL path unless it looks like an Unsplash id.
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(service, "_make_request") as request:
            for bad in ("", "../collections", "abc/def", "a b", None):
                with self.subTest(photo_id=bad):
                    self.assertIsNone(service.get_photo(bad))
            service.access_key = None
            self.assertIsNone(service.get_photo("abc123"))
        request.assert_not_called()

    def test_api_failure_or_malformed_photo_gives_none(self):
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(service, "_make_request", return_value=None):
            self.assertIsNone(service.get_photo("gone1"))
        with mock.patch.object(service, "_make_request", return_value={"id": "x"}):
            self.assertIsNone(service.get_photo("broken1"))


class RebuildAttributionTest(SimpleTestCase):
    """Todo 442: the backfill credits the real name when Unsplash can be asked."""

    LOOKED_UP = {
        "photographer": {
            "name": "Jane Doe",
            "username": "janedoe",
            "profile_url": "https://unsplash.com/@janedoe",
        }
    }
    TAGS = ["unsplash", "botanical", "photographer:janedoe", "unsplash_id:abc123"]

    def service(self, photo):
        service = PlantImageService.__new__(PlantImageService)
        service.unsplash = mock.Mock()
        service.unsplash.get_photo.return_value = photo
        return service

    def test_unsplash_lookup_gives_the_real_name_and_profile_link(self):
        service = self.service(self.LOOKED_UP)
        self.assertEqual(
            service.rebuild_attribution(self.TAGS),
            ("Photo by Jane Doe on Unsplash", f"https://unsplash.com/@janedoe?{UTM}"),
        )
        service.unsplash.get_photo.assert_called_once_with("abc123")

    def test_lookup_failure_falls_back_to_the_tags(self):
        service = self.service(None)
        self.assertEqual(
            service.rebuild_attribution(self.TAGS),
            ("Photo by janedoe on Unsplash", f"https://unsplash.com/@janedoe?{UTM}"),
        )

    def test_lookup_without_a_name_falls_back_to_the_tags(self):
        service = self.service({"photographer": {"name": None}})
        self.assertEqual(
            service.rebuild_attribution(self.TAGS)[0], "Photo by janedoe on Unsplash"
        )

    def test_lookup_recovers_a_credit_the_tags_cannot(self):
        # The services write photographer:unknown when the provider sent none.
        service = self.service(self.LOOKED_UP)
        tags = ["unsplash", "photographer:unknown", "unsplash_id:abc123"]
        self.assertEqual(
            service.rebuild_attribution(tags)[0], "Photo by Jane Doe on Unsplash"
        )

    def test_pexels_and_ai_tags_are_never_looked_up(self):
        # The owner decision scoped the API call to Unsplash (2026-09-28).
        service = self.service(self.LOOKED_UP)
        self.assertEqual(
            service.rebuild_attribution(
                ["pexels", "photographer:Sam_Roe", "pexels_id:7"]
            ),
            ("Photo by Sam Roe from Pexels", ""),
        )
        self.assertEqual(
            service.rebuild_attribution(["ai_generated", "dall_e_3"])[0],
            "AI-generated botanical image (DALL-E 3)",
        )
        service.unsplash.get_photo.assert_not_called()

    def test_ambiguous_or_missing_photo_id_is_not_looked_up(self):
        service = self.service(self.LOOKED_UP)
        for tags in [
            ["unsplash", "photographer:janedoe"],
            ["unsplash", "photographer:janedoe", "unsplash_id:a", "unsplash_id:b"],
            ["unsplash", "pexels", "photographer:x", "unsplash_id:a"],
        ]:
            with self.subTest(tags=tags):
                service.rebuild_attribution(tags)
        service.unsplash.get_photo.assert_not_called()
