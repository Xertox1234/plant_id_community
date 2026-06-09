"""Tests for the dashboard_stats endpoint's forum portion (wagtail_forum)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()

DASHBOARD_URL = "/api/v1/auth/me/dashboard-stats/"


class DashboardStatsForumTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="ada", password="TestPass123!")
        # Build the wagtail_forum page tree: root -> ForumIndex -> ForumBoard
        root = Page.objects.get(id=1)
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
        self.board = index.add_child(
            instance=ForumBoard(title="General", slug="general")
        )

    def _topic(self, slug, *, live):
        return Topic.objects.create(
            board=self.board, title=slug.title(), slug=slug, author=self.user, live=live
        )

    def test_forum_stats_count_only_live_content_by_user(self):
        live_topic = self._topic("live", live=True)
        Post.objects.create(
            topic=live_topic, author=self.user, is_opening_post=True, live=True
        )
        Post.objects.create(
            topic=live_topic, author=self.user, is_opening_post=False, live=True
        )

        draft_topic = self._topic("draft", live=False)
        Post.objects.create(
            topic=draft_topic, author=self.user, is_opening_post=True, live=False
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        forum = resp.data["forum_stats"]
        self.assertEqual(forum["total_topics"], 1)  # live topic only
        self.assertEqual(forum["total_posts"], 2)  # 2 live posts; draft excluded
        self.assertEqual(forum["topics_this_month"], 1)
        self.assertEqual(forum["posts_this_month"], 2)

    def test_recent_activity_url_uses_live_web_forum_scheme(self):
        live_topic = self._topic("hello-world", live=True)
        Post.objects.create(
            topic=live_topic, author=self.user, is_opening_post=True, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        forum_items = [
            a for a in resp.data["recent_activity"] if a["type"].startswith("forum")
        ]
        self.assertTrue(forum_items)
        expected = (
            f"/forum/{self.board.id}-{self.board.slug}"
            f"/{live_topic.id}-{live_topic.slug}"
        )
        self.assertTrue(all(item["url"] == expected for item in forum_items))
