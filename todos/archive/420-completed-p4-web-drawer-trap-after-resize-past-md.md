---
status: completed
priority: p4
issue_id: "420"
tags: [web, accessibility]
dependencies: []
triage: ready
triaged: 2026-09-28
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

- [x] Reproduce in a browser: open the drawer at 390px, resize to 1280px, then
      press Tab. Record what happens.
- [x] If it reproduces, close the drawer when the `md` media query starts
      matching (for example, a `matchMedia` listener in AppShell). Add a test
      that fails without it.

## Work Log

### 2026-09-24 - Filed from todo 400 review (non-blocking)

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Reproduced in headless Chrome (`.sweep-evidence/g9/420-repro.mjs`): open the
  drawer at 390px, resize to 1280px. The drawer stays in the DOM but is not
  rendered, focus falls to `<body>`, and three Tabs leave focus on `<body>`.
  The hypothesis holds. The body scroll lock (`overflow: hidden`) also stays on.
- Fix: AppShell subscribes to `DRAWER_HIDDEN_MEDIA_QUERY` (`(min-width: 48rem)`,
  Tailwind's `md`) while the drawer is open, and closes it on a `change` to
  matching. Closing releases the trap and the scroll lock.
- New AppShell test stubs `matchMedia`, fires the md transition, and asserts
  the dialog is gone and `overflow` is cleared. It failed before the listener
  existed (1 failed, 22 passed) and passes with it.
- The same browser run after the fix: the drawer leaves the DOM on the resize,
  the scroll lock is released, and Tab moves Search, New post, theme toggle.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `node .sweep-evidence/g9/420-repro.mjs` — evidence `.sweep-evidence/g9/420-ac0.txt`, last lines:

  ```text
      {"activeElement":"<body>","activeElementVisible":"n/a","activeElementInsideDrawer":false,"drawerInDom":true,"drawerRendered":false,"bodyOverflow":"hidden"}
  3.3 press Tab
      {"activeElement":"<body>","activeElementVisible":"n/a","activeElementInsideDrawer":false,"drawerInDom":true,"drawerRendered":false,"bodyOverflow":"hidden"}

  RESULT: after widening past md with the drawer open, Tab DOES NOT move focus (trap swallows Tab); drawer in DOM: true; body overflow: hidden
  ```

- AC 2: `cd web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx` — evidence `.sweep-evidence/g9/420-ac1.txt`, last lines:

  ```text

   Test Files  1 passed (1)
        Tests  23 passed (23)
     Start at  16:16:24
     Duration  1.28s (transform 56ms, setup 101ms, import 140ms, tests 482ms, environment 480ms)
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
