---
status: completed
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

- [x] Failed LLM attempts (timeout/exception/unparseable) do NOT consume the AI
      budget; a sustained outage keeps failing closed (hold), never silently
      flips to publish. Test: N>GLOBAL_LIMIT consecutive provider failures still
      return `is_clean=False` (held), and `check_global_limit` is not net-burned.
- [x] The provider call is bounded by an inner timeout so worker threads unblock;
      pool recovers after a transient hang (documented or tested).
- [x] (If pursued) forum spam screening uses a budget key distinct from blog AI.
- [x] Document that the setting is now safe to enable, and record the enable
      procedure + the operational knobs it depends on.

> **Scope note (run 2026-07-25-1825).** This criterion originally also required
> *enabling* the setting in a target environment. Actually flipping
> `WAGTAILFORUM_SPAM_BACKEND` in a live environment is a production config
> change with real LLM spend attached, and is the operator's call — not this
> todo's. Split by user decision: the **documentation** half stays here (it is
> the gate's deliverable); the **env flip** is spun out to a follow-up todo and
> stays owned by epic 255.

## Notes

Parent epic: todo 255 (`255-in_progress-p1-forum-ai-premium.md`), H13 slice 2.
This todo is the "before enabling" gate referenced in that epic's work log.

## Work Log

### 2026-07-25 - Started by completing-todos skill (run 2026-07-25-1825)

- Picked up by automated workflow via `/todo-next`.

### 2026-07-25 - Implementation

**Item 1 — budget accounting.** Added `AIRateLimiter.peek_budget(key, limit)`
(read-only), `consume_budget(key, limit)`, and `reset_budget(key)` to
`apps/blog/services/ai_rate_limiter.py`. `check_global_limit`/`check_user_limit`
are untouched, so blog behaviour is unchanged. `spam.py` now peeks before the
call and consumes **inside `_parse()`, on the `CLEAN`/`SPAM` branches only**.

> Design note — one deviation considered and rejected. The first cut consumed
> immediately after `_call_llm` returned, on the theory that a
> returned-but-unparseable reply was still billed, so over-counting was the safe
> direction. That contradicts this todo's criterion 1, which lists
> **unparseable** alongside timeout and exception. The criterion is right and the
> first cut was wrong: unparseable verdicts are deliberately not cached, so every
> retry re-calls the provider — counting them would let a provider stuck emitting
> garbage drain the cap and flip the backend to publish-unscreened, which is the
> exact posture change this todo exists to prevent. The cost objection does not
> hold either: spend during such an incident is one call per post submission, the
> same rate as healthy operation, so the cap protects nothing there. Reverted to
> consume-on-definitive-verdict.

**Item 2 — provider deadline.** `generate_ai_text()` takes an optional
`timeout` kwarg, forwarded as a completion kwarg (omitted entirely when `None`,
so every existing call site keeps its exact payload). Verified the kwarg path
end-to-end before writing it: `CachedLLMService.completion(**kwargs)` →
`LLMService.completion` → `AnyLLM.acompletion(**kwargs)` →
`_convert_completion_params` → `client.chat.completions.create(timeout=…)`.
`get_llm_service` is `functools.cache`d, so a per-call kwarg is the only correct
lever — `WAGTAIL_AI['PROVIDERS']` would be shared and cached.

**Item 3 — budget isolation.** `SPAM_LLM_BUDGET_CACHE_KEY`
(`ai_rate_limit:forum_spam`) + `SPAM_LLM_BUDGET_LIMIT` (200/hr) in
`apps/forum_host/constants.py`, separate from the blog's `ai_rate_limit:global`.

**Rejected implementation — `cache.incr()`.** Considered a fixed-window counter
via `cache.add` + `cache.incr` to stop the sliding-TTL restamp. Checked the
source: Django's `BaseCache.incr` is `get()` then `set(key, value)` with **no
timeout**, so it re-stamps with the backend's default `TIMEOUT` — 300s in this
project's `CACHES` — instead of `AIRateLimiter.TTL` (3600s). That is a silent
12x window shrink that differs between LocMem (local) and Redis (prod). Kept the
explicit `cache.set(key, calls + 1, cls.TTL)` idiom and pinned it with
`test_consume_sets_the_one_hour_ttl_explicitly`.

**Minor cleanups (both bundled).** `verdict[:80]` → `SPAM_LLM_LOG_TRUNCATE_CHARS`;
`verdict[4:]` → a first-word split, so `"SPAMMY: too promotional"` yields the
reason `"too promotional"` rather than `"MY: too promotional"`. `extract_text` now
runs once per screened post via a new package-side
`HeuristicSpamBackend.check_text(text)` (`check(obj)` delegates to it), instead of
the body being flattened once by the heuristic and again by the LLM pass.

### 2026-07-25 - Verification (run 2026-07-25-1825)

Full suite, the three affected apps:

```
$ python -m pytest apps/forum_host packages/wagtail_forum apps/blog -q
737 passed, 0 failed, 7 skipped
```

Named evidence per criterion:

