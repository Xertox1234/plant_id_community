"""Stock-photo credit on the `plant_spotlight` block (todo 376).

Unsplash and Pexels require a credit with a link back ON DISPLAY. The
`populate_plant_images` command writes `image_credit`/`image_credit_url`
into the block alongside the image; these tests pin that the credit reaches
every render path (Wagtail template and API v2) and that a non-http(s) URL
never becomes an `href`.
"""

from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page

from ..blocks import PlantSpotlightBlock, safe_http_url
from ..models import BlogIndexPage, BlogPostPage

User = get_user_model()

CREDIT = "Photo by Jane Doe on Unsplash"
CREDIT_URL = (
    "https://unsplash.com/@janedoe?utm_source=plant_community&utm_medium=referral"
)


def spotlight_block():
    return BlogPostPage._meta.get_field("content_blocks").stream_block.child_blocks[
        "plant_spotlight"
    ]


def spotlight_raw(**overrides):
    raw = {
        "plant_name": "Monstera",
        "scientific_name": "Monstera deliciosa",
        "description": "<p>A climbing aroid.</p>",
        "care_difficulty": "easy",
        "image": None,
    }
    raw.update(overrides)
    return raw


class SafeHttpUrlTest(SimpleTestCase):
    def test_accepts_absolute_http_and_https(self):
        self.assertEqual(safe_http_url("https://a.example/x"), "https://a.example/x")
        self.assertEqual(safe_http_url("http://a.example"), "http://a.example")

    def test_rejects_every_other_shape(self):
        for url in [
            "javascript:alert(1)",
            "JavaScript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "mailto:a@example.com",
            "//evil.example",
            "/relative/path",
            "https:///no-host",
            "",
            None,
        ]:
            with self.subTest(url=url):
                self.assertEqual(safe_http_url(url), "")


class PlantSpotlightBlockTest(SimpleTestCase):
    def test_block_is_the_credit_aware_subclass(self):
        self.assertIsInstance(spotlight_block(), PlantSpotlightBlock)

    def test_context_exposes_vetted_credit_href(self):
        block = spotlight_block()
        value = block.to_python(
            spotlight_raw(image_credit=CREDIT, image_credit_url=CREDIT_URL)
        )
        self.assertEqual(block.get_context(value)["credit_href"], CREDIT_URL)

    def test_context_refuses_javascript_url(self):
        block = spotlight_block()
        value = block.to_python(
            spotlight_raw(image_credit=CREDIT, image_credit_url="javascript:alert(1)")
        )
        self.assertEqual(block.get_context(value)["credit_href"], "")

    def test_block_saved_before_the_credit_fields_still_loads(self):
        block = spotlight_block()
        value = block.to_python(spotlight_raw())
        self.assertFalse(value.get("image_credit"))
        self.assertEqual(block.get_context(value)["credit_href"], "")

    def test_api_representation_includes_credit(self):
        block = spotlight_block()
        value = block.to_python(
            spotlight_raw(image_credit=CREDIT, image_credit_url=CREDIT_URL)
        )
        api = block.get_api_representation(value)
        self.assertEqual(api["image_credit"], CREDIT)
        self.assertEqual(api["image_credit_url"], CREDIT_URL)


