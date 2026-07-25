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

- [ ] `WAGTAILFORUM_SPAM_BACKEND` is set to the LLM backend in at least one
      environment, with a working `OPENAI_API_KEY`.
- [ ] A real post is screened end-to-end (a `[SECURITY] Forum spam LLM flagged
      content` or a clean publish observed in that environment's logs).
- [ ] Budget/timeout tunables reviewed against that environment's actual forum
      volume; adjusted if the defaults (200/hr, 4 workers, 3s) do not fit.

## Notes

Parent epic: todo 255 (`255-in_progress-p1-forum-ai-premium.md`), H13 slice 2.
Gate: todo 274 (archived) — read its Work Log for what the hardening changed.
