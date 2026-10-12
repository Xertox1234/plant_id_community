---
status: pending
priority: p4
issue_id: "634"
tags: [web, tests, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PRs #1079 and #1085 (todos 610, 612, 615, web test gaps)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1079 (todos 610, 612, choice-capture depth test). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1079 (todo sweep run 2026-10-12-0349, group g9, todos 610, 612); follow-ups: verified.

1. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:351` The new regex balances parens only two levels deep (stated in the comment), but no test pins what a 3-level tail does. A future change to the depth (or to a recursive parser) has no discriminating case, and a 3-level tail silently truncates at its own `)`.
2. **low** `web/src/pages/forum/NewThreadPage.test.tsx:930` (rolled in from PR #1085, todo 615) In the two 'keeps ... no stored draft' tests, the only wait is `fetchCategory` toHaveBeenCalledWith(5); the keep assertions then run at once, so a regression that resets the poll or attachment in a later effect tick could still pass. Wait on a board-switch-finished signal, then confirm the tests go red with the reset guard removed.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1079 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g9`.
