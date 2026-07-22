# Design — Forum AI thread summarization (todo 255, slice 3 / H14)

Branch `todo-255-slice3-ai-summarization` (off fresh `main`). Epic todo:
`todos/255-in_progress-p1-forum-ai-premium.md`. Source finding H14 from the
2026-07-11 forum-modernization audit.

## Problem

A premium-gated "summarize this thread" perk is an acceptance criterion of the
forum-AI epic and has zero implementation. All substrate it needs already ships
(slice 1 entitlement primitive `IsPremiumUser` + `AIRateLimiter.PREMIUM_LIMIT`;
`generate_ai_text`; `AICacheService` content-hash cache; the `send_forum_push`
Celery pattern). This slice wires them into one endpoint + one task.

## Goals

- `GET /api/v1/forum/topics/<int:topic_id>/summary/`, **premium-gated**
  (`IsPremiumUser`), returns a cached AI summary of a topic's thread.
- **Celery-generated**: the endpoint never calls the LLM in-request. On a cache
  miss it enqueues a task and returns `202 {"status": "pending"}`; the client
  polls until `200 {"status": "ready", "summary": ...}`.
- **Content-hash cached** via `AICacheService` (feature `forum_topic_summary`),
  so a summary auto-invalidates when the thread changes (new/edited posts) and
  identical thread state is free.
- Respects the shared global AI budget (`AIRateLimiter.check_global_limit()`).
- Ships **inert until consumed** — no web/Flutter client wiring in this slice
  (Waves 3/4 own clients; todo 255 AC is a backend endpoint). Prompt-injection
  hardened like the slice-2 spam prompt (thread framed as untrusted DATA).

## Non-goals (YAGNI / deferred)

- No web/mobile UI (later waves; the epic parks AI "until real posting activity").
- No streaming/partial responses; a single cached string.
- No per-user summary personalization; the summary is thread-state-derived and
  shared across all premium viewers (maximizes cache hits).
- No new Celery queue/routing — default queue, bounded by the existing global
  `CELERY_TASK_SOFT_TIME_LIMIT=90` / `TIME_LIMIT=120`.

## Architecture

Shared source-of-truth helper (used by BOTH view and task so their cache keys
match):

```python
# apps/forum_host/summary.py
def build_summary_source(topic) -> tuple[str, int]:
    """Return (canonical content string, live post count) for a topic.

    The content string folds in a prompt version + each live post's id,
    updated_at and plain-text excerpt in chronological order, so the
    AICacheService content hash changes whenever the thread changes or the
    prompt is revised. Bounded to SUMMARY_MAX_CHARS.
    """
```

### Endpoint — `TopicSummaryView(APIView)` (`apps/forum_host/summary.py`)

- `permission_classes = [IsPremiumUser]`; `versioning_class = None` (mirrors
  package views); `@extend_schema` documents 200/202/403/404.
- Throttled GET via the existing `_throttled("topic_summary", "GET")` helper in
  `api.py` (records `_forum_throttled_methods` → schema 429 documented for free).
- `get(request, topic_id)`:
  1. Fetch `Topic.objects.filter(pk=topic_id, live=True)` → 404 if absent.
  2. `content, post_count = build_summary_source(topic)`.
  3. `post_count < SUMMARY_MIN_POSTS` → `200 {"status": "too_short"}`.
  4. `cached = AICacheService.get_cached_response("forum_topic_summary", content)`
     → if present, `200 {"status": "ready", **cached}`.
  5. Else enqueue `generate_topic_summary.delay(topic_id)` guarded by a
     short-TTL pending lock (so a burst of polls enqueues at most one task per
     thread state), return `202 {"status": "pending"}`.

### Task — `generate_topic_summary` (`apps/forum_host/tasks.py`)

```python
@shared_task(bind=True, max_retries=SUMMARY_MAX_RETRIES,
             default_retry_delay=SUMMARY_RETRY_DELAY)
def generate_topic_summary(self, topic_id: int) -> None:
```

Guard-clause structure mirroring `send_forum_push`:

1. Topic missing / not live → return (log, no retry).
2. `content, post_count = build_summary_source(topic)`;
   `post_count < SUMMARY_MIN_POSTS` → return.
3. Already cached (a racing task won) → return, clear pending lock.
4. `not AIRateLimiter.check_global_limit()` → log `[PERF]`, return **without
   retry** (budget is a cost decision, not an outage — matches slice-2 spam
   "degrade" posture). Do NOT `self.retry` (would burn the budget further).
5. `summary = generate_ai_text(prompt, alias=SUMMARY_ALIAS)` — bounded by the
   Celery soft time limit (no request/atomic path here, so no thread-pool
   wrapper needed, unlike spam). On transient exception → `self.retry(exc,
   countdown=default_retry_delay * 2**retries)`.
