"""Security regression suite for the forum API.

Tests are accumulated here as tasks complete.  Run the full suite with:
    python manage.py test apps.forum_integration.tests.test_security --noinput
"""

import io
from unittest import mock

from apps.forum_integration.constants import (
    FORUM_IMAGE_MAX_PER_POST,
    FORUM_MAX_PAGE_SIZE,
    FORUM_RATE_LIMITS,
)
from apps.forum_integration.models import ForumPostImage, RichPost
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from freezegun import freeze_time
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

    def test_crash_mid_run_rolls_back_all_changes(self):
        # todo 114: the whole run is atomic. If sanitization raises partway, every
        # already-sanitized post must roll back — no half-cleaned table.
        self._make_post("<p>one</p><script>a()</script>")
        self._make_post("<p>two</p><script>b()</script>")

        calls = {"n": 0}

        def flaky(_html):
            # 1st post: return a changed value (triggers a save inside the atomic
            # block). 2nd post: raise, which must roll back the 1st post's save.
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated crash mid-run")
            return "<p>sanitized</p>"

        with mock.patch(
            "apps.forum_integration.management.commands."
            "sanitize_forum_content.sanitize_forum_html",
            side_effect=flaky,
        ):
            with self.assertRaises(RuntimeError):
                call_command("sanitize_forum_content", verbosity=0)

        # The first post's sanitization was rolled back: both posts still hold
        # their original (un-sanitized) content.
        for post in Post.objects.all():
            self.assertIn("<script", str(post.content))


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

    def test_upload_exceeding_max_per_post_rejected(self):
        # todo 113: a batch that would exceed the per-post cap is rejected by the
        # count check (now performed under a select_for_update row lock), and NO
        # images are partially created.
        files = [
            SimpleUploadedFile(
                f"img{i}.png", _make_png_bytes(), content_type="image/png"
            )
            for i in range(FORUM_IMAGE_MAX_PER_POST + 1)
        ]
        resp = self.client.post(self.url, {"images": files}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(ForumPostImage.objects.filter(post=self.post).count(), 0)

    def test_cap_enforced_with_existing_images(self):
        # todo 113: the race-relevant path — images already exist and a new batch
        # crosses the cap (existing_count > 0). Seed MAX-1, upload 2 → 400, and the
        # existing rows are untouched.
        for i in range(FORUM_IMAGE_MAX_PER_POST - 1):
            png = _make_png_bytes()
            ForumPostImage.objects.create(
                post=self.post,
                image=SimpleUploadedFile(f"seed{i}.png", png, content_type="image/png"),
                original_filename=f"seed{i}.png",
                file_size=len(png),
                # Explicit non-zero order: the model's auto-assign has a separate
                # bug (`max_order or -1` treats order 0 as falsy → collides on the
                # 2nd image) — tracked in todo 116. The cap check is count-based,
                # so the order values are irrelevant here.
                upload_order=i + 1,
            )
        extra = [
            SimpleUploadedFile(
                f"extra{i}.png", _make_png_bytes(), content_type="image/png"
            )
            for i in range(2)
        ]
        resp = self.client.post(self.url, {"images": extra}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            ForumPostImage.objects.filter(post=self.post).count(),
            FORUM_IMAGE_MAX_PER_POST - 1,
        )

    def test_partial_success_with_invalid_file_in_batch(self):
        # todo 113: under the new atomic block, a mixed batch still commits the
        # valid file and reports the invalid one (partial-success preserved).
        valid = SimpleUploadedFile(
            "ok.png", _make_png_bytes(), content_type="image/png"
        )
        bad = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        resp = self.client.post(self.url, {"images": [valid, bad]}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["images"]), 1)
        self.assertEqual(len(resp.data.get("errors", [])), 1)
        self.assertEqual(ForumPostImage.objects.filter(post=self.post).count(), 1)

    def test_multiple_images_get_sequential_upload_orders(self):
        # todo 116: uploading several images in one request must assign distinct
        # sequential upload_orders (0, 1, 2). Before the fix the 2nd image computed
        # `(0 or -1) + 1 == 0` and collided on unique_together(post, upload_order).
        files = [
            SimpleUploadedFile(
                f"seq{i}.png", _make_png_bytes(), content_type="image/png"
            )
            for i in range(3)
        ]
        resp = self.client.post(self.url, {"images": files}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data["images"]), 3)
        orders = sorted(
            ForumPostImage.objects.filter(post=self.post).values_list(
                "upload_order", flat=True
            )
        )
        self.assertEqual(orders, [0, 1, 2])

    def test_update_image_metadata_preserves_upload_order(self):
        # todo 116: editing metadata must NOT relocate upload_order — the save()
        # auto-assign is insert-only. Without the pk-is-None guard, patching the
        # order-0 image would re-fire the auto-assign and bump it to max+1.
        files = [
            SimpleUploadedFile(f"u{i}.png", _make_png_bytes(), content_type="image/png")
            for i in range(2)
        ]
        self.client.post(self.url, {"images": files}, format="multipart")
        first = (
            ForumPostImage.objects.filter(post=self.post)
            .order_by("upload_order")
            .first()
        )
        self.assertEqual(first.upload_order, 0)

        patch_url = f"/api/v1/forum/posts/{self.post.id}/images/{first.id}/"
        resp = self.client.patch(patch_url, {"alt_text": "edited"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["image"]["upload_order"], 0)
        first.refresh_from_db()
        self.assertEqual(first.upload_order, 0)
        self.assertEqual(first.alt_text, "edited")


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

        # Freeze time so all requests share one rate-limit window (see
        # MissingRateLimitTests._assert_429_after_limit for the rationale).
        with freeze_time("2026-05-28 12:00:00"):
            for _ in range(limit):
                resp = self.client.get("/api/v1/forum/search/?q=rose")
                self.assertNotEqual(resp.status_code, 429, "Hit limit too early")

            resp = self.client.get("/api/v1/forum/search/?q=rose")
        self.assertEqual(resp.status_code, 429)
        # todo 115: Retry-After reflects the 30/m window (60s), not a flat 3600.
        self.assertEqual(resp["Retry-After"], "60")


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


@override_settings(ENABLE_FORUM=True)
class MissingRateLimitTests(TestCase):
    """Previously-unthrottled mutating endpoints now return 429 (todos 106-109).

    Each endpoint routes through the custom exception handler that converts
    django-ratelimit's Ratelimited into a 429 (not the DRF-default 403).
    """

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(name="RL Forum", type=Forum.FORUM_POST)
        cls.user = User.objects.create_user(
            username="rl_user",
            email="rl_user@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="RL Topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        cls.post = Post.objects.create(
            topic=cls.topic, poster=cls.user, content="<p>rl</p>", approved=True
        )

    def setUp(self):
        cache.clear()  # reset rate-limit counters between tests
        self.client = APIClient()

    def _assert_429_after_limit(self, rate_key, send):
        """`send()` issues one request; it must 429 only AFTER `limit` calls."""
        limit = int(FORUM_RATE_LIMITS[rate_key].split("/")[0])
        # Freeze time so every request lands in the same rate-limit window — the
        # per-key jittered 60s window could otherwise roll over mid-hammer and
        # reset the counter, making the test flaky in long suite runs.
        with freeze_time("2026-05-28 12:00:00"):
            for _ in range(limit):
                self.assertNotEqual(send().status_code, 429, "Hit the limit too early")
            self.assertEqual(send().status_code, 429)

    def test_mark_viewed_rate_limited(self):
        # 106: AllowAny, keyed by IP.
        url = f"/api/v1/forum/topics/{self.topic.id}/mark-viewed/"
        self._assert_429_after_limit("mark_viewed", lambda: self.client.post(url))

    def test_topic_update_rate_limited(self):
        # 107: keyed by user. The user is the topic poster, so ownership passes.
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/forum/topics/{self.topic.id}/update/"
        self._assert_429_after_limit(
            "update_topic",
            lambda: self.client.patch(url, {"is_locked": True}, format="json"),
        )

    def test_image_delete_rate_limited(self):
        # 108: a nonexistent image_id still enters the delete handler (404 is
        # raised inside, after the rate-limit increment), so it counts.
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/forum/posts/{self.post.id}/images/999999/delete/"
        self._assert_429_after_limit("image_delete", lambda: self.client.delete(url))

    def test_image_update_rate_limited(self):
        # 109: same nonexistent-image reasoning as the delete case.
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/forum/posts/{self.post.id}/images/999999/"
        self._assert_429_after_limit(
            "image_update",
            lambda: self.client.patch(url, {"alt_text": "x"}, format="json"),
        )

    def test_retry_after_reflects_hourly_window(self):
        # todo 115: an /h-rated endpoint (create_topic = 10/h) returns
        # Retry-After 3600, proving the header is derived from the rate window —
        # not a flat 60 (which the /m search assertion alone could not rule out).
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/forum/categories/{self.forum.id}/topics/create/"
        payload = {"subject": "rl", "content": "<p>x</p>", "content_format": "html"}
        limit = int(FORUM_RATE_LIMITS["create_topic"].split("/")[0])
        with freeze_time("2026-05-28 12:00:00"):
            for _ in range(limit):
                self.assertNotEqual(
                    self.client.post(url, payload, format="json").status_code,
                    429,
                    "Hit the limit too early",
                )
            resp = self.client.post(url, payload, format="json")
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp["Retry-After"], "3600")


# ---------------------------------------------------------------------------
# PR-291: CreatePostSerializer.update() — PATCH must not drop rich_content
# ---------------------------------------------------------------------------


@override_settings(ENABLE_FORUM=True)
class PatchPostRichContentTests(TestCase):
    """PATCH /api/v1/forum/posts/<id>/ must persist rich_content via RichPost."""

    @classmethod
    def setUpTestData(cls):
        _ensure_site()
        cls.forum = Forum.objects.create(
            name="Patch Rich Content Forum", type=Forum.FORUM_POST
        )
        cls.user = User.objects.create_user(
            username="patch_rich_tester",
            email="patch_rich_tester@example.com",
            password="pass123!",  # pragma: allowlist secret
        )
        cls.topic = Topic.objects.create(
            forum=cls.forum,
            poster=cls.user,
            subject="Patch rich content topic",
            type=Topic.TOPIC_POST,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _make_post(self, content="<p>initial</p>"):
        return Post.objects.create(
            topic=self.topic, poster=self.user, content=content, approved=True
        )

    def test_patch_with_rich_content_updates_rich_post_record(self):
        post = self._make_post()
        RichPost.objects.create(
            post=post,
            rich_content=[{"type": "paragraph", "value": "old"}],
            content_format="draftail",
        )
        new_blocks = [{"type": "paragraph", "value": "updated"}]

        resp = self.client.patch(
            f"/api/v1/forum/posts/{post.id}/",
            {
                "content": "<p>updated</p>",
                "content_format": "draftail",
                "rich_content": new_blocks,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        rich_post = RichPost.objects.get(post=post)
        self.assertEqual(rich_post.rich_content, new_blocks)
        self.assertEqual(rich_post.content_format, "draftail")

    def test_patch_creates_rich_post_when_post_had_none(self):
        post = self._make_post()
        self.assertFalse(RichPost.objects.filter(post=post).exists())
        blocks = [{"type": "paragraph", "value": "new rich"}]

        resp = self.client.patch(
            f"/api/v1/forum/posts/{post.id}/",
            {
                "content": "<p>rich now</p>",
                "content_format": "draftail",
                "rich_content": blocks,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        rich_post = RichPost.objects.get(post=post)
        self.assertEqual(rich_post.rich_content, blocks)

    def test_patch_plain_content_does_not_create_rich_post(self):
        post = self._make_post()
        self.assertFalse(RichPost.objects.filter(post=post).exists())

        resp = self.client.patch(
            f"/api/v1/forum/posts/{post.id}/",
            {"content": "<p>just plain</p>"},
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(RichPost.objects.filter(post=post).exists())

    def test_patch_ai_metadata_persisted_on_rich_post(self):
        post = self._make_post()
        prompts = ["describe this plant"]

        resp = self.client.patch(
            f"/api/v1/forum/posts/{post.id}/",
            {
                "content": "<p>ai content</p>",
                "content_format": "draftail",
                "rich_content": [{"type": "paragraph", "value": "ai"}],
                "ai_assisted": True,
                "ai_prompts_used": prompts,
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 200)
        rich_post = RichPost.objects.get(post=post)
        self.assertTrue(rich_post.ai_assisted)
        self.assertEqual(rich_post.ai_prompts_used, prompts)
