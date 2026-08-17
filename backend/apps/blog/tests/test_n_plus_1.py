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
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.images.models import SourceImageIOError
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, Site

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


class BlogPostsListFeaturedImageContractTest(TestCase):
    """blog:blog-posts-list — featured_image / featured_image_thumb contract.

    PR #540 review finding #1 claimed the list serializer's missing
    featured_image field made grid covers render blurry. Verified FALSE at
    the time: `BlogPostPageViewSet.get_serializer_class()` branched on
    `self.action == "list"`, but Wagtail's router sets
    `self.action = "listing_view"` for this endpoint, so the check never
    matched and `/api/v2/blog-posts/` served the full BlogPostPageSerializer
    (detail) — which already had featured_image at fill-800x400. A live
    probe against the pre-fix commit confirmed the field was already
    present.

    featured_image was still added to BlogPostPageListSerializer (+ its
    queryset prefetch sites) because that serializer IS genuinely used by
    the routed `popular` action, and because todo 306 (now fixed — see
    `BlogPostsListSerializerRoutingTest` below) makes the list endpoint
    start using it too. This test pins the response contract so a
    regression is caught either way.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="imageauthor",
            email="imageauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Image N1 Blog", slug="image-n1-blog")
        root.add_child(instance=self.blog_index)
        # NOT reverse("v1:blog:blog-posts-list") — that's the unrelated
        # legacy DRF-router blog API (apps/blog/views.py). The frontend
        # (web/src/services/blogService.ts) and this fix both target the
        # Wagtail API v2 endpoint, which has no name to reverse().
        self.url = "/api/v2/blog-posts/"

    def test_featured_image_present_with_grid_rendition(self):
        """The list endpoint must expose featured_image at fill-800x400,
        not just featured_image_thumb — key presence, not just absence of
        an error (DRF SkipField-shaped failure: a missing prefetch/
        annotation drops a field silently)."""
        image = get_image_model().objects.create(
            title="Cover", file=get_test_image_file(filename="cover.png")
        )
        post = BlogPostPage(
            title="Image Post",
            slug="image-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
            featured_image=image,
        )
        self.blog_index.add_child(instance=post)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        item = response.data["items"][0]
        self.assertIn(
            "featured_image",
            item,
            "featured_image is missing from the list response — BlogCard's "
            "grid cover falls back to the 300x200 thumb and renders it "
            "upscaled/blurry.",
        )
        self.assertIn("/images/", item["featured_image"]["url"])
        self.assertIn(".fill-800x400", item["featured_image"]["url"])
        self.assertIn("featured_image_thumb", item)
        self.assertIn(".fill-300x200", item["featured_image_thumb"]["url"])


class BlogPostsListSerializerRoutingTest(TestCase):
    """`/api/v2/blog-posts/` list vs detail serializer selection (todo 306 AC1).

    `BlogPostPageViewSet.get_serializer_class()` used to check
    `self.action == "list"`, which Wagtail's router never sets (it uses
    `"listing_view"`/`"detail_view"` — see `BlogPostsListFeaturedImageContractTest`
    above) — so the list endpoint always served the full
    `BlogPostPageSerializer`, paying its per-row `related_posts` N+1 (a fresh
    `BlogPostPage.objects...` query per row) on every request. Pins the
    correctness fix (light serializer on list, full on detail) via field
    presence/absence — `related_posts` is a field
    `BlogPostPageListSerializer` doesn't define at all, so its absence
    proves `get_related_posts()` (the per-row query) never runs on this
    endpoint; this is a structural guarantee, not a measured query count
    (see `BlogPostsListFeaturedImageContractTest`'s docstring history for
    why a query-count assertion here would double-count the unrelated,
    pre-existing `BlogCategorySerializer.get_post_count()` N+1).
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="routingauthor",
            email="routingauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Routing Blog", slug="routing-blog")
        root.add_child(instance=self.blog_index)
        # A shared category so every post's (list-serializer-absent)
        # related_posts fallback query has candidates to actually fetch —
        # an empty candidate set would make the N+1 test pass vacuously.
        self.category = BlogCategory.objects.create(name="Routing", slug="routing")
        self._seq = 0

    def _make_post(self):
        self._seq += 1
        i = self._seq
        post = BlogPostPage(
            title=f"Routing Post {i}",
            slug=f"routing-post-{i}",
            author=self.user,
            publish_date=date.today(),
            introduction=f"<p>intro {i}</p>",
            content_blocks=[],
        )
        self.blog_index.add_child(instance=post)
        PostCategoryThrough.objects.get_or_create(
            blogpostpage=post, blogcategory=self.category
        )
        return post

    def test_list_serves_light_serializer(self):
        """Fields unique to the detail serializer (related_posts,
        content_blocks, introduction) must be absent from the list
        response — proves listing_view now resolves
        BlogPostPageListSerializer, not the full one."""
        self._make_post()
        response = self.client.get("/api/v2/blog-posts/")
        self.assertEqual(response.status_code, 200)
        item = response.data["items"][0]
        for field in ("related_posts", "content_blocks", "introduction"):
            self.assertNotIn(
                field,
                item,
                f"'{field}' is detail-only and must not appear on the list "
                f"endpoint — get_serializer_class() is not routing "
                f"listing_view to BlogPostPageListSerializer.",
            )

    def test_detail_still_serves_full_serializer(self):
        """The fix must not regress the detail endpoint — related_posts and
        content_blocks stay present there."""
        post = self._make_post()
        response = self.client.get(f"/api/v2/blog-posts/{post.id}/")
        self.assertEqual(response.status_code, 200)
        for field in ("related_posts", "content_blocks", "introduction"):
            self.assertIn(field, response.data, f"'{field}' missing from detail")

    # N+1 elimination is proven by test_list_serves_light_serializer above:
    # BlogPostPageListSerializer has no related_posts field at all, so
    # get_related_posts() (the per-row query) never runs on this endpoint —
    # field absence IS the N+1 proof. A total-query-count scaling
    # assertion was tried and rejected: it also caught the nested
    # BlogCategorySerializer.get_post_count() per-category COUNT, a
    # pre-existing N+1 unrelated to this todo (out of scope here).


