---
status: completed
priority: p4
issue_id: "590"
tags: [todos, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1448

Follow-ups for PR #1027 (todo 556).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Findings 1 and 7 fixed: `readInlineChoices` in `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` now drops trailing `#` comments as well as whole-line ones, skipping quoted strings so a `#` inside a label survives. New tests: a trailing comment on a tuple line, and a `#` inside a label.
- Finding 2 fixed: whatever follows the closing `]` up to the next `,` or `)` (`choices=[...] + EXTRA`, on the same line or the next) now joins the residue. Three new cases pin it.
- Findings 3, 6 and 8 fixed: the parser's self-tests run against a fixed fixture instead of `models.py`, so a real choice added, removed or reordered fails only the drift guard. One remaining test reads the real declaration but pins no count or line, only that it parses with no residue.
- Finding 5 fixed: two tests in `web/src/layouts/AppShell.test.tsx` (setTimeout -> setTimeout and rAF -> rAF) check that `flushDeferred` runs a chained deferral. Both failed when the flush was mutated back to `runOnlyPendingTimersAsync`, and so did the new parser tests when the parser changes were reverted.
- Finding 4 declined: the 1000 ms window is a deliberate trade-off that the `flushDeferred` comment already documents. A restore deferred longer than a second is not a realistic focus-restore shape, and any fixed window has some limit; widening it only moves that limit. Catching chained deferrals (finding 5) is the stronger guard.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `cd web && npx vitest --run src/layouts/AppShell.test.tsx src/pages/diagnosis/DiseaseDiagnosePage.test.tsx && grep -n -A8 'Implemented by the todo sweep (run 2026-10-11-2219)' todos/archive/590-completed-p4-web-test-guards-pr1027-followups.md` — evidence `.sweep-evidence/g8/590-ac0.txt` (not committed), last lines:

  ```text
  45-- Findings 1 and 7 fixed: `readInlineChoices` in `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` now drops trailing `#` comments as well as whole-line ones, skipping quoted strings so a `#` inside a label survives. New tests: a trailing comment on a tuple line, and a `#` inside a label.
  46-- Finding 2 fixed: whatever follows the closing `]` up to the next `,` or `)` (`choices=[...] + EXTRA`, on the same line or the next) now joins the residue. Three new cases pin it.
  47-- Findings 3, 6 and 8 fixed: the parser's self-tests run against a fixed fixture instead of `models.py`, so a real choice added, removed or reordered fails only the drift guard. One remaining test reads the real declaration but pins no count or line, only that it parses with no residue.
  48-- Finding 5 fixed: two tests in `web/src/layouts/AppShell.test.tsx` (setTimeout -> setTimeout and rAF -> rAF) check that `flushDeferred` runs a chained deferral. Both failed when the flush was mutated back to `runOnlyPendingTimersAsync`, and so did the new parser tests when the parser changes were reverted.
  49-- Finding 4 declined: the 1000 ms window is a deliberate trade-off that the `flushDeferred` comment already documents. A restore deferred longer than a second is not a realistic focus-restore shape, and any fixed window has some limit; widening it only moves that limit. Catching chained deferrals (finding 5) is the stronger guard.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
