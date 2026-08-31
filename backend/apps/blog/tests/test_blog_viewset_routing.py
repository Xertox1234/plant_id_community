"""
Tests for BlogPostPageViewSet's manually-routed @action endpoints (todo 307).

Wagtail's API router only auto-mounts list/retrieve/find — every custom
@action needs its own explicit path() entry in
plant_community_backend/urls.py, exactly like `popular` already had. These
tests hit the REAL urlconf via the Django test client (not
ViewSet.as_view() direct dispatch, which several other blog tests use and
which proves nothing about routing) to confirm `featured`, `recent`,
`by_category`, `search_suggestions`, and `related` are actually reachable
over HTTP, plus a routing-parity guard so a future unrouted action fails
loudly instead of silently shipping unreachable code again.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from plant_community_backend import urls as project_urls
from wagtail.models import Page

from ..api.viewsets import BlogPostPageViewSet
from ..models import BlogCategory, BlogIndexPage, BlogPostPage

User = get_user_model()


class BlogPostPageViewSetRoutingParityTestCase(TestCase):
    """Drift guard: every @action on BlogPostPageViewSet must have a manual
    path() entry in urls.py, or it's unreachable dead code (todo 307)."""

    def test_all_extra_actions_are_routed(self):
        # Keyed by pattern string, not just a membership set, so we can also
        # check that the matched path() actually dispatches to the RIGHT
        # action — a route wired with the correct path text but the wrong
        # `{"get": "..."}` mapping (e.g. a copy-paste error) would pass a
        # pattern-string-only check while still 404ing/misrouting in prod.
        patterns_by_str = {str(p.pattern): p for p in project_urls.urlpatterns}

        for action_func in BlogPostPageViewSet.get_extra_actions():
            if action_func.detail:
                expected = f"api/v2/blog-posts/<int:pk>/{action_func.url_path}/"
            else:
                expected = f"api/v2/blog-posts/{action_func.url_path}/"
            self.assertIn(
                expected,
                patterns_by_str,
                f"Action '{action_func.__name__}' has no manual path() entry "
                f"in urls.py (expected pattern: {expected!r}) — Wagtail's "
                "API router does not auto-mount @action-decorated methods.",
            )
            callback = patterns_by_str[expected].callback
            self.assertIs(
                callback.cls,
                BlogPostPageViewSet,
                f"Path {expected!r} is not dispatched by BlogPostPageViewSet.",
            )
            self.assertEqual(
                callback.actions.get("get"),
                action_func.__name__,
                f"Path {expected!r} is wired to action "
                f"{callback.actions.get('get')!r}, not {action_func.__name__!r}.",
            )


class BlogPostPageViewSetRoutedActionsHTTPTestCase(TestCase):
    """HTTP-level tests hitting the real URLconf for each newly-routed action."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="routingauthor",
            email="routing@example.com",
            password="pass",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Routing Blog", slug="routing-blog")
        root.add_child(instance=self.blog_index)

        self.category = BlogCategory.objects.create(
            name="Routing Cat", slug="routing-cat", is_featured=True
        )

        self.featured_post = self._make_post("featured-post", is_featured=True)
        self.plain_post = self._make_post("plain-post")
        self._attach_category(self.plain_post, self.category)

    def tearDown(self):
        cache.clear()

    def _make_post(self, slug, is_featured=False):
        post = BlogPostPage(
            title=slug,
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
            is_featured=is_featured,
        )
        self.blog_index.add_child(instance=post)
        return post

    def _attach_category(self, post, category):
        # ParentalManyToManyField only commits in-memory M2M changes on
        # page.save(); add_child already saved the page without categories,
        # so write to the junction table directly — same pattern as
        # ByCategoryQueryCountTestCase in test_blog_viewsets_caching.py.
        through = BlogPostPage.categories.through
        through.objects.get_or_create(blogpostpage=post, blogcategory=category)

    def test_featured_action_is_routed_and_returns_featured_posts(self):
        response = self.client.get("/api/v2/blog-posts/featured/")
        self.assertEqual(response.status_code, 200)
        slugs = {post["slug"] for post in response.json()}
        self.assertIn("featured-post", slugs)
        self.assertNotIn("plain-post", slugs)

    def test_recent_action_is_routed_and_returns_posts(self):
        response = self.client.get("/api/v2/blog-posts/recent/")
        self.assertEqual(response.status_code, 200)
        slugs = {post["slug"] for post in response.json()}
        self.assertIn("featured-post", slugs)
        self.assertIn("plain-post", slugs)

    def test_by_category_action_is_routed_and_groups_posts(self):
        response = self.client.get("/api/v2/blog-posts/by_category/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["category"]["slug"], "routing-cat")
        post_slugs = {post["slug"] for post in data[0]["posts"]}
        self.assertIn("plain-post", post_slugs)

    def test_search_suggestions_action_is_routed(self):
        response = self.client.get(
            "/api/v2/blog-posts/search_suggestions/", {"q": "featured"}
        )
        self.assertEqual(response.status_code, 200)
        titles = {row["text"] for row in response.json() if row["type"] == "title"}
        self.assertIn("featured-post", titles)

    def test_related_action_is_routed_and_returns_category_matches(self):
        related_post = self._make_post("related-post")
        self._attach_category(related_post, self.category)

        response = self.client.get(f"/api/v2/blog-posts/{self.plain_post.id}/related/")
        self.assertEqual(response.status_code, 200)
        slugs = {post["slug"] for post in response.json()}
        self.assertIn("related-post", slugs)
        self.assertNotIn("plain-post", slugs)  # self excluded


class BlogPostPageViewSetOrderingTestCase(TestCase):
    """Regression test: featured()/recent() sliced an unordered queryset with
    no .order_by() (found in the todo 307 review's wagtail-reviewer pass,
    empirically reproduced) — /recent/ did not actually return posts in
    recency order. Posts are created in a scrambled order relative to their
    first_published_at so a bug that relies on creation/tree order instead
    of publish recency is caught."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="orderingauthor",
            email="ordering@example.com",
            password="pass",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Ordering Blog", slug="ordering-blog")
        root.add_child(instance=self.blog_index)

        now = timezone.now()
        # Created in the order middle, oldest, newest — deliberately NOT the
        # same order as their first_published_at, so ordering by creation
        # order would fail these assertions.
        self._make_post("middle-post", now - timedelta(days=5))
        self._make_post("oldest-post", now - timedelta(days=10))
        self._make_post("newest-post", now - timedelta(days=1))

    def tearDown(self):
        cache.clear()

    def _make_post(self, slug, first_published_at):
        post = BlogPostPage(
            title=slug,
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
            is_featured=True,
        )
        self.blog_index.add_child(instance=post)
        # Wagtail auto-stamps first_published_at to "now" on first live save;
        # override it directly so the three posts have distinguishable,
        # deliberately-scrambled-vs-creation-order timestamps.
        BlogPostPage.objects.filter(pk=post.pk).update(
            first_published_at=first_published_at
        )
        return post

    def test_recent_orders_by_first_published_at_descending(self):
        response = self.client.get("/api/v2/blog-posts/recent/")
        self.assertEqual(response.status_code, 200)
        slugs = [post["slug"] for post in response.json()]
        self.assertEqual(slugs, ["newest-post", "middle-post", "oldest-post"])

    def test_featured_orders_by_first_published_at_descending(self):
        response = self.client.get("/api/v2/blog-posts/featured/")
        self.assertEqual(response.status_code, 200)
        slugs = [post["slug"] for post in response.json()]
        self.assertEqual(slugs, ["newest-post", "middle-post", "oldest-post"])
