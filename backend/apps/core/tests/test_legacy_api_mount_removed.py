"""The legacy unversioned ``/api/`` mount is gone (todo 405 slice 4).

``plant_community_backend/urls.py`` used to mount users, plant-identification,
blog, blog-api and calendar a second time under ``/api/`` with no version. It
duplicated every ``/api/v1/`` route (187 at removal), no client called it (web,
mobile and Cloud Functions all use ``/api/v1/``), and it was load-bearing only
by accident: its un-namespaced include registered the ROOT namespaces
``users:``, ``blog_api:`` ... that a few reverses and path lists still named.

These tests pin the removal and every caller that had to move with it.
"""

import re
from pathlib import Path
from unittest import mock

from apps.blog.models import BlogSeries
from apps.blog.serializers import BlogSeriesSerializer
from apps.core.middleware import SECURITY_SENSITIVE_PATHS, SecurityMetricsMiddleware
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse
from rest_framework.test import APIClient

# One real route per family the legacy mount carried, as (legacy, v1).
FAMILY_PATHS = [
    ("/api/auth/user/", "/api/v1/auth/user/"),
    (
        "/api/plant-identification/identify/",
        "/api/v1/plant-identification/identify/",
    ),
    ("/api/blog/series/", "/api/v1/blog/series/"),
    ("/api/blog-api/plant-stats/", "/api/v1/blog-api/plant-stats/"),
    ("/api/calendar/api/events/", "/api/v1/calendar/api/events/"),
]


def _is_real_route(path):
    """True when ``path`` resolves to an app view, not the Wagtail catch-all.

    The root URLconf ends with ``re_path("", include(wagtail_urls))``, so any
    path "resolves" to ``wagtail_serve`` — which then 404s. A removed route
    therefore shows up as wagtail_serve, not as Resolver404.
    """
    try:
        return resolve(path).url_name != "wagtail_serve"
    except Resolver404:
        return False


class LegacyMountRemovedTests(SimpleTestCase):
    def test_legacy_paths_are_not_routes(self):
        for legacy, _ in FAMILY_PATHS:
            with self.subTest(path=legacy):
                self.assertFalse(_is_real_route(legacy))

    def test_v1_twins_still_route(self):
        for _, v1 in FAMILY_PATHS:
            with self.subTest(path=v1):
                self.assertTrue(_is_real_route(v1))

    def test_root_app_namespaces_are_gone(self):
        # Each name exists under v1: — only the un-versioned root copy is gone.
        for name in (
            "users:current_user",
            "plant_identification:simple_identify",
            "blog:blog-series-list",
            "blog_api:plant_stats",
            "garden_calendar:community-events-list",
        ):
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)
                reverse(f"v1:{name}")


class LegacyMountHttpTests(TestCase):
    """DRF's NamespaceVersioning already 404'd every DRF view under the legacy
    mount ("Invalid version in URL path"), so only plain Django views still
    answered there — these redirected to login (302) until the removal."""

    def test_legacy_plain_django_views_are_404(self):
        for path in (
            "/api/blog/admin/",
            "/api/blog-api/plant-stats/",
            "/api/auth/me/email-preferences/",
        ):
            with self.subTest(path=path):
                self.assertEqual(APIClient().get(path).status_code, 404)


class SeriesPostsUrlTests(TestCase):
    def test_posts_url_points_at_the_v1_route(self):
        series = BlogSeries.objects.create(
            title="Repotting", slug="repotting", description="d"
        )
        request = RequestFactory().get("/")

        url = BlogSeriesSerializer(series, context={"request": request}).data[
            "posts_url"
        ]

        self.assertEqual(url, "http://testserver/api/v1/blog/series/repotting/posts/")
        self.assertEqual(
            resolve(url[len("http://testserver") :]).url_name, "blog-series-posts"
        )


class BlogPostTemplateCommentsFetchTests(SimpleTestCase):
    """The Wagtail-rendered blog page fetches its comments client-side."""

    def test_comments_fetch_path_is_a_real_route(self):
        template = Path(settings.BASE_DIR, "templates/blog/blog_post_page.html")
        match = re.search(r"fetch\(`([^`]*comments/)`\)", template.read_text())
        self.assertIsNotNone(match)

        match = resolve(match.group(1).replace("{{ page.pk }}", "1"))

        self.assertEqual(match.view_name, "v1:blog:blog-posts-comments")
        self.assertEqual(match.kwargs, {"pk": "1"})  # the template sends a pk

    def test_comment_text_is_never_interpolated_into_html(self):
        """The fetch reached a dead route until this slice, so its render code
        never ran. Now it does: comment text is user input and must land via
        textContent, not a template literal assigned to innerHTML."""
        source = Path(
            settings.BASE_DIR, "templates/blog/blog_post_page.html"
        ).read_text()

        self.assertNotRegex(source, r"\$\{\s*comment\.")
        self.assertIn("body.textContent = comment.content", source)
        self.assertIn("author.textContent = comment.author.display_name", source)


