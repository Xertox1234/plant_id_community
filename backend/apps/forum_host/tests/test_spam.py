"""Tests for the host-side forum spam backend (todo 255 slice 2 / H13)."""

import time
from types import SimpleNamespace
from unittest.mock import patch

from apps.forum_host import constants
from apps.forum_host.spam import LLMSpamBackend
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from wagtail_forum.spam import base as spam_base
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
BUDGET = "apps.forum_host.spam.AIRateLimiter.peek_budget"
LIMIT = "apps.forum_host.constants.SPAM_LLM_BUDGET_LIMIT"


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

    @patch(GEN)
    def test_empty_text_is_clean_without_llm(self, mock_gen):
        # Empty title+body: heuristic passes, extract_text is blank, so we
        # short-circuit to clean before any budget/LLM spend.
        result = LLMSpamBackend().check(_post(title="", body=""))
        self.assertTrue(result.is_clean)
        mock_gen.assert_not_called()

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="SPAM: casino promo")
    def test_spam_verdict_is_cached_second_check_skips_llm(self, mock_gen, _budget):
        backend = LLMSpamBackend()
        first = backend.check(_post(body="buy now at my shop"))
        second = backend.check(_post(body="buy now at my shop"))
        self.assertFalse(first.is_clean)
        self.assertFalse(second.is_clean)
        # Cached SPAM verdict is re-served verbatim, no second LLM call.
        self.assertEqual(second.reason, first.reason)
        self.assertIn("casino", second.reason.lower())
        mock_gen.assert_called_once()

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="SPAM:promotional link farm")
    def test_spam_reason_survives_a_missing_space_after_the_colon(
        self, mock_gen, _budget
    ):
        # The model does not reliably put a space after the colon. Splitting on
        # whitespace would truncate this reason to its last word ("farm"), so
        # the verdict word is stripped as a prefix instead.
        result = LLMSpamBackend().check(_post(body="a no-space-colon body"))
        self.assertEqual(result.reason, "AI: promotional link farm")

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="SPAMMY: too promotional")
    def test_spam_lookalike_verdict_word_is_stripped_whole(self, mock_gen, _budget):
        # "SPAMMY" still flags (safe direction), but the reason must not carry
        # the tail of the verdict word — the old len("SPAM") slice gave "MY:".
        result = LLMSpamBackend().check(_post(body="a spammy-word body"))
        self.assertEqual(result.reason, "AI: too promotional")

    @patch(BUDGET, return_value=True)
    @patch(GEN, return_value="CLEANLY a legitimate post, not spam")
    def test_clean_lookalike_reply_fails_closed_and_is_not_cached(
        self, mock_gen, _budget
    ):
        backend = LLMSpamBackend()
        result = backend.check(_post(body="lookalike body"))
        # "CLEANLY ..." must NOT be read as CLEAN — it fails closed (held).
        self.assertFalse(result.is_clean)
        self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)
        # Not cached (ambiguous/transient): a second identical check re-calls.
        backend.check(_post(body="lookalike body"))
        self.assertEqual(mock_gen.call_count, 2)


