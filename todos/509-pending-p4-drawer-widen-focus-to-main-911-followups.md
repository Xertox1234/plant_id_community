---
status: pending
priority: p4
issue_id: "509"
tags: [web, a11y, testing]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Finding 9: keep focus:outline-none on <main> (programmatic landmark focus; a ring around the content area is noise); record the reason in the Work Log (2026-10-01)"
---

# Drawer widen focus-to-main: non-blocking findings from PR #911 (todo 488)

## Problem

PR #911 (todo 488) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`todos/archive/488-completed-p4-drawer-widen-close-followups.md:70`** (low, round 2). The Work Log embeds absolute worktree paths and .sweep-evidence references. These are ephemeral and will dangle once the worktree is removed.
   Suggested: Use repo-relative commands and drop or inline the evidence paths.

2. **`todos/archive/488-completed-p4-drawer-widen-close-followups.md:88`** (low, round 1). Work log entries dated 2026-09-30 cite run id 2026-10-01-0121, so the dates are inconsistent. The log also embeds local absolute worktree paths and `.sweep-evidence` refs that will not resolve after merge.
   Suggested: Optionally normalise the dates and use repo-relative commands.

3. **`web/src/layouts/AppShell.test.tsx:228`** (low, round 1). Test stub reads matches only for the md query and returns false for others. If another AppShell child later subscribes to the same query, the 'listeners.size toBe(1)' unmount test will become brittle.
   Suggested: Assert listener count returns to 0 after unmount and that it is greater than 0 while mounted, rather than exactly 1.

4. **`web/src/layouts/AppShell.test.tsx:290`** (low, round 1). The 'stays open when md changes to not matching' test fires false while md is already false, so useMediaQuery's setMatches(false) changes no state. It passes even if AppShell ignores drawerHidden entirely and only catches an inverted setMatches. The AC is met in letter only.
   Suggested: Make the test exercise a real transition: fire(true) then fire(false) on a non-drawer probe, or assert drawerHidden-driven behaviour. Otherwise add a comment that it guards only against an inverted event.matches in useMediaQuery.

5. **`web/src/layouts/AppShell.test.tsx:314`** (low, round 2). The unmount test asserts md.listeners.size toBe(1). That pins the exact subscriber count on the md query, so a second legitimate subscriber (another useMediaQuery on the same query) would fail it. The intent is only that unmount removes the listener.
   Suggested: Capture the size after render as `before`, assert `before > 0`, then assert it is 0 after unmount.

6. **`web/src/layouts/AppShell.tsx:157`** (low, round 1). The focus-to-main effect depends on a mutable ref (closedOnWidenRef) and on effect ordering against useModalFocus's cleanup. The 'focus on main' assertion is the only guard; a refactor of useModalFocus restore timing (e.g. rAF) would silently break it.
   Suggested: Keep the focus-on-main assertion in both the change-event and already-matches tests, and add a comment or test pinning that useModalFocus restores synchronously.

7. **`web/src/layouts/AppShell.tsx:181`** (low, round 2). Nothing tests the one-shot reset of closedOnWidenRef. If `closedOnWidenRef.current = false` is deleted, the suite stays green, and after one widen auto-close every later Escape or Close menu close sends focus to \<main> instead of the Open menu trigger.
   Suggested: Add a test with this sequence: stub md false, open the drawer, fire(true) (focus lands on main), fire(false), reopen, press Escape, then assert that Open menu has focus and main does not.

8. **`web/src/layouts/AppShell.tsx:182`** (low, round 1, round 2). mainRef.current?.focus() runs without preventScroll. \<main> is a tall element, so a browser's focus scroll-into-view can move the page when the drawer auto-closes on widen. The old fall-to-\<body> path never scrolled. Hypothesis, not verified: this depends on the engine and on where main sits in the viewport.
   Suggested: Use mainRef.current?.focus({ preventScroll: true }) so the auto-close moves focus without moving the page.
   Also reported: mainRef.current?.focus() is called without preventScroll. Body focus never scrolled, but focusing a tall \<main> that is only partly in view can scroll the page to main's edge. At scroll-top, main sits below the ~65px sticky header, so a widen-close may jump the page. Hypothesis from Chromium's focus-scroll rules, not reproduced.

9. **`web/src/layouts/AppShell.tsx:330`** (low, round 1, round 2). `<main tabIndex={-1} focus:outline-none>` hides the focus ring. A click on any non-focusable area inside main now focuses main with no indicator. Harmless for a programmatic target, but the removal is broader than the need.
   Suggested: Accept as is, or use `focus-visible:outline-none` so only mouse/programmatic focus is silent.
   Also reported: tabIndex={-1} makes \<main> click-focusable. A click on non-interactive content or on a disabled control inside main now focuses \<main> instead of \<body>. SettingsPage's refocus guards test activeElement === body or 'strayed', so their refocus is skipped after such a click while a save is in flight.
   Also reported: \<main> gets tabIndex={-1} with focus:outline-none. Click-focus and the programmatic focus draw no indicator. Acceptable for a programmatic-only target, but the outline is suppressed on every focus.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #911 review rounds 1-2.
