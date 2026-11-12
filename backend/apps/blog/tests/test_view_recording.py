"""A read of a post through the blog API is logged (todo 701).

The website and the app read a post at ``/api/v2/blog-posts/<id>/``. The view
log used to live only in ``BlogViewTrackingMiddleware``, which waits for a
``request._wagtail_page`` that nothing sets, so no ``BlogPostView`` row was
ever written and ``view_count`` never moved. These tests drive the real route.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from wagtail.models import Page

from ..models import BlogIndexPage, BlogPostPage, BlogPostView

User = get_user_model()


class BlogApiViewRecordingTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        author = User.objects.create_user(username="writer", email="w@example.com")
        index = BlogIndexPage(title="Blog", slug="blog-recording")
        Page.objects.get(id=1).add_child(instance=index)
        self.post = BlogPostPage(
            title="Post",
            slug="post-recording",
            author=author,
            publish_date=date.today(),
            introduction="<p>i</p>",
            content_blocks=[],
        )
        index.add_child(instance=self.post)
        self.url = f"/api/v2/blog-posts/{self.post.id}/"

    def tearDown(self):
        cache.clear()

    def _read(self, user=None, **headers):
        self.client.force_authenticate(user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(self.url, **headers)
        self.assertEqual(response.status_code, 200)
        return response

    def test_an_anonymous_read_is_logged_and_counted(self):
        self._read(HTTP_USER_AGENT="Mozilla/5.0", HTTP_REFERER="https://x.test/")

        row = BlogPostView.objects.get()
        self.assertIsNone(row.user)
        self.assertEqual(row.referrer, "https://x.test/")
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)

    def test_a_signed_in_read_names_the_reader(self):
        # force_authenticate stands in for the JWT sign-in: the user is the
        # API's, which the plain request (session only) would not see.
        reader = User.objects.create_user(username="reader", email="r@example.com")

        self._read(reader)

        self.assertEqual(BlogPostView.objects.get().user, reader)

    def test_a_read_served_from_the_cache_is_still_logged(self):
        first = User.objects.create_user(username="one", email="1@example.com")
        second = User.objects.create_user(username="two", email="2@example.com")

        self._read(first)
        self._read(second)

        self.assertEqual(
            set(BlogPostView.objects.values_list("user__username", flat=True)),
            {"one", "two"},
        )

    def test_usage_records_off_writes_no_row_but_the_post_still_counts(self):
        quiet = User.objects.create_user(
            username="quiet", email="q@example.com", usage_records=False
        )

        self._read(quiet)

        self.assertFalse(BlogPostView.objects.exists())
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)

    def test_a_reread_within_the_window_counts_once(self):
        reader = User.objects.create_user(username="again", email="a@example.com")

        self._read(reader)
        self._read(reader)

        self.assertEqual(BlogPostView.objects.count(), 1)
