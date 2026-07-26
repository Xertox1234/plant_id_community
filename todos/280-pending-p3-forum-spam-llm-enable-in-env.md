---
status: pending
priority: p3
issue_id: "280"
tags: [forum, spam, ai, moderation, ops, deploy]
dependencies: ["274"]
source_review: "docs/audits/2026-07-11-forum-modernization.md"
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

- [ ] **Prerequisite:** an attempts counter caps spend during provider
      misbehaviour (chronic timeout / unparseable replies) by failing **closed**,
      without letting failures drain the verdict budget into publish-unscreened.
      Todo 274's three sustained-failure tests must still pass unchanged.
- [ ] `WAGTAILFORUM_SPAM_BACKEND` is set to the LLM backend in at least one
      environment, with a working `OPENAI_API_KEY`.
- [ ] A real post is screened end-to-end (a `[SECURITY] Forum spam LLM flagged
      content` or a clean publish observed in that environment's logs).
- [ ] Budget/timeout tunables reviewed against that environment's actual forum
      volume; adjusted if the defaults (200/hr, 4 workers, 3s) do not fit.

## Notes

Parent epic: todo 255 (`255-in_progress-p1-forum-ai-premium.md`), H13 slice 2.
Gate: todo 274 (archived) — read its Work Log for what the hardening changed.