class PlantSpotlightTemplateCreditTest(TestCase):
    """The Wagtail template renders the credit under the image."""

    def setUp(self):
        self.image = get_image_model().objects.create(
            title="Monstera", file=get_test_image_file(filename="monstera.png")
        )

    def render(self, **overrides):
        block = spotlight_block()
        return block.render(
            block.to_python(spotlight_raw(image=self.image.pk, **overrides))
        )

    def test_renders_credit_as_safe_external_link(self):
        html = self.render(image_credit=CREDIT, image_credit_url=CREDIT_URL)
        self.assertIn(CREDIT, html)
        self.assertInHTML(
            f'<a href="{CREDIT_URL}" target="_blank" rel="noopener noreferrer">'
            f"{CREDIT}</a>",
            html,
        )

    def test_non_http_url_renders_credit_as_text_without_link(self):
        html = self.render(image_credit=CREDIT, image_credit_url="javascript:alert(1)")
        self.assertIn(CREDIT, html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("<a ", html)

    def test_credit_without_url_renders_as_text(self):
        html = self.render(image_credit=CREDIT)
        self.assertIn(CREDIT, html)
        self.assertNotIn("<a ", html)

    def test_no_credit_renders_no_credit_markup(self):
        html = self.render()
        self.assertNotIn("image-credit", html)

    def test_credit_is_not_rendered_without_an_image(self):
        block = spotlight_block()
        html = block.render(
            block.to_python(
                spotlight_raw(image_credit=CREDIT, image_credit_url=CREDIT_URL)
            )
        )
        self.assertNotIn(CREDIT, html)


class PlantSpotlightCreditFlowTest(TestCase):
    """populate_plant_images -> stored block -> API v2 output."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="creditauthor",
            email="creditauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Credit Blog", slug="credit-blog")
        root.add_child(instance=self.blog_index)
        self.image = get_image_model().objects.create(
            title="Monstera", file=get_test_image_file(filename="monstera.png")
        )
        self.post = BlogPostPage(
            title="Spotlight Credit Post",
            slug="spotlight-credit-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", spotlight_raw())],
        )
        self.blog_index.add_child(instance=self.post)

    def run_command(self, source, image_data):
        # Patch only the provider lookup: the real get_attribution_text /
        # get_attribution_url run, so this pins the text and the UTM link.
        with (
            mock.patch(
                "apps.plant_identification.services.plant_image_service."
                "PlantImageService.get_best_plant_image",
                return_value=(source, image_data, self.image),
            ),
            mock.patch(
                "apps.plant_identification.services.plant_image_service."
                "PlantImageService.get_source_stats",
                return_value={},
            ),
        ):
            call_command(
                "populate_plant_images", post_id=self.post.id, stdout=StringIO()
            )
        self.post.refresh_from_db()
        spotlight = next(
            b for b in self.post.content_blocks if b.block_type == "plant_spotlight"
        )
        return spotlight.value

    def test_unsplash_credit_is_stored_with_utm_link(self):
        value = self.run_command(
            "unsplash",
            {
                "photographer": {
                    "name": "Jane Doe",
                    "username": "janedoe",
                    "profile_url": "https://unsplash.com/@janedoe",
                }
            },
        )
        self.assertEqual(value["image"].pk, self.image.pk)
        self.assertEqual(value["image_credit"], CREDIT)
        self.assertEqual(value["image_credit_url"], CREDIT_URL)

    def test_pexels_credit_is_stored(self):
        value = self.run_command(
            "pexels",
            {
                "photographer": {
                    "name": "Sam Roe",
                    "url": "https://www.pexels.com/@samroe",
                }
            },
        )
        self.assertEqual(value["image_credit"], "Photo by Sam Roe from Pexels")
        self.assertEqual(value["image_credit_url"], "https://www.pexels.com/@samroe")

    def test_ai_image_gets_disclosure_text_and_no_link(self):
        value = self.run_command("ai", {})
        self.assertEqual(
            value["image_credit"], "AI-generated botanical image (DALL-E 3)"
        )
        self.assertFalse(value["image_credit_url"])

    def test_api_serves_the_stored_credit(self):
        self.run_command(
            "unsplash",
            {
                "photographer": {
                    "name": "Jane Doe",
                    "profile_url": "https://unsplash.com/@janedoe",
                }
            },
        )
        response = self.client.get(f"/api/v2/blog-posts/{self.post.id}/")
        self.assertEqual(response.status_code, 200)
        spotlight = next(
            b for b in response.data["content_blocks"] if b["type"] == "plant_spotlight"
        )
        self.assertEqual(spotlight["value"]["image_credit"], CREDIT)
        self.assertEqual(spotlight["value"]["image_credit_url"], CREDIT_URL)