class BlogPostDetailContentBlocksContractTest(TestCase):
    """`/api/v2/blog-posts/<id>/` content_blocks shape (todo 306 AC3).

    Before this fix, `content_blocks` fell back to DRF ModelSerializer's
    default handling of an unmapped Wagtail StreamField model field — a
    stringified raw JSON blob the client had to `JSON.parse()` itself, with
    any `ImageChooserBlock` value serialized as a bare integer PK (no way to
    render it). Wagtail's own `StreamField` API field (`content_blocks =
    StreamFieldAPIField(...)`) returns real structured blocks; the nested
    `plant_spotlight.image` block still needed `APIImageChooserBlock`
    (`apps/blog/blocks.py`) on top, since even Wagtail's default chooser
    block API representation is `get_prep_value()` — the bare PK again.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="contentauthor",
            email="contentauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Content Blog", slug="content-blog")
        root.add_child(instance=self.blog_index)
        self.image = get_image_model().objects.create(
            title="Monstera", file=get_test_image_file(filename="monstera.png")
        )

    def test_content_blocks_is_structured_not_a_string(self):
        post = BlogPostPage(
            title="Spotlight Post",
            slug="spotlight-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[
                ("heading", "Meet the Monstera"),
                (
                    "plant_spotlight",
                    {
                        "plant_name": "Monstera",
                        "scientific_name": "Monstera deliciosa",
                        "description": "<p>A climbing aroid.</p>",
                        "care_difficulty": "easy",
                        "image": self.image,
                    },
                ),
            ],
        )
        self.blog_index.add_child(instance=post)

        response = self.client.get(f"/api/v2/blog-posts/{post.id}/")
        self.assertEqual(response.status_code, 200)
        blocks = response.data["content_blocks"]
        self.assertIsInstance(
            blocks,
            list,
            "content_blocks must be structured JSON (a list of block dicts), "
            "not a stringified blob the client has to JSON.parse() itself.",
        )

        heading = next(b for b in blocks if b["type"] == "heading")
        self.assertEqual(heading["value"], "Meet the Monstera")

        spotlight = next(b for b in blocks if b["type"] == "plant_spotlight")
        image_value = spotlight["value"]["image"]
        self.assertIsInstance(
            image_value,
            dict,
            f"plant_spotlight.image must resolve to a rendition dict, not a "
            f"bare PK a client cannot turn into a URL — got {image_value!r}.",
        )
        self.assertIn("/images/", image_value["url"])
        self.assertIn(".fill-800x400", image_value["url"])
        # Always absolute (built from the request, not a relative + separate
        # full_url pair) — matches the forum's serialize_image_for_api
        # precedent for this exact StreamField-image-block problem.
        self.assertTrue(image_value["url"].startswith("http"))
        self.assertIn("id", image_value)

    def test_plant_spotlight_image_degrades_to_none_on_missing_source_file(self):
        """A missing source media file (Image row survives, file wiped —
        e.g. on redeploy) must degrade plant_spotlight.image to None, not
        crash the endpoint or return an invalid {"error": ...} dict a
        client can't render (code review, todo 306)."""
        post = BlogPostPage(
            title="Broken Image Post",
            slug="broken-image-post",
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[
                (
                    "plant_spotlight",
                    {
                        "plant_name": "Monstera",
                        "scientific_name": "",
                        "description": "<p>desc</p>",
                        "care_difficulty": "easy",
                        "image": self.image,
                    },
                ),
            ],
        )
        self.blog_index.add_child(instance=post)

        with mock.patch(
            "wagtail.images.models.AbstractImage.get_rendition",
            side_effect=SourceImageIOError("source file missing"),
        ):
            response = self.client.get(f"/api/v2/blog-posts/{post.id}/")

        self.assertEqual(response.status_code, 200)
        spotlight = next(
            b for b in response.data["content_blocks"] if b["type"] == "plant_spotlight"
        )
        self.assertIsNone(spotlight["value"]["image"])