6. `AICacheService.set_cached_response("forum_topic_summary", content,
   {"summary": summary, "post_count": post_count, "generated_at": <iso>})`;
   clear the pending lock.

Enqueue from the view is wrapped in `try/except` logging `[CELERY]` (mirrors
`notifications.py`), so a broker outage degrades to a normal 202 the client can
retry rather than a 500.

### Prompt design

Framed like the slice-2 spam prompt: the thread is untrusted DATA, any
instructions inside it are content to summarize, never commands. Asks for a
concise neutral summary (≈3–5 sentences) of what the thread discusses and any
resolution.

## Constants — `apps/forum_host/constants.py`

- `SUMMARY_CACHE_FEATURE = "forum_topic_summary"`
- `SUMMARY_MIN_POSTS = 3`
- `SUMMARY_MAX_CHARS = 6000`
- `SUMMARY_PER_POST_EXCERPT_CHARS = 1000`
- `SUMMARY_ALIAS = "default"`
- `SUMMARY_PROMPT_VERSION = 1` (folded into the content string → prompt change
  invalidates every cached summary)
- `SUMMARY_PENDING_LOCK_PREFIX`, `SUMMARY_PENDING_LOCK_TTL = 120`
- `SUMMARY_MAX_RETRIES = 2`, `SUMMARY_RETRY_DELAY = 10`
- `SUMMARY_PROMPT_TEMPLATE`

Throttle rate added to `DEFAULT_FORUM_RATELIMITS`: `"topic_summary": "30/h"`.

## Route drift guard

`api_urls.py` adds `path("topics/<int:topic_id>/summary/", ...)`. The
`test_host_api_routes_match_package` drift guard currently asserts host routes
== package routes; relaxed to `package ⊆ host` plus an explicit allow-list of
the one intentional host-only AI route, preserving the guard's real intent
(every package route must be mounted).

## Testing — `apps/forum_host/tests/test_summary.py` (new)

Mirrors `test_spam.py` (mock `generate_ai_text`) and `test_tasks.py` (Celery
task) and `test_signals.py` (enqueue assertions):

- non-premium user → 403; anonymous → 401/403.
- too-short topic → 200 `too_short`, no enqueue.
- cache miss → 202 `pending` + exactly one `.delay` enqueue; burst of polls →
  still one enqueue (pending lock).
- cache hit → 200 `ready` with the summary, no enqueue.
- task: builds prompt, calls `generate_ai_text`, writes cache; second run with a
  populated cache is a no-op.
- task: global budget exhausted → no LLM call, no cache write, no retry.
- task: transient LLM error → `self.retry` invoked.
- `build_summary_source` hash changes when a post is added/edited (invalidation).

## Verification

`manage.py check`; `makemigrations --check` (no model changes → none expected);
`spectacular` OK; `pytest apps/forum_host apps/blog apps/users --create-db`.

## Acceptance criteria satisfied (epic AC #4)

> Premium thread-summary endpoint: Celery-generated, content-hash cached,
> entitlement-gated — all four properties realized by this slice.

---

## H15 pgvector-on-Railway precheck — RESULT: GREEN (recorded, epic AC #5)

Run 2026-07-22 read-only against the production Postgres via its public proxy
(`railway variables -s Postgres` → `DATABASE_PUBLIC_URL`, `acela.proxy.rlwy.net`):

```
-- pg_available_extensions
pg_trgm | 1.6   | 1.6      (installed)
vector  | 0.8.2 | (null)   (AVAILABLE, not yet installed)

-- server_version
18.4 (Debian 18.4-1.pgdg13+1)

-- current role privileges
current_user=postgres  rolsuper=t  rolcreatedb=t  rolcreaterole=t

-- installed extensions
pg_trgm, plpgsql
```

**Conclusion:** the `vector` extension (v0.8.2) is present in Railway's Postgres
18 image and the app's DB role is a superuser, so the pgvector storage app's
shipped `VectorExtension()` migration (`CREATE EXTENSION vector`) **would
succeed at deploy**. H15 is therefore **infra-viable** — the "Railway support
UNVERIFIED" blocker from the audit is resolved. (Note: this refutes the earlier
"deploy migration might fail" risk — it is NOT a valid descope reason.)

**Remaining (non-infra) considerations for a build-vs-defer decision:** the forum
currently has ~empty content (no corpus to embed), semantic similar-topics has no
consumer until the Wave 3/4 clients, and standing up an embeddings provider
carries recurring per-rebuild API cost. These are product/cost tradeoffs, not
technical blockers — surfaced to the user as a scope decision.

**Decision (user, 2026-07-22): BUILD H15 now** as slice 4 (separate PR off fresh
main after this slice-3 H14 PR merges). Own design spec:
`2026-07-22-forum-similar-topics-pgvector-design.md`.
