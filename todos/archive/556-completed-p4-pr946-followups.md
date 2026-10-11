---
status: completed
priority: p4
issue_id: "556"
tags: [todo-sweep, follow-ups, backend, web]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #946 (todos 515, 522), run 2026-10-02-0335

## Problem

Promoted out of todo 527 on 2026-10-10 (owner decision: slice it per PR). Todo-sweep run 2026-10-02-0335
merged PR #946; its review rounds reported the non-blocking findings below, which a curation pass
checked against main and a refuter failed to refute. Line numbers are as of 2026-10-02, so re-check each
finding against main before acting on it.

## Findings

### PR #946 (todos 515, 522)

1. **`web/src/layouts/AppShell.test.tsx:277`** (medium, defect). flushDeferred's runOnlyPendingTimersAsync skips chained deferrals, so a re-deferred focus restore passes both widen tests. vi.runOnlyPendingTimersAsync is sinon runToLast: it ticks only to the last timer pending at call time, and a timer scheduled during that tick lands at now+1 or later, so a useModalFocus restore deferred twice (setTimeout(0)->setTimeout(0), rAF->rAF, rAF->timeout) never runs. Reviewers' mutants left all 28 tests green where the old 50 ms sleep failed both widen tests. The comment at 264 promises every deferral 'however long'; its runAllTimers rationale (273-274) cites the unread poll, which never starts in these logged-out tests. rAF coverage rests on Vitest 4 deriving toFake from jsdom globals (no fakeTimers config).
   Suggested: Flush a bounded window: `await vi.advanceTimersByTimeAsync(1000)` (precedent CommandPalette.test.tsx:118; stays under the 30 s UNREAD\_POLL\_INTERVAL\_MS), or runAllTimersAsync since no interval exists logged out. Rewrite 264-274 to state what is flushed, mutation-check with a nested restore, optionally pin toFake incl. requestAnimationFrame, and correct the 'however long' claim in archived 522 Work Log line 64.
   Seen on main: AppShell.test.tsx:277 `await vi.runOnlyPendingTimersAsync();`, :264 'Run every deferral (rAF or timeout, however long)'. vitest dist test.DNmyFkvJ.js:2693-2700 runToLast ticks to lastTimer().callAt; :1612-1613 callAt = now + (delay || (duringTick ? 1 : 0)). UnreadNotificationsContext.tsx:73-79 returns before setInterval (:84) when logged out; AppShell.test.tsx:52 sets isAuthenticated=false.

2. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:186`** (low, defect). Tuple-line count sees only lines opening with '(', so a list-form or spread choice is neither counted nor parsed and drift passes. The counter added for todo 515 (so no choice is dropped silently) counts `^\s*\(` lines. A choice written as a list literal `["dormant", "Dormant"],` (valid Django choices) or contributed by `*EXTRA_CONDITIONS,` matches neither the counter nor the key/label regex, so parsed equals counted and the test passes when web lacks the choice too: the exact fail-open 515 finding 4 meant to close. Probed in memory on main's models.py: both forms give parsed 5, lines 5.
   Suggested: Replace the line count with a residue check: strip `#` comment lines, remove every parsed tuple from the block (with an optional trailing comma, `",?\s*\)`), and expect the leftover to be only whitespace and commas, with a message quoting the leftover. Probed in memory: it catches spread, list-form and gettext entries and passes main, commented and Black-wrapped tuples.
   Seen on main: DiseaseDiagnosePage.test.tsx:186 `const tupleLines = choices![1].match(/^\s*\(/gm) ?? [];`, :187 `expect(backendChoices).toHaveLength(tupleLines.length);`, :178 parser `/\(\s*"([^"]+)",\s*"([^"]+)"\s*\)/g`. Probe on models.py:853-864 plus `["dormant", "Dormant"],` or `*EXTRA,`: parsed 5, lines 5.

3. **`web/src/layouts/AppShell.test.tsx:286`** (low, polish). No afterEach restores real timers, so one hung fake-timer test cascades; the bystander comment claims a check the stub cannot make. Fake timers (and the matchMedia stub) are restored only in each test's own finally, and a test that times out never reaches it, so the fakes leak into later userEvent tests (reviewer probe: one hang, three failures). Separately, the unmount test's comment says the bystander shows AppShell's cleanup 'removes only its own listeners', but the stub deletes by callback identity and AppShell never receives the bystander, so no implementation could remove it; the bystander only makes the count relative.
   Suggested: Add `afterEach(() => { vi.useRealTimers(); });` with a block body, as ThreadSummaryPanel.test.tsx:51-54 does. Reword 416-418: the bystander keeps the baseline non-zero so the assertion is relative; drop the 'removes only its own listeners' claim.
   Seen on main: AppShell.test.tsx:1 imports beforeEach, not afterEach; vi.useFakeTimers() at :286/:365 is undone only in finally at :315/:379. :250-252 removeEventListener does `md.listeners.delete(cb)`; :422 bystander `md.listeners.add(() => {})` is never handed to AppShell; :417-418 'AppShell's cleanup is shown to remove only its own listeners'.

4. **`web/src/pages/diagnosis/DiseaseDiagnosePage.test.tsx:178`** (low, polish). Drift guard false-reds on legitimate formatting with a misleading length message; field slice assumes a multi-line declaration; two guards lack messages. Parser and counter disagree and report drift where there is none: a `#`-commented tuple is parsed but not counted (6 vs 5); a Black-exploded tuple with its magic trailing comma is counted but not parsed (5 vs 6; Black runs on backend/); a one-line list gives 2 vs 1; a `]` in a label truncates the list (3 vs 4). The slice end `^ {4}\)` (174) assumes a multi-line declaration: a one-liner runs into later fields. Today the next field (location) has no choices, so the message stays right; an adjacent inline-choices field would be parsed and blamed. The expects at 181 and 187 carry no message.
   Suggested: The residue check from the list-form item fixes the comment, trailing-comma and one-line cases. Also temper the slice so it cannot cross a declaration, e.g. `/^ {4}plant_condition = models\.CharField\(((?:(?!\n {4}\S)[\s\S])*)/m` (probed: main parses 5, a one-liner gets 'no inline choices'), give the 181/187 expects messages naming the remedy, and note the `]`-in-label limit.
   Seen on main: DiseaseDiagnosePage.test.tsx:174 slice ends at `^ {4}\)`; :178 regex has no `,?` before `\)`; :181 `expect(backendChoices.length).toBeGreaterThan(0);` and :187 have no message. In-memory probes on models.py: commented 6 vs 5, Black-wrapped 5 vs 6, one-line list 2 vs 1, `]` in label 3 vs 4. .pre-commit-config.yaml:134-140 runs Black on backend/.

## Acceptance Criteria

- [x] Each of its 4 findings is fixed with a test, or the Work Log records why it was left as is.

## Work Log

### 2026-10-10 - Promoted out of todo 527

- Split from the consolidated follow-up todo 527 (owner decision 2026-10-10: one todo per source PR).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- Finding 1: `flushDeferred` in `web/src/layouts/AppShell.test.tsx` now runs `vi.advanceTimersByTimeAsync(1000)`, which also runs timers scheduled during the advance; its comment states what is flushed (one simulated second; the 30 s unread poll never starts logged out; rAF is faked via jsdom's globals). Probed by deferring `useModalFocus`'s restore twice (`setTimeout(0)` -> `setTimeout(0)`, then rAF -> rAF): both widen tests fail, and pass again once reverted. The "however long" claim in archived todo 522's Work Log is corrected in place.
- Findings 2 and 4: `DiseaseDiagnosePage.test.tsx` reads the choices through `readInlineChoices`, which bounds the field slice so it stops at the next 4-space-indented line (a one-liner cannot run into the next field), drops `#` comment lines, accepts Black's trailing comma inside a tuple, and returns the unparsed residue instead of counting `(` lines. The guard expects the residue to be empty and quotes it; every expect names its remedy. A new `readInlineChoices` describe pins each review probe: list-form, spread, gettext and single-quoted choices are reported; commented, Black-exploded and one-line lists parse clean; a one-liner field reports "no inline choices". The `]`-in-label limit is noted in the comment.
- Finding 3: an `afterEach(() => { vi.useRealTimers(); })` restores real timers even when a fake-timer test times out before its `finally`, and the unmount test's comment no longer claims the bystander shows which listeners the cleanup removes.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c "cd web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx src/pages/diagnosis/DiseaseDiagnosePage.test.tsx && grep -n '^- Finding' todos/archive/556-completed-p4-pr946-followups.md"` — evidence `.sweep-evidence/g4/556-ac0.txt` (not committed), last lines:

  ```text
     Duration  1.53s (transform 152ms, setup 267ms, import 453ms, tests 975ms, environment 1.12s)

  52:- Finding 1: `flushDeferred` in `web/src/layouts/AppShell.test.tsx` now runs `vi.advanceTimersByTimeAsync(1000)`, which also runs timers scheduled during the advance; its comment states what is flushed (one simulated second; the 30 s unread poll never starts logged out; rAF is faked via jsdom's globals). Probed by deferring `useModalFocus`'s restore twice (`setTimeout(0)` -> `setTimeout(0)`, then rAF -> rAF): both widen tests fail, and pass again once reverted. The "however long" claim in archived todo 522's Work Log is corrected in place.
  53:- Findings 2 and 4: `DiseaseDiagnosePage.test.tsx` reads the choices through `readInlineChoices`, which bounds the field slice so it stops at the next 4-space-indented line (a one-liner cannot run into the next field), drops `#` comment lines, accepts Black's trailing comma inside a tuple, and returns the unparsed residue instead of counting `(` lines. The guard expects the residue to be empty and quotes it; every expect names its remedy. A new `readInlineChoices` describe pins each review probe: list-form, spread, gettext and single-quoted choices are reported; commented, Black-exploded and one-line lists parse clean; a one-liner field reports "no inline choices". The `]`-in-label limit is noted in the comment.
  54:- Finding 3: an `afterEach(() => { vi.useRealTimers(); })` restores real timers even when a fake-timer test times out before its `finally`, and the unmount test's comment no longer claims the bystander shows which listeners the cleanup removes.
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
