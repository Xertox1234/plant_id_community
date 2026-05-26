"""Security regression suite for the forum API.

Tests are accumulated here as tasks complete.  Run the full suite with:
    python manage.py test apps.forum_integration.tests.test_security --noinput
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Post, Topic
from wagtail.models import Page, Site

User = get_user_model()


def _ensure_site():
    root = Page.get_first_root_node()
    if not Site.objects.filter(is_default_site=True).exists():
        Site.objects.create(
            hostname="localhost",
            root_page=root,
            is_default_site=True,
            site_name="Test Site",
        )
    return root


# ---------------------------------------------------------------------------
# Task 4: backfill command
# ---------------------------------------------------------------------------


@override_settings(ENABLE_FORUM=True)
class BackfillSanitizationTests(TestCase):
    """sanitize_forum_content management command."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Security Test Forum", type=Forum.FORUM_POST
        )
        cls.user = User.objects.create_user(
            username="backfill_tester",
            email="backfill_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="Backfill test topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )

    def _make_post(self, content):
        post = Post(topic=self.topic, poster=self.user, approved=True, content=content)
        post.save()
        return post

    def test_backfill_neutralizes_existing_malicious_content(self):
        post = self._make_post("<p>good</p><script>alert(1)</script>")
        call_command("sanitize_forum_content", verbosity=0)
        post.refresh_from_db()
        content = str(post.content)
        self.assertNotIn("<script", content)
        self.assertIn("<p>good</p>", content)

    def test_backfill_dry_run_does_not_save(self):
        malicious = "<p>safe</p><script>evil()</script>"
        post = self._make_post(malicious)
        call_command("sanitize_forum_content", dry_run=True, verbosity=0)
        post.refresh_from_db()
        self.assertEqual(str(post.content), malicious)

    def test_backfill_leaves_clean_content_unchanged(self):
        clean = "<p>This is fine.</p>"
        post = self._make_post(clean)
        call_command("sanitize_forum_content", verbosity=0)
        post.refresh_from_db()
        self.assertEqual(str(post.content), clean)
