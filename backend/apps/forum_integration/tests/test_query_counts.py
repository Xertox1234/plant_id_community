"""Query-count regression tests for forum list endpoints.

Each test pins the exact number of DB queries so N+1 regressions are caught at CI time.
Run with:
    python manage.py test apps.forum_integration.tests.test_query_counts --noinput
"""

from apps.forum_integration.models import PostReaction
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
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
        """TopicDetailView query count is constant regardless of post count.

        4 queries = topic + posts-count + posts + reactions-prefetch. The
        reactions prefetch (todo 105) is a single constant query for all posts;
        if it regressed to an N+1 this count would scale with post count.
        """
        with self.assertNumQueries(4):
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


@override_settings(ENABLE_FORUM=True)
class PostListReactionCountsTests(TestCase):
    """PostSerializer.reaction_counts is correct and free of N+1 queries."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="RC Forum", type=Forum.FORUM_POST)
        cls.author = User.objects.create_user(
            username="rc_author",
            email="rc_author@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        # Distinct users so multiple reactions are valid under the
        # unique_together = (post, user, reaction_type) constraint.
        cls.reactors = [
            User.objects.create_user(
                username=f"rc_reactor_{i}",
                email=f"rc_reactor_{i}@example.com",
                password="pass123!",  # pragma: allowlist secret
            )
            for i in range(4)
        ]
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.author,
            subject="RC Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.url = f"/api/v1/forum/posts/?topic={self.topic.id}"

    def _make_post(self):
        return Post.objects.create(
            topic=self.topic, poster=self.author, content="<p>p</p>", approved=True
        )

    def _react(self, post, user, reaction_type, is_active=True):
        PostReaction.objects.create(
            post=post, user=user, reaction_type=reaction_type, is_active=is_active
        )

    def _row_for(self, resp, post_id):
        return next(r for r in resp.json()["results"] if r["id"] == post_id)

    def test_reaction_counts_reflect_only_active_reactions(self):
        post = self._make_post()
        self._react(post, self.reactors[0], "like")
        self._react(post, self.reactors[1], "like")
        self._react(post, self.reactors[2], "like")
        self._react(post, self.reactors[0], "love")
        # Inactive (toggled-off) reaction must NOT be counted.
        self._react(post, self.reactors[1], "helpful", is_active=False)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._row_for(resp, post.id)["reaction_counts"], {"like": 3, "love": 1}
        )

    def test_post_with_no_reactions_returns_empty_dict(self):
        post = self._make_post()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._row_for(resp, post.id)["reaction_counts"], {})

    def test_post_serializer_includes_topic_id(self):
        # todo 112: posts expose their topic id so the web client can build a
        # non-empty thread reference (updatePost previously returned thread === '').
        post = self._make_post()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._row_for(resp, post.id)["topic_id"], self.topic.id)

    def test_reaction_counts_no_n_plus_1(self):
        # Two posts, each reacted to by every reactor.
        for _ in range(2):
            p = self._make_post()
            for user in self.reactors:
                self._react(p, user, "like")
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get(self.url).status_code, 200)

        # Triple the posts (and their reactions). Query count must NOT grow —
        # if reaction_counts were an N+1, it would scale with post count.
        for _ in range(4):
            p = self._make_post()
            for user in self.reactors:
                self._react(p, user, "like")
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get(self.url).status_code, 200)

        self.assertEqual(
            len(large.captured_queries),
            len(small.captured_queries),
            "reaction_counts triggers an N+1 — query count grew with post count: "
            f"{len(small.captured_queries)} -> {len(large.captured_queries)}",
        )


@override_settings(ENABLE_FORUM=True)
class FeedAndSearchReactionCountsNoNPlus1Tests(TestCase):
    """reaction_counts must not N+1 on the other PostSerializer list paths.

    PostSerializer.reaction_counts is also serialized by the public feed
    (TopicsFeedView -> first_post) and search (forum_search) endpoints; each
    needs its own prefetch.
    """

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="Feed RC Forum", type=Forum.FORUM_POST)
        cls.author = User.objects.create_user(
            username="feed_rc_author",
            email="feed_rc_author@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.reactors = [
            User.objects.create_user(
                username=f"feed_rc_reactor_{i}",
                email=f"feed_rc_reactor_{i}@example.com",
                password="pass123!",  # pragma: allowlist secret
            )
            for i in range(3)
        ]

    def setUp(self):
        cache.clear()  # reset the search IP rate-limit counter between tests
        self.client = APIClient()

    def _make_topic_with_reacted_first_post(self, subject, content):
        topic = Topic.objects.create(
            forum=self.forum,
            poster=self.author,
            subject=subject,
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        post = Post.objects.create(
            topic=topic, poster=self.author, content=content, approved=True
        )
        # Guarantee a first_post regardless of machina signal behavior in tests.
        Topic.objects.filter(pk=topic.pk).update(first_post=post)
        for user in self.reactors:
            PostReaction.objects.create(
                post=post, user=user, reaction_type="like", is_active=True
            )
        return topic

    def _assert_constant_query_count(self, url, content):
        for i in range(2):
            self._make_topic_with_reacted_first_post(f"RC {url} {i}", content)
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.client.get(url).status_code, 200)
        for i in range(2, 6):
            self._make_topic_with_reacted_first_post(f"RC {url} {i}", content)
        with CaptureQueriesContext(connection) as large:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            len(large.captured_queries),
            len(small.captured_queries),
            f"reaction_counts N+1 on {url}: "
            f"{len(small.captured_queries)} -> {len(large.captured_queries)}",
        )

    def test_feed_reaction_counts_no_n_plus_1(self):
        self._assert_constant_query_count(
            "/api/v1/forum/topics/feed/", "<p>feed body</p>"
        )

    def test_search_reaction_counts_no_n_plus_1(self):
        # Term appears only in post content, so only the posts path (which uses
        # PostSerializer) is exercised, not the topic-subject path.
        self._assert_constant_query_count(
            "/api/v1/forum/search/?q=zzqsearchterm", "<p>zzqsearchterm body</p>"
        )