```
LLMSpamBudgetAccountingTests::test_sustained_outage_burns_nothing_and_never_flips_to_publish PASSED
LLMSpamBudgetAccountingTests::test_sustained_timeouts_burn_nothing PASSED
LLMSpamBudgetAccountingTests::test_sustained_unparseable_replies_burn_nothing PASSED
LLMSpamBudgetAccountingTests::test_unparseable_reply_consumes_nothing PASSED
LLMSpamBudgetAccountingTests::test_provider_call_carries_an_inner_timeout PASSED
LLMSpamBudgetAccountingTests::test_forum_budget_is_separate_from_the_blog_global_counter PASSED
LLMSpamBudgetAccountingTests::test_exhausted_budget_degrades_to_heuristic_publish PASSED
GenerateAiTextHelperTestCase::test_timeout_is_forwarded_as_a_completion_kwarg PASSED
GenerateAiTextHelperTestCase::test_timeout_is_omitted_when_not_supplied PASSED
```

- **Criterion 1** — the three sustained-failure arms (exception / timeout /
  unparseable) each run `N > SPAM_LLM_BUDGET_LIMIT` consecutive failures, assert
  every result is `is_clean=False` with `SPAM_LLM_UNAVAILABLE_REASON`, and assert
  the forum counter is still `0`. Note the evidence reads on the **forum** key,
  not `check_global_limit` — since item 3 landed, the forum no longer touches
  `ai_rate_limit:global` at all, which would make the criterion's original
  wording vacuously true. The untouched global counter is asserted separately as
  the item-3 proof.
- **Criterion 2** — asserted at both hops: `spam.py` passes
  `timeout=SPAM_LLM_TIMEOUT_SECONDS` into `generate_ai_text`, and
  `generate_ai_text` forwards it to `service.completion(...)`. Recovery
  behaviour documented in `forum.md`.
- **Criterion 3** — `test_forum_budget_is_separate_from_the_blog_global_counter`
  asserts `ai_rate_limit:global` is still `0` after a successful forum screen.
- **Criterion 4** — `backend/docs/patterns/domain/forum.md` gained a
  "Keeping the two postures independent" subsection, an "Enable procedure", and
  an operational-knobs table.

**Mutation-tested, not just green.** Every new guarantee was verified to fail
when the fix is removed:

| Mutation | Result |
|----------|--------|
| consume moved *before* `_call_llm` | 4 failed — incl. `attempt 3 published`, reproducing the exact sticky fail-open H13 describes |
| consume moved to right after `_call_llm` (bills unparseable) | 2 failed — both unparseable arms |
| `timeout=` dropped from the `submit()` | 1 failed — `KeyError: 'timeout'` |
| `check_text(text)` reverted to `check(obj)` | 1 failed — `2 != 1` walks |

The extract-once test was itself found vacuous on first write (an instance-level
spy on `backend.extract_text` cannot see the heuristic's own binding, so it read
1 either way) and was rewritten to spy the shared module-level
`wagtail_forum.spam.base.extract_text`.

Lint: `flake8` clean on all 9 changed Python files; `black` reformatted 2 files
(cosmetic) and the suite was re-run green afterwards.

**Deferred by user decision:** enabling the setting in a live environment →
todo 280 (`280-pending-p3-forum-spam-llm-enable-in-env.md`).

### 2026-07-25 - Code review (run 2026-07-25-1825)

`code-review-orchestrator` routed the diff to `wagtail-reviewer`,
`django-drf-reviewer`, and `cross-cutting-reviewer`. **0 critical, 0 high,
1 medium, 7 informational.** Confirmed clean: the definitive-verdict-only
consume path (unreachable from the unparseable branch), the `timeout is not
None` gate keeping existing `generate_ai_text` call sites byte-identical, the
`CLEAN`/`CLEANLY` lookalike rejection, and the package reusability contract (no
`apps.*` imports added to `wagtail_forum`).

#### Known issues — accepted at completion

- **[MEDIUM] `spam.py` — peek→consume TOCTOU window.** N concurrent moderations
  can each peek under the cap and then each consume, overshooting by up to N-1.
  The window is genuinely wider than the old check-and-increment: it now spans
  the provider call (~3s) rather than two adjacent cache ops. **Accepted** — the
  consequence is bounded *overspend* at the cap boundary, not a safety-property
  violation (it cannot cause a fail-open publish), and the pre-existing
  `check_global_limit` was already a non-atomic `get`-then-`set` with the same
  class of race. Making it atomic would need a Lua/`incr`-based counter, and
  `cache.incr` is exactly the primitive rejected above for silently collapsing
  the TTL. Revisit only if real traffic shows the cap being materially
  overshot; `SPAM_LLM_MAX_WORKERS` bounds in-flight screens per process.

### 2026-07-25 - Completed by completing-todos skill (run 2026-07-25-1825)

- Verification: all 4 acceptance criteria passed, each backed by named test
  output quoted above; every new guarantee additionally mutation-tested.
- Review: 8 findings total, 0 blocking — 1 medium accepted and documented above.
- CI gates run locally: `manage.py check` → "System check identified no issues";
  `manage.py spectacular` → exit 0.
- Source finding `#H13` was already checked off by todo 255 slice 2; its line in
  `docs/audits/2026-07-11-forum-modernization.md` was annotated to record this
  hardening pass (274) and the open enable step (280) rather than re-flipping an
  already-closed box.
