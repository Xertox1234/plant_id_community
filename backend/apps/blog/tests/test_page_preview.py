"""
Headless blog preview (web dead-code audit 2026-09-23, M2).

Wagtail's "Preview" button was wired to a React route that only said
"coming soon", and the backend never registered a preview API. Worse,
settings still defined the removed HEADLESS_PREVIEW_CLIENT_URLS, so every
read of the library's settings raised RuntimeError and the button errored.

These tests hit the real URLconf through the Django test client.
"""

from datetime import date
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from wagtail.models import Page
from wagtail_headless_preview.settings import headless_preview_settings

from ..models import BlogIndexPage, BlogPostPage

User = get_user_model()

ENDPOINT = "/api/v2/page_preview/"


class HeadlessPreviewSettingsTestCase(TestCase):
    def test_library_settings_load_without_the_removed_setting(self):
        # The old top-level name makes every attribute read raise RuntimeError.
        self.assertFalse(hasattr(settings, "HEADLESS_PREVIEW_CLIENT_URLS"))
        self.assertTrue(headless_preview_settings.REDIRECT_ON_PREVIEW)
        self.assertEqual(
            headless_preview_settings.CLIENT_URLS["default"],
            settings.HEADLESS_PREVIEW_CLIENT_URL,
        )

    def test_preview_client_origin_may_be_framed_by_the_admin(self):
        policy = getattr(settings, "CONTENT_SECURITY_POLICY", None) or getattr(
            settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY"
        )
        self.assertIn(
            settings.HEADLESS_PREVIEW_CLIENT_ORIGIN,
            policy["DIRECTIVES"]["frame-src"],
        )


class BlogPostPreviewAPITestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="previewauthor", email="preview@example.com"
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Preview Blog", slug="preview-blog")
        root.add_child(instance=self.blog_index)
        self.post = BlogPostPage(
            title="Live title",
            slug="preview-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=self.post)

    def tearDown(self):
        cache.clear()

    def _draft_token(self, title="Draft title"):
        page = BlogPostPage.objects.get(pk=self.post.pk)
        page.title = title  # an unsaved, unpublished edit
        return page.create_page_preview().token

    def test_preview_url_uses_query_parameters_on_the_web_route(self):
        request = RequestFactory().get("/")
        url = self.post.get_preview_url(request, "tok")
        parts = urlsplit(url)
        self.assertEqual(
            f"{parts.scheme}://{parts.netloc}{parts.path}",
            settings.HEADLESS_PREVIEW_CLIENT_URL,
        )
        self.assertEqual(
            parse_qs(parts.query),
            {"content_type": ["blog.blogpostpage"], "token": ["tok"]},
        )

    def test_returns_the_draft_not_the_live_page(self):
        token = self._draft_token()

        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Draft title")
        self.assertEqual(response.json()["slug"], "preview-post")

    def test_does_not_poison_the_live_post_cache(self):
        token = self._draft_token()
        self.client.get(ENDPOINT, {"content_type": "blog.blogpostpage", "token": token})

        live = self.client.get(f"/api/v2/blog-posts/{self.post.pk}/")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["title"], "Live title")

    def test_tampered_token_is_404(self):
        token = self._draft_token()
        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token + "x"}
        )
        self.assertEqual(response.status_code, 404)

    def test_well_signed_but_unknown_token_is_404(self):
        # A valid signature with no stored draft (e.g. garbage-collected).
        token = BlogPostPage.get_preview_signer().sign("id=999999")
        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )
        self.assertEqual(response.status_code, 404)

    def test_non_previewable_content_type_is_404(self):
        token = self._draft_token()
        for content_type in ("users.user", "auth.group", "nope.nothing", "garbage"):
            with self.subTest(content_type=content_type):
                response = self.client.get(
                    ENDPOINT, {"content_type": content_type, "token": token}
                )
                self.assertEqual(response.status_code, 404)

    def test_missing_parameters_are_404(self):
        self.assertEqual(self.client.get(ENDPOINT).status_code, 404)
