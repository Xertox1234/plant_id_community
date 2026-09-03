---
status: in_progress
priority: p3
issue_id: "280"
tags: [forum, spam, ai, moderation, ops, deploy]
dependencies: ["274"]
source_review: "docs/audits/2026-07-11-forum-modernization-COMPLETED.md"
source_finding: "H13"
---

# Enable the LLM spam backend in a target environment

Split out of todo 274 (the pre-enable hardening gate) on 2026-07-25. **274 is
the engineering work and it is done**; this todo is the remaining *operator*
action, deliberately not performed by an automated run because it is a
production config change with real LLM spend attached.

## Why this is separate

274's final acceptance criterion originally bundled two unlike things:
"document that the setting is safe to enable" (an engineering deliverable, now
landed) and "enable it in the target environment" (an ops decision requiring a
funded `OPENAI_API_KEY` and a chosen environment). Only the operator can decide
which environment goes first and when to accept the spend.

## Prerequisites (all satisfied by todo 274)

- Failed provider calls no longer consume AI budget, so an outage keeps failing
  closed (hold) and can never decay into publishing LLM-unscreened content.
- The forum screens against its own `ai_rate_limit:forum_spam` counter, so it
  cannot starve the blog's AI quota (or vice versa).
- The provider call carries an inner request deadline, so a hung provider
  unblocks the worker thread instead of parking the pool.

## Blocking prerequisite — uncapped spend while the provider misbehaves

**RESOLVED 2026-07-31** — see the Work Log. `SPAM_LLM_ATTEMPTS_CACHE_KEY` /
`SPAM_LLM_ATTEMPTS_LIMIT` now cap the misbehaviour case with a hold. The
analysis below is kept as the rationale.

Surfaced by `/code-review medium` of PR #500 (2026-07-25), **after** todo 274
landed. Resolve this before flipping the setting, not after.

Budget is consumed only for a **definitive** verdict. That is correct and
deliberate — it is what stops a provider failure from draining the cap and
flipping the backend to publish-unscreened (the H13 bug). But it leaves an
asymmetry:

| Provider state | Billable requests | Counted? | Capped? |
|---|---|---|---|
| Healthy | 1 per screened post | yes | yes, at 200/hr |
| Chronic timeout (answers in >`SPAM_LLM_TIMEOUT_SECONDS`) | 1 per screened post | **no** | **no** |
| Garbage/unparseable replies (never cached, so every retry re-calls) | 1 per screened post | **no** | **no** |

A `future.result()` expiry means the request *was* issued — the caller simply
stopped waiting for it. So the cap bounds spend exactly when spend is
well-behaved, and stops bounding it when the provider misbehaves. Exposure is
bounded by post-submission rate rather than unbounded, so it only bites above
`SPAM_LLM_BUDGET_LIMIT` posts/hr — but that is precisely the busy-forum case.

**Do NOT fix this by counting failures against the existing counter** — that
reintroduces the exact sticky fail-open todo 274 removed, and
`test_sustained_outage_burns_nothing_and_never_flips_to_publish` will go red.
The two postures must stay on separate counters:

- **Verdict budget** (`ai_rate_limit:forum_spam`, existing) — exhaustion is a
  cost decision on *working* screening → degrade to heuristic → **publish**.
- **Attempts counter** (new) — counts every call that reached the provider,
  including timeouts and unparseable replies. Exhaustion means the provider is
  misbehaving → stop spending → **hold** (fail closed), never publish.

Note `test_sustained_timeouts_burn_nothing` currently codifies the blind spot
as a guarantee; it will need to assert against the *verdict* counter
specifically once an attempts counter exists.

## Recommended Action

Follow the **Enable procedure** in
`backend/docs/patterns/domain/forum.md` → "LLM spam backend":

1. Confirm `OPENAI_API_KEY` is set and working in the target environment.
2. Set `WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend`.
3. Restart and watch the three log lines named in that section.

