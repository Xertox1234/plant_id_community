---
status: completed
priority: p3
issue_id: "669"
tags: [forum, forum-categories, backend, web, wagtail]
dependencies: ["666"]
triage: ready
triaged: 2026-11-01
blocked_on: "An owner choice on the rules format (plain text, limited rich text, rules_url, or text plus link like phpBB) and the icon format (emoji or a named icon)"
owner_decision: "Rules: plain text plus an optional rules URL (phpBB style). Icon: a single emoji. Colour: chosen from the existing Canopy accent tokens (dark-mode safe). (owner, 2026-10-30) Forum image: add it now as an optional wagtailimages.Image FK with on_delete=SET_NULL, chosen in the Wagtail admin and shown on the forum index. (owner, 2026-10-31)"
---

# Forum categories slice 5: per-forum display settings (locked, rules, icon/colour/image, topics per page, default sort)

## Problem

phpBB forums carry status and display settings; Discourse adds colour/icon and a default sort. None exist per board today.

## Findings

- Field list: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB *Forum settings*, Discourse colour/icon/default sort/read-only banner).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Fields: `is_locked` (no new topics or replies; staff exempt), `rules` (plain/limited rich text) or `rules_url`, `icon`, `colour` (validated against Canopy-safe tokens), optional image, `topics_per_page` (0 = default), `default_sort` (one of the existing `?sort=` values).
2. Admin: a *Display* and *Rules* tab.
3. API: expose the fields; enforce locked on topic/post create (403 with a clear code).
4. Web: colour/icon on category headers and forum rows, rules panel on the forum page, locked badge + disabled composer, page size and default sort honoured.

## Technical Details

- `api/views.py` create paths, `api/pagination.py` (default sort), web `CategoryListPage.tsx`, `ThreadListPage.tsx`, `NewThreadPage.tsx`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: posting to a locked forum returns 403 for members and succeeds for staff.
- [x] Test: `topics_per_page` and `default_sort` change the topic list response.
- [x] Test: invalid colour values are rejected.
- [x] Web Vitest: rules panel, locked state, colour/icon rendered.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Rules: plain text plus an optional rules URL (phpBB style). Icon: a single emoji. Colour: chosen from the existing Canopy accent tokens (dark-mode safe).

### 2026-10-31 - owner decision

- Owner answered the re-triage question: add the optional forum image now (wagtailimages FK, SET_NULL).

### 2026-11-01 - Implemented by the todo sweep (run 2026-11-01-0035)

- `Forum` gains `is_closed`, `rules`, `rules_url`, `icon`, `colour`, `image`, `topics_per_page`, `default_sort` (migration 0050, a `db_default` on each column for the deploy window). The status field is `is_closed`, not `is_locked`: the API's `is_locked` already means a password forum this session has not unlocked (todo 680), and the name mirrors `Topic.is_closed`.
- A closed forum refuses new topics and replies with 403 `forum_closed`; staff and the forum's own moderators are exempt. `topics_per_page` (0 = default, at most 100) and `default_sort` (one of the `?sort=` values) are applied by `TopicCursorPagination`; an explicit `?sort=`/`?page_size=` still wins.
- Owner decisions: rules are plain text plus an optional http(s) link; the icon is one emoji (`validate_forum_icon`, a structural check since Python `re` has no grapheme class); the colour is one of the Canopy accents `sage`/`pollen`/`bloom`/`orchid`; the image is an optional Wagtail image (`SET_NULL`), served as the original file URL (`image_url`) so no rendition is written on a read path.
- Admin: new *Display* and *Rules* tabs. Web: accent and emoji on category headers and forum rows, the image on the index, a rules panel and a Closed badge on the forum page, no composer link in a closed forum; with no `?order=` the page sends no sort, so the forum's default applies (two ThreadListPage assertions now expect `sort: undefined`).

### 2026-11-01 - Verified by the todo sweep (run 2026-11-01-0035)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_display_settings.py::test_posting_to_a_closed_forum_is_403_for_members_and_allowed_for_staff --create-db` — evidence `.sweep-evidence/g1/669-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 3 warnings in 21.57s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_display_settings.py::test_topics_per_page_and_default_sort_change_the_topic_list packages/wagtail_forum/wagtail_forum/tests/test_forum_display_settings.py::test_default_sort_choices_match_the_topic_list_sorts --create-db` — evidence `.sweep-evidence/g1/669-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 20.37s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_display_settings.py::test_invalid_colour_values_are_rejected packages/wagtail_forum/wagtail_forum/tests/test_forum_display_settings.py::test_canopy_accent_colours_are_accepted --create-db` — evidence `.sweep-evidence/g1/669-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 9 passed, 2 warnings in 19.82s ========================
  ```

- AC 4: `cd web && npx vitest run src/pages/forum/ThreadListPage.test.tsx src/pages/forum/CategoryListPage.test.tsx` — evidence `.sweep-evidence/g1/669-ac3.txt` (not committed), last lines:

  ```text

   Test Files  2 passed (2)
        Tests  84 passed (84)
     Start at  19:52:38
     Duration  1.75s (transform 278ms, setup 122ms, import 1.52s, tests 1.23s, environment 499ms)
  ```

### 2026-11-01 - Completed by the todo sweep (run 2026-11-01-0035)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-01 - Review round 1: non-blocking findings

Round 1 (PR #1232) was clean, with no blocking findings. Each non-blocking finding is fixed by hand with a test, or declined with a reason:

- **Fixed** (medium) `web/src/components/forum/ForumCard.tsx`: the forum image `src` did not go through `mediaUrl()`, so a local `/media/` URL resolved against the Vite origin. Test: `ForumCard.test.tsx` "serves the forum image from the API media origin", mutation-checked. `CategoryListPage.test.tsx` auto-mocks blogService, so its `beforeEach` now passes `mediaUrl` through.
- **Fixed** (low) `validate_forum_icon` accepted a lone skin-tone modifier and a keycap without VS16. Both are rejected now, and so is a trailing joiner. Three new parametrized cases; 2 fail against the old validator, and a trailing joiner was already rejected.
- **Declined** (low) `rules_url` scheme on the web: it is a model `URLField`, set only in the Wagtail admin form, whose validator allows only http, https, ftp and ftps. A `javascript:` URL cannot be stored.
