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

    def test_forum_stats_and_activity_exclude_other_users_content(self):
        # ada's own live thread: opening post + a reply (both live).
        ada_topic = self._topic("ada-topic", live=True)
        Post.objects.create(
            topic=ada_topic, author=self.user, is_opening_post=True, live=True
        )
        Post.objects.create(
            topic=ada_topic, author=self.user, is_opening_post=False, live=True
        )

        # bob's live thread in the SAME board: must never count toward ada's
        # dashboard or appear in ada's recent activity.
        bob = User.objects.create_user(username="bob", password="TestPass123!")
        bob_topic = Topic.objects.create(
            board=self.board, title="Bob", slug="bob-topic", author=bob, live=True
        )
        Post.objects.create(
            topic=bob_topic, author=bob, is_opening_post=True, live=True
        )
        Post.objects.create(
            topic=bob_topic, author=bob, is_opening_post=False, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        forum = resp.data["forum_stats"]
        self.assertEqual(forum["total_topics"], 1)  # ada's topic only
        self.assertEqual(forum["total_posts"], 2)  # ada's 2 posts only; bob's excluded

        forum_items = [
            a for a in resp.data["recent_activity"] if a["type"].startswith("forum")
        ]
        # ada's activity spans both a topic and a (non-opening) post entry.
        self.assertEqual(
            {item["type"] for item in forum_items}, {"forum_topic", "forum_post"}
        )
        # Every forum activity item points at ada's thread, never bob's.
        ada_fragment = f"{ada_topic.id}-{ada_topic.slug}"
        bob_fragment = f"{bob_topic.id}-{bob_topic.slug}"
        self.assertTrue(all(ada_fragment in item["url"] for item in forum_items))
        self.assertFalse(any(bob_fragment in item["url"] for item in forum_items))
