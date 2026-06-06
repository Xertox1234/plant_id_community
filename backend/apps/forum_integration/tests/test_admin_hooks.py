"""Regression tests for Wagtail global admin hooks.

The Wagtail admin login page (``/cms/login/``) renders every hook registered
for ``insert_global_admin_css`` / ``insert_global_admin_js`` by calling each
with no arguments (``[fn() for fn in hooks.get_hooks(name)]``).  A hook that
raises takes down the *entire* admin.

A bare ``format_html("<link ...>")`` with no interpolation args raises
``TypeError("args or kwargs must be provided.")`` on Django 6.0 (the production
version) — it was only a deprecation warning on 5.x — which 500'd ``/cms/login/``
on 2026-06-06.  These tests call the project's global admin hooks the same way
Wagtail does, so the regression fails fast on the prod-matching Django.
"""

from django.test import SimpleTestCase, override_settings
from django.utils.safestring import SafeString
from wagtail import hooks

# Pin the non-hashing static storage so ``static()`` resolves deterministically
# without a collected manifest (prod uses WhiteNoise's manifest storage).
SIMPLE_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=SIMPLE_STORAGES)
class GlobalAdminHookRenderTests(SimpleTestCase):
    """Every project global-admin hook must render without raising."""

    def _project_hooks(self, hook_name):
        # Limit to this project's hooks; third-party hooks are out of scope.
        return [
            fn for fn in hooks.get_hooks(hook_name) if fn.__module__.startswith("apps.")
        ]

    def test_global_admin_css_hooks_render(self):
        rendered = [fn() for fn in self._project_hooks("insert_global_admin_css")]
        self.assertGreater(len(rendered), 0, "expected at least one project CSS hook")
        for result in rendered:
            self.assertIsInstance(result, SafeString)
            self.assertIn("<link", result)

    def test_global_admin_js_hooks_render(self):
        rendered = [fn() for fn in self._project_hooks("insert_global_admin_js")]
        self.assertGreater(len(rendered), 0, "expected at least one project JS hook")
        for result in rendered:
            self.assertIsInstance(result, SafeString)
            self.assertIn("<script", result)

    def test_forum_hooks_are_registered_and_reference_static_assets(self):
        from apps.forum_integration import wagtail_hooks as forum_hooks

        # Guard the @hooks.register wiring, not just the functions in isolation:
        # a refactor that drops the decorator must fail this test.
        self.assertIn(
            forum_hooks.global_admin_css, hooks.get_hooks("insert_global_admin_css")
        )
        self.assertIn(
            forum_hooks.global_admin_js, hooks.get_hooks("insert_global_admin_js")
        )

        css = forum_hooks.global_admin_css()
        js = forum_hooks.global_admin_js()
        self.assertIn("forum_integration/css/admin.css", css)
        self.assertIn("forum_integration/js/admin.js", js)
