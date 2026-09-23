---
status: pending
priority: p3
issue_id: "414"
tags: [web, forum, ai]
dependencies: []
source_review: "todos/405-pending-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Add the premium "Summarize thread" button on web (`forum/topics/<id>/summary/`)

## Problem

`GET forum/topics/<id>/summary/` (`apps/forum_host/summary.py`; 20 tests;
`IsPremiumUser`, throttled) is finished. It is the only premium AI feature with
no UI: compose-assist and care/ask are wired at
`web/src/services/forumService.ts:827,915`. Its design spec says the UI belongs
to a later wave (`docs/superpowers/specs/2026-07-22-forum-thread-summarization-design.md:26,32`).
The owner decided (todo 405) to wire it up.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Add a service call and a premium-only button on `ThreadDetailPage`.
2. Handle the loading, error, throttled (429) and non-premium states.
3. Add tests.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] A premium user sees and can run a summary; a non-premium user sees nothing, or an upsell.
- [ ] Tests cover the 429 and 403 paths.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
