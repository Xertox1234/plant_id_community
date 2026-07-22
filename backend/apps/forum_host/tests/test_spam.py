"""Tests for the host-side forum spam backend (todo 255 slice 2 / H13)."""

import time
from types import SimpleNamespace
from unittest.mock import patch

from apps.forum_host import constants
from apps.forum_host.spam import LLMSpamBackend
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from wagtail_forum.spam import get_spam_backend
from wagtail_forum.spam.heuristic import HeuristicSpamBackend


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


# Patch the names as bound INTO the spam module, not at their source.
GEN = "apps.forum_host.spam.generate_ai_text"
BUDGET = "apps.forum_host.spam.AIRateLimiter.check_global_limit"


class LLMSpamBackendTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch(GEN)
    def test_heuristic_flag_short_circuits_with_no_llm_call(self, mock_gen):
        with self.settings(WAGTAILFORUM_SPAM_BANNED_WORDS=["casino"]):
            result = LLMSpamBackend().check(_post(title="Win", body="visit my casino"))
        self.assertFalse(result.is_clean)
        self.assertIn("casino", result.reason.lower())
        mock_gen.assert_not_called()

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="CLEAN")
    def test_heuristic_clean_then_llm_clean_publishes(self, mock_gen, _budget):
        result = LLMSpamBackend().check(_post())
        self.assertTrue(result.is_clean)
        mock_gen.assert_called_once()

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="SPAM: promotional link farm")
    def test_llm_flags_spam(self, mock_gen, _budget):
        result = LLMSpamBackend().check(_post())
        self.assertFalse(result.is_clean)
        self.assertIn("promotional", result.reason.lower())

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="CLEAN")
    def test_verdict_is_cached_second_check_skips_llm(self, mock_gen, _budget):
        backend = LLMSpamBackend()
        backend.check(_post(body="identical body"))
        backend.check(_post(body="identical body"))
        mock_gen.assert_called_once()

    @patch(BUDGET, return_value=True)
    @patch("apps.forum_host.constants.SPAM_LLM_TIMEOUT_SECONDS", 0.2)
    def test_timeout_fails_closed(self, _budget):
        def slow(*args, **kwargs):
            time.sleep(2)
            return "CLEAN"

        with patch(GEN, side_effect=slow):
            started = time.monotonic()
            result = LLMSpamBackend().check(_post())
            elapsed = time.monotonic() - started

        # Fail closed: a completed slow() would have parsed to CLEAN (is_clean
        # True), so is_clean False can only come from the timeout path.
        self.assertFalse(result.is_clean)
        self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)
        self.assertLess(elapsed, 1.5)  # returned well before the 2s sleep

    @patch(BUDGET, return_value=True)
    @patch(GEN, side_effect=RuntimeError("provider down"))
    def test_exception_fails_closed(self, _gen, _budget):
        result = LLMSpamBackend().check(_post())
        self.assertFalse(result.is_clean)
        self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="hmm, maybe, not sure")
    def test_unparseable_reply_fails_closed_and_is_not_cached(self, mock_gen, _budget):
        backend = LLMSpamBackend()
        result = backend.check(_post())
        self.assertFalse(result.is_clean)
        self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)
        # Not cached (transient): a second identical check calls the LLM again.
        backend.check(_post())
        self.assertEqual(mock_gen.call_count, 2)

    @patch(BUDGET, return_value=False)
    @patch(GEN)
    def test_budget_exhausted_degrades_to_heuristic(self, mock_gen, _budget):
        result = LLMSpamBackend().check(_post())
        self.assertTrue(result.is_clean)  # degrade to heuristic → publish
        mock_gen.assert_not_called()  # no spend past the cap

    def test_dormant_default_backend_is_heuristic(self):
        self.assertIsInstance(get_spam_backend(), HeuristicSpamBackend)

    @override_settings(WAGTAILFORUM_SPAM_BACKEND="apps.forum_host.spam.LLMSpamBackend")
    def test_one_setting_swap_selects_llm_backend(self):
        self.assertIsInstance(get_spam_backend(), LLMSpamBackend)
