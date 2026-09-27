---
status: pending
priority: p3
issue_id: "464"
tags: [testing, tech-debt]
dependencies: []
source_review: "todos/394-pending-p3-triage-the-grandfathered-archived-todos.md"
---

# Three behaviours whose code landed but was never tested

## Problem

The todo 394 triage found three archived todos whose code is live but
whose test AC never landed. Each file is now `superseded` with a pointer
here.

- **PlantNet circuit breaker** (from 001): `plantnet_service.py` wraps
  calls in `create_monitored_circuit("plantnet_api")`, but
  `test_circuit_breaker_locks.py` exercises only `_plant_id_circuit`.
  Nothing shows the PlantNet breaker opening after 5 failures and then
  failing fast without an HTTP call.
- **Reaction toggle concurrency** (from 004-reaction): `wagtail_forum`'s
  `ReactionToggleView` relies on a `UniqueConstraint` plus an atomic create
  that catches `IntegrityError`, and `Reaction.recount` locks the Post row.
  The only tests are sequential.
- **TipTap destroy on unmount** (from 015):
  `web/src/components/forum/TipTapEditor.tsx:633-640` calls `destroy()` in
  cleanup, but no test spies on it.

## Acceptance Criteria

- [ ] A PlantNet breaker test: after N failures the breaker is open, and
      the next call raises without touching the HTTP layer.
- [ ] A `ReactionToggleView` concurrency test (threads or a
      `TransactionTestCase`): two simultaneous toggles leave a consistent
      count and at most one row.
- [ ] A TipTap test asserting `destroy()` runs on unmount.
- [ ] Each test fails with its guard removed (mutation-checked).
