---
status: completed
priority: p4
issue_id: "681"
tags: [forum, forum-categories, web, backend]
dependencies: ["669"]
triage: ready
triaged: 2026-11-01
blocked_on: "Theme variant list + relation to 669's colour field undecided; 669 must land first"
owner_decision: "Ship four themes (botanical, moss, terracotta, slate) as a token-scope override. 669's colour stays as an accent on top. (owner, 2026-10-30)"
---

# Forum categories slice 15: per-forum theme override

## Problem

phpBB can give one forum its own style. With a single Canopy design system this means a constrained accent/theme override, not arbitrary CSS.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB forum_style).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `theme` from a fixed list of Canopy-safe variants; web applies it as a token scope on the forum and thread pages.

## Technical Details

- `web/docs/patterns/tailwind.md`, Canopy tokens.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: only listed theme values are accepted.
- [x] Web Vitest: the forum page applies the theme scope; contrast checks pass in light and dark.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Ship four themes (botanical, moss, terracotta, slate) as a token-scope override. 669's colour stays as an accent on top.

### 2026-11-01 - Implemented by the todo sweep (run 2026-11-01-0035)

- `Forum.theme`, one of `botanical`, `moss`, `terracotta`, `slate` or blank (migration 0052, model choices, so `full_clean` and the admin *Display* tab refuse anything else); served on the forum rows of `/forum/categories/`.
- `web/src/index.css` defines each theme as a token scope (`[data-mode='light'|'dark'] [data-forum-theme='…']`) overriding the surface, ink and primary tokens with literal hex; the forum and thread pages set `data-forum-theme`. 669's accent colour stays on top, from the mode's own tokens.
- `web/src/utils/forumThemeContrast.test.ts` reads `index.css` and checks every theme in both modes: ink and ink-2 at least 4.5:1 on every surface, on-primary on primary 4.5:1, ink-3 and the four accents 3:1.

### 2026-11-01 - Verified by the todo sweep (run 2026-11-01-0035)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_theme.py --create-db` — evidence `.sweep-evidence/g1/681-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 11 passed, 3 warnings in 20.18s ========================
  ```

- AC 2: `cd web && npx vitest run src/utils/forumThemeContrast.test.ts src/pages/forum/ThreadListPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx` — evidence `.sweep-evidence/g1/681-ac1.txt` (not committed), last lines:

  ```text

   Test Files  3 passed (3)
        Tests  144 passed (144)
     Start at  19:52:41
     Duration  3.86s (transform 421ms, setup 180ms, import 1.78s, tests 3.20s, environment 779ms)
  ```

### 2026-11-01 - Completed by the todo sweep (run 2026-11-01-0035)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
