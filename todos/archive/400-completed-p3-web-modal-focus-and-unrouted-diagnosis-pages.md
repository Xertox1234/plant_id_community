---
status: completed
priority: p3
issue_id: "400"
tags: [web, accessibility, tech-debt, testing]
dependencies: []
---

# Remaining modals without useModalFocus, unrouted diagnosis pages, act() warnings

## Problem

These are leftovers noticed while shipping todo 396. None blocked it, and they
are independent of each other.

### 1. Three more modals hand-roll focus handling

Todo 396 added `web/src/hooks/useModalFocus.ts`, which provides:

- autofocus;
- Escape;
- a Tab/Shift+Tab trap that skips disabled controls;
- a restore target captured once per open.

It adopted the hook in `ConfirmDialog` and `ForumImagePicker` only. Still
hand-rolled:

- **`components/forum/EditHistoryDialog.tsx`.** Its docstring copies the
  ConfirmDialog pattern. Check whether its focus effect depends on an inline
  `onClose` and so has the same per-render re-capture bug todo 396 fixed.
- **`components/CommandPalette.tsx`** (around line 392). It has its own Tab
  wrap, whose selector `'a[href], button, input'` does not exclude disabled
  controls.
- **`layouts/AppShell.tsx`** (around line 213). The `aria-modal` drawer has no
  Tab handling at all.

Unverified: whether each one has the bug. Probe each one by mutation or a
browser keyboard check before changing it.

### 2. The diagnosis pages are not routed

None of these four is imported by `App.tsx` or by any routed page:

- `DiagnosisListPage.tsx`
- `DiagnosisDetailPage.tsx`
- `ReminderManager.tsx`
- `SaveDiagnosisModal.tsx`

They are reachable only from each other. Todo 396 added `focus:ring-2` to 13
inputs in them, which could not be checked in a browser for that reason. So
either wire them into the router or delete them. This is a product call.

### 3. `act()` warnings in `SettingsPage.test.tsx` (todo 396 finding 7)

The whole-page smoke tests mount `SettingsPage` without awaiting each section's
fetch. That produced 4 warnings before todo 374 and 6 after. Every dedicated
section test is clean. Await each section's settled state in the smoke tests.

## Acceptance Criteria

- [x] Each of the three modals either uses `useModalFocus` or has a stated
      reason not to, with a trap test that fails when the trap is removed:
      all three use it (2026-09-24). Neutralizing the hook's Tab branch gives
      "7 failed | 48 passed (55)": exactly the 7 new Tab tests across the
      three suites.
- [x] The diagnosis pages are either routed or deleted (decision recorded):
      deleted by the 2026-09-23 web dead-code audit (H1). Their backend was
      gone: migration `plant_identification/0025` ran `DeleteModel` on
      DiagnosisCard and DiagnosisReminder, and all 16 endpoints they called
      resolve to `wagtail_serve`. Routing them could not have worked.
- [x] `SettingsPage.test.tsx` runs with zero `act()` warnings. On
      2026-09-24, `grep -c "not wrapped in act"` gave 6 before and 0 after,
      with "Tests  42 passed (42)".

## Work Log

### 2026-09-23 - Filed from todo 396

None of these was in todo 396's acceptance criteria. Filed under the
review-loop budget rather than widening that PR.

### 2026-09-23 - Item 2 closed by the web dead-code audit

The route-or-delete question has a factual answer: **delete**. The
diagnosis-card and reminder backend was removed in November 2025 (migration
0025), so the pages called 16 dead endpoints. They were deleted along with
diagnosisService, the unused types, and their tests. See
`docs/audits/2026-09-23-web-dead-code.md` H1. Items 1 (modal focus) and 3
(act() warnings) remain open.

### 2026-09-24 - Items 1 and 3 done

**Item 1: all three modals now use `useModalFocus`.** The trap tests were
written first and run against the old code: 7 of 10 new tests failed.

