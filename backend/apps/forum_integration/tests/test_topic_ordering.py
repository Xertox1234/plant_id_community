"""ForumTopicsListView honors the `ordering` query param via an allowlist.

Regression coverage for the sort dropdown being non-functional (todo 104).
Run with:
    python manage.py test apps.forum_integration.tests.test_topic_ordering --noinput
"""

from apps.forum_integration.constants import FORUM_TOPIC_ORDERING_MAP
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic
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
class TopicOrderingTests(TestCase):
    """Dropdown values map to safe ORM fields; unknown values fall back."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Ordering Test Forum", type=Forum.FORUM_POST
        )
        cls.user = User.objects.create_user(
            username="ordering_tester",
            email="ordering_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )

        def _make_topic(subject, views, posts):
            topic = Topic.objects.create(
                forum=cls.forum,
                poster=cls.user,
                subject=subject,
                type=Topic.TOPIC_POST,
                status=Topic.TOPIC_UNLOCKED,
                approved=True,
            )
            # .update() bypasses any save-time counter recomputation.
            Topic.objects.filter(pk=topic.pk).update(
                views_count=views, posts_count=posts
            )
            return topic.pk

        # Deliberately non-parallel counts so view-count order and post-count
        # order differ — this proves the param actually changes the results.
        cls.pk_a = _make_topic("Topic A", views=100, posts=1)
        cls.pk_b = _make_topic("Topic B", views=10, posts=50)
        cls.pk_c = _make_topic("Topic C", views=50, posts=5)

        cls.url = f"/api/v1/forum/categories/{cls.forum.id}/topics/"

    def setUp(self):
        self.client = APIClient()

    def _ids(self, ordering=None):
        params = {"ordering": ordering} if ordering is not None else {}
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        return resp, [row["id"] for row in resp.json()["results"]]

    def test_ordering_by_view_count_desc(self):
        _, ids = self._ids("-view_count")
        self.assertEqual(ids, [self.pk_a, self.pk_c, self.pk_b])

    def test_ordering_by_post_count_desc(self):
        _, ids = self._ids("-post_count")
        self.assertEqual(ids, [self.pk_b, self.pk_c, self.pk_a])

    def test_ordering_param_changes_result_order(self):
        # AC: the sort dropdown changes the result order. Two valid orderings
        # produce different sequences over the same data.
        _, by_views = self._ids("-view_count")
        _, by_posts = self._ids("-post_count")
        self.assertNotEqual(by_views, by_posts)

    def test_unknown_ordering_falls_back_to_default(self):
        # AC: unknown values fall back; AC: no raw param reaches .order_by().
        # A malicious value must return 200 (no FieldError 500) and match the
        # default-ordered result.
        resp, garbage_ids = self._ids("'; DROP TABLE forum_conversation_topic; --")
        self.assertEqual(resp.status_code, 200)
        _, default_ids = self._ids()  # no ordering param → default
        self.assertEqual(garbage_ids, default_ids)

    def test_allowlist_covers_every_frontend_dropdown_value(self):
        # Guard against the frontend/backend naming drift this todo fixed:
        # every value the web sort dropdown emits must be in the allowlist,
        # else that option silently falls back to the default.
        frontend_values = {
            "-last_activity_at",  # Recent Activity
            "-created_at",  # Newest First
            "created_at",  # Oldest First
            "-view_count",  # Most Viewed
            "-post_count",  # Most Replies
        }
        self.assertTrue(
            frontend_values.issubset(set(FORUM_TOPIC_ORDERING_MAP)),
            "Frontend dropdown values missing from FORUM_TOPIC_ORDERING_MAP: "
            f"{frontend_values - set(FORUM_TOPIC_ORDERING_MAP)}",
        )

    def test_all_mapped_orm_fields_are_valid(self):
        # Every mapped value must reach .order_by() without a FieldError. A typo
        # in any ORM field (e.g. "-created" → "-creatd") would otherwise pass the
        # key-presence guard above but 500 at request time.
        for frontend_key, orm_field in FORUM_TOPIC_ORDERING_MAP.items():
            with self.subTest(frontend_key=frontend_key, orm_field=orm_field):
                resp, _ = self._ids(frontend_key)
                self.assertEqual(
                    resp.status_code, 200, msg=f"FieldError on {orm_field!r}"
                )
