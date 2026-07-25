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
    a hit forum-budget cap degrades to the heuristic (publish). The two postures
    are kept independent by consuming budget only for a DEFINITIVE verdict, so
    no provider-side failure can decay into the publish posture.
    """

    def __init__(self) -> None:
        self._heuristic = HeuristicSpamBackend()

    def check(self, obj) -> SpamResult:
        # 1. Flatten the body ONCE. Both passes screen this same string, so a
        #    large StreamField is not walked twice per screened post.
        text = self.extract_text(obj)

        # 2. Heuristic first: obvious spam is rejected with no LLM cost, and the
        #    deterministic banned-word / link-flood guarantees are preserved.
        heuristic_result = self._heuristic.check_text(text)
        if not heuristic_result.is_clean:
            return heuristic_result

        # 3. Bound the text the LLM will see (same text the heuristic screened,
        #    incl. the opening-post topic title).
        text = text[: constants.SPAM_LLM_MAX_CHARS]
        if not text.strip():
            return SpamResult(True)

        cache_key = self._cache_key(text)

        # 4-7. LLM screening. check() runs inside the workflow's
        #      @transaction.atomic publish path, so EVERY failure here — the
        #      Redis verdict cache, the Redis-backed forum-budget check, the
        #      provider call (timeout or error), or the parse/cache write — must
        #      fail CLOSED by RETURNING a rejected SpamResult, never by raising:
        #      a raise would roll the workflow back and leave a limbo draft with
        #      no moderation-queue entry. The one deliberate publish path is a
        #      hit budget cap (a cost decision, not an outage), returned inline.
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return SpamResult(cached["is_clean"], cached["reason"])

            # Peek, never check-and-increment: budget is consumed only once a
            # definitive verdict comes back (in _parse). Otherwise a
            # sustained outage burns the cap via failed attempts and the
            # backend silently flips from fail-closed (hold) to
            # degrade-to-heuristic (publish LLM-unscreened) — a spam-publishing
            # posture change caused purely by the provider being down.
            if not AIRateLimiter.peek_budget(
                constants.SPAM_LLM_BUDGET_CACHE_KEY,
                constants.SPAM_LLM_BUDGET_LIMIT,
            ):
                logger.info(
                    "[PERF] Forum spam LLM skipped: forum AI budget exhausted; "
                    "degrading to heuristic verdict"
                )
                return SpamResult(True)

            reply = self._call_llm(text)
            # Budget is consumed inside _parse(), and ONLY for a definitive
            # CLEAN/SPAM verdict — see the note there.
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
        # Read the timeout off the module at call time so tests can patch it.
        timeout = constants.SPAM_LLM_TIMEOUT_SECONDS
        future = _get_executor().submit(
            generate_ai_text,
            prompt,
            alias=constants.SPAM_LLM_ALIAS,
            timeout=timeout,
        )
        # The same deadline is applied twice, deliberately:
        #   - the inner `timeout=` is the PROVIDER's request deadline, so the
        #     worker thread unblocks. A submitted future cannot be cancelled
        #     once running, so without it a truly-hung provider parks workers
        #     until all SPAM_LLM_MAX_WORKERS are gone and the pool never
        #     recovers.
        #   - future.result() bounds the CALLER, which is sitting inside the
        #     workflow's @transaction.atomic publish path.
        return future.result(timeout=timeout)

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
            # Split the verdict word off rather than slicing a hardcoded
            # len("SPAM"): a "SPAMMY: too promotional" reply must yield the
            # reason "too promotional", not "MY: too promotional".
            parts = verdict.split(maxsplit=1)
            tail = parts[1] if len(parts) > 1 else ""
            reason = tail.lstrip(":- ").strip() or "flagged by AI moderation"
            result = SpamResult(False, f"AI: {reason}")
            logger.info("[SECURITY] Forum spam LLM flagged content: %s", result.reason)
        else:
            # Unparseable / ambiguous → fail closed, do NOT cache (transient),
            # and do NOT consume budget: this reply gave us no verdict. That
            # early return is what keeps a provider stuck emitting garbage from
            # draining the cap and flipping the backend to publish-unscreened —
            # the same guarantee the timeout and exception paths have.
            logger.warning(
                "[ERROR] Forum spam LLM returned unparseable reply %r; "
                "failing closed",
                verdict[: constants.SPAM_LLM_LOG_TRUNCATE_CHARS],
            )
            return SpamResult(False, constants.SPAM_LLM_UNAVAILABLE_REASON)

        # A definitive verdict — and ONLY here — spends budget. Every failure
        # mode (timeout, provider error, unparseable reply) returns before this
        # line, so no provider-side failure can ever burn the cap.
        AIRateLimiter.consume_budget(
            constants.SPAM_LLM_BUDGET_CACHE_KEY,
            constants.SPAM_LLM_BUDGET_LIMIT,
        )

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
