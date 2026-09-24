---
status: pending
priority: p4
issue_id: "420"
tags: [web, accessibility]
dependencies: []
---

# Drawer focus trap may swallow Tab after the window is widened past `md`

## Problem

Todo 400 moved the AppShell mobile drawer onto `useModalFocus`. The drawer is
hidden on wide screens only by CSS (`md:hidden`), and `drawerOpen` is never
reset by a resize.

**Hypothesis, not verified** (it came from the todo 400 code review and has not
been reproduced):

1. Open the drawer on a narrow window.
2. Widen the window past the `md` breakpoint.
3. The drawer is now `display: none`, but the hook is still active. Tab is
   `preventDefault`ed, and the wrap target `.focus()`es an element that isn't
   displayed, which is a no-op. So Tab does nothing until the user presses
   Escape.

Before todo 400 there was no trap, so Tab moved through the page, although the
scroll lock stayed on. The case is rare: a narrow-to-wide resize with the
drawer open.

## Acceptance Criteria

- [ ] Reproduce in a browser: open the drawer at 390px, resize to 1280px, then
      press Tab. Record what happens.
- [ ] If it reproduces, close the drawer when the `md` media query starts
      matching (for example, a `matchMedia` listener in AppShell). Add a test
      that fails without it.

## Work Log

### 2026-09-24 - Filed from todo 400 review (non-blocking)
