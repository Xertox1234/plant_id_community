---
status: pending
priority: p2
issue_id: "274"
tags: [forum, spam, ai, moderation, budget, hardening]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H13"
---

# H13 LLM spam backend — pre-enable hardening (budget accounting + provider timeout)

**Hard gate before `WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend`
is ever set in any environment.** The backend shipped **dormant** in todo 255
slice 2 (PR #479); it is correct and safe as-is with the default heuristic
backend. These items only matter once the LLM screen is actually enabled — do
NOT enable the setting until they land. Surfaced by the `/code-review medium` of
PR #479 and the whole-branch review; all three are budget/robustness couplings,
not correctness bugs in the shipped path.

Code: `backend/apps/forum_host/spam.py`. Spec/plan:
`docs/superpowers/specs/2026-07-21-forum-llm-spam-backend-design.md`,
`docs/superpowers/plans/2026-07-21-forum-llm-spam-backend.md`.

## Items

### 1. Don't count failed LLM attempts against the global budget (sticky fail-open)

`AIRateLimiter.check_global_limit()` check-and-**increments before** the provider
call (`spam.py` step 4). A timeout/exception still burns budget and is not cached,
so a sustained provider outage exhausts `ai_rate_limit:global` via ~`GLOBAL_LIMIT`
failed attempts, after which `check()` flips from **fail-closed (hold)** to
**degrade-to-heuristic (publish LLM-unscreened)**. The flip is **sticky**: every
increment resets the 1h TTL (`ai_rate_limiter.py:103`), and any steady forum *or*
blog AI traffic keeps the counter exhausted (they share the key — see item 3), so
it never rolls over until a full quiet hour or an admin reset.

**Fix direction:** only consume budget on a *successful* screen (increment after
a completed LLM call, or refund/skip-increment on failure). Requires either a
new `AIRateLimiter` method (`try_consume`/`refund`) or moving the increment to
after `_call_llm` returns. Keep the two postures intact: a deliberate budget cap
still degrades-to-heuristic (publish); an *outage* must keep failing closed
(hold) without silently converting to publish over time.

### 2. Bound the provider call so worker threads can't park indefinitely

The wall-clock `future.result(timeout=SPAM_LLM_TIMEOUT_SECONDS)` protects the
**caller** (returns in ~3s, fails closed) but does **not** cancel the submitted
`generate_ai_text` worker — a `ThreadPoolExecutor` future can't be cancelled once
running. If `generate_ai_text` has no inner network/socket timeout, a truly-hung
provider parks worker threads until they unblock; after `SPAM_LLM_MAX_WORKERS`
(=4) hung calls the whole pool is parked and every subsequent check queues →
times out at 3s → fails closed until a worker returns. Fail-closed and bounded,
but the pool self-degrades with no recovery signal.

**Fix direction:** confirm whether `generate_ai_text` (wagtail-ai LLMService)
already enforces a request timeout; if not, add one (an HTTP client timeout on
the provider call) so parked workers unblock and the pool recovers. Consider
whether `SPAM_LLM_MAX_WORKERS` is sized for peak concurrent moderation.

### 3. Decouple the forum spam budget from the blog AI counter

Forum spam-screening consumes the same `ai_rate_limit:global` (100/hr) as blog
AI generation, so either subsystem can starve the other's AI quota with no
per-feature accounting. This was the spec's ratified "reuse global limit"
decision and is acceptable at low volume, but once enabled at scale it should get
a **forum-specific budget key** (e.g. `ai_rate_limit:forum_spam`) with its own
cap, so forum load and blog load are independently observable and tunable.
(Interacts with item 1 — a forum-specific key also isolates the outage-burn.)

## Minor cleanups (optional, low priority; bundle if the file is being touched)

- `spam.py` `_parse`: `verdict[:80]` log-truncation is an inline magic number —
  move to a `SPAM_LLM_*` constant (backend/CLAUDE.md "no magic numbers"). The
  same method's `verdict[4:]` hardcodes `len("SPAM")` (garbles a `"SPAMMY: …"`
  reason but still flags — safe direction).
- `spam.py` `check`: `extract_text(obj)` is computed twice per screened post
  (once inside `self._heuristic.check(obj)`, once directly). Screen the text once
  and pass it to both to avoid re-flattening a large StreamField body.

## Acceptance

- [ ] Failed LLM attempts (timeout/exception/unparseable) do NOT consume the AI
      budget; a sustained outage keeps failing closed (hold), never silently
      flips to publish. Test: N>GLOBAL_LIMIT consecutive provider failures still
      return `is_clean=False` (held), and `check_global_limit` is not net-burned.
- [ ] The provider call is bounded by an inner timeout so worker threads unblock;
      pool recovers after a transient hang (documented or tested).
- [ ] (If pursued) forum spam screening uses a budget key distinct from blog AI.
- [ ] Only then: document that the setting is safe to enable, and enable it in
      the target environment (needs a working `OPENAI_API_KEY`).

## Notes

Parent epic: todo 255 (`255-in_progress-p1-forum-ai-premium.md`), H13 slice 2.
This todo is the "before enabling" gate referenced in that epic's work log.
