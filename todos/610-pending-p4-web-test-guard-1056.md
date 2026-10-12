---
status: pending
priority: p4
issue_id: "610"
tags: [web, testing, follow-ups]
dependencies: []
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1056 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g8`.
