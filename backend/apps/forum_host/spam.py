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

        # 3. Verdict cache: a hit skips the LLM and the timeout machinery.
        cache_key = self._cache_key(text)
        cached = cache.get(cache_key)
        if cached is not None:
            return SpamResult(cached["is_clean"], cached["reason"])

        # 4. Spend cap. A hit budget is a deliberate cost decision, not an
        #    outage, so it degrades to the heuristic (publish), NOT fail-closed.
        if not AIRateLimiter.check_global_limit():
            logger.info(
                "[PERF] Forum spam LLM skipped: global AI budget exhausted; "
                "degrading to heuristic verdict"
            )
            return SpamResult(True)

        # 5. LLM call under a hard wall-clock timeout. Any failure fails CLOSED
        #    by returning a rejected SpamResult (a normal reject -> pending
        #    draft in the moderation queue), NOT by raising: a raise would roll
        #    the workflow back and leave a limbo draft with no queue entry.
        try:
            reply = self._call_llm(text)
        except Exception:
            logger.exception(
                "[ERROR] Forum spam LLM call failed; failing closed "
                "(held for review)"
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)

        # 6. Parse (and cache definitive verdicts).
        return self._parse(reply, cache_key)

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
        if upper.startswith("CLEAN"):
            result = SpamResult(True)
        elif upper.startswith("SPAM"):
            reason = verdict[4:].lstrip(":- ").strip() or "flagged by AI moderation"
            result = SpamResult(False, f"AI: {reason}")
            logger.info("[SECURITY] Forum spam LLM flagged content: %s", result.reason)
        else:
            # Unparseable → fail closed, do NOT cache (transient).
            logger.warning(
                "[ERROR] Forum spam LLM returned unparseable reply %r; "
                "failing closed",
                verdict[:80],
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)

        cache.set(
            cache_key,
            {"is_clean": result.is_clean, "reason": result.reason},
            constants.SPAM_LLM_CACHE_TTL_SECONDS,
        )
        return result
