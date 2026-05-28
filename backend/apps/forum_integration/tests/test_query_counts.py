"""Query-count regression tests for forum list endpoints.

Each test pins the exact number of DB queries so N+1 regressions are caught at CI time.
Run with:
    python manage.py test apps.forum_integration.tests.test_query_counts --noinput
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Post, Topic
from rest_framework.test import APIClient
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


@override_settings(ENABLE_FORUM=True)
class UserTopicsQueryCountTests(TestCase):
    """UserTopicsListView must not issue N queries for N forums."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.user = User.objects.create_user(
            username="qc_user",
            email="qc@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        # Create several forums to exercise the bulk permission path.
        cls.forums = [
            Forum.objects.create(name=f"QC Forum {i}", type=Forum.FORUM_POST)
            for i in range(3)
        ]
        cls.topic = Topic.objects.create(
            forum=cls.forums[0],
            poster=cls.user,
            subject="QC Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        Post.objects.create(
            topic=cls.topic,
            poster=cls.user,
            content="<p>QC post</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_user_topics_list_query_count_is_fixed(self):
        """Query count must be constant regardless of how many forums exist."""
        with self.assertNumQueries(7):
            response = self.client.get(f"/api/v1/forum/users/{self.user.id}/topics/")
        self.assertEqual(response.status_code, 200)


@override_settings(ENABLE_FORUM=True)
class UserWatchedTopicsQueryCountTests(TestCase):
    """UserWatchedTopicsListView must not issue N queries for N forums."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.user = User.objects.create_user(
            username="qc_watched_user",
            email="qc_watched@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.forums = [
            Forum.objects.create(name=f"QC Watched Forum {i}", type=Forum.FORUM_POST)
            for i in range(3)
        ]
        cls.topic = Topic.objects.create(
            forum=cls.forums[0],
            poster=cls.user,
            subject="QC Watched Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        # A post by this user makes the topic appear in "watched" results.
        Post.objects.create(
            topic=cls.topic,
            poster=cls.user,
            content="<p>QC watched post</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_user_watched_topics_list_query_count_is_fixed(self):
        """Query count must be constant regardless of how many forums exist."""
        with self.assertNumQueries(7):
            response = self.client.get(
                f"/api/v1/forum/users/{self.user.id}/watched-topics/"
            )
        self.assertEqual(response.status_code, 200)


@override_settings(ENABLE_FORUM=True)
class TopicDetailQueryCountTests(TestCase):
    """TopicDetailView must fetch topic + relations in a fixed query count."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.user = User.objects.create_user(
            username="qc_detail_user",
            email="qc_detail@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.forum = Forum.objects.create(name="QC Detail Forum", type=Forum.FORUM_POST)
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="QC Detail Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        # Create 4 posts so the test verifies count is constant with multiple posts.
        for i in range(4):
            Post.objects.create(
                topic=cls.topic,
                poster=cls.user,
                content=f"<p>QC detail post {i}</p>",
                approved=True,
            )

    def setUp(self):
        self.client = APIClient()

    def test_topic_detail_query_count_is_pinned(self):
        """TopicDetailView query count is constant regardless of post count."""
        with self.assertNumQueries(3):
            response = self.client.get(f"/api/v1/forum/topics/{self.topic.id}/")
        self.assertEqual(response.status_code, 200)


@override_settings(ENABLE_FORUM=True)
class PostReactionQueryCountTests(TestCase):
    """PostReactionView.post must not issue more than 3 reaction-specific queries."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.user = User.objects.create_user(
            username="qc_reaction_user",
            email="qc_reaction@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.forum = Forum.objects.create(
            name="QC Reaction Forum", type=Forum.FORUM_POST
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="QC Reaction Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic,
            poster=cls.user,
            content="<p>QC reaction post</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_reaction_toggle_query_count(self):
        """Toggle uses: 404-guard + toggle-get + toggle-save + combined counts/user query = 4."""
        with self.assertNumQueries(4):
            response = self.client.post(
                f"/api/v1/forum/posts/{self.post.id}/reactions/",
                {"reaction_type": "like"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
