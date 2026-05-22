"""
N+1 query regression tests for the DRF blog API list endpoints (todo 079).

The four blog list endpoints serialize a `post_count` / `comment_count` on every
row. The naive implementation issued one `COUNT(*)` query per serialized object
(an N+1 pattern): the query count grew linearly with the number of objects on
the page. The fix annotates the counts on the queryset in `apps/blog/views.py`
so the serializers in `apps/blog/serializers.py` read an annotation
(`hasattr(obj, "_post_count")` / `_comment_count`) instead of issuing a COUNT.

These tests prove the fix holds by counting only the ``SELECT COUNT(...)``
queries issued while serving each endpoint, with a SMALL fixture set and then
again with a larger one. The per-row COUNT that the naive code issued (one
``SELECT COUNT(*)`` per serialized row for the count field) is exactly that
shape; the annotated fix folds the count into the main SELECT and issues no
extra COUNT query. If the COUNT-query total is EQUAL across the small and
large fixtures, the count fields do not scale with object count — no N+1. A
regression (reintroducing the per-row COUNT) makes the larger fixture issue
more COUNT queries and fails the assertion.

Counting only COUNT-shaped queries (rather than every query) keeps the
assertion focused on what todo 079 fixed — the serializer count N+1 — and
immune to unrelated per-row query patterns elsewhere in the serializer chain
(e.g. the pre-existing ``expertise_areas`` taggit N+1 on the authors endpoint,
which is out of scope for this todo).

This is a relative O(1) assertion (small N == large N), which is intentionally
more robust than an absolute `assertEqual(count, N)` against Wagtail's variable
base-query plumbing — see docs/patterns/performance/query-optimization.md.

Object counts stay at/below 6 so every object lands on page 1 of the blog
pagination (page_size = 12 — see BlogPagination in apps/blog/views.py).
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from wagtail.models import Page

from ..models import (
    BlogAuthorPage,
    BlogCategory,
    BlogComment,
    BlogIndexPage,
    BlogPostPage,
    BlogSeries,
)

User = get_user_model()

# ParentalManyToManyField (BlogPostPage.categories) only commits in-memory M2M
# changes on page.save(); add_child() already saved the page without categories.
# Writing to the junction table directly is the proven workaround — mirrors
# _make_post() in test_blog_viewsets_caching.py.
PostCategoryThrough = BlogPostPage.categories.through


class BlogListN1TestMixin:
    """Shared helpers for measuring an endpoint's query count under cache miss."""

    def _measure(self, url):
        """Return the number of ``SELECT COUNT(...)`` queries serving a GET.

        Only COUNT-shaped queries are counted: the naive serializer issued one
        per row for the count field, so a growing COUNT total is the exact
        N+1 signature todo 079 eliminated. Counting only COUNT queries keeps
        the measurement immune to unrelated per-row query patterns (e.g. the
        taggit ``expertise_areas`` N+1 on the authors endpoint).

        Cache is cleared first so every measurement is a true cache miss — the
        DRF blog viewsets have no list-level cache, but clearing keeps the
        measurement deterministic regardless of any incidental caching.
        """
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 from {url}, got {response.status_code}",
        )
        return sum(1 for q in ctx.captured_queries if "COUNT(" in q["sql"])

    def _assert_no_n_plus_1(self, url, small_count, large_count):
        """Assert COUNT-query total did not grow as the fixture set grew."""
        self.assertEqual(
            small_count,
            large_count,
            f"N+1 regression detected on {url}: COUNT-query total grew from "
            f"{small_count} (small fixture) to {large_count} (large fixture). "
            f"The count fields must be read from a queryset annotation folded "
            f"into the main SELECT, not from a per-row COUNT query. "
            f"See docs/patterns/performance/query-optimization.md.",
        )


