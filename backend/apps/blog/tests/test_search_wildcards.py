"""SQL LIKE wildcard regression tests for blog search endpoints (todo 269).

`escape_search_query()` was removed from every blog search call site because it
double-escaped SQL LIKE wildcards on top of Django ORM's own
``PatternLookup.process_rhs()`` auto-escaping, silently dropping real matches
(a search for ``Rosa_`` stopped matching the row ``Rosa_care``).

Each test follows the discriminating design pinned by
``packages/wagtail_forum/.../test_user_search.py::test_search_escapes_sql_wildcards``:

1. The query string contains a literal ``_``.
2. A REAL target row whose searched field contains that literal substring is
   asserted RETURNED (this FAILS under the old double-escape bug — the point).
3. A DECOY row that would match only if ``_`` were a SQL wildcard (``X`` in
   place of ``_``) is asserted NOT returned (proves ``_`` is literal).
"""

from datetime import date

from apps.blog.api.viewsets import BlogPostPageViewSet
from apps.blog.models import BlogCategory, BlogComment, BlogIndexPage, BlogPostPage
from apps.plant_identification.models import PlantSpecies
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory
from wagtail.models import Page

User = get_user_model()


def _blog_index():
    """Return (creating if needed) the BlogIndexPage under the tree root."""
    try:
        return BlogIndexPage.objects.get(slug="blog")
    except BlogIndexPage.DoesNotExist:
        index = BlogIndexPage(title="Blog", slug="blog")
        Page.objects.get(id=1).add_child(instance=index)
        return index


def _publish_post(title, slug, author, tags=None):
    post = BlogPostPage(
        title=title,
        slug=slug,
        author=author,
        publish_date=date.today(),
        introduction="<p>Intro.</p>",
    )
    _blog_index().add_child(instance=post)
    post.save_revision().publish()
    if tags:
        for tag in tags:
            post.tags.add(tag)
        post.save_revision().publish()
    return post


class ModerateCommentsWildcardTests(TestCase):
    """blog_admin:moderate_comments — content__icontains (staff-only)."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="wildcard-mod-admin", email="mod@example.com"
        )
        self.client.force_login(self.admin)
        author = User.objects.create_user(username="commenter")
        post = _publish_post("Care Guide", "care-guide", author)
        # Target comment content contains the literal "Rosa_".
        self.target = BlogComment.objects.create(
            post=post, author=author, content="Rosa_care advice", is_approved=True
        )
        # Decoy matches only if "_" acts as a wildcard.
        self.decoy = BlogComment.objects.create(
            post=post, author=author, content="RosaXcare advice", is_approved=True
        )

    def test_search_treats_underscore_as_literal(self):
        # status=all so is_approved does not filter the fixtures out.
        response = self.client.get(
            reverse("blog_admin:moderate_comments"), {"q": "Rosa_", "status": "all"}
        )
        self.assertEqual(response.status_code, 200)
        ids = {c.id for c in response.context["page_obj"].object_list}
        self.assertIn(self.target.id, ids)
        self.assertNotIn(self.decoy.id, ids)


class BlogAdminSearchWildcardTests(TestCase):
    """blog_admin:search — BlogCategory name__icontains (staff-only)."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="wildcard-search-admin", email="search@example.com"
        )
        self.client.force_login(self.admin)
        self.target = BlogCategory.objects.create(
            name="Rosa_pests", slug="rosa-pests", description="Pest guide"
        )
        self.decoy = BlogCategory.objects.create(
            name="RosaXpests", slug="rosax-pests", description="Other guide"
        )

    def test_search_treats_underscore_as_literal(self):
        response = self.client.get(reverse("blog_admin:search"), {"q": "Rosa_"})
        self.assertEqual(response.status_code, 200)
        names = {c.name for c in response.context["results"]["categories"]}
        self.assertIn("Rosa_pests", names)
        self.assertNotIn("RosaXpests", names)


class PlantSuggestionsWildcardTests(TestCase):
    """blog_api:plant_suggestions — scientific_name__icontains (staff-only)."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser(
            username="wildcard-suggest-admin", email="suggest@example.com"
        )
        self.client.force_login(self.admin)
        self.target = PlantSpecies.objects.create(scientific_name="Rosa_alba")
        self.decoy = PlantSpecies.objects.create(scientific_name="RosaXalba")

    def test_suggestions_treat_underscore_as_literal(self):
        # Query must be >= 2 chars; "Rosa_" is 5.
        response = self.client.get(
            reverse("v1:blog_api:plant_suggestions"), {"q": "Rosa_"}
        )
        self.assertEqual(response.status_code, 200)
        values = {s["value"] for s in response.json()["suggestions"]}
        self.assertIn("Rosa_alba", values)
        self.assertNotIn("RosaXalba", values)


class BlogPostTagFilterWildcardTests(TestCase):
    """v1:blog:blog-posts-list ?tag= — tags__name__icontains (anonymous)."""

    def setUp(self):
        cache.clear()
        author = User.objects.create_user(username="tag-author")
        self.target = _publish_post(
            "Underscore Tagged", "underscore-tagged", author, tags=["rosa_x"]
        )
        self.decoy = _publish_post(
            "Wildcard Tagged", "wildcard-tagged", author, tags=["rosaXx"]
        )

    def test_tag_filter_treats_underscore_as_literal(self):
        response = self.client.get(reverse("v1:blog:blog-posts-list"), {"tag": "rosa_"})
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(self.target.id, ids)
        self.assertNotIn(self.decoy.id, ids)


class BlogPublicSearchWildcardTests(TestCase):
    """v1:blog:blog-search — BlogCategory name__icontains (anonymous)."""

    def setUp(self):
        cache.clear()
        self.target = BlogCategory.objects.create(
            name="Rose_disease", slug="rose-disease", description="Disease guide"
        )
        self.decoy = BlogCategory.objects.create(
            name="RoseXdisease", slug="rosex-disease", description="Other guide"
        )

    def test_empty_query_returns_400(self):
        response = self.client.get(reverse("v1:blog:blog-search"), {"q": ""})
        self.assertEqual(response.status_code, 400)

    def test_search_treats_underscore_as_literal(self):
        response = self.client.get(reverse("v1:blog:blog-search"), {"q": "Rose_"})
        self.assertEqual(response.status_code, 200)
        names = {c["name"] for c in response.data["categories"]}
        self.assertIn("Rose_disease", names)
        self.assertNotIn("RoseXdisease", names)


class SearchSuggestionsActionWildcardTests(TestCase):
    """BlogPostPageViewSet.search_suggestions — title__icontains.

    Not URL-routed; exercised via a direct action call as instructed.
    """

    def setUp(self):
        cache.clear()
        author = User.objects.create_user(username="suggest-post-author")
        # Titles contain the literal "ro_" vs the wildcard-only decoy "roX".
        self.target = _publish_post("Ro_ses at home", "ro-ses-at-home", author)
        self.decoy = _publish_post("RoXses at home", "rox-ses-at-home", author)

    def test_title_suggestions_treat_underscore_as_literal(self):
        request = APIRequestFactory().get("/?q=ro_")
        response = BlogPostPageViewSet.as_view({"get": "search_suggestions"})(request)
        self.assertEqual(response.status_code, 200)
        titles = {row["text"] for row in response.data if row["type"] == "title"}
        self.assertIn("Ro_ses at home", titles)
        self.assertNotIn("RoXses at home", titles)
