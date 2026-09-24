"""Tests for the dashboard_stats endpoint (wagtail_forum aggregates only).

Todo 411 removed the plant block (``plant_stats``, ``plant_identification``
activity entries and ``total_activity_score``): it read
``PlantIdentificationRequest`` / ``SavedCareInstructions``, whose only writer
is the broken demo seeder (todo 412), so every value was a permanent zero.
"""

from apps.plant_identification.models import PlantIdentificationRequest
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

    def test_a_taken_down_topics_reply_neither_counts_nor_lists(self):
        # PR #821: the reply stays live=True when a moderator takes the TOPIC
        # down; the forum hides it, so the dashboard must too.
        other = User.objects.create_user(username="bea", password="TestPass123!")
        gone = Topic.objects.create(
            board=self.board, title="Gone", slug="gone", author=other, live=False
        )
        Post.objects.create(
            topic=gone, author=self.user, is_opening_post=False, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.data["forum_stats"]["total_posts"], 0)
        self.assertEqual(resp.data["recent_activity"], [])

    def test_content_on_an_unpublished_board_is_hidden(self):
        hidden = self.board.get_parent().add_child(
            instance=ForumBoard(title="Staff", slug="staff")
        )
        hidden.unpublish()
        topic = Topic.objects.create(
            board=hidden, title="Secret", slug="secret", author=self.user, live=True
        )
        Post.objects.create(
            topic=topic, author=self.user, is_opening_post=False, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.data["forum_stats"]["total_topics"], 0)
        self.assertEqual(resp.data["forum_stats"]["total_posts"], 0)
        self.assertEqual(resp.data["recent_activity"], [])

    def test_a_reply_links_to_the_post_itself(self):
        topic = self._topic("deep", live=True)
        reply = Post.objects.create(
            topic=topic, author=self.user, is_opening_post=False, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        (item,) = [a for a in resp.data["recent_activity"] if a["type"] == "forum_post"]
        self.assertEqual(
            item["url"],
            f"/forum/{self.board.id}-{self.board.slug}/{topic.id}-{topic.slug}#post-{reply.pk}",
        )

    def test_payload_carries_no_plant_fields(self):
        # A row the old view would have counted and listed: an identified
        # request. Nothing in the app writes these (todo 411), so the payload
        # must not expose fields that can only ever read zero.
        PlantIdentificationRequest.objects.create(
            user=self.user,
            image_1="plants/identifications/never-written.jpg",
            status="identified",
        )
        live_topic = self._topic("with-plant", live=True)
        Post.objects.create(
            topic=live_topic, author=self.user, is_opening_post=True, live=True
        )

        self.client.force_authenticate(user=self.user)
        resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.data), {"forum_stats", "recent_activity"})
        self.assertNotIn("plant_stats", resp.data)
        self.assertNotIn("total_activity_score", resp.data)
        self.assertEqual(
            {item["type"] for item in resp.data["recent_activity"]}, {"forum_topic"}
        )

    def test_query_count_is_constant(self):
        # Several topics and replies: select_related keeps the recent-activity
        # lists from issuing a query per row. 2 aggregates + 2 recent lists.
        for n in range(3):
            topic = self._topic(f"topic-{n}", live=True)
            Post.objects.create(
                topic=topic, author=self.user, is_opening_post=True, live=True
            )
            Post.objects.create(
                topic=topic, author=self.user, is_opening_post=False, live=True
            )

        self.client.force_authenticate(user=self.user)
        # Five: the view-restriction lookup behind .public() (PR #821), two
        # aggregates, two select_related lists.
        with self.assertNumQueries(5):
            resp = self.client.get(DASHBOARD_URL)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["recent_activity"]), 4)
