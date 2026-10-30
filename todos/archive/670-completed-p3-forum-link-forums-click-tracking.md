---
status: completed
priority: p3
issue_id: "670"
tags: [forum, forum-categories, backend, web]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 6: link forums with click tracking

## Problem

phpBB link forums are rows on the index that redirect to a URL, optionally counting clicks.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (FORUM_LINK; phpBB stores clicks in the post counter — use a dedicated field).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Add the `link` option to the todo-666 admin form. Fields: `link_url` (http/https only, validated), `track_clicks`, `click_count`.
2. Endpoint `/forum/links/{id}/go/` that increments atomically (`F()`) and 302s; untracked links render the URL directly with `rel="noopener nofollow"`.
3. Link forums never accept topics (API 400/404) and never appear as move targets.
4. Type changes involving `link`, moved here from todo 667 (owner decision 2026-10-29): forum→link requires its topics moved or deleted first (reuse 667's change-type form), category→link requires it has no forums, link→forum/category clears the URL.

## Technical Details

- New view in `api/views.py` or a host redirect view; web forum row component.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Test: tracked click increments once per request and redirects; `javascript:` and other schemes rejected at save.
- [x] Test: creating a topic in a link forum is refused.
- [x] Test: link forums never appear in `GET /forum/boards/` (Flutter would fetch `/topics/` on them).
- [x] Test: the admin form offers `link` and requires a valid URL for it.
- [x] Test: forum→link and category→link enforce 667's rules (no topics / no forums left) and link→forum/category clears the URL.
- [x] Web Vitest: link rows render as external links with a click count when tracked.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).

### 2026-10-29 - Link type changes moved here

- Owner decision during todo 667 triage: 667 builds forum↔category type changes only; every conversion to or from `link` lands here, with the URL field.

### 2026-10-30 - Implemented by the todo sweep (run 2026-10-30-0417)

- `Forum` gained `link_url` (http/https only: a scheme-restricted `URLValidator`, required for a link and cleared for any other type in `Forum.clean`), `track_clicks` and `click_count` (migration `0046_forum_links_reads_collapsed`, shared with todos 671 and 673).
- `GET /forum/links/{id}/go/` (`api/forum_rows.py`) 302s to a visible link, incrementing `click_count` with one `F()` UPDATE when tracked; never cached, throttled per IP host-side (`link_go`, 60/m, bounding count inflation), and it re-checks the stored scheme so a row written around validation never redirects to `javascript:`.
- The admin offers `link`; "Change type" now covers all six conversions (`services/forum_structure.change_type`): forum→link reuses the move-or-delete topics choice, category→link is refused while it holds forums, link→forum/category clears the URL and click count.
- `/forum/categories/` lists each category's links under `links` (one prefetch with its forums, so still two queries); `/forum/boards/` stays forums only. A link with no URL is left out. Web: `ForumLinkCard` renders an external `rel="noopener noreferrer nofollow"` link, through the redirect with a click count when tracked.
- Changed existing tests for the behaviour change: `test_forum_admin.py` (create choices now include link; the "rejects a link type" test became "refuses a link without its URL") and `test_admin_forum_change_type.py` (`test_a_link_cannot_change_type_yet` became `test_a_link_can_change_type`).

### 2026-10-30 - Verified by the todo sweep (run 2026-10-30-0417)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_link_rows.py -k "tracked_click or untracked_link or redirect_404s or rejected_at_save or http_and_https or javascript_url" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/670-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 10 passed, 16 deselected, 3 warnings in 20.01s ================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_link_rows.py -k "topic_in_a_link_forum or never_a_topic_move_target" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/670-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 2 passed, 24 deselected, 3 warnings in 19.43s =================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_link_rows.py packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py -k "never_appear_in_the_board_list or listed_under_their_category or board_list_keeps_its_keys" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/670-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 3 passed, 35 deselected, 3 warnings in 19.98s =================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_link_rows.py packages/wagtail_forum/wagtail_forum/tests/test_forum_admin.py -k "offers_the_link_type or requires_a_url_for_a_link or creates_a_link_with_a_valid_url or javascript_url or refuses_a_link_without_its_url" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/670-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 5 passed, 42 deselected, 3 warnings in 19.82s =================
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 4 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_link_rows.py packages/wagtail_forum/wagtail_forum/tests/test_admin_forum_change_type.py -k "become_a_link or becomes_a_link or becoming_a_link or changing_type_clears or category_with_forums_cannot_become or link_can_change_type or offers_change_type" --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g2/670-ac4.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ================ 10 passed, 36 deselected, 3 warnings in 19.73s ================
  ```

- AC 6: `cd web && npx vitest run src/components/forum/ForumCard.test.tsx -t "ForumLinkCard"` — evidence `.sweep-evidence/g2/670-ac5.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  4 passed | 12 skipped (16)
     Start at  04:48:35
     Duration  1.40s (transform 49ms, setup 111ms, import 639ms, tests 68ms, environment 509ms)
  ```

### 2026-10-30 - Completed by the todo sweep (run 2026-10-30-0417)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-30 - Review round 1: non-blocking findings

- **Fixed (regression):** a link saved without a URL before this slice could not be moved in the structure tree, because `move_forum` ran the whole `Forum.clean` and its "a link needs a URL" rule. `move_forum` now checks only the parent rules (`Forum._clean_parent`). Test `test_a_link_saved_without_a_url_can_still_be_moved`, mutation-checked (with `forum.clean()` back, it fails).
- **Fixed:** the host throttle wrappers had no host-level test. Added `apps/forum_host/tests/test_forum_row_throttles.py`: the link redirect returns 429 on its second request per IP and stops counting clicks, and each read-mark and collapse scope returns 429 at its limit.
- **Declined:** link prefetchers and crawlers can inflate `click_count` (two reviewers). Counts are approximate by design, and the per-IP `link_go` limit (60/m) bounds one client.
- **Declined:** no test for a category holding only links, or for URL-less links being dropped from `/categories/`. Low; the listing rules are covered by `test_links_are_listed_under_their_category_with_a_click_count_when_tracked` and the view's own exclude.
