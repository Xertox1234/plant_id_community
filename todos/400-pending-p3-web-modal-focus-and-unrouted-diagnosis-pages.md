---
status: pending
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

- [ ] Each of the three modals either uses `useModalFocus` or has a stated
      reason not to, with a trap test that fails when the trap is removed
- [ ] The diagnosis pages are either routed or deleted (decision recorded)
- [ ] `SettingsPage.test.tsx` runs with zero `act()` warnings

## Work Log

### 2026-09-23 - Filed from todo 396

None of these was in todo 396's acceptance criteria. Filed under the
review-loop budget rather than widening that PR.