class BlogPostMediaUrlConsistencyTest(TestCase):
    """Every image field in the blog API emits the same rendition-dict
    shape with a request-derived `full_url` (todo 306 AC4).

    Before this fix, `related_posts[].featured_image` was a bare URL
    string built from `Rendition.full_url` (which prefixes
    `settings.WAGTAILADMIN_BASE_URL` — defaults to `http://localhost:8000`
    when unset, which this project does not set for every deploy
    environment) while every other image field returned a
    `{url, full_url, width, height, alt}` dict built from the request's
    actual host via `get_full_url()`.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="mediaauthor",
            email="mediaauthor@example.com",
            password="pass12345",  # pragma: allowlist secret
        )
        root = Page.objects.get(id=1)
        self.blog_index = BlogIndexPage(title="Media Blog", slug="media-blog")
        root.add_child(instance=self.blog_index)
        self.category = BlogCategory.objects.create(name="Media", slug="media")
        self.image = get_image_model().objects.create(
            title="Cover", file=get_test_image_file(filename="cover.png")
        )

    def _make_post(self, slug):
        post = BlogPostPage(
            title=f"Media Post {slug}",
            slug=slug,
            author=self.user,
            publish_date=date.today(),
            introduction="<p>intro</p>",
            content_blocks=[],
            featured_image=self.image,
        )
        self.blog_index.add_child(instance=post)
        PostCategoryThrough.objects.get_or_create(
            blogpostpage=post, blogcategory=self.category
        )
        return post

    def test_related_posts_featured_image_matches_top_level_shape(self):
        main_post = self._make_post("media-main")
        self._make_post("media-related")  # shares the category → related

        response = self.client.get(f"/api/v2/blog-posts/{main_post.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["related_posts"], "expected a related post")

        top_level_image = response.data["featured_image"]
        related_image = response.data["related_posts"][0]["featured_image"]
        self.assertIsInstance(
            related_image,
            dict,
            f"related_posts[].featured_image must be a rendition dict, "
            f"same shape as the top-level featured_image field — got "
            f"{related_image!r}.",
        )
        self.assertEqual(
            set(related_image.keys()),
            set(top_level_image.keys()),
            "related_posts[].featured_image has different keys than the "
            "top-level featured_image field.",
        )
        self.assertTrue(related_image["full_url"].startswith("http"))

    @override_settings(ALLOWED_HOSTS=["blog.example.com", "testserver"])
    def test_full_url_is_request_derived_not_settings_based(self):
        """`full_url` must resolve via `get_full_url()` (Wagtail Sites,
        request-aware) for whatever Site actually matches the incoming
        request, not `Rendition.full_url`'s single global
        `settings.WAGTAILADMIN_BASE_URL` (unset in some deploys → silently
        wrong host in production, and incapable of ever reflecting a
        second Site). Registering a second Site with a distinct hostname
        and requesting through it is the only way to prove that — a Site
        record it does NOT match would fall back to the default Site,
        masking the very bug this test exists to catch.
        """
        root = Page.objects.get(id=1)
        Site.objects.create(hostname="blog.example.com", port=80, root_page=root)
        post = self._make_post("media-host")
        response = self.client.get(
            f"/api/v2/blog-posts/{post.id}/", SERVER_NAME="blog.example.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.data["featured_image"]["full_url"].startswith(
                "http://blog.example.com/"
            ),
            response.data["featured_image"]["full_url"],
        )
