"""
Wagtail admin render smoke tests (todo 217).

Guards the `/cms/` admin render path end to end. A global admin hook or admin
template that raises — e.g. the Django 6.0 `format_html("<literal>")` no-arg
`TypeError` that 500'd *all* of `/cms/` (including the login page) in production
on 2026-06-06 — fails these tests instead of shipping undetected.

Placement note: this lives in `apps/blog/tests/` because at the time of writing
forum apps were gated behind `ENABLE_FORUM` (off in CI) and a smoke test there
would not have run. That flag was removed on 2026-06-10 (forum apps are always
installed), but blog remains a fine home for a global admin render gate. See
todo 217 for the forum admin-hook coverage decision.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class WagtailAdminRenderSmokeTests(TestCase):
    """Render the admin login page and the authenticated dashboard."""

    def test_cms_login_page_renders(self):
        """Unauthenticated login page renders (200), not a 500.

        `insert_global_admin_css`/`insert_global_admin_js` hooks render on every
        admin page including login, so a raising global hook surfaces here.
        `secure=True` clears `SECURE_SSL_REDIRECT` (active when `DEBUG=False`).
        """
        response = self.client.get(reverse("wagtailadmin_login"), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_admin_dashboard_renders(self):
        """A superuser hitting the admin home renders the dashboard (200), not 500.

        Exercises `construct_homepage_panels` (the blog summary panel's
        `format_html`) plus admin templates and static resolution end to end.
        """
        admin = User.objects.create_superuser(
            username="smoke-admin",
            email="smoke-admin@example.com",
            password="smoke-admin-pw-217",  # pragma: allowlist secret
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("wagtailadmin_home"), secure=True)
        self.assertEqual(response.status_code, 200)
