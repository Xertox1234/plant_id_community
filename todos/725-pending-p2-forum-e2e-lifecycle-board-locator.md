---
status: pending
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

- [ ] `forum-authenticated.spec.js` "create thread → reply → edit → react → delete" passes under
      `chromium-authenticated` and `firefox-authenticated`.
- [ ] The board locator is not tied to a heading level (role, accessible name or test id).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision ("Confirm; file the main
  failure"), while confirming todo 712's Playwright criterion (235 passed on the 712 tree).