Start with a non-production environment if one is available. Roll back by
unsetting the variable — the heuristic default returns with no code change.

## Technical Details

No code changes expected. Files only if a tunable needs adjusting for real
traffic: `backend/apps/forum_host/constants.py` (`SPAM_LLM_BUDGET_LIMIT`,
`SPAM_LLM_MAX_WORKERS`, `SPAM_LLM_TIMEOUT_SECONDS`).

## Acceptance

- [x] **Prerequisite:** an attempts counter caps spend during provider
      misbehaviour (chronic timeout / unparseable replies) by failing **closed**,
      without letting failures drain the verdict budget into publish-unscreened.
      Todo 274's three sustained-failure tests must still pass unchanged.
- [ ] **Prerequisite (added 2026-09-02):** every `get_spam_backend()` call site
      is trust-gated before the flip. The DM send path was ungated — see the
      2026-09-02 Work Log entry.
- [ ] `WAGTAILFORUM_SPAM_BACKEND` is set to the LLM backend in at least one
      environment, with a working `OPENAI_API_KEY`.
- [ ] A real post is screened end-to-end (a `[SECURITY] Forum spam LLM flagged
      content` or a clean publish observed in that environment's logs).
- [ ] Budget/timeout tunables reviewed against that environment's actual forum
      volume; adjusted if the defaults (200/hr, 4 workers, 3s) do not fit.

## Notes

Parent epic: todo 255 (`255-in_progress-p1-forum-ai-premium.md`), H13 slice 2.
Gate: todo 274 (archived) — read its Work Log for what the hardening changed.

## Work Log

### 2026-07-31 - Started by completing-todos skill (run 2026-07-31-1738)

- Picked up by automated workflow.

### 2026-07-31 - AC1 (the engineering prerequisite) shipped

**Scope call up front:** AC1 is engineering and was done here. AC2–4 are
*operator* actions — they need a chosen environment, an accepted LLM bill, and
observed production logs. This run deliberately did not perform them, so the
todo stays `in_progress`; see "Remaining — operator decision" below.

**What landed** (`backend/apps/forum_host/{constants,spam}.py`):

A third counter, `SPAM_LLM_ATTEMPTS_CACHE_KEY`
(`ai_rate_limit:forum_spam_attempts`, limit `SPAM_LLM_ATTEMPTS_LIMIT` = 400/hr),
incremented in `_call_llm()` immediately before `submit()` — so **every** call
issued to the provider is counted, including the timeouts and unparseable
replies the verdict budget deliberately ignores. Exhaustion returns a rejected
`SpamResult` (**hold**), and stops calling the provider at all.

Three properties are load-bearing, each pinned by a test:

1. **Opposite posture from the verdict budget.** Failures are counted on the
   *new* key only. Counting them on `ai_rate_limit:forum_spam` would restore the
   sticky fail-open todo 274 removed.
2. **Peeked BEFORE the verdict budget.** A half-broken provider can exhaust
   both; verdict-first would take the degrade-to-heuristic branch and publish
   unscreened while the provider is known bad — the exact H13 flip.
3. **Peeked AFTER the verdict-cache lookup.** A cached verdict costs nothing, so
   the circuit must not hold it.

Counted at *issue* time, not on outcome: a `future.result()` expiry means the
request was issued and is billed, and we can never learn afterwards whether it
was. The write is guarded (`_consume_attempt`) so a Redis blip weakens the cap
rather than holding every post.

`SPAM_LLM_ATTEMPTS_LIMIT` (400) must stay **above** `SPAM_LLM_BUDGET_LIMIT`
(200) — every verdict is also an attempt, so inverting them makes the circuit
trip first under healthy traffic and converts the intended cost-degrade
(publish) into a hold. Pinned by `test_attempts_limit_stays_above_the_verdict_limit`.

**Known trade, documented not fixed:** `consume_budget` re-stamps the 1h TTL on
every write, so a tripped attempts cap is a *sticky* hold that clears only after
~1h of silence. Held posts are pending drafts, not lost — degraded-but-safe.
`AIRateLimiter.reset_budget(constants.SPAM_LLM_ATTEMPTS_CACHE_KEY)` clears it
early; recorded in `forum.md`.

**One existing test was edited, deliberately.**
`test_budget_exhausted_degrades_to_heuristic` patched `peek_budget` with a
blanket `return_value=False`. With two peeks that no longer expresses "the
verdict budget ran out" — it exhausts both, and the fail-closed attempts branch
correctly wins. Replaced with a key-specific `_only_exhausted(...)` side_effect.
Its assertions are unchanged. Todo 274's three sustained-failure tests were not
touched (one docstring clarified "budget" → "VERDICT budget").

### Verification

`pytest apps/forum_host/tests/test_spam.py --create-db`:

```
Pytest: 39 passed
```

Todo 274's three sustained-failure tests, by name, still green:

```
LLMSpamBudgetAccountingTests::test_sustained_outage_burns_nothing_and_never_flips_to_publish PASSED
LLMSpamBudgetAccountingTests::test_sustained_timeouts_burn_nothing PASSED
LLMSpamBudgetAccountingTests::test_sustained_unparseable_replies_burn_nothing PASSED
LLMSpamAttemptsCapTests::test_sustained_outage_stops_spending_at_the_cap PASSED
LLMSpamAttemptsCapTests::test_sustained_unparseable_replies_stop_spending_at_the_cap PASSED
```

Mutation check — the new guard replaced with `if False:` makes the new tests red,
so they are not hollow:

```
FAILED LLMSpamAttemptsCapTests::test_exhausted_attempts_holds_even_when_the_verdict_budget_is_also_out
FAILED LLMSpamAttemptsCapTests::test_sustained_outage_stops_spending_at_the_cap
2 failed, 37 deselected
```

Full backend suite, single invocation, fresh DB (`pytest -q --create-db`):

```
Pytest: 1443 passed, 0 failed, 8 skipped
```

`flake8` clean on all three changed Python files.

### Remaining — operator decision (AC2–4)

Read-only check of the Railway project `PlantID Community` on 2026-07-31:

- Exactly **one** environment exists: `production`. There is no staging target,
  so the todo's "start with a non-production environment if one is available"
  has no non-prod option here.
- `OPENAI_API_KEY` **is** set on the `plant_id_community` service.
- `WAGTAILFORUM_SPAM_BACKEND` is **not** set → the heuristic default is live.

So flipping the setting means enabling it in production, with real spend, on the
first try. That is the operator's call, not an automated run's.

**Operator decision, 2026-07-31: not yet — leave this todo open.** Nothing was
spent and no Railway variable was written. The engineering gate is now fully
clear (274 + this run's AC1), so enabling is a pure ops action whenever the
spend is acceptable:

1. Set `WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend` on the
   `plant_id_community` service.
2. Restart and watch the four log lines in `backend/docs/patterns/domain/forum.md`
   → "LLM spam backend" → Enable procedure. `[CIRCUIT] Forum spam LLM attempts
   cap reached` is the one to alert on — it means screening is holding every
   post.
3. Roll back by unsetting the variable; the heuristic default returns with no
   code change.

Caps in force on day one: 200 verdicts/hr (then degrade to heuristic → publish)
and 400 provider calls/hr (then hold). Review both against real volume — AC4.

### 2026-09-02 - Operator unblocked the key; a pre-flip gate surfaced (run 2026-09-02-2327)

**Operator decision reversed the 2026-07-31 hold:** `OPENAI_API_KEY` on the
`plant_id_community` service is now funded and current (confirmed by the
operator — Railway's API returns `valuesRedacted: true`, so no automated check
can verify a key value).

Railway state re-confirmed read-only before touching anything: still exactly one
environment (`production`), `OPENAI_API_KEY` present, `WAGTAILFORUM_SPAM_BACKEND`
still unset (heuristic default live).

**Blocking finding — the todo's blast-radius description was stale.** This todo
was written 2026-07-25; DMs shipped after it (todo 319). `get_spam_backend()`
has two call sites, and only one was trust-gated:

| Surface | Trust gate before this run |
|---------|----------------------------|
| Topic/Post publish (`models/moderation.py`) | Yes — the workflow only starts for `trust_level < TRUST_AUTOPUBLISH_LEVEL` |
| DM send (`api/direct_messages.py:227`) | **None** — every sender, every trust level |

So flipping the setting would have put a synchronous, billable LLM call on
**every DM send by every user**, not just on untrusted posts. And the two
surfaces are not equivalent under fail-closed: a flagged Post becomes a pending
draft a moderator can publish, but `Message` has no revision/workflow state to
hold (that module's own docstring says so), so the same verdict rejects the send
with a 400 and the text is gone. A 3s provider timeout would therefore *destroy*
a legitimate DM.

**Operator call: gate DMs first, then enable.** AC2–4 stay open pending the
deploy.

**What landed** (`packages/wagtail_forum/wagtail_forum/api/direct_messages.py`):

`_screen_dm_body(sender, text)` trust-routes the DM screen on the same
`TRUST_AUTOPUBLISH_LEVEL` the post path uses. It splits the two passes rather
than skipping screening:

- The **heuristic floor runs for everyone** — link flood / banned words are
  deterministic, offline and free, and weakening them with trust would trade one
  problem for a worse one.
- Only the **configured backend's** extra pass is gated, so untrusted senders
  (the actual DM-spam risk, and the same population the post path screens) still
  get the full LLM screen.

Three tests pin it, written RED first:

```
test_untrusted_sender_dm_is_screened_by_the_configured_backend
test_trusted_sender_dm_skips_the_configured_backend
test_trusted_sender_dm_still_gets_the_heuristic_floor
```

The third is the load-bearing one — without it the gate could silently drop
link-flood screening for every established member's DMs.

### Verification — DM trust gate

RED before the fix (2 of 3 new tests failing on current behaviour):

```
[FAIL] test_trusted_sender_dm_skips_the_configured_backend      assert 400 == 201
[FAIL] test_trusted_sender_dm_still_gets_the_heuristic_floor    assert 'link' in 'ai: recorded'
```

GREEN after:

```
Pytest: 26 passed          # test_direct_messages_api.py
Pytest: 1118 passed        # packages/wagtail_forum + apps/forum_host
Pytest: 1947 passed, 0 failed, 8 skipped   # full backend suite, --create-db
```

Mutation check — `>=` weakened to `>` (a MEMBER at exactly the threshold) makes
the boundary test red, so it is not hollow:

```
[FAIL] test_trusted_sender_dm_skips_the_configured_backend      assert 400 == 201
```

`flake8` clean on both changed files. Codified as "Every screening surface must
be trust-gated" in `backend/docs/patterns/domain/forum.md`.

### Remaining — AC2–4, after this deploys

The gate must be **live in production before** the variable is set; otherwise
the currently-deployed code still screens every DM. Order:

1. Merge this PR, confirm the Railway deploy settled.
2. Set `WAGTAILFORUM_SPAM_BACKEND=apps.forum_host.spam.LLMSpamBackend` on the
   `plant_id_community` service only (**not** environment-wide —
   `forum-prune-cron` imports the same settings and screens nothing).
3. AC3 evidence: a trust-0 throwaway account posts promotional text with ≤3
   links (so the heuristic passes it through to the LLM), and the
   `[SECURITY] Forum spam LLM flagged content` line is captured. Note a CLEAN
   verdict logs **nothing** — `_parse()` only logs on SPAM and on unparseable —
   so the SPAM line is the only positive in-log evidence available.
4. AC4 evidence gathered read-only already, ahead of the flip: production
   `/forum/rss/` lists **18 topics ever**, most seeded 2026-08-15/16, newest
   2026-08-30. Real volume is ~0–2 topics/day against a 200/hr verdict cap.
