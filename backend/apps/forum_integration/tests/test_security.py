"""Security regression suite for the forum API.

Tests are accumulated here as tasks complete.  Run the full suite with:
    python manage.py test apps.forum_integration.tests.test_security --noinput
"""

import io

from apps.forum_integration.constants import FORUM_MAX_PAGE_SIZE
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Post, Topic
from PIL import Image
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


def _make_png_bytes(width=10, height=10):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(100, 200, 50)).save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


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


# ---------------------------------------------------------------------------
# Task 11: security regression suite
# ---------------------------------------------------------------------------


@override_settings(ENABLE_FORUM=True)
class StoredXSSTests(TestCase):
    """Sanitization on write: stored XSS cannot survive create or update."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="XSS Test Forum", type=Forum.FORUM_POST)
        cls.user = User.objects.create_user(
            username="xss_tester",
            email="xss_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="XSS Test Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic,
            poster=cls.user,
            content="<p>original</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_topic_sanitizes_xss(self):
        url = f"/api/v1/forum/categories/{self.forum.id}/topics/create/"
        resp = self.client.post(
            url,
            {
                "subject": "XSS Topic",
                "content": "<p>Hello</p><script>alert(1)</script>",
                "content_format": "html",
            },
        )
        self.assertEqual(resp.status_code, 201)
        first_post_id = resp.data.get("first_post_id")
        self.assertIsNotNone(first_post_id)
        post = Post.objects.get(id=first_post_id)
        content = str(post.content)
        self.assertNotIn("<script", content)
        self.assertIn("<p>Hello</p>", content)

    def test_update_post_sanitizes_xss(self):
        url = f"/api/v1/forum/posts/{self.post.id}/"
        resp = self.client.patch(
            url,
            {
                "content": "<p>Updated</p><script>evil()</script>",
                "content_format": "html",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.post.refresh_from_db()
        content = str(self.post.content)
        self.assertNotIn("<script", content)
        self.assertIn("<p>Updated</p>", content)


@override_settings(ENABLE_FORUM=True)
class ContentFormatValidationTests(TestCase):
    """content_format ChoiceField rejects values outside {plain, draftail, html}."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Format Test Forum", type=Forum.FORUM_POST
        )
        cls.user = User.objects.create_user(
            username="format_tester",
            email="format_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_invalid_content_format_rejected(self):
        url = f"/api/v1/forum/categories/{self.forum.id}/topics/create/"
        resp = self.client.post(
            url,
            {
                "subject": "Format Topic",
                "content": "<p>Hello</p>",
                "content_format": "javascript",
            },
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(ENABLE_FORUM=True)
class PaginationCapTests(TestCase):
    """page_size=100000 is capped at FORUM_MAX_PAGE_SIZE."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Pagination Test Forum", type=Forum.FORUM_POST
        )
        cls.user = User.objects.create_user(
            username="pagination_tester",
            email="pagination_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        for i in range(FORUM_MAX_PAGE_SIZE + 5):
            Topic.objects.create(
                forum=cls.forum,
                poster=cls.user,
                subject=f"Pagination Topic {i}",
                type=Topic.TOPIC_POST,
                status=Topic.TOPIC_UNLOCKED,
                approved=True,
            )

    def setUp(self):
        self.client = APIClient()

    def test_page_size_capped_at_maximum(self):
        resp = self.client.get("/api/v1/forum/topics/?page_size=100000")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertLessEqual(len(data["results"]), FORUM_MAX_PAGE_SIZE)


@override_settings(ENABLE_FORUM=True)
class ImageUploadValidationTests(TestCase):
    """4-layer upload validation: extension, MIME, size, PIL magic-number."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Image Upload Test Forum", type=Forum.FORUM_POST
        )
        cls.superuser = User.objects.create_superuser(
            username="img_superuser",
            email="img_superuser@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.superuser,
            subject="Image Upload Test Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic,
            poster=cls.superuser,
            content="<p>image test post</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.superuser)
        self.url = f"/api/v1/forum/posts/{self.post.id}/images/upload/"

    def test_spoofed_mime_upload_rejected(self):
        fake_file = SimpleUploadedFile(
            "spoof.jpg", b"this is not an image", content_type="image/jpeg"
        )
        resp = self.client.post(self.url, {"images": fake_file}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_oversized_upload_rejected(self):
        big_data = b"\x00" * (6 * 1024 * 1024)  # 6 MB of zeros
        big_file = SimpleUploadedFile("big.jpg", big_data, content_type="image/jpeg")
        resp = self.client.post(self.url, {"images": big_file}, format="multipart")
        self.assertEqual(resp.status_code, 400)

    def test_valid_png_accepted(self):
        png_bytes = _make_png_bytes()
        valid_file = SimpleUploadedFile(
            "valid.png", png_bytes, content_type="image/png"
        )
        resp = self.client.post(self.url, {"images": valid_file}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("images", resp.data)
        self.assertEqual(len(resp.data["images"]), 1)


@override_settings(ENABLE_FORUM=True)
class RateLimitTests(TestCase):
    """Rate-limited endpoints return 429 (not 403) via the custom exception handler."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_search_rate_limit_returns_429(self):
        from apps.forum_integration.constants import FORUM_RATE_LIMITS

        limit_str = FORUM_RATE_LIMITS["search"]
        limit = int(limit_str.split("/")[0])

        for _ in range(limit):
            resp = self.client.get("/api/v1/forum/search/?q=rose")
            self.assertNotEqual(resp.status_code, 429, "Hit limit too early")

        resp = self.client.get("/api/v1/forum/search/?q=rose")
        self.assertEqual(resp.status_code, 429)


@override_settings(ENABLE_FORUM=True)
class OwnershipAuthzTests(TestCase):
    """Non-owner cannot edit or delete a post."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="Authz Test Forum", type=Forum.FORUM_POST)
        cls.user_a = User.objects.create_user(
            username="authz_user_a",
            email="authz_a@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.user_b = User.objects.create_user(
            username="authz_user_b",
            email="authz_b@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user_a,
            subject="Authz Test Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic,
            poster=cls.user_a,
            content="<p>user_a's post</p>",
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user_b)

    def test_non_owner_cannot_edit_post(self):
        resp = self.client.patch(
            f"/api/v1/forum/posts/{self.post.id}/",
            {"content": "<p>hijacked</p>", "content_format": "html"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_non_owner_cannot_delete_post(self):
        resp = self.client.delete(f"/api/v1/forum/posts/{self.post.id}/delete/")
        self.assertEqual(resp.status_code, 403)


@override_settings(ENABLE_FORUM=True)
class IDORTests(TestCase):
    """Authenticated user cannot enumerate another user's topic list."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="IDOR Test Forum", type=Forum.FORUM_POST)
        cls.user_a = User.objects.create_user(
            username="idor_user_a",
            email="idor_a@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.user_b = User.objects.create_user(
            username="idor_user_b",
            email="idor_b@example.com",
            password="pass123!",  # pragma: allowlist secret
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user_b)

    def test_user_cannot_access_other_users_topics(self):
        resp = self.client.get(f"/api/v1/forum/users/{self.user_a.id}/topics/")
        self.assertEqual(resp.status_code, 403)