class LLMSpamBudgetAccountingTests(TestCase):
    """H13 items 1 + 3 — budget is consumed ONLY by calls that reached the
    provider, and on a forum-private counter.

    These tests deliberately do NOT patch the budget methods: they read the
    real counter out of the cache, because the whole point is what gets
    written to it.
    """

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _spent(self) -> int:
        return cache.get(constants.SPAM_LLM_BUDGET_CACHE_KEY, 0)

    @patch(GEN, return_value="CLEAN")
    def test_successful_screen_consumes_one_unit(self, mock_gen):
        result = LLMSpamBackend().check(_post(body="a first body"))
        self.assertTrue(result.is_clean)
        self.assertEqual(self._spent(), 1)

    @patch(GEN, return_value="CLEAN")
    def test_cached_verdict_consumes_nothing_extra(self, mock_gen):
        backend = LLMSpamBackend()
        backend.check(_post(body="a repeated body"))
        backend.check(_post(body="a repeated body"))
        mock_gen.assert_called_once()
        self.assertEqual(self._spent(), 1)  # not 2 — the re-screen was free

    @patch(GEN, return_value="not a verdict at all")
    def test_unparseable_reply_consumes_nothing(self, mock_gen):
        # No verdict came back, so nothing is spent — the acceptance criterion
        # lists "unparseable" alongside timeout and exception.
        result = LLMSpamBackend().check(_post(body="an unparseable body"))
        self.assertFalse(result.is_clean)
        self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)
        self.assertEqual(self._spent(), 0)

    @patch(LIMIT, 3)
    @patch(GEN, return_value="not a verdict at all")
    def test_sustained_unparseable_replies_burn_nothing(self, mock_gen):
        """The subtlest arm of criterion 1.

        Unparseable verdicts are deliberately NOT cached (they are transient),
        so every retry re-calls the provider. If those calls consumed budget, a
        provider stuck emitting garbage would drain the cap and flip the
        backend to degrade-to-heuristic — publishing unscreened — which is the
        very posture change this todo exists to prevent.
        """
        backend = LLMSpamBackend()
        attempts = 3 + 5  # deliberately past the patched cap

        for i in range(attempts):
            result = backend.check(_post(body=f"a garbage-reply body {i}"))
            self.assertFalse(result.is_clean, f"attempt {i} published")
            self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)

        self.assertEqual(mock_gen.call_count, attempts)
        self.assertEqual(self._spent(), 0)

    @patch(LIMIT, 3)
    @patch(GEN, side_effect=RuntimeError("provider down"))
    def test_sustained_outage_burns_nothing_and_never_flips_to_publish(self, mock_gen):
        """The H13 item 1 regression: N > limit consecutive provider failures.

        Before the peek/consume split these burned budget, exhausted the cap,
        and flipped the backend from fail-closed (hold) to
        degrade-to-heuristic (publish LLM-unscreened) — a spam-publishing
        posture reached purely by the provider being down.
        """
        backend = LLMSpamBackend()
        attempts = 3 + 5  # deliberately past the patched cap

        for i in range(attempts):
            result = backend.check(_post(body=f"an outage body {i}"))
            self.assertFalse(result.is_clean, f"attempt {i} published")
            self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)

        self.assertEqual(mock_gen.call_count, attempts)  # never short-circuited
        self.assertEqual(self._spent(), 0)  # nothing burned

    @patch(LIMIT, 2)
    @patch("apps.forum_host.constants.SPAM_LLM_TIMEOUT_SECONDS", 0.05)
    def test_sustained_timeouts_burn_nothing(self):
        """The timeout path must not consume budget either."""

        def slow(*args, **kwargs):
            time.sleep(0.4)
            return "CLEAN"

        with patch(GEN, side_effect=slow):
            for i in range(4):  # past the patched cap of 2
                result = LLMSpamBackend().check(_post(body=f"a slow body {i}"))
                self.assertFalse(result.is_clean)
                self.assertEqual(result.reason, constants.SPAM_LLM_UNAVAILABLE_REASON)

        self.assertEqual(self._spent(), 0)

    def test_exhausted_budget_degrades_to_heuristic_publish(self):
        """A deliberate cap is a COST decision — it still publishes."""
        cache.set(
            constants.SPAM_LLM_BUDGET_CACHE_KEY,
            constants.SPAM_LLM_BUDGET_LIMIT,
            constants.SPAM_LLM_CACHE_TTL_SECONDS,
        )

        with patch(GEN) as mock_gen:
            result = LLMSpamBackend().check(_post(body="an over-cap body"))

        self.assertTrue(result.is_clean)  # degrade to heuristic → publish
        mock_gen.assert_not_called()  # no spend past the cap

    @patch(GEN, return_value="CLEAN")
    def test_forum_budget_is_separate_from_the_blog_global_counter(self, mock_gen):
        """H13 item 3 — forum load must not eat the blog's AI quota."""
        LLMSpamBackend().check(_post(body="a separate-keys body"))

        self.assertEqual(self._spent(), 1)
        self.assertEqual(cache.get("ai_rate_limit:global", 0), 0)

    @patch(GEN, return_value="CLEAN")
    def test_budget_write_failure_does_not_discard_a_paid_verdict(self, mock_gen):
        """A counter-write failure must not throw away a verdict we paid for.

        consume_budget() runs inside the try/except that fails closed, so an
        unguarded cache error there would hold a post whose definitive CLEAN
        had already come back — the same mistake the verdict-cache write below
        it explicitly guards against.
        """
        with patch(
            "apps.forum_host.spam.AIRateLimiter.consume_budget",
            side_effect=RuntimeError("redis OOM"),
        ):
            result = LLMSpamBackend().check(_post(body="a budget-write-fail body"))

        self.assertTrue(result.is_clean)  # verdict survives, post publishes

    @patch(GEN, return_value="CLEAN")
    def test_provider_call_carries_an_inner_timeout(self, mock_gen):
        """H13 item 2 — the worker thread gets its own deadline.

        future.result() only bounds the caller; a submitted future cannot be
        cancelled once running, so the provider call itself must be bounded or
        a hung provider parks the pool.
        """
        LLMSpamBackend().check(_post(body="a timeout-kwarg body"))

        _, kwargs = mock_gen.call_args
        self.assertEqual(kwargs["timeout"], constants.SPAM_LLM_TIMEOUT_SECONDS)


class HeuristicTextReuseTests(TestCase):
    """The StreamField body is flattened once, not once per pass."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch(GEN, return_value="CLEAN")
    def test_extract_text_runs_once_per_screened_post(self, mock_gen):
        # Spy the SHARED module-level walker, not the backend instance: the
        # heuristic is a separate object with its own bound extract_text, so an
        # instance-level spy counts 1 whether or not the body is walked twice.
        with patch.object(
            spam_base, "extract_text", wraps=spam_base.extract_text
        ) as spy:
            LLMSpamBackend().check(_post(body="a single-walk body"))

        self.assertEqual(spy.call_count, 1)
