# Design — Forum LLM spam backend (todo 255, slice 2 / H13)

- **Date:** 2026-07-21
- **Epic:** `todos/255-in_progress-p1-forum-ai-premium.md` (forum AI & premium)
- **Finding:** H13 (2026-07-11 forum-modernization audit)
- **Depends on:** nothing — premium-agnostic, independent of slice 1 (H12). Branches
  off `main` before slice 1 merges.

## Problem

The forum's automated moderation runs one pluggable spam check on the publish path.
The only implementation is `HeuristicSpamBackend` — banned-word and link-count
matching. The audit's H13 calls for an LLM-backed screen that reuses the existing
`generate_ai_text()` substrate to catch spam the heuristics miss (rephrased
promotions, novel scams), behind the package's existing one-setting swap.

The extension point already exists and is the contract we build to:

- `wagtail_forum.spam.base.SpamBackend.check(obj) -> SpamResult` — the interface.
- `WAGTAILFORUM_SPAM_BACKEND` (`wagtail_forum/conf.py`) — dotted path to the backend
  class; `get_spam_backend()` imports and instantiates it.
- `wagtail_forum.spam.base.extract_text(obj)` — flattens a Topic/Post title + body
  (and, for an opening post, the topic title) into one screened string.

**The core constraint:** `check()` runs **synchronously** inside
`SpamCheckTask.start()`, which Wagtail calls inside `AbstractWorkflow.start()` —
a `@transaction.atomic` block on the create/edit publish path. A slow or hanging
provider call therefore holds a DB transaction open. An *exception* is already
handled safely (`submit_for_moderation` catches moderation-step failures and leaves
the post a pending draft — fail closed), but an unbounded *hang* is not. The design
must impose a hard wall-clock ceiling on the provider call.

## Goals

- An `LLMSpamBackend` that screens forum content via `generate_ai_text()`, selectable
  by flipping `WAGTAILFORUM_SPAM_BACKEND` — no code change to enable.
- The publish path never blocks on provider latency or outage: a hard wall-clock
  timeout, degrading to the heuristic verdict.
- Deterministic heuristic guarantees (banned words, link floods) are preserved even
  when the LLM backend is enabled.
- Verdicts cached in Redis by content hash so re-screens and duplicate spam are free.
- Ships **dormant**: the default backend stays heuristic. Enabling is an ops decision
  (one env var), not a behavior change merged unreviewed.

## Non-goals (YAGNI / deferred)

- **No async/Celery moderation.** `SpamCheckTask`'s contract is synchronous by design;
  moving moderation off the request is a separate redesign, not H13.
- **No per-user rate limiting on spam checks.** It is a system operation on a
  low-volume path (untrusted authors only); the timeout + verdict cache bound cost.
- **No change to the `wagtail_forum` package.** The LLM backend is host-side; the
  package's `SpamBackend` contract and `test_reusability.py` purity are untouched.
- **Prompt injection is mitigated, not solved.** User content is framed as data with
  an ignore-instructions guard; the report-driven auto-hide
  (`REPORT_AUTO_HIDE_THRESHOLD`) remains the backstop.

## Architecture

A new host-side module `apps/forum_host/spam.py` defines:

```text
LLMSpamBackend(wagtail_forum.spam.base.SpamBackend)
  ._heuristic = HeuristicSpamBackend()          # composed, not subclassed
  .check(obj) -> SpamResult
```

It lives in `apps/forum_host/` (the host app), **not** in the package, so it may
import `apps.blog.wagtail_ai_v3_integration.generate_ai_text`. `test_reusability.py`
forbids `apps.*` imports only *inside* the package; the host app is unconstrained.

### `check(obj)` algorithm

1. **Heuristic first.** `result = self._heuristic.check(obj)`. If `not
   result.is_clean`, return it immediately — banned-word/link-flood spam is rejected
   with **no LLM call** (deterministic guarantee preserved, zero cost on obvious
   spam).
2. **Extract + bound.** `text = self.extract_text(obj)[:SPAM_LLM_MAX_CHARS]` — the
   same text the heuristic screened (includes the opening-post topic title, audit
   M1), truncated to cap tokens/latency. If `text` is empty/whitespace, return clean
   (nothing to screen).
