---
status: completed
priority: p4
issue_id: "522"
tags: [web, a11y, testing]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Findings 1-4: record as left-as-is per todo 524's decision not to backfill archived Verified entries; code changes only for the six AppShell.test.tsx findings (2026-10-02)"
---

# Drawer widen focus: non-blocking findings from PR #934 (todo 509)

## Problem

PR #934 (todo 509) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`todos/archive/509-completed-p4-drawer-widen-focus-to-main-911-followups.md:63`** (low, round 1). The archived 509 Work Log embeds absolute worktree paths and a .sweep-evidence reference. That is the same dangling-path problem this todo's finding 1 fixed in todo 488.
   Suggested: Rewrite the AC 1 command and the grep output lines to repo-relative paths and drop the .sweep-evidence name.

2. **`todos/archive/509-completed-p4-drawer-widen-focus-to-main-911-followups.md:66`** (low, round 2). The new 'Verified' AC 1 entry quotes absolute worktree paths (incl. home dir username), a `.sweep-evidence` file, and `todos/509-pending-…` (renamed by this diff). Findings 1-2 removed exactly these from todo 488. Not a security issue: 118 such paths already exist in archive.
   Suggested: Rewrite the AC 1 command repo-relative (`cd web && …`, `todos/archive/509-completed-…`) and drop the `.sweep-evidence` reference, as done for 488. Or note the land.py output convention in todo 512/513 follow-ups.

3. **`todos/archive/509-completed-p4-drawer-widen-focus-to-main-911-followups.md:67`** (low, round 1, round 2). The new Verified entry quotes absolute home-directory worktree paths (/Users/williamtower/...) and a .sweep-evidence file. That is the same thing findings 1-2 removed from todo 488 in this PR. Exposure is minor because 39 archived todos already carry such paths.
   Suggested: Rewrite the AC 1 command with repo-relative paths (cd web && ...; todos/...) and drop the .sweep-evidence reference, or have land.py relativize paths when it writes the Verified entry.
   Also reported: The new Verified entry brings back the problem Findings 1-2 just removed from todo 488. It quotes absolute worktree paths and a `.sweep-evidence` file, and its grep points at `todos/509-pending-...md`, which this same diff renamed. The command can no longer be re-run.
   Also reported: The AC 1 evidence brings back the absolute worktree paths and the .sweep-evidence reference that Findings 1-2 just removed from 488. It also greps todos/509-pending-...md, which this same diff renames, so the recorded command no longer runs.
   Also reported: The 509 Verified entry quotes absolute worktree paths and a `.sweep-evidence` file, which is the pattern findings 1-2 just removed from 488. Its grep also targets `todos/509-pending-...`, a path this rename removed, so the command cannot be rerun.

4. **`todos/archive/509-completed-p4-drawer-widen-focus-to-main-911-followups.md:69`** (low, round 1). The Verified AC 1 entry has the same defect that Findings 1-2 just fixed in todo 488. It quotes an absolute worktree path and a `.sweep-evidence` file. It also greps `todos/509-pending-...md`, a path this same diff renames into the archive, so the recorded command cannot be rerun.
   Suggested: Rewrite AC 1 with repo-relative paths (`cd web && ...`, `todos/archive/509-completed-...md`) and drop the `.sweep-evidence` reference, the same way 488 was rewritten. If land.py writes this entry, fix the generator in a follow-up todo.

5. **`web/src/layouts/AppShell.test.tsx:266`** (low, round 1). flushDeferred waits a real 50 ms setTimeout. That is a wall-clock sleep, and it only covers deferrals of 50 ms or less. A rAF or short timeout is caught, but a longer one slips through.
   Suggested: Accept it, or use vi.useFakeTimers with advanceTimersByTimeAsync to make the flush deterministic.

6. **`web/src/layouts/AppShell.test.tsx:295`** (low, round 2). `toHaveBeenCalledWith({ preventScroll: true })` passes if ANY call to main.focus carried the option. A later second focus() on \<main> without preventScroll (the call that would actually scroll) would still pass.
   Suggested: Assert every call: `expect(focusSpy.mock.calls.every(([o]) => o?.preventScroll === true)).toBe(true)`, or use `toHaveBeenLastCalledWith` plus `toHaveBeenCalledTimes(1)`.

7. **`web/src/layouts/AppShell.test.tsx:390`** (low, round 1). The edit is justified, with one weak spot. Going from toBe(1) to >0 still catches leaks through the absolute 0 check after unmount. But the comment says 'count relative to what was there' while no relative comparison is made, and the test no longer catches a double subscription that is later cleaned up.
   Suggested: Reword the comment to match the code ('at least one listener while mounted, none after unmount'). Or assert `md.listeners.size` drops by exactly AppShell's count. Either way the absolute 0 check after unmount stays, which is what guards against the leak.