class SecurityPathListsTests(TestCase):
    """SecurityMetricsMiddleware matches hard-coded path prefixes. The list
    named only the legacy ``/api/auth/...`` paths, so it never fired on real
    (``/api/v1/``) traffic. Every listed path must be a real route.

    Failed logins were matched by path too, until todo 435 moved that call
    into the login view; the tracking tests below drive the view."""

    def test_every_listed_path_is_a_real_route(self):
        for path in SECURITY_SENSITIVE_PATHS:
            with self.subTest(path=path):
                self.assertTrue(_is_real_route(path))

    def test_v1_login_is_security_sensitive(self):
        middleware = SecurityMetricsMiddleware(get_response=lambda r: None)
        self.assertTrue(
            middleware._is_security_sensitive_endpoint("/api/v1/auth/login/")
        )

    def _post_tracked(self, path, data):
        cache.clear()  # the test cache persists django-ratelimit counters
        with mock.patch(
            "apps.core.security.SecurityMonitor.track_failed_login"
        ) as track:
            response = APIClient().post(path, data, format="json")
        return response, track

    def test_rejected_v1_login_is_tracked(self):
        response, track = self._post_tracked(
            "/api/v1/auth/login/",
            {
                "username": "nobody",
                "password": "wrong-password",  # pragma: allowlist secret
            },
        )

        self.assertEqual(response.status_code, 401)
        # Todo 419 item 1: the attempted username reaches the tracker. Since
        # todo 435 the login view reports it directly; `once` also pins that
        # no middleware branch counts the same 401 a second time.
        track.assert_called_once_with(mock.ANY, "nobody")

    def test_login_validation_error_is_not_tracked(self):
        # A 400 is a malformed form, not a rejected credential.
        response, track = self._post_tracked("/api/v1/auth/login/", {})

        self.assertEqual(response.status_code, 400)
        track.assert_not_called()

    def test_register_validation_error_is_not_tracked(self):
        # Retrying a signup form (username taken, weak password) must not
        # count toward a brute-force alert.
        response, track = self._post_tracked(
            "/api/v1/auth/register/", {"username": "x"}
        )

        self.assertEqual(response.status_code, 400)
        track.assert_not_called()

    def test_rejected_email_login_is_tracked_with_the_email(self):
        # PR #818 review: the web client posts {email, password}, not
        # {username, password}; the tracker must still see the identifier.
        response, track = self._post_tracked(
            "/api/v1/auth/login/",
            {
                "email": "nobody@example.com",
                "password": "wrong-password",  # pragma: allowlist secret
            },
        )

        self.assertEqual(response.status_code, 401)
        track.assert_called_once_with(mock.ANY, "nobody@example.com")

    def test_failed_login_logs_and_alerts_only_a_pseudonym(self):
        from apps.core.security import SecurityMonitor

        cache.clear()
        email = "private.person@example.com"
        with self.assertLogs(
            "apps.core.security", level="WARNING"
        ) as logs, mock.patch.object(
            SecurityMonitor, "_trigger_security_alert"
        ) as alert:
            for _ in range(SecurityMonitor.MAX_FAILED_LOGINS):
                SecurityMonitor.track_failed_login("203.0.113.9", email)

        self.assertNotIn(email, "\n".join(logs.output))
        payload = alert.call_args[0][1]
        self.assertNotIn(email, str(payload))
        self.assertEqual(len(payload["usernames"]), 1)

    def test_security_metrics_keep_no_per_endpoint_cache_state(self):
        # Todo 419 item 2: the write was unbounded (TTL reset on every hit, a
        # growing raw-IP set, lost updates) and nothing read it.
        cache.clear()
        APIClient().post(
            "/api/v1/auth/login/",
            {"username": "nobody", "password": "wrong"},  # pragma: allowlist secret
            format="json",
        )

        self.assertIsNone(cache.get("security_metrics:/api/v1/auth/login/:POST"))

    def test_security_metrics_middleware_writes_nothing_to_the_cache(self):
        # Any key shape, not just the old one (PR #818 review).
        from django.http import HttpResponse

        request = RequestFactory().post("/api/v1/auth/login/")
        with mock.patch("apps.core.middleware.cache") as middleware_cache:
            SecurityMetricsMiddleware(lambda r: HttpResponse(status=401))(request)

        middleware_cache.set.assert_not_called()


