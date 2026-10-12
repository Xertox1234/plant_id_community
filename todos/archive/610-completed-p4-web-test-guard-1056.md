---
status: completed
priority: p4
issue_id: "610"
tags: [web, testing, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1056 (todo 590, web test guard follow-ups)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1056 (todo 590, web test guard follow-ups). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1056 (todo sweep run 2026-10-11-2219, group g8, todos 590); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:53` Trailing-residue capture `([^,)]*)` stops at the first `,` or `)`, so `] + list(EXTRA)` yields the truncated residue `+ list(EXTRA` (the test pins this string). The guard still fails closed, so this only makes the failure message confusing. | also: The post-list tail capture `([^,)]*)` stops at the first `)`, so `] + list(EXTRA)` is reported as the truncated residue `+ list(EXTRA` (the test pins this). The guard still fails closed, so this is only a confusing failure message. (reported at line 51)
2. **low** `web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:51` The post-list tail capture `([^,)]*)` stops at the first `)`, so `] + list(EXTRA)` is reported as the truncated residue `+ list(EXTRA` (the test pins this). The guard still fails closed, so this is only a confusing failure message.

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/layouts/AppShell.test.tsx:295 The new flushDeferred tests call vi.useFakeTimers() inside the test. If a describe-level beforeEach already faked timers, that call would be redundant, and the finally block's useRealTimers() could leak into later tests. (fixed on main: The premise does not hold on origin/main. The top-level beforeEach (line 51) does not fake timers, so no test depends on fakes it installs. A top-level afterEach (lines 69-71) calls vi.useRealTimers(), so each test's own fake/real-timer pair cannot leak.; the refuter agreed: The premise is false. The top-level beforeEach (line 51) only resets mocks and storage and never fakes timers, so the in-test vi.useFakeTimers() is not redundant. The top-level afterEach (lines 69-71) calls vi.useRealTimers() after every test, so the finally block cannot leak state into later tests.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1056 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g8`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Findings 1 and 2 (one defect, reported twice): fixed. The post-list tail capture in
  `readInlineChoices` (`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx`) now allows balanced
  parentheses two levels deep, so `] + list(EXTRA)` is reported whole as `+ list(EXTRA)` instead of
  the truncated `+ list(EXTRA`. It still stops at the declaration's top-level `,` or closing `)`.
- The test that pinned the truncated string now pins the full one, and a nested-call case
  (`+ list(chain(A, B))`) was added. The guard fails closed either way; this only fixes the message.
- Evidence: `npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx` from `web/`, 24 passed.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `cd web && npx vitest run src/pages/diagnosis/DiseaseDiagnosePage.test.tsx --reporter=verbose` — evidence `.sweep-evidence/g9/610-ac0.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  24 passed (24)
     Start at  09:49:02
     Duration  1.22s (transform 65ms, setup 107ms, import 236ms, tests 316ms, environment 492ms)
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
