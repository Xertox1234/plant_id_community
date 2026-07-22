"""Host-side LLM spam backend for the forum (todo 255 slice 2 / H13).

Lives host-side (not in the wagtail_forum package) so it may import the blog
app's AI helpers; the package forbids apps.* imports (test_reusability.py).
Selected via WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend;
ships dormant (default stays the heuristic backend).

See docs/superpowers/specs/2026-07-21-forum-llm-spam-backend-design.md.
"""

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from apps.blog.services.ai_rate_limiter import AIRateLimiter
from apps.blog.wagtail_ai_v3_integration import generate_ai_text
from django.core.cache import cache
from wagtail_forum.spam.base import SpamBackend, SpamResult
from wagtail_forum.spam.heuristic import HeuristicSpamBackend

from . import constants

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """Lazily create the shared thread pool.

    Never created at import, so a gunicorn ``--preload`` parent never forks a
    live thread pool. Double-checked locking keeps concurrent first-callers to a
    single pool.
    """
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(
                    max_workers=constants.SPAM_LLM_MAX_WORKERS,
                    thread_name_prefix="forum-spam-llm",
                )
    return _executor


class LLMSpamBackend(SpamBackend):
    """Heuristic-first composite that adds an LLM screen behind the setting swap.

    check() runs synchronously inside the moderation workflow's
    @transaction.atomic publish path, so the LLM call is bounded by a hard
    wall-clock timeout. Provider failures fail CLOSED (reject -> pending draft);
    a hit global-budget cap degrades to the heuristic (publish).
    """

    def __init__(self) -> None:
        self._heuristic = HeuristicSpamBackend()

    def check(self, obj) -> SpamResult:
        # 1. Heuristic first: obvious spam is rejected with no LLM cost, and the
        #    deterministic banned-word / link-flood guarantees are preserved.
        heuristic_result = self._heuristic.check(obj)
        if not heuristic_result.is_clean:
            return heuristic_result

        # 2. Extract + bound the text the LLM will see (same text the heuristic
        #    screened, incl. the opening-post topic title).
        text = self.extract_text(obj)[: constants.SPAM_LLM_MAX_CHARS]
        if not text.strip():
            return SpamResult(True)

        cache_key = self._cache_key(text)

        # 3-6. LLM screening. check() runs inside the workflow's
        #      @transaction.atomic publish path, so EVERY failure here — the
        #      Redis verdict cache, the Redis-backed global-budget check, the
        #      provider call (timeout or error), or the parse/cache write — must
        #      fail CLOSED by RETURNING a rejected SpamResult, never by raising:
        #      a raise would roll the workflow back and leave a limbo draft with
        #      no moderation-queue entry. The one deliberate publish path is a
        #      hit budget cap (a cost decision, not an outage), returned inline.
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return SpamResult(cached["is_clean"], cached["reason"])

            if not AIRateLimiter.check_global_limit():
                logger.info(
                    "[PERF] Forum spam LLM skipped: global AI budget exhausted; "
                    "degrading to heuristic verdict"
                )
                return SpamResult(True)

            reply = self._call_llm(text)
            return self._parse(reply, cache_key)
        except FuturesTimeoutError:
            # Expected under a slow/overloaded provider — no traceback needed.
            logger.warning(
                "[ERROR] Forum spam LLM timed out after %ss; failing closed "
                "(held for review)",
                constants.SPAM_LLM_TIMEOUT_SECONDS,
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)
        except Exception:
            # Provider error, Redis outage, or any other unexpected fault.
            logger.exception(
                "[ERROR] Forum spam screening failed; failing closed "
                "(held for review)"
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (
            f"{constants.SPAM_LLM_CACHE_KEY_PREFIX}"
            f":v{constants.SPAM_LLM_PROMPT_VERSION}:{digest}"
        )

    def _call_llm(self, text: str) -> str:
        prompt = constants.SPAM_LLM_PROMPT_TEMPLATE.format(content=text)
        future = _get_executor().submit(
            generate_ai_text, prompt, alias=constants.SPAM_LLM_ALIAS
        )
        # Read the timeout off the module at call time so tests can patch it.
        return future.result(timeout=constants.SPAM_LLM_TIMEOUT_SECONDS)

    def _parse(self, reply: str, cache_key: str) -> SpamResult:
        verdict = (reply or "").strip()
        upper = verdict.upper()
        # CLEAN only on an exact one-word verdict (tolerating trailing
        # punctuation). A lookalike like "CLEANLY not spam" must NOT pass — that
        # is the one unsafe direction (spam published), so it falls through to
        # the fail-closed branch below.
        first_word = upper.split(maxsplit=1)[0].strip(".,:;!-") if upper else ""
        if first_word == "CLEAN":
            result = SpamResult(True)
        elif upper.startswith("SPAM"):
            reason = verdict[4:].lstrip(":- ").strip() or "flagged by AI moderation"
            result = SpamResult(False, f"AI: {reason}")
            logger.info("[SECURITY] Forum spam LLM flagged content: %s", result.reason)
        else:
            # Unparseable / ambiguous → fail closed, do NOT cache (transient).
            logger.warning(
                "[ERROR] Forum spam LLM returned unparseable reply %r; "
                "failing closed",
                verdict[:80],
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)

        # Cache the definitive verdict. A cache-write failure must not discard a
        # verdict we already have, nor raise into the atomic publish path.
        try:
            cache.set(
                cache_key,
                {"is_clean": result.is_clean, "reason": result.reason},
                constants.SPAM_LLM_CACHE_TTL_SECONDS,
            )
        except Exception:
            logger.warning(
                "[ERROR] Forum spam verdict-cache write failed; verdict "
                "still applied"
            )
        return result
