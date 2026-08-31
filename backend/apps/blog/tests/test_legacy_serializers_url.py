"""
Regression test for the legacy `apps/blog/serializers.py` module's `url`
field (todo 326) — a second, older blog API surface (mounted at
`/api/v1/blog/posts/`, distinct from the live `/api/v2/blog-posts/` the web
frontend actually calls) with no test coverage before this fix.

`BlogPostPageSerializer.get_url`/`BlogPostListSerializer.get_url` used to
call `request.build_absolute_uri(obj.get_url())` directly — the same
todo-308 landmine: `obj.get_url()` returns an already-absolute,
Site-rooted URL once more than one Wagtail `Site` row exists, which
`build_absolute_uri()` passes through unchanged. Registering a second
`Site` sharing the same root page and requesting through its hostname
proves the fix, matching the pattern in
`apps/blog/tests/test_n_plus_1.py::test_full_url_is_request_derived_not_settings_based`.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from wagtail.models import Site

from ..models import BlogPostPage

User = get_user_model()


class LegacyBlogPostSerializerUrlTestCase(TestCase):
    def setUp(self):
        self.site_root = Site.objects.get(is_default_site=True).root_page
        self.user = User.objects.create_user(
            username="legacyserializertest", email="legacy@example.com"
        )
        self.post = BlogPostPage(
            title="Legacy Serializer Post",
            slug="legacy-serializer-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
        )
        self.site_root.add_child(instance=self.post)

    @override_settings(ALLOWED_HOSTS=["legacy.example.com", "testserver"])
    def test_detail_url_is_request_derived_not_site_rooted(self):
        Site.objects.create(
            hostname="legacy.example.com", port=80, root_page=self.site_root
        )
        response = self.client.get(
            f"/api/v1/blog/posts/{self.post.id}/", SERVER_NAME="legacy.example.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.data["url"].startswith("http://legacy.example.com/"),
            response.data["url"],
        )

    @override_settings(ALLOWED_HOSTS=["legacy.example.com", "testserver"])
    def test_list_url_is_request_derived_not_site_rooted(self):
        Site.objects.create(
            hostname="legacy.example.com", port=80, root_page=self.site_root
        )
        response = self.client.get(
            "/api/v1/blog/posts/", SERVER_NAME="legacy.example.com"
        )
        self.assertEqual(response.status_code, 200)
        urls = [row["url"] for row in response.data["results"]]
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith("http://legacy.example.com/"), url)
