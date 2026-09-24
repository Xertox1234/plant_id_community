"""
Headless blog preview (web dead-code audit 2026-09-23, M2).

Wagtail's "Preview" button was wired to a React route that only said
"coming soon", and the backend never registered a preview API. Worse,
settings still defined the removed HEADLESS_PREVIEW_CLIENT_URLS, so every
read of the library's settings raised RuntimeError and the button errored.

These tests hit the real URLconf through the Django test client.
"""

import ast
import inspect
import time
from datetime import date
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, TestCase
from plant_community_backend import settings as settings_module
from wagtail.models import Page
from wagtail_headless_preview.models import HeadlessPreviewMixin
from wagtail_headless_preview.settings import headless_preview_settings

from ..api.viewsets import BlogPostPreviewAPIViewSet
from ..models import BlogCategory, BlogIndexPage, BlogPostPage

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

    def test_both_csp_dicts_take_frame_src_from_the_shared_constant(self):
        # Tests run with one DEBUG value, so only one CSP dict is ever built;
        # the enforcing production dict can't be read at runtime. Pin the
        # source instead: every "frame-src" entry is the PREVIEW_FRAME_SRC name,
        # and that constant carries the preview origin (todo 407, item 7).
        self.assertIn(
            settings.HEADLESS_PREVIEW_CLIENT_ORIGIN, settings.PREVIEW_FRAME_SRC
        )
        tree = ast.parse(inspect.getsource(settings_module))
        values = [
            value
            for node in ast.walk(tree)
            if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and key.value == "frame-src"
        ]
        self.assertEqual(len(values), 2)  # report-only (DEBUG) + enforcing
        for value in values:
            self.assertIsInstance(value, ast.Name)
            self.assertEqual(value.id, "PREVIEW_FRAME_SRC")

    def test_old_path_template_client_url_is_rejected(self):
        # The pre-0.9 format kept the env var's name (todo 407, item 2).
        with self.assertRaises(ImproperlyConfigured):
            settings_module.validate_preview_client_url(
                "https://web.example/{content_type}/{token}/"
            )
        settings_module.validate_preview_client_url("https://web.example/blog/preview")


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

    def test_previews_a_brand_new_never_saved_post(self):
        # Wagtail offers Preview on the create screen; the draft then has no pk
        # (PagePreview.as_page() restores pk=None). Code review round 1 found
        # this 500'd in get_comment_count's obj.comments query.
        draft = BlogPostPage(
            title="Brand new draft",
            slug="brand-new-draft",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>first words</p>",
            content_blocks=[],
        )
        # Exactly what Wagtail 8's pages PreviewOnCreateView.get_object() does
        # (wagtail/admin/views/pages/preview.py): populate treebeard's
        # depth/path from the parent so get_parent() resolves. The library's
        # create_page_preview() needs that for its "parent_id=…" identifier.
        parent = self.blog_index
        draft.depth = parent.depth + 1
        if parent.is_leaf():
            draft.path = draft._get_path(parent.path, draft.depth, 1)
        else:
            draft.path = parent.get_last_child()._inc_path()
        token = draft.create_page_preview().token

        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Brand new draft")

    def test_never_saved_draft_serializes_a_populated_relation(self):
        # Round 2 (item 11): mirror the get_form() step too, which gives the
        # pk-less draft its relations. A category must serialize, not 500.
        category = BlogCategory.objects.create(name="Ferns", slug="ferns")
        draft = BlogPostPage(
            title="Draft with category",
            slug="draft-with-category",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>first words</p>",
            content_blocks=[],
        )
        draft.categories = [category]
        parent = self.blog_index
        draft.depth = parent.depth + 1
        if parent.is_leaf():
            draft.path = draft._get_path(parent.path, draft.depth, 1)
        else:
            draft.path = parent.get_last_child()._inc_path()
        token = draft.create_page_preview().token

        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["slug"] for c in response.json()["categories"]], ["ferns"])

    def test_preview_response_is_never_cached(self):
        token = self._draft_token()
        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])

    def test_expired_token_is_404(self):
        # The library never expires a token (todo 407, item 1).
        # Mint the token in the past rather than patch the clock during the
        # request: a patched time.time leaks into the Redis cache pickler.
        max_age = BlogPostPreviewAPIViewSet.PREVIEW_TOKEN_MAX_AGE
        minted_at = time.time() - max_age - 5
        with mock.patch("django.core.signing.time.time", new=lambda: minted_at):
            token = self._draft_token()
        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )
        self.assertEqual(response.status_code, 404)
        # And a fresh token for the same draft still works.
        fresh = self.client.get(
            ENDPOINT,
            {"content_type": "blog.blogpostpage", "token": self._draft_token()},
        )
        self.assertEqual(fresh.status_code, 200)

    def test_only_the_listing_route_is_exposed(self):
        # The inherited <int:pk>/ route ignored pk and find/ searched live
        # pages (todo 407, item 3).
        token = self._draft_token()
        params = {"content_type": "blog.blogpostpage", "token": token}
        self.assertEqual(
            self.client.get(f"{ENDPOINT}{self.post.pk}/", params).status_code, 404
        )
        self.assertEqual(self.client.get(f"{ENDPOINT}find/", params).status_code, 404)

    def test_a_warm_live_post_cache_does_not_leak_into_the_preview(self):
        # Read direction of the cache bypass (item 5): warm the live post's
        # cache entry first, then the preview must still serve the draft.
        live = self.client.get(f"/api/v2/blog-posts/{self.post.pk}/")
        self.assertEqual(live.json()["title"], "Live title")
        token = self._draft_token()

        response = self.client.get(
            ENDPOINT, {"content_type": "blog.blogpostpage", "token": token}
        )

        self.assertEqual(response.json()["title"], "Draft title")

    def test_a_preview_model_that_is_not_a_blog_post_is_404(self):
        # BlogPostPage is the only HeadlessPreviewMixin model, so nothing
        # exercised the issubclass(model, BlogPostPage) half (item 4).
        other_draft = BlogPostPage.objects.get(pk=self.post.pk)

        class OtherPreviewable(HeadlessPreviewMixin):
            @classmethod
            def get_page_from_preview_token(cls, token):
                return other_draft

        fake_ct = mock.Mock()
        fake_ct.model_class.return_value = OtherPreviewable
        with mock.patch(
            "django.contrib.contenttypes.models.ContentTypeManager.get_by_natural_key",
            return_value=fake_ct,
        ):
            # A validly signed token (the mixin's salt), so the request gets
            # past the signature check and only the model guard can stop it.
            token = OtherPreviewable.get_preview_signer().sign("id=1")
            response = self.client.get(
                ENDPOINT, {"content_type": "other.previewable", "token": token}
            )
        self.assertEqual(response.status_code, 404)

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
