---
status: completed
priority: p2
issue_id: "725"
tags: [web, forum, e2e, testing]
dependencies: []
triage: ready
triaged: 2026-11-22
---

# Forum e2e write-lifecycle test can't find a board on the forum index

## Problem

`web/e2e/forum-authenticated.spec.js:39` ("create thread → reply → edit → react → delete") fails
on origin/main in both `chromium-authenticated` and `firefox-authenticated`. Its first step finds
no forum board link on `/forum`, so the forum's one end-to-end write test covers nothing.

## Findings

- Measured 2026-11-21 on origin/main 5ce82c65 (clean g1 sweep worktree, dev DB seeded with
  `create_test_user` and `seed_default_forum`): 2 failed, 52 passed for
  `e2e/forum-responsive.spec.ts e2e/forum-authenticated.spec.js`. The same failure appeared on the
  todo 711/712 tree, so it is not caused by those bumps.
- Error: `no forum board found — run: manage.py seed_default_forum`. The locator is
  `a[href^="/forum/"]` filtered to links containing an `h3` (spec lines 45–57), on the
  assumption that "a board CategoryCard link wraps an `<h3>`".
- Hypothesis, not verified: the forum index was rebuilt (forums as plain models with category
  headers, #1216 to #1241), and its forum rows no longer render a link wrapping an `h3`, so the
  locator matches nothing even though forums exist.

## Recommended Action

Read what the forum index renders for a forum row now. Point the locator at that, using a
role or test id, not a heading level. Then run the spec under both authenticated projects.

## Technical Details

- Spec: `web/e2e/forum-authenticated.spec.js`. Forum index: `web/src/pages/forum/`.
- Running Playwright from a worktree needs the venv and node_modules linked in, and
  `PYTHONPATH=<worktree>/backend/packages/wagtail_forum` so the worktree's forum package loads.
  Stop anything on :5174 and :8000 first: `reuseExistingServer` would otherwise test the wrong tree.

## Acceptance Criteria

- [x] `forum-authenticated.spec.js` "create thread → reply → edit → react → delete" passes under
      `chromium-authenticated` and `firefox-authenticated`.
- [x] The board locator is not tied to a heading level (role, accessible name or test id).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision ("Confirm; file the main
  failure"), while confirming todo 712's Playwright criterion (235 passed on the 712 tree).

### 2026-11-22 - Implemented by the todo sweep (run 2026-11-22-1957)

- Cause confirmed: `CategoryListPage.tsx` renders a forum under a category header with
  `headingLevel="h4"` (todo 665), so the spec's `a[href^="/forum/"]` filtered on a wrapped `h3`
  matched nothing.
- `ForumCard`'s row link now carries `data-testid="forum-board-link"`; the spec finds the first
  board with `getByTestId('forum-board-link')`, independent of the heading level.
- The rest of the lifecycle (new thread, reply, edit, react, delete) passed unchanged against the
  current UI: 4 passed (two setups, chromium-authenticated, firefox-authenticated).
- Browsers for Playwright 1.65.0 were missing from the laptop cache; they were installed under
  `/Volumes/U34Bolt/plant_id_community/tmp/ms-playwright` and the run points `PLAYWRIGHT_BROWSERS_PATH` there.

### 2026-11-22 - Verified by the todo sweep (run 2026-11-22-1957)

- AC 1: `/usr/bin/env PYTHONPATH=backend/packages/wagtail_forum PLAYWRIGHT_BROWSERS_PATH=/Volumes/U34Bolt/plant_id_community/tmp/ms-playwright web/node_modules/.bin/playwright test -c web/playwright.config.ts forum-authenticated.spec.js --project=chromium-authenticated --project=firefox-authenticated --reporter=list` — evidence `.sweep-evidence/g1/725-ac0.txt` (not committed), last lines:

  ```text
  [WebServer] INFO "POST /api/v1/forum/posts/152/reactions/ HTTP/1.1" 200 45
  [WebServer] INFO "DELETE /api/v1/forum/posts/152/ HTTP/1.1" 204 0
    ✓  4 [firefox-authenticated] › .claude/worktrees/sweep-2026-11-22-1957-g1/web/e2e/forum-authenticated.spec.js:39:3 › Authenticated forum write lifecycle › create thread → reply → edit → react → delete (6.1s)

    4 passed (15.5s)
  ```

- AC 2: `grep -n "forum-board-link\|locator('h3')\|has: page.locator" web/e2e/forum-authenticated.spec.js web/src/components/forum/ForumCard.tsx` — evidence `.sweep-evidence/g1/725-ac1.txt` (not committed), last lines:

  ```text
  web/e2e/forum-authenticated.spec.js:47:    // link carries data-testid="forum-board-link" (todo 725). It used to filter
  web/e2e/forum-authenticated.spec.js:52:    const boardLink = page.getByTestId('forum-board-link').first();
  web/src/components/forum/ForumCard.tsx:42:        data-testid="forum-board-link"
  ```

### 2026-11-22 - Completed by the todo sweep (run 2026-11-22-1957)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-22 - Review round 1: non-blocking findings

- **Fixed: no unit test pinned `data-testid="forum-board-link"` (low).** Added a
  `ForumCard.test.tsx` case asserting the board link carries the id and its href. Mutation check:
  with the attribute deleted from `ForumCard.tsx` the case fails (1 failed, 20 passed); restored,
  21 passed.

### 2026-11-22 - Review round 2: non-blocking findings

- **Declined: `.first()` could pick a card in a collapsed category (low, two reviewers).** The
  e2e user never collapses a section, and the pre-725 locator had the same `.first()` shape. If
  it ever flakes, the fix is `.filter({ visible: true })`.
- **Declined: the spec's header comment undercounts the forum's test ids (low).** Comment only;
  it names the ids this spec uses.
