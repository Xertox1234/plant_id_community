"""Tests for the host-side forum spam backend (todo 255 slice 2 / H13)."""

from types import SimpleNamespace

from django.conf import settings
from django.test import TestCase


class _FakeBody:
    """Mimic a StreamValue: iterating yields blocks with a ``.value``."""

    def __init__(self, text: str):
        self._blocks = [SimpleNamespace(value=text)]

    def __iter__(self):
        return iter(self._blocks)


def _post(title: str = "Hello", body: str = "a normal gardening post"):
    """A minimal Topic/Post stand-in for extract_text()."""
    return SimpleNamespace(title=title, body=_FakeBody(body))


class SpamBackendSettingTests(TestCase):
    def test_spam_backend_setting_defaults_to_heuristic(self):
        # The env var is unset in tests, so the config() default applies.
        self.assertEqual(
            settings.WAGTAILFORUM_SPAM_BACKEND,
            "wagtail_forum.spam.heuristic.HeuristicSpamBackend",
        )
