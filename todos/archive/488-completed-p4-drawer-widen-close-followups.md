---
status: completed
priority: p4
issue_id: "488"
tags: [web, react, accessibility]
dependencies: []
source_review: "PR #881"
triage: ready
triaged: 2026-09-30
owner_decision: "On auto-close, move focus to <main> (tabIndex -1), not <body> (2026-09-30)"
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

- [x] After an auto-close, focus lands on a visible target, or a comment records why `<body>` is
      accepted.
- [x] A drawer that is open while md already matches closes, with a test.
- [x] The test covers `matches: false` (the drawer stays open) and listener removal.
- [x] The md query literal is pinned.

## Work Log

### 2026-09-28 - Filed from PR #881 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- `AppShell` now tracks md with the shared `useMediaQuery` hook instead of a change-only
  subscription made while the drawer is open, so a drawer open while md already matches closes
  too (finding 2).
- After that auto-close, focus moves to `<main id="main-content">` (now `tabIndex={-1}`, per the
  owner decision), in an effect that runs after `useModalFocus` restores focus to the md:hidden
  trigger. Escape and the other closes still return focus to Open menu (finding 1).
- The tests stub the md query as the literal `'(min-width: 48rem)'`, and the constant is no longer
  exported (finding 4). New tests cover `matches: false`, an open while md already matches, and
  listener removal on unmount (finding 3). The existing widen test gained a focus-on-main assertion.
- Probed: the new tests fail 3 of 26 against the old `AppShell`, and dropping
  `removeEventListener` from `useMediaQuery` fails the unmount test.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-2/web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx -t "widens past md|already matches|back to Open menu on Escape"` — evidence `.sweep-evidence/g8/488-ac0.txt`, last lines:

  ```text

   Test Files  1 passed (1)
        Tests  3 passed | 23 skipped (26)
     Start at  21:41:29
     Duration  608ms (transform 55ms, setup 53ms, import 119ms, tests 134ms, environment 240ms)
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-2/web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx -t "already matches"` — evidence `.sweep-evidence/g8/488-ac1.txt`, last lines:

  ```text

   Test Files  1 passed (1)
        Tests  1 passed | 25 skipped (26)
     Start at  21:41:36
     Duration  556ms (transform 54ms, setup 53ms, import 117ms, tests 82ms, environment 237ms)
  ```

- AC 3: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-2/web && ./node_modules/.bin/vitest run src/layouts/AppShell.test.tsx -t "not matching|listener on unmount"` — evidence `.sweep-evidence/g8/488-ac2.txt`, last lines:

  ```text

   Test Files  1 passed (1)
        Tests  2 passed | 24 skipped (26)
     Start at  21:41:37
     Duration  559ms (transform 55ms, setup 53ms, import 118ms, tests 86ms, environment 238ms)
  ```

- AC 4: `grep -nE "48rem|DRAWER_HIDDEN_MEDIA_QUERY|from './AppShell'" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-2/web/src/layouts/AppShell.test.tsx` — evidence `.sweep-evidence/g8/488-ac3.txt`, last lines:

  ```text
  6:import AppShell from './AppShell';
  230:  const MD_QUERY = '(min-width: 48rem)';
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
