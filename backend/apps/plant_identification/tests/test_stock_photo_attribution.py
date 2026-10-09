"""Stock-photo credit link (todo 376).

`PlantImageService.get_attribution_url` supplies the link stored beside the
credit text in the blog `plant_spotlight` block. Unsplash's API guidelines
require referral UTM parameters on links back to Unsplash; a non-http(s)
provider value must never be stored as a link.
"""

from unittest import mock

from apps.plant_identification.services.plant_image_service import (
    CREDIT_FALLBACK,
    CREDIT_FROM_LOOKUP,
    CREDIT_FROM_TAGS,
    CREDIT_LOOKUP_UNAVAILABLE,
    PlantImageService,
)
from apps.plant_identification.services.unsplash_service import (
    PHOTO_FOUND,
    PHOTO_GONE,
    PHOTO_LOOKUP_DISABLED,
    PHOTO_UNAVAILABLE,
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
            service, "_request", return_value=(200, self.PHOTO)
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
            service, "_request", return_value=(200, self.PHOTO)
        ) as request:
            service.get_photo("cached1")
            service.get_photo("cached1")
        request.assert_called_once()

    def test_no_request_without_a_key_or_for_a_malformed_id(self):
        # The id comes from an image tag editors can change in the CMS, so it
        # must never reach the URL path unless it looks like an Unsplash id.
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(service, "_request") as request:
            for bad in ("", "../collections", "abc/def", "a b", None):
                with self.subTest(photo_id=bad):
                    self.assertIsNone(service.get_photo(bad))
            service.access_key = None
            self.assertIsNone(service.get_photo("abc123"))
        request.assert_not_called()

    def test_api_failure_or_malformed_photo_gives_none(self):
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(service, "_request", return_value=(None, None)):
            self.assertIsNone(service.get_photo("gone1"))
        with mock.patch.object(service, "_request", return_value=(200, {"id": "x"})):
            self.assertIsNone(service.get_photo("broken1"))

    # --- todo 530: why a lookup failed, and remembering a 404 ---

    def test_lookup_says_why_it_found_nothing(self):
        service = UnsplashImageService(access_key="k")
        cases = [
            ((404, None), PHOTO_GONE),
            ((None, None), PHOTO_UNAVAILABLE),  # rate limit / network
            ((503, None), PHOTO_UNAVAILABLE),
            ((200, {"id": "x"}), PHOTO_UNAVAILABLE),  # malformed answer
        ]
        for index, (answer, expected) in enumerate(cases):
            with self.subTest(answer=answer):
                with mock.patch.object(service, "_request", return_value=answer):
                    self.assertEqual(
                        service.lookup_photo(f"photo{index}"), (expected, None)
                    )
        with mock.patch.object(service, "_request") as request:
            self.assertEqual(service.lookup_photo("../x"), (PHOTO_GONE, None))
            service.access_key = None
            self.assertEqual(
                service.lookup_photo("abc123"), (PHOTO_LOOKUP_DISABLED, None)
            )
        request.assert_not_called()

    def test_a_deleted_photo_is_asked_about_once(self):
        # A re-run must not spend the 50/h budget on a photo Unsplash 404'd.
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(
            service, "_request", return_value=(404, None)
        ) as request:
            self.assertEqual(service.lookup_photo("gone2"), (PHOTO_GONE, None))
            self.assertEqual(service.lookup_photo("gone2"), (PHOTO_GONE, None))
        request.assert_called_once()

    def test_a_transient_failure_is_not_remembered(self):
        service = UnsplashImageService(access_key="k")
        with mock.patch.object(
            service, "_request", return_value=(None, None)
        ) as request:
            service.lookup_photo("flaky1")
            service.lookup_photo("flaky1")
        self.assertEqual(request.call_count, 2)