class SecurityMiddlewareCleanupTests(SimpleTestCase):
    """Todo 435: the non-blocking findings of the PR #818 review."""

    def test_security_middleware_does_not_read_the_login_body(self):
        # Findings 1 and 4. The middleware buffered every tracked login body
        # before the view's rate limiter could reject the request, to re-parse
        # an identifier the view had already resolved. The view reports its
        # own rejections now (test_rejected_v1_login_is_tracked asserts exactly
        # one tracker call); the middleware leaves the stream untouched and no
        # longer counts a 401 itself.
        from apps.core.security import SecurityMiddleware, SecurityMonitor
        from django.http import HttpResponse

        request = RequestFactory().post(
            "/api/v1/auth/login/",
            data='{"username": "stream-reader"}',
            content_type="application/json",
        )
        with mock.patch.object(SecurityMonitor, "track_failed_login") as track:
            SecurityMiddleware(lambda r: HttpResponse(status=401))(request)

        self.assertFalse(request._read_started)
        track.assert_not_called()

    def test_failed_login_tracker_strips_control_characters(self):
        # The identifier comes from the request body: a newline in it must
        # not break the warning into a forged second line (PR #818 review).
        # The stripping lives in the tracker now that the view calls it with
        # the raw field.
        from apps.core.security import SecurityMonitor

        cache.clear()
        with self.assertLogs("apps.core.security", level="WARNING") as logs:
            SecurityMonitor.track_failed_login(
                "203.0.113.9", "x\n[SECURITY] Successful login"
            )

        self.assertEqual(len(logs.output), 1)
        self.assertNotIn("\n", logs.output[0])
        self.assertIn("username=x[S***", logs.output[0])

    def test_security_metrics_middleware_logs_a_slow_request(self):
        # Finding 2, the behaviour that stays: the slow-request warning.
        from django.http import HttpResponse

        request = RequestFactory().post("/api/v1/auth/login/")
        with mock.patch("apps.core.middleware.SLOW_SECURITY_REQUEST_SECONDS", -1.0):
            with self.assertLogs("apps.core.middleware", level="WARNING") as logs:
                SecurityMetricsMiddleware(lambda r: HttpResponse(status=401))(request)

        self.assertEqual(len(logs.output), 1)
        self.assertIn(
            "Slow security endpoint: endpoint=/api/v1/auth/login/", logs.output[0]
        )
        self.assertIn("user_id=anonymous, status=401", logs.output[0])

    def test_security_metrics_middleware_does_not_resolve_the_client_ip(self):
        # Finding 2, the behaviour that goes: the IP only fed the removed
        # cache key, and resolving it logged one "Invalid IP in
        # X-Forwarded-For" WARNING per bad entry on top of SecurityMiddleware's.
        from apps.core.security import SecurityMonitor
        from django.http import HttpResponse
        from django.test import override_settings

        request = RequestFactory().post(
            "/api/v1/auth/login/", HTTP_X_FORWARDED_FOR="not-an-ip"
        )
        with override_settings(USE_X_FORWARDED_HOST=True):
            # Control: resolving this request's IP does warn.
            with self.assertLogs("apps.core.security", level="WARNING"):
                SecurityMonitor._get_client_ip(request)

            with self.assertNoLogs("apps.core.security", level="WARNING"):
                SecurityMetricsMiddleware(lambda r: HttpResponse(status=401))(request)

    def test_security_modules_import_their_constants_unconditionally(self):
        # Finding 3: both modules carried a `try: from .constants import ...
        # except ImportError:` fallback below an unconditional import of the
        # same module, so the fallback values could never run and would have
        # drifted from constants.py unnoticed.
        import ast
        import inspect

        from apps.core import middleware, security

        for module in (security, middleware):
            with self.subTest(module=module.__name__):
                handlers = [
                    ast.unparse(node.type)
                    for node in ast.walk(ast.parse(inspect.getsource(module)))
                    if isinstance(node, ast.ExceptHandler) and node.type is not None
                ]
                self.assertNotIn("ImportError", " ".join(handlers))

    def test_failed_login_warning_pseudonymizes_the_ip_but_the_alert_keeps_it(self):
        # Finding 5, owner decision: the log line gets log_safe_ip like the
        # rest of the module; the brute_force_login alert payload keeps the
        # raw address so an operator can block it.
        from apps.core.security import SecurityMonitor
        from apps.core.utils.pii_safe_logging import log_safe_ip

        cache.clear()
        ip = "203.0.113.9"
        with mock.patch.object(SecurityMonitor, "_trigger_security_alert") as alert:
            with self.assertLogs("apps.core.security", level="WARNING") as logs:
                for _ in range(SecurityMonitor.MAX_FAILED_LOGINS):
                    SecurityMonitor.track_failed_login(ip, "someone")

        joined = "\n".join(logs.output)
        self.assertNotIn(ip, joined)
        self.assertIn(f"ip={log_safe_ip(ip)}", joined)
        alert.assert_called_once()
        self.assertEqual(alert.call_args[0][1]["ip_address"], ip)
