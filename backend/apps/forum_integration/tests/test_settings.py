import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

_SETTINGS_MODULE = "plant_community_backend.settings"

_INSTALLED_APPS_SCRIPT = (
    "import os, sys; sys.path.insert(0, os.getcwd()); "
    "import django; django.setup(); "
    "from django.conf import settings as s; "
    "print('\\n'.join(s.INSTALLED_APPS))"
)


def _installed_apps_for(*, enable_forum: bool) -> list[str]:
    env = {
        **os.environ,
        "ENABLE_FORUM": "True" if enable_forum else "False",
        "DJANGO_SETTINGS_MODULE": _SETTINGS_MODULE,
    }
    result = subprocess.run(
        [sys.executable, "-c", _INSTALLED_APPS_SCRIPT],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"django.setup() failed (ENABLE_FORUM={enable_forum}):\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )
    return result.stdout.strip().splitlines()


# manage.py check may attempt DB/cache connections via Channels/caching system checks.
def _manage_check(*, enable_forum: bool) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "ENABLE_FORUM": "True" if enable_forum else "False",
        "DJANGO_SETTINGS_MODULE": _SETTINGS_MODULE,
    }
    return subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class ForumStartupCheckTest(SimpleTestCase):
    """manage.py check passes for both ENABLE_FORUM values."""

    def test_check_passes_with_forum_disabled(self):
        result = _manage_check(enable_forum=False)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"manage.py check failed (ENABLE_FORUM=False):\n{result.stderr}\n{result.stdout}",
        )

    def test_check_passes_with_forum_enabled(self):
        result = _manage_check(enable_forum=True)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"manage.py check failed (ENABLE_FORUM=True):\n{result.stderr}\n{result.stdout}",
        )


class EnableForumFalseInstalledAppsTest(SimpleTestCase):
    """INSTALLED_APPS is correct when ENABLE_FORUM=False (headless forum path)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._apps = _installed_apps_for(enable_forum=False)

    def test_headless_forum_in_installed_apps(self):
        self.assertIn("apps.forum", self._apps)

    def test_forum_integration_not_in_installed_apps(self):
        self.assertNotIn("apps.forum_integration", self._apps)

    def test_machina_forum_not_in_installed_apps(self):
        self.assertNotIn("machina.apps.forum", self._apps)


class EnableForumTrueInstalledAppsTest(SimpleTestCase):
    """INSTALLED_APPS is correct when ENABLE_FORUM=True (Machina path)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._apps = _installed_apps_for(enable_forum=True)

    def test_forum_integration_in_installed_apps(self):
        self.assertIn("apps.forum_integration", self._apps)

    def test_headless_forum_not_in_installed_apps(self):
        self.assertNotIn("apps.forum", self._apps)

    def test_machina_forum_in_installed_apps(self):
        self.assertIn("machina.apps.forum", self._apps)
