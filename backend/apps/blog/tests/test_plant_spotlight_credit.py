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
UNSPLASH_URL = "https://unsplash.com/?utm_source=plant_community&utm_medium=referral"
PEXELS_CREDIT = "Photo by Sam Roe from Pexels"
PEXELS_URL = "https://www.pexels.com/@samroe"


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


class SafeHttpUrlCredentialsTest(SimpleTestCase):
    def test_rejects_embedded_credentials_like_the_web(self):
        # PR #820: the template and the React renderer must agree.
        creds = "https://user:pass@evil.example/"  # pragma: allowlist secret
        self.assertEqual(safe_http_url(creds), "")
        self.assertEqual(safe_http_url("https://user@evil.example/"), "")
        self.assertEqual(safe_http_url("https://"), "")
        self.assertEqual(safe_http_url("https:///path"), "")


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

    def test_context_splits_an_unsplash_credit_to_link_unsplash(self):
        # Todo 438: the guidelines want the photographer AND Unsplash linked.
        block = spotlight_block()
        value = block.to_python(
            spotlight_raw(image_credit=CREDIT, image_credit_url=CREDIT_URL)
        )
        context = block.get_context(value)
        self.assertEqual(context["credit_lead"], "Photo by Jane Doe")
        self.assertEqual(context["unsplash_href"], UNSPLASH_URL)

    def test_context_does_not_link_unsplash_for_other_credits(self):
        block = spotlight_block()
        for credit in [PEXELS_CREDIT, "on Unsplash", "Photo by X on unsplash", ""]:
            with self.subTest(credit=credit):
                context = block.get_context(
                    block.to_python(spotlight_raw(image_credit=credit))
                )
                self.assertEqual(context["unsplash_href"], "")
                self.assertEqual(context["credit_lead"], "")

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
        html = self.render(image_credit=PEXELS_CREDIT, image_credit_url=PEXELS_URL)
        self.assertInHTML(
            f'<a href="{PEXELS_URL}" target="_blank" rel="noopener noreferrer">'
            f"{PEXELS_CREDIT}</a>",
            html,
        )

    def test_unsplash_credit_links_photographer_and_unsplash(self):
        # Todo 438: "Photo by <a>Jane Doe</a> on <a>Unsplash</a>", both with
        # the UTM params the Unsplash guidelines require.
        html = self.render(image_credit=CREDIT, image_credit_url=CREDIT_URL)
        self.assertInHTML(
            f'<p class="image-credit"><a href="{CREDIT_URL}" target="_blank" '
            'rel="noopener noreferrer">Photo by Jane Doe</a> on '
            f'<a href="{UNSPLASH_URL}" target="_blank" '
            'rel="noopener noreferrer">Unsplash</a></p>',
            html,
        )

    def test_unsplash_credit_without_url_still_links_unsplash(self):
        html = self.render(image_credit=CREDIT)
        self.assertInHTML(
            '<p class="image-credit">Photo by Jane Doe on '
            f'<a href="{UNSPLASH_URL}" target="_blank" '
            'rel="noopener noreferrer">Unsplash</a></p>',
            html,
        )

    def test_non_http_url_renders_credit_as_text_without_link(self):
        html = self.render(
            image_credit=PEXELS_CREDIT, image_credit_url="javascript:alert(1)"
        )
        self.assertIn(PEXELS_CREDIT, html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("<a ", html)

    def test_non_http_url_on_unsplash_credit_links_only_unsplash(self):
        html = self.render(image_credit=CREDIT, image_credit_url="javascript:alert(1)")
        self.assertNotIn("javascript:", html)
        self.assertEqual(html.count("<a "), 1)
        self.assertIn(UNSPLASH_URL.replace("&", "&amp;"), html)  # autoescaped

    def test_credit_without_url_renders_as_text(self):
        html = self.render(image_credit=PEXELS_CREDIT)
        self.assertIn(PEXELS_CREDIT, html)
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

    def test_null_photographer_still_saves_the_image(self):
        # PR #820: the credit is now built BEFORE the save; a provider's
        # "photographer": null must not drop the image.
        value = self.run_command("unsplash", {"photographer": None})
        self.assertEqual(value["image"].pk, self.image.pk)
        self.assertEqual(value["image_credit"], "Photo by Unknown on Unsplash")
        self.assertEqual(value["image_credit_url"], "")

    def test_an_overlong_credit_is_truncated_to_the_block_limit(self):
        # PR #820: a longer value would fail every later admin edit.
        value = self.run_command("pexels", {"photographer": {"name": "N" * 400}})
        self.assertEqual(len(value["image_credit"]), 255)


class PopulatePublishesThroughRevisionTest(TestCase):
    """Todo 438: populate_plant_images writes via save_revision().publish().

    A bare `post.save()` left the admin's latest revision without the image
    (the next admin publish dropped it) and fired no `page_published`, so the
    blog cache served the old response for up to 24h.
    """

    UNSPLASH_DATA = {
        "photographer": {
            "name": "Jane Doe",
            "profile_url": "https://unsplash.com/@janedoe",
        }
    }

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="publishauthor",
            email="publishauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Publish Blog", slug="publish-blog")
        root.add_child(instance=self.blog_index)
        self.image = get_image_model().objects.create(
            title="Monstera", file=get_test_image_file(filename="monstera.png")
        )

    def make_post(self, slug, live=True):
        post = BlogPostPage(
            title=f"Post {slug}",
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[("plant_spotlight", spotlight_raw())],
            live=live,
        )
        self.blog_index.add_child(instance=post)
        return post

    def run_command(self, post):
        out = StringIO()
        with (
            mock.patch(
                "apps.plant_identification.services.plant_image_service."
                "PlantImageService.get_best_plant_image",
                return_value=("unsplash", self.UNSPLASH_DATA, self.image),
            ) as fetch,
            mock.patch(
                "apps.plant_identification.services.plant_image_service."
                "PlantImageService.get_source_stats",
                return_value={},
            ),
            mock.patch(
                "apps.blog.services.blog_cache_service.BlogCacheService."
                "invalidate_blog_post"
            ) as invalidate,
        ):
            call_command("populate_plant_images", post_id=post.id, stdout=out)
        post.refresh_from_db()
        return fetch, invalidate, out.getvalue()

    @staticmethod
    def spotlight(page):
        return next(b for b in page.content_blocks if b.block_type == "plant_spotlight")

    def test_latest_revision_carries_image_and_credit(self):
        post = self.make_post("revision-parity")
        self.run_command(post)
        revision_page = post.get_latest_revision().as_object()
        value = self.spotlight(revision_page).value
        self.assertEqual(value["image"].pk, self.image.pk)
        self.assertEqual(value["image_credit"], CREDIT)
        self.assertEqual(value["image_credit_url"], CREDIT_URL)
        # Published, not left as a draft.
        self.assertTrue(post.live)
        self.assertFalse(post.has_unpublished_changes)
        self.assertEqual(self.spotlight(post).value["image"].pk, self.image.pk)

    def test_publish_invalidates_the_blog_cache(self):
        post = self.make_post("cache-invalidation")
        _, invalidate, _ = self.run_command(post)
        invalidate.assert_called_with(post.slug)

    def test_block_id_is_preserved(self):
        post = self.make_post("block-id")
        block_id = self.spotlight(post).id
        self.run_command(post)
        self.assertEqual(self.spotlight(post).id, block_id)

    def test_page_with_unpublished_draft_is_skipped_before_fetching(self):
        # Publishing a revision built from the live row would discard the
        # editor's draft; the command must leave both alone and say so.
        post = self.make_post("editor-draft")
        post.title = "Editor draft title"
        post.save_revision()
        draft_revision_id = post.latest_revision_id

        fetch, invalidate, out = self.run_command(post)

        fetch.assert_not_called()
        invalidate.assert_not_called()
        self.assertIn("unpublished draft changes", out)
        self.assertEqual(post.latest_revision_id, draft_revision_id)
        self.assertTrue(post.has_unpublished_changes)
        self.assertIsNone(self.spotlight(post).value["image"])
        self.assertEqual(
            post.get_latest_revision().as_object().title, "Editor draft title"
        )

    def test_page_that_is_not_live_gets_a_draft_revision_and_stays_unpublished(self):
        post = self.make_post("never-published", live=False)
        _, invalidate, out = self.run_command(post)
        self.assertFalse(post.live)
        invalidate.assert_not_called()
        value = self.spotlight(post.get_latest_revision().as_object()).value
        self.assertEqual(value["image"].pk, self.image.pk)
        self.assertEqual(value["image_credit"], CREDIT)
        self.assertIn("draft revision", out)
