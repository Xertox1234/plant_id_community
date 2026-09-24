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
from apps.core.security import FAILED_AUTH_TRACKED_PATHS
from apps.users.oauth_adapters import CustomSocialAccountAdapter
from apps.users.oauth_views import oauth_callback
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


class SocialLoginRedirectTests(SimpleTestCase):
    """allauth's post-login redirect used ``reverse("users:oauth_callback")``,
    a name that only the legacy mount registered — removing it would have
    raised NoReverseMatch on every social login. The redirect must keep the
    exact URL it has always emitted, served by the root OAuth mount."""

    def test_redirect_url_is_unchanged_and_routes_to_the_callback_view(self):
        request = RequestFactory().get("/")
        request._oauth_provider = "google"

        url = CustomSocialAccountAdapter(request).get_login_redirect_url(request)

        self.assertEqual(url, "/api/auth/oauth/google/callback/")
        self.assertIs(resolve(url).func, oauth_callback)


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
    """The security middlewares match hard-coded paths. They named only the
    legacy ``/api/auth/...`` paths, so they never fired on real (``/api/v1/``)
    traffic. Every listed path must be a real route."""

    def test_every_listed_path_is_a_real_route(self):
        for path in (*SECURITY_SENSITIVE_PATHS, *FAILED_AUTH_TRACKED_PATHS):
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
        # Todo 419 item 1: the attempted username reaches the tracker. The
        # middleware sees a WSGIRequest whose JSON body DRF has already read,
        # so without caching the body first this was always None.
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

    def test_rejected_firebase_token_exchange_is_tracked(self):
        # Todo 419 item 3: every mobile sign-in goes through the exchange, so
        # a stream of rejected tokens from one IP is the mobile brute force.
        response, track = self._post_tracked(
            "/api/v1/auth/firebase-token-exchange/",
            {"firebase_token": "not-a-real-token", "email": "a@example.com"},
        )

        self.assertEqual(response.status_code, 401)
        track.assert_called_once_with(mock.ANY, None)  # no username to report

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

    def test_middleware_keeps_the_username_when_the_view_consumes_the_stream(self):
        # Pins the pre-read (todo 419 item 1) independently of the test
        # client: a view that reads the raw stream, as DRF's parser does,
        # leaves request.body unreadable unless the middleware cached it.
        import json as _json

        from apps.core.security import SecurityMiddleware
        from django.http import HttpResponse

        def view(request):
            request.read()  # consume the stream, like DRF's JSONParser
            return HttpResponse(status=401)

        request = RequestFactory().post(
            "/api/v1/auth/login/",
            data=_json.dumps({"username": "stream-reader"}),
            content_type="application/json",
        )
        with mock.patch(
            "apps.core.security.SecurityMonitor.track_failed_login"
        ) as track:
            SecurityMiddleware(view)(request)

        track.assert_called_once_with(mock.ANY, "stream-reader")
