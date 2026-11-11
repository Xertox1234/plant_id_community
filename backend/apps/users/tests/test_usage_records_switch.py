"""The per-person switch for email click records and blog view logging.

``User.usage_records`` is on by default (owner decision 2026-11-10: both stay
on). Off, no new ``EmailClick`` or ``BlogPostView`` row is written for that
account, which is how an objection to those two uses is honoured (todo 701).
"""

from unittest.mock import MagicMock, patch

from apps.blog.middleware import BlogViewTrackingMiddleware
from apps.blog.models import BlogIndexPage, BlogPostPage, BlogPostView
from apps.core.email_feedback import record_click
from apps.core.models import EmailClick, EmailNotification
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()


def _notification(user):
    return EmailNotification.objects.create(
        email_type="forum_reply",
        recipient_email=user.email,
        user=user,
        subject="s",
        template_name="forum_reply",
        status=EmailNotification.STATUS_SENT,
        sent_at=timezone.now(),
    )


class DefaultTests(TestCase):
    def test_on_by_default(self):
        user = User.objects.create_user(username="d", email="d@example.com")
        self.assertIs(user.usage_records, True)


class ProfileApiTests(TestCase):
    client: APIClient

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(username="p", email="p@example.com")
        self.client.force_authenticate(self.user)

    def test_the_owner_reads_and_changes_it(self):
        current = self.client.get(reverse("v1:users:current_user"))
        self.assertIs(current.data["usage_records"], True)

        response = self.client.patch(
            reverse("v1:users:update_profile"),
            {"usage_records": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIs(self.user.usage_records, False)


class EmailClickTests(TestCase):
    def test_a_click_is_recorded_while_on(self):
        user = User.objects.create_user(username="on", email="on@example.com")
        row = _notification(user)

        self.assertTrue(record_click(str(row.uuid), "topic"))
        self.assertEqual(EmailClick.objects.count(), 1)

    def test_no_click_is_recorded_while_off(self):
        user = User.objects.create_user(
            username="off", email="off@example.com", usage_records=False
        )
        row = _notification(user)

        self.assertFalse(record_click(str(row.uuid), "topic"))
        self.assertEqual(EmailClick.objects.count(), 0)


class BlogViewTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        from wagtail.models import Locale, Page, Site

        locale, _ = Locale.objects.get_or_create(language_code="en")
        try:
            root = Site.objects.get(is_default_site=True).root_page
        except Site.DoesNotExist:
            root = Page.objects.filter(depth=1).first() or Page.add_root(
                title="Root", locale=locale
            )
            Site.objects.create(
                hostname="localhost", root_page=root, is_default_site=True
            )
        self.author = User.objects.create_user(username="author")
        index = BlogIndexPage(title="Blog", slug="blog-usage")
        root.add_child(instance=index)
        self.post = BlogPostPage(
            title="Post",
            slug="post-usage",
            author=self.author,
            publish_date=timezone.now().date(),
            introduction="i",
        )
        index.add_child(instance=self.post)
        self.middleware = BlogViewTrackingMiddleware(
            get_response=lambda r: MagicMock(status_code=200)
        )

    def _view(self, user):
        request = RequestFactory().get("/blog/post-usage/")
        request.user = user
        request.resolver_match = MagicMock()
        request._wagtail_page = self.post
        with patch("django.db.transaction.on_commit") as on_commit:
            on_commit.side_effect = lambda func: func()
            self.middleware._track_view(request, MagicMock(status_code=200))

    def test_a_view_is_logged_while_on(self):
        self._view(User.objects.create_user(username="reader"))

        self.assertEqual(BlogPostView.objects.count(), 1)

    def test_no_row_is_written_while_off_but_the_post_still_counts_it(self):
        self._view(User.objects.create_user(username="quiet", usage_records=False))

        self.assertEqual(BlogPostView.objects.count(), 0)
        self.post.refresh_from_db()
        self.assertEqual(self.post.view_count, 1)
