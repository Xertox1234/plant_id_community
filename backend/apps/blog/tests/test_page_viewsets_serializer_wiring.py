"""
Tests for BlogIndexPageViewSet, BlogCategoryPageViewSet, and
BlogAuthorPageViewSet's serializer wiring (todo 324).

Before this fix, all three viewsets set `serializer_class` — a plain DRF
`GenericAPIView` attribute Wagtail's own `get_serializer_class()` never
reads. Wagtail instead built a serializer *dynamically* from
`model.api_fields`, which none of `BlogIndexPage`/`BlogCategoryPage`/
`BlogAuthorPage` define, so every custom field (`featured_posts`,
`categories`, `posts`, `author`, `bio`, `recent_posts`, etc.) silently
vanished from the response with no error — live-confirmed via
`/api/v2/blog-authors/` returning only stock Wagtail page fields. These
tests hit the real `/api/v2/` routes and assert the custom fields are
actually present, which a `base_serializer_class` rename alone would NOT
have fixed (Wagtail's dynamic construction ignores a serializer's own
`Meta.fields` regardless of which attribute name points at it) — see the
`get_serializer_class()` docstrings in `apps/blog/api/viewsets.py`.

Also covers the accompanying todo-308-class `url` field bug these
serializers had (no `get_url` override -> DRF auto-builds `url` from
`Page.get_url(request=None)`, not the request).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from wagtail.models import Site

from ..models import BlogAuthorPage, BlogCategory, BlogCategoryPage, BlogIndexPage

User = get_user_model()


def _site_root():
    """The default Wagtail `Site`'s actual root page ("/home/"), not the
    invisible tree root (`Page.objects.get(id=1)`). `get_url_parts()` only
    resolves a page that's a descendant of a configured `Site`'s root — a
    page added directly under the bare tree root isn't under any Site and
    `get_url()`/`get_url_parts()` return `None`."""
    return Site.objects.get(is_default_site=True).root_page


class BlogIndexPageViewSetSerializerTestCase(TestCase):
    def setUp(self):
        self.blog_index = BlogIndexPage(title="Index Test", slug="index-test")
        _site_root().add_child(instance=self.blog_index)

    def test_custom_fields_present_in_response(self):
        response = self.client.get(f"/api/v2/blog-index/{self.blog_index.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for field in ("featured_posts", "categories", "recent_posts"):
            self.assertIn(field, data)

    def test_url_is_request_derived(self):
        response = self.client.get(f"/api/v2/blog-index/{self.blog_index.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["url"].startswith("http://testserver/"))


class BlogCategoryPageViewSetSerializerTestCase(TestCase):
    def setUp(self):
        category = BlogCategory.objects.create(name="Succulents", slug="succulents")
        self.category_page = BlogCategoryPage(
            title="Succulents", slug="succulents-page", category=category
        )
        _site_root().add_child(instance=self.category_page)

    def test_custom_fields_present_in_response(self):
        response = self.client.get(f"/api/v2/blog-categories/{self.category_page.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for field in ("category", "posts"):
            self.assertIn(field, data)
        self.assertEqual(data["category"]["slug"], "succulents")

    def test_url_is_request_derived(self):
        response = self.client.get(f"/api/v2/blog-categories/{self.category_page.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["url"].startswith("http://testserver/"))


class BlogAuthorPageViewSetSerializerTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="authorpagetest", email="authorpagetest@example.com"
        )
        self.author_page = BlogAuthorPage(
            title="Author Test",
            slug="author-test",
            author=self.user,
            bio="<p>Bio.</p>",
        )
        _site_root().add_child(instance=self.author_page)

    def test_custom_fields_present_in_response(self):
        response = self.client.get(f"/api/v2/blog-authors/{self.author_page.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for field in ("author", "bio", "expertise_areas", "post_count", "recent_posts"):
            self.assertIn(field, data)
        self.assertEqual(data["author"]["username"], "authorpagetest")

    def test_url_is_request_derived(self):
        response = self.client.get(f"/api/v2/blog-authors/{self.author_page.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["url"].startswith("http://testserver/"))