8. **`web/src/layouts/AppShell.test.tsx:391`** (low, round 1). The comment promises a relative count, but the test still asserts an absolute 0 after unmount, and `before` is only checked to be > 0. The edit is justified because it is no stricter than before, but the comment misstates what the test checks.
   Suggested: Change the comment to say that at least one listener is registered and that every listener is gone after unmount. Alternatively, record the count before render and assert that unmount brings it back to that number.

9. **`web/src/layouts/AppShell.test.tsx:396`** (low, round 1). The unmount-listener test now captures `before` but only asserts it is >0, then asserts the final size is exactly 0. If another legitimate subscriber to the same query exists, the final `toBe(0)` fails, which contradicts the comment about not pinning an exact count.
   Suggested: Assert `md.listeners.size` is `before - 1` after unmount (or compare against the pre-render size) so the test matches its comment.

10. **`web/src/layouts/AppShell.test.tsx:401`** (low, round 2). The unmount test's comment says it counts relative to existing listeners, but the final assertion is still an absolute toBe(0). The 'before' count is only checked >0, so the relaxation from toBe(1) is half-done and a second legitimate subscriber would still fail the test.
   Suggested: Assert listeners.size equals the count captured before render, or drop the relative-count comment.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #934 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Findings 1-4 (left as is, owner decision 2026-10-02): the archived 509 Verified entry keeps its absolute worktree paths, `.sweep-evidence` pointer and pre-archive todo path, per todo 524's decision not to backfill the ~102 already-archived lines. Todo 524 fixed the source instead: `land.py flip_acs` now relativizes paths, rewrites the todo's own path to its archived path and labels the pointer "(not committed)", so entries written since do not carry them.
- Finding 5: `flushDeferred` runs `vi.runOnlyPendingTimersAsync()` under fake timers instead of sleeping 50 ms, so every deferral the close scheduled runs, however long, and no wall-clock passes. The two tests that use it install `vi.useFakeTimers()` before rendering, open the drawer with `trigger.focus()` + `fireEvent.click` (user-event hangs under Vitest fake timers: RTL's `asyncWrapper` drains with a `setTimeout(0)` it advances only for Jest, and `userEvent.setup()` cannot redefine the non-configurable `navigator.clipboard` polyfill from `setup.ts`), and restore real timers in `finally`. Probed by restoring focus in a 200 ms `setTimeout` in `useModalFocus`: before, both tests stayed green; after, both fail at the post-flush `toHaveFocus()`.
- Finding 6: the widen test asserts `toHaveBeenCalledTimes(1)` and `toHaveBeenCalledWith({ preventScroll: true })` on `main.focus`, after the flush. Probed by adding a second bare `mainRef.current?.focus()`: before, green; after, fails on the call count.
- Findings 7-10: the unmount test seeds one bystander listener, records the count before render, asserts render adds at least one (not exactly 1, by todo 509's decision) and unmount returns the count to the recorded value; the comment now says exactly that. Probed by dropping `useMediaQuery`'s cleanup: fails, "expected 2 to be 1".

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx && grep -nE "^- Findings? [0-9]" todos/archive/522-completed-p4-drawer-widen-focus-934-followups.md` — evidence `.sweep-evidence/g6/522-ac0.txt` (not committed), last lines:

  ```text

  63:- Findings 1-4 (left as is, owner decision 2026-10-02): the archived 509 Verified entry keeps its absolute worktree paths, `.sweep-evidence` pointer and pre-archive todo path, per todo 524's decision not to backfill the ~102 already-archived lines. Todo 524 fixed the source instead: `land.py flip_acs` now relativizes paths, rewrites the todo's own path to its archived path and labels the pointer "(not committed)", so entries written since do not carry them.
  64:- Finding 5: `flushDeferred` runs `vi.runOnlyPendingTimersAsync()` under fake timers instead of sleeping 50 ms, so every deferral the close scheduled runs, however long, and no wall-clock passes. The two tests that use it install `vi.useFakeTimers()` before rendering, open the drawer with `trigger.focus()` + `fireEvent.click` (user-event hangs under Vitest fake timers: RTL's `asyncWrapper` drains with a `setTimeout(0)` it advances only for Jest, and `userEvent.setup()` cannot redefine the non-configurable `navigator.clipboard` polyfill from `setup.ts`), and restore real timers in `finally`. Probed by restoring focus in a 200 ms `setTimeout` in `useModalFocus`: before, both tests stayed green; after, both fail at the post-flush `toHaveFocus()`.
  65:- Finding 6: the widen test asserts `toHaveBeenCalledTimes(1)` and `toHaveBeenCalledWith({ preventScroll: true })` on `main.focus`, after the flush. Probed by adding a second bare `mainRef.current?.focus()`: before, green; after, fails on the call count.
  66:- Findings 7-10: the unmount test seeds one bystander listener, records the count before render, asserts render adds at least one (not exactly 1, by todo 509's decision) and unmount returns the count to the recorded value; the comment now says exactly that. Probed by dropping `useMediaQuery`'s cleanup: fails, "expected 2 to be 1".
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