3. **Verdict cache.** key = `f"{SPAM_LLM_CACHE_KEY_PREFIX}:v{SPAM_LLM_PROMPT_VERSION}:{sha256(text)}"`.
   On a cache hit, return the cached `SpamResult` — skips the LLM and the timeout
   machinery entirely.
4. **LLM call under a hard timeout.** Build the prompt (below), submit
   `generate_ai_text(prompt, alias=SPAM_LLM_ALIAS)` to a module-level
   `ThreadPoolExecutor`, and read `future.result(timeout=SPAM_LLM_TIMEOUT_SECONDS)`.
5. **Parse + cache.** Map the reply to a `SpamResult`, cache definitive verdicts, and
   return.

### Prompt design

A single-string prompt (reusing the existing `generate_ai_text(prompt)` signature —
no new provider plumbing):

- States the task: classify a community forum post as spam or not.
- Delimits the post body clearly as untrusted **data** and instructs the model to
  treat any instructions inside it as content to classify, never commands to obey
  (best-effort prompt-injection guard).
- Requires a strict, single-line reply: exactly `CLEAN`, or `SPAM: <short reason>`.

`SPAM_LLM_PROMPT_VERSION` is part of the cache key so a prompt change invalidates old
verdicts without a manual flush.

### Timeout mechanism

`generate_ai_text` exposes no socket timeout, and the OpenAI client default is far
longer than the publish path can tolerate. A module-level
`ThreadPoolExecutor(max_workers=SPAM_LLM_MAX_WORKERS)` with
`future.result(timeout=SPAM_LLM_TIMEOUT_SECONDS)` bounds the **wall-clock** wait
regardless of the provider:

- On timeout, `future.result` raises `TimeoutError`; we abandon the future (do not
  block on it) and fall back. The worker thread runs until the provider's own socket
  timeout fires, then frees itself — self-healing. Under a sustained outage, at most
  `SPAM_LLM_MAX_WORKERS` threads are parked and further `check()` calls still return
  within the timeout (a pending future times out even when no worker is free).
- The executor is **not** used as a context manager (its `__exit__` waits for the
  worker, which would defeat the timeout). It is a module singleton.

Configuring the shared OpenAI client's socket timeout would shorten zombie-thread
lifetime but is cross-cutting (affects blog AI) and out of scope; noted as a possible
follow-up.

## Error handling

Every non-definitive path **fails open to the heuristic's clean verdict** — the code
only reaches the LLM when the heuristic already passed, so the fallback is
`SpamResult(True)`. This keeps the publish path flowing (untrusted posts are not
piled into pending) during any provider problem, degrading to heuristic-only
protection rather than getting stricter-than-before or stuck.

| Outcome | Returned | Cached? | Log |
|---|---|---|---|
| Heuristic flags | `SpamResult(False, reason)` | — (no LLM call) | — |
| Empty text after extract | `SpamResult(True)` | no | — |
| LLM reply `CLEAN` | `SpamResult(True)` | yes | — |
| LLM reply `SPAM: x` | `SpamResult(False, "AI: x")` | yes | `[SECURITY]` info |
| Reply unparseable | `SpamResult(True)` (fail open) | no | `[ERROR]` warning |
| Timeout / exception | `SpamResult(True)` (fail open) | no | `[ERROR]` |

The held transaction is bounded by `SPAM_LLM_TIMEOUT_SECONDS`. This path fires only
for untrusted authors (trust < `TRUST_AUTOPUBLISH_LEVEL`) on publish — an inherently
low-volume, already-moderated route; the verdict cache makes repeats instant.

## Constants — `apps/forum_host/constants.py`

Per backend/CLAUDE.md (no magic numbers), all tunables live in the host app's
`constants.py`:

- `SPAM_LLM_TIMEOUT_SECONDS = 5` — hard wall-clock ceiling on the provider call.
- `SPAM_LLM_CACHE_TTL_SECONDS = 60 * 60 * 24` — verdict TTL (24h).
- `SPAM_LLM_CACHE_KEY_PREFIX = "forum_spam_llm"`.
- `SPAM_LLM_PROMPT_VERSION = 1` — bump to invalidate cached verdicts on prompt change.
- `SPAM_LLM_MAX_CHARS = 4000` — LLM input truncation bound.
- `SPAM_LLM_MAX_WORKERS = 4` — thread pool size (parked-thread ceiling under outage).
- `SPAM_LLM_ALIAS = "default"` — `generate_ai_text` provider alias.
- `SPAM_LLM_PROMPT_TEMPLATE` — the classification prompt with a `{content}` slot.

## Settings wiring — `plant_community_backend/settings.py`

```python
WAGTAILFORUM_SPAM_BACKEND = config(
    "WAGTAILFORUM_SPAM_BACKEND",
    default="wagtail_forum.spam.heuristic.HeuristicSpamBackend",
)
```

The default is unchanged, so the live publish path keeps using the heuristic. To
enable the LLM backend in an environment, set the env var:

```text
WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend
```

(env var name == setting name; one name to remember). Prerequisite: a working
`OPENAI_API_KEY` — verified present on the Railway `plant_id_community` service in
slice 1 (L7).

## Testing — `apps/forum_host/tests/test_spam.py` (new)

`generate_ai_text` is patched in every test (no live provider calls); `cache.clear()`
in `setUp`.

- **Heuristic short-circuit** — banned-word content is flagged and `generate_ai_text`
  is asserted **not called**.
- **Clean → LLM clean** — heuristic passes, patched LLM returns `CLEAN` → `is_clean`.
- **LLM flags** — LLM returns `SPAM: promotional` → `not is_clean`, reason carries the
  AI text.
- **Timeout → fail open** — patched `generate_ai_text` sleeps past a short
  test-patched `SPAM_LLM_TIMEOUT_SECONDS` → `is_clean` True and the call returns
  promptly (timeout fired).
- **Exception → fail open** — patched to raise → `is_clean` True.
- **Unparseable → fail open, not cached** — patched to return garbage → `is_clean`
  True, and a second identical check calls the LLM again (proving no cache write).
- **Verdict cached** — two checks of identical clean content → `generate_ai_text`
  called exactly once.
- **One-setting swap** — with `WAGTAILFORUM_SPAM_BACKEND` set to the LLM backend,
  `get_spam_backend()` returns an `LLMSpamBackend`; unset, it returns
  `HeuristicSpamBackend` (guards the dormant default).

## Verification

- `python manage.py check` and `python manage.py spectacular --file /dev/null` (mirror
  CI `backend-checks`). No model change → no migration; `makemigrations --check` clean.
- `python manage.py test apps.forum_host --noinput` (fresh DB) — new tests pass.
- Package spam + reusability suites still green
  (`test apps ... wagtail_forum.tests.test_spam`, `test_reusability`).

## Files changed

1. `apps/forum_host/spam.py` (new) — `LLMSpamBackend`.
2. `apps/forum_host/constants.py` — spam-LLM constants + prompt template.
3. `plant_community_backend/settings.py` — env-backed `WAGTAILFORUM_SPAM_BACKEND`
   (default heuristic).
4. `apps/forum_host/tests/test_spam.py` (new) — the tests above.
5. `backend/docs/patterns/domain/forum.md` — document the LLM backend + enablement
   env var + fail-open contract.
6. `CLAUDE.md` Environment Variables table — add `WAGTAILFORUM_SPAM_BACKEND`.
7. `todos/255-...md` — AC #3 checked, slice-2 work-log entry; epic stays `in_progress`.
8. `docs/audits/2026-07-11-forum-modernization.md` — Finding Status for H13.

## Acceptance criteria satisfied (epic AC #3)

> LLM spam backend runs behind the one-setting swap with timeout + heuristic
> fallback — publish path never blocks on provider outage (tested)

- One-setting swap: `WAGTAILFORUM_SPAM_BACKEND` (tested).
- Timeout: `ThreadPoolExecutor` wall-clock ceiling (tested).
- Heuristic fallback: every non-definitive path returns the heuristic verdict
  (tested for timeout, exception, unparseable).
- Never blocks: bounded wall-clock + fail-open-to-clean on the untrusted publish path.