class UnsplashRateCounterTest(SimpleTestCase):
    """Todo 530: the shared counter moves only on a real header."""

    def setUp(self):
        cache.clear()

    def request(self, status_code=200, headers=None):
        service = UnsplashImageService(access_key="k")
        response = mock.Mock(status_code=status_code, headers=headers or {})
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None
        with mock.patch.object(service.session, "get", return_value=response):
            return service, service._request("photos/abc123")

    def test_a_response_without_the_header_leaves_the_counter_alone(self):
        service, answer = self.request()
        self.assertEqual(answer, (200, {"ok": True}))
        self.assertIsNone(cache.get(UnsplashImageService.RATE_LIMIT_KEY))
        self.assertFalse(service.is_rate_limited())

    def test_a_malformed_header_leaves_the_counter_alone(self):
        service, _ = self.request(headers={"X-Ratelimit-Remaining": "lots"})
        self.assertIsNone(cache.get(UnsplashImageService.RATE_LIMIT_KEY))

    def test_the_header_sets_the_counter(self):
        service, _ = self.request(headers={"X-Ratelimit-Remaining": "45"})
        self.assertEqual(cache.get(UnsplashImageService.RATE_LIMIT_KEY), 5)
        _, _ = self.request(headers={"X-Ratelimit-Remaining": "0"})
        self.assertTrue(service.is_rate_limited())

    def test_a_404_is_reported_not_raised(self):
        _, answer = self.request(status_code=404)
        self.assertEqual(answer, (404, None))


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

    def service(self, photo, status=None):
        if status is None:
            status = PHOTO_FOUND if photo else PHOTO_GONE
        service = PlantImageService.__new__(PlantImageService)
        service.unsplash = mock.Mock()
        service.unsplash.lookup_photo.return_value = (status, photo)
        service.unsplash.is_rate_limited.return_value = False
        return service

    def test_unsplash_lookup_gives_the_real_name_and_profile_link(self):
        service = self.service(self.LOOKED_UP)
        self.assertEqual(
            service.rebuild_attribution(self.TAGS),
            ("Photo by Jane Doe on Unsplash", f"https://unsplash.com/@janedoe?{UTM}"),
        )
        service.unsplash.lookup_photo.assert_called_once_with("abc123")

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
        service.unsplash.lookup_photo.assert_not_called()

    def test_ambiguous_or_missing_photo_id_is_not_looked_up(self):
        service = self.service(self.LOOKED_UP)
        for tags in [
            ["unsplash", "photographer:janedoe"],
            ["unsplash", "photographer:janedoe", "unsplash_id:a", "unsplash_id:b"],
            ["unsplash", "pexels", "photographer:x", "unsplash_id:a"],
            ["unsplash", "photographer:janedoe", "unsplash_id:"],  # todo 530
            ["unsplash", "photographer:janedoe", "unsplash_id:  "],
        ]:
            with self.subTest(tags=tags):
                service.rebuild_attribution(tags)
        service.unsplash.lookup_photo.assert_not_called()


class RebuildAttributionBasisTest(SimpleTestCase):
    """Todo 530: the backfill can tell a named credit from a fallback."""

    TAGS = RebuildAttributionTest.TAGS
    service = RebuildAttributionTest.service

    def test_each_outcome_names_its_basis(self):
        username = (
            "Photo by janedoe on Unsplash",
            f"https://unsplash.com/@janedoe?{UTM}",
        )
        cases = [
            (RebuildAttributionTest.LOOKED_UP, PHOTO_FOUND, CREDIT_FROM_LOOKUP),
            ({"photographer": {"name": ""}}, PHOTO_FOUND, CREDIT_FALLBACK),
            (None, PHOTO_GONE, CREDIT_FALLBACK),
            (None, PHOTO_LOOKUP_DISABLED, CREDIT_FALLBACK),
            (None, PHOTO_UNAVAILABLE, CREDIT_LOOKUP_UNAVAILABLE),
        ]
        for photo, status, basis in cases:
            with self.subTest(status=status, basis=basis):
                credit, got = self.service(
                    photo, status
                ).rebuild_attribution_with_basis(self.TAGS)
                self.assertEqual(got, basis)
                if basis != CREDIT_FROM_LOOKUP:
                    self.assertEqual(credit, username)

    def test_no_lookup_is_tags_basis(self):
        service = self.service(None)
        self.assertEqual(
            service.rebuild_attribution_with_basis(["pexels", "photographer:Sam_Roe"]),
            (("Photo by Sam Roe from Pexels", ""), CREDIT_FROM_TAGS),
        )
        self.assertEqual(
            service.rebuild_attribution_with_basis(["botanical"]),
            (None, CREDIT_FROM_TAGS),
        )
