---
status: pending
priority: p4
issue_id: "488"
tags: [web, react, accessibility]
dependencies: []
source_review: "PR #881"
---

# Drawer close on widen: non-blocking findings from PR #881 (todos 420, 470)

## Problem

PR #881 closes the mobile drawer when the viewport crosses md. Both review rounds were clean. The
kimi gate raised finding 2 as a WARNING, and the reviewers rated it low.

## Findings

1. **Focus drops to `<body>` after the auto-close.** `useModalFocus` restores focus to the
   "Open menu" trigger, which is `md:hidden` at that width, so `focus()` does nothing. Tab still
   moves on normally, but a keyboard user lands at the top of the document
   (`AppShell.tsx:154-163`).
2. **A query that already matches is ignored.** The effect reacts only to `change` events. If md
   already matches when it subscribes, the drawer stays open. The existing `useMediaQuery` hook
   handles that case and would replace the hand-rolled subscription (`AppShell.tsx:159`).
3. **The test pins only half the behaviour.** It fires only `matches: true`. Dropping the
   `event.matches` guard, or the cleanup's `removeEventListener`, leaves the suite green. The
   stub already counts listeners (`AppShell.test.tsx:254`).
4. **The media query tracks its constant.** The test imports `DRAWER_HIDDEN_MEDIA_QUERY`, so
   changing the breakpoint stays green. Pin `'(min-width: 48rem)'`.

## Acceptance Criteria

- [ ] After an auto-close, focus lands on a visible target, or a comment records why `<body>` is
      accepted.
- [ ] A drawer that is open while md already matches closes, with a test.
- [ ] The test covers `matches: false` (the drawer stays open) and listener removal.
- [ ] The md query literal is pinned.

## Work Log

### 2026-09-28 - Filed from PR #881 rounds 1 and 2 (todo sweep run 2026-09-28-2018)
