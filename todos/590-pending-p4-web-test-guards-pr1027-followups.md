---
status: pending
priority: p4
issue_id: "590"
tags: [todos, follow-ups]
dependencies: []
---

# Follow-ups from PR #1027 (todo 556)

## Problem

Todo-sweep run 2026-10-11-1448 merged PR #1027 (the diagnosis-choices and focus-restore test guards). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1027 (todo sweep run 2026-10-11-1448, group g4, todos 556); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:46` readInlineChoices removes only whole-line `#` comments. A trailing comment on a tuple line, e.g. `("a", "A"),  # note`, stays in the residue, so the guard fails on a valid choices list. This is a false failure, not a false pass. | also: Only full-line `#` comments are removed. A trailing comment on a tuple line, such as `("a", "A"),  # note`, ends up in the residue, so a legitimate backend edit fails the guard with a confusing message. It fails loudly, not silently. (line 44)
2. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:47` The residue covers only the text inside `[...]`. A choice added outside the list, e.g. `choices=[(...)] + EXTRA_CONDITIONS`, gives an empty residue and passes, even though the comment says anything unparsed is reported.
3. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:296` The readInlineChoices self-tests run against the real models.py and hardcode toHaveLength(5) plus a literal LAST anchor. Adding a plant_condition choice, or moving 'critical' off the last line, turns these parser tests red even though the parser is fine. | also: The readInlineChoices self-tests run against the real models.py and hardcode toHaveLength(5) plus the LAST anchor. Adding or reordering a legitimate plant_condition choice turns these parser unit tests red, though the parser is fine. (line 321) | The `readInlineChoices` self-tests hardcode `toHaveLength(5)` against the real models.py. Adding a backend choice therefore also breaks the parser's own unit tests with a bare length mismatch, which hides the real drift signal. (line 298)
4. **low** `web/src/layouts/AppShell.test.tsx:290` flushDeferred now advances a fixed 1000 ms. That catches chained deferrals, but a single focus restore deferred by more than 1 s no longer fails the test, which runOnlyPendingTimersAsync did catch. The comment documents the limit, so this is a trade-off rather than a bug. | also: Moving from runOnlyPendingTimersAsync to advanceTimersByTimeAsync(1000) catches chained deferrals but no longer catches a single restore deferred by more than 1 s, which the old flush did catch. The comment documents this, but the guard is narrower on that axis.
5. **low** `web/src/layouts/AppShell.test.tsx:271` flushDeferred switched from runOnlyPendingTimersAsync to advanceTimersByTimeAsync(1000) to catch chained deferrals, but no test fails when a double-deferred restore (setTimeout->setTimeout, rAF->rAF) is reintroduced, so the claim is unpinned.
6. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:321` The readInlineChoices self-tests run against the real models.py and hardcode toHaveLength(5) plus the LAST anchor. Adding or reordering a legitimate plant_condition choice turns these parser unit tests red, though the parser is fine.
7. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:44` Only full-line `#` comments are removed. A trailing comment on a tuple line, such as `("a", "A"),  # note`, ends up in the residue, so a legitimate backend edit fails the guard with a confusing message. It fails loudly, not silently.
8. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:298` The `readInlineChoices` self-tests hardcode `toHaveLength(5)` against the real models.py. Adding a backend choice therefore also breaks the parser's own unit tests with a bare length mismatch, which hides the real drift signal.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1027 (todo 556).