class BlogPostsListN1Test(BlogListN1TestMixin, TestCase):
    """blog:blog-posts-list — post_count on nested categories + comment_count.

    Exercises two annotations at once:
      - BlogPostListSerializer.get_comment_count() reads `_comment_count`.
      - Nested BlogCategorySerializer.get_post_count() reads `_post_count`
        (the categories queryset is annotated via Prefetch in get_queryset()).
    Every post is given a category and an approved comment so both code paths
    fire — without a category attached the nested COUNT-per-row never runs and
    the test would pass vacuously.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="postauthor",
            email="postauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Posts N1 Blog", slug="posts-n1-blog")
        root.add_child(instance=self.blog_index)

        self.category = BlogCategory.objects.create(name="Ferns", slug="ferns")
        self.url = reverse("v1:blog:blog-posts-list")
        self._post_seq = 0

    def _make_post(self):
        """Create one live blog post with a category and an approved comment."""
        self._post_seq += 1
        i = self._post_seq
        post = BlogPostPage(
            title=f"Post {i}",
            slug=f"post-{i}",
            author=self.user,
            publish_date=date.today(),
            introduction=f"<p>intro {i}</p>",
            content_blocks=[],
            allow_comments=True,
        )
        self.blog_index.add_child(instance=post)
        PostCategoryThrough.objects.get_or_create(
            blogpostpage=post, blogcategory=self.category
        )
        BlogComment.objects.create(
            post=post, author=self.user, content=f"comment {i}", is_approved=True
        )
        return post

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 posts.
        self._make_post()
        self._make_post()
        small = self._measure(self.url)

        # Large fixture: 6 posts total (still page 1 — page_size is 12).
        for _ in range(4):
            self._make_post()
        large = self._measure(self.url)

        self._assert_no_n_plus_1(self.url, small, large)


class BlogCategoriesListN1Test(BlogListN1TestMixin, TestCase):
    """blog:blog-categories-list — BlogCategorySerializer.get_post_count().

    BlogCategoryViewSet.queryset annotates `_post_count`. Each category is given
    a distinct live post so the COUNT path is meaningful per row.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="catauthor",
            email="catauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Cat N1 Blog", slug="cat-n1-blog")
        root.add_child(instance=self.blog_index)
        self.url = reverse("v1:blog:blog-categories-list")
        self._seq = 0

    def _make_category_with_post(self):
        """Create a category plus one live post assigned to it."""
        self._seq += 1
        i = self._seq
        category = BlogCategory.objects.create(name=f"Category {i}", slug=f"cat-{i}")
        post = BlogPostPage(
            title=f"Cat Post {i}",
            slug=f"cat-post-{i}",
            author=self.user,
            publish_date=date.today(),
            introduction=f"<p>intro {i}</p>",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=post)
        PostCategoryThrough.objects.get_or_create(
            blogpostpage=post, blogcategory=category
        )
        return category

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 categories.
        self._make_category_with_post()
        self._make_category_with_post()
        small = self._measure(self.url)

        # Large fixture: 6 categories total.
        for _ in range(4):
            self._make_category_with_post()
        large = self._measure(self.url)

        self._assert_no_n_plus_1(self.url, small, large)


