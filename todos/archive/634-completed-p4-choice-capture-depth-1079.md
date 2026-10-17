---
status: completed
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1079 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g9`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Finding 1 fixed with a test: `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` now pins a
  three-level tail, `] + list(chain(f(A), B))`, as residue `+ list` -- cut short at the `(` the
  two-level regex cannot balance, but never empty, so the drift guard still fails. The parser's
  comment names this as a known limit. A change to the depth (or a recursive parser) now turns it red.
- Finding 2 fixed: the two 'keeps ... no stored draft' tests in
  `web/src/pages/forum/NewThreadPage.test.tsx` serve board 5 as "Pests" and wait for that name to
  render (the fetch resolved and the page re-rendered), not for `fetchCategory` to be called.
- Mutation check (a script kept in the gitignored evidence dir): with the `stored === null` keep branch
  disabled, and separately with a poll/attachment reset fired only once board 5's fetch resolves, both
  tests fail; restored, both pass. Noted: the old wait also caught the later-tick reset (RTL's
  `waitFor` flushes the resolved mock inside `act`), so the new wait is the explicit signal rather
  than a fix for a live gap.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `bash -c 'cd web && ./node_modules/.bin/vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx src/pages/forum/NewThreadPage.test.tsx 2>&1 | grep -E "three-level|no stored draft|Test Files|Tests "; bash .sweep-evidence/g8/mutate-634.sh'` — evidence `.sweep-evidence/g8/634-ac0.txt` (not committed), last lines:

  ```text
        Tests  2 failed | 44 skipped (46)
  === restored, unmutated (expect 2 passed) ===
   ✓ src/pages/forum/NewThreadPage.test.tsx > NewThreadPage > keeps the poll when a ?category= change goes to a board with no stored draft (todo 615) 294ms
   ✓ src/pages/forum/NewThreadPage.test.tsx > NewThreadPage > "Ask the community" handoff (audit M6) > keeps the attachment when a ?category= change goes to a board with no stored draft (todo 615) 55ms
        Tests  2 passed | 44 skipped (46)
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