- **EditHistoryDialog.** Two bugs, both confirmed:
  - It had no Tab trap at all.
  - Its focus effect was keyed on `[open, onClose]`. With an inline `onClose`,
    a parent re-render yanked focus to Close; the failing test got the Close
    button instead of the focused row. This is **latent** in production:
    `PostCard`, the only caller, passes a `useCallback`. The hook removes the
    dependency on callers memoizing.
- **CommandPalette.** The stated bug is **not live**. The palette renders only
  an `<input>` and router `<Link>`s, never a `disabled` control, so the
  `'a[href], button, input'` selector could not pick a disabled wrap target.
  Its Tab-wrap and restore tests passed against the old code. The real gap:
  the trap was a panel `onKeyDown`, so Tab with focus outside the panel
  escaped. Clicking a section label in Chrome does drop focus to `<body>`. The
  "focus on body" test failed before and passes now. Arrow/Enter navigation
  stays on the input's own handler, which does not stop propagation.
- **AppShell drawer.** It had no Tab trap, and focus fell to `<body>` on close,
  because the Close button unmounted and nothing restored focus. Both are
  confirmed and fixed. Route changes still close the drawer through each
  link's `onNavigate`, and the hook does not touch that.

Mutation checks (copy aside, mutate, run, restore from the copy):

- Deleting the `useModalFocus(...)` call fails 4/10 EditHistoryDialog tests,
  6/23 CommandPalette tests and 4/22 AppShell tests. Every trap test is among
  them.
- Neutralizing only the hook's Tab branch fails exactly the 7 Tab tests, and
  "7 failed | 48 passed (55)".

**Browser keyboard check** (Playwright against this worktree's Vite on :5174):

- **Drawer at 390px:**
  - opening focuses Close menu;
  - Tab x12 cycles Home through Log in, then the brand link, then Close menu,
    staying inside;
  - Shift+Tab wraps backward;
  - Escape returns focus to Open menu.
  - Cmd+K with the drawer open closes the drawer, puts focus in the palette
    input, and Escape then returns focus to Open menu.
- **Palette at 1280px:**
  - Tab x6 goes from the input through the 4 rows and back to the input;
  - Shift+Tab wraps;
  - ArrowDown sets `aria-activedescendant=qa-new-thread` with focus still in
    the input;
  - clicking the "Quick actions" label puts focus on BODY, and the next Tab
    goes to the input;
  - Escape returns focus to the search pill.
- **EditHistoryDialog:** real thread 74. The revision endpoints are stubbed
  via `page.route`, because the edited dev posts have no author.
  - Opening focuses Close;
  - Tab cycles row, row, Close, row;
  - Shift+Tab wraps;
  - Enter on a row shows the revision and keeps focus on it;
  - Escape returns focus to "Edited 3 days ago".

**Item 3: `SettingsPage.test.tsx` act() warnings went from 6 to 0.**

- All 6 came from one test, `renders no palette controls`, which asserted
  synchronously and returned before the five section fetches landed.
- The three theme-control tests now use `renderPageSettled()`, which awaits
  each section's settled state: blocked empty, muted empty, digest Frequency,
  a notification cell, and the images empty state.
- `grep -c "not wrapped in act"` went from 6 to 0, with 42/42 passing.

**Verification:**

- `npm run type-check`, `npm run lint` and `npm run check:classes` are clean
  (133 files, 5737 tokens).
- Prettier is clean on the changed files.
- Full vitest: 102 files, **1386 passed** (1376 + 10 new).

### 2026-09-24 - Completed by completing-todos skill (run 2026-09-24-0400)

- Verification: all 3 acceptance criteria are checked, with the evidence
  quoted above.
- Review: bundled `/code-review` (medium), 0 blocking findings. One
  non-blocking hypothesis, not reproduced: the drawer trap may swallow Tab
  after the window is widened past `md` with the drawer open. Filed as
  **todo 420**.