class BlogSeriesListN1Test(BlogListN1TestMixin, TestCase):
    """blog:blog-series-list — BlogSeriesSerializer.get_post_count().

    BlogSeriesViewSet.queryset annotates `_post_count`. Each series is given a
    distinct live post (series is an FK on BlogPostPage) so the COUNT path is
    meaningful per row.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="seriesauthor",
            email="seriesauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Series N1 Blog", slug="series-n1-blog")
        root.add_child(instance=self.blog_index)
        self.url = reverse("v1:blog:blog-series-list")
        self._seq = 0

    def _make_series_with_post(self):
        """Create a series plus one live post assigned to it (FK)."""
        self._seq += 1
        i = self._seq
        series = BlogSeries.objects.create(
            title=f"Series {i}", slug=f"series-{i}", description=f"desc {i}"
        )
        post = BlogPostPage(
            title=f"Series Post {i}",
            slug=f"series-post-{i}",
            author=self.user,
            publish_date=date.today(),
            introduction=f"<p>intro {i}</p>",
            content_blocks=[],
            series=series,
        )
        self.blog_index.add_child(instance=post)
        return series

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 series.
        self._make_series_with_post()
        self._make_series_with_post()
        small = self._measure(self.url)

        # Large fixture: 6 series total.
        for _ in range(4):
            self._make_series_with_post()
        large = self._measure(self.url)

        self._assert_no_n_plus_1(self.url, small, large)


class BlogAuthorsListN1Test(BlogListN1TestMixin, TestCase):
    """blog:blog-authors-list — BlogAuthorSerializer.get_post_count().

    BlogAuthorViewSet.get_queryset() filters to BlogAuthorPage rows whose User
    has at least one live post (`author__blogpostpage__live=True`) and annotates
    `_post_count`. Each new author therefore needs a User, a BlogAuthorPage, and
    at least one live BlogPostPage by that User — without the live post the
    author page is filtered out entirely.
    """

    def setUp(self):
        cache.clear()
        self.root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Author N1 Blog", slug="author-n1-blog")
        self.root.add_child(instance=self.blog_index)
        self.url = reverse("v1:blog:blog-authors-list")
        self._seq = 0

    def _make_author_with_post(self):
        """Create a User + BlogAuthorPage + one live BlogPostPage by that User."""
        self._seq += 1
        i = self._seq
        user = User.objects.create_user(
            username=f"author{i}",
            email=f"author{i}@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        author_page = BlogAuthorPage(
            title=f"Author {i}",
            slug=f"author-page-{i}",
            author=user,
            bio=f"<p>bio {i}</p>",
        )
        self.root.add_child(instance=author_page)
        # Give every author the same two expertise tags so the taggit
        # resolution path (expertise_areas.all()) actually fires per row —
        # without tags the N+1 measurement below would be vacuous.
        author_page.expertise_areas.add("ferns", "mosses")
        post = BlogPostPage(
            title=f"Author Post {i}",
            slug=f"author-post-{i}",
            author=user,
            publish_date=date.today(),
            introduction=f"<p>intro {i}</p>",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=post)
        return author_page

    def test_no_n_plus_1_scaling(self):
        # Small fixture: 2 authors.
        self._make_author_with_post()
        self._make_author_with_post()
        small = self._measure(self.url)

        # Large fixture: 6 authors total.
        for _ in range(4):
            self._make_author_with_post()
        large = self._measure(self.url)

        self._assert_no_n_plus_1(self.url, small, large)

    def _measure_taggit_queries(self, url):
        """Return the number of queries that resolve ``expertise_areas`` tags.

        ``BlogAuthorSerializer.expertise_areas`` is a taggit
        ``TagListSerializerField`` that reads ``obj.expertise_areas.all()``.
        taggit resolves that with a SELECT joining ``taggit_tag``; without a
        prefetch the serializer issues one such query per author (the N+1 this
        todo fixes), and with ``prefetch_related('expertise_areas')`` it
        resolves every author's tags in a single query. Counting
        ``taggit_tag``-shaped queries isolates this endpoint's expertise N+1 —
        distinct from the ``COUNT``-shaped serializer N+1 that ``_measure()``
        targets (todo 079), which deliberately excludes this one.
        """
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200 from {url}, got {response.status_code}",
        )
        return sum(1 for q in ctx.captured_queries if "taggit_tag" in q["sql"])

    def test_no_expertise_areas_n_plus_1(self):
        """expertise_areas (taggit) must not scale taggit_tag queries with authors."""
        # Small fixture: 2 authors, each with expertise tags.
        self._make_author_with_post()
        self._make_author_with_post()
        small = self._measure_taggit_queries(self.url)

        # Guard against a vacuous pass: the taggit path must actually fire.
        self.assertGreaterEqual(
            small,
            1,
            "Expected at least one taggit_tag query — expertise_areas is not "
            "being resolved, so this test would pass vacuously.",
        )

        # Large fixture: 6 authors total.
        for _ in range(4):
            self._make_author_with_post()
        large = self._measure_taggit_queries(self.url)

        self.assertEqual(
            small,
            large,
            f"expertise_areas N+1 on the authors endpoint: taggit_tag query "
            f"total grew from {small} (2 authors) to {large} (6 authors). "
            f"BlogAuthorViewSet.get_queryset() must "
            f"prefetch_related('expertise_areas') so taggit resolves all "
            f"authors' tags in one query. "
            f"See docs/patterns/performance/query-optimization.md.",
        )
