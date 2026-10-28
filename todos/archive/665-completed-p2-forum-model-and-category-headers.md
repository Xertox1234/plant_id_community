---
status: completed
priority: p2
issue_id: "665"
tags: [forum, forum-categories, backend, web, migration]
dependencies: []
triage: ready
triaged: 2026-10-28
owner_decision: "Web: rename the board types to Forum/ForumCard and use Category for real categories; sitemap lists forum_type=forum rows only from the Forum model (2026-10-28)"
---

# Forum categories slice 1: Forum model, migration off Wagtail pages, category headers on the web index

## Problem

Boards are Wagtail pages (`ForumBoard`) with no way to group them, so the forum index is one flat grid. This slice replaces them with a forum-specific `Forum` model (types category/forum/link, category parent, position) and renders category headers on the web index. Every later forum-categories slice builds on it.

## Findings

- Design + owner decisions: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §1, §3, §4.
- `ForumBoard(Page)` with `subpage_types = []` — `backend/packages/wagtail_forum/wagtail_forum/models/boards.py:85-99`.
- `Topic.board` FK is `on_delete=CASCADE` — `models/topics.py:23-25`.
- Visibility = `ForumBoard.objects.live().public()` — `api/views.py:134-141`; slug lookup 409s on ambiguity — `api/views.py:180-194`.
- 11 non-test files reference `ForumBoard` (spec §3 lists them); 94 test files do.
- Flutter consumes `GET /forum/boards/` and `/forum/boards/{slug}/topics/` — `plant_community_mobile/lib/features/forum/services/forum_api.dart:412,429`.
- Topic URLs embed the board id — `models/topics.py:220-222`.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Add `Forum` model (spec §4): `forum_type`, `parent` (self FK, null), `position`, `name`, `slug` (unique forum-wide among forums and links via a partial constraint excluding categories — spec §4), `description`, the existing counters, interim `is_hidden`. Model validation: categories have no parent; forums/links must have a category parent; only categories may be parents.
2. Data migration: create category "General"; copy each `ForumBoard` into `Forum` **keeping its id**; set `is_hidden=True` for any board that was non-live or carried a `PageViewRestriction`; reset the id sequence; repoint `Topic.board` (and any other FK) at `Forum`, switching to `on_delete=PROTECT` — **keep the field name `board` and `related_name="topics"`**; in a `RunPython` placed **before** `RemoveModel(ForumBoard)`, delete the boards through the historical `ForumBoard` model (removes the `wagtailcore_page` base rows) and recompute `ForumIndex.numchild`; set `ForumIndex.subpage_types = []` and move `ForumIndex.get_context` (H17 fallback) off `get_children()`.
3. Replace `_visible_boards()` with a `Forum`-based equivalent (`forum_type=forum`, not hidden); keep `/forum/boards/` and `/forum/boards/{slug}/topics/` response shapes byte-compatible for Flutter, listing only `forum_type="forum"` rows; add a new additive endpoint (or field) that returns categories with their forums, category rows summing their visible forums' counts and newest last post at read time.
4. Update the touch list: seed commands (`seed_default_forum` must create a category + forum), `redirects.py` (board rename redirects no longer come from `page_slug_changed`), `sitemaps.py` (decide: list forums from the new model), `apps/users/views.py`, serializers, signals.
5. Add a shared test factory (e.g. `make_forum(category=..., ...)`) and migrate the 94 test files to it mechanically (one script, verify once).
6. Web naming: `web/src` already calls boards "categories" (`fetchCategories`, `Category`, `CategoryListPage`, `CategoryCard`) — pick a distinct name for real categories (or rename the board types to `Forum`) and record the choice in the Work Log. Then `CategoryListPage.tsx` renders a header per category with its forums under it; breadcrumbs show Category › Forum on the thread list and thread pages.

## Technical Details

- Forum package: `backend/packages/wagtail_forum/wagtail_forum/models/boards.py`, `api/views.py`, `api/serializers.py`, `signals.py`.
- Host: `backend/apps/forum_host/{redirects.py,sitemaps.py,management/commands/seed_default_forum.py,management/commands/seed_demo_content.py}`, `backend/apps/users/views.py`.
- Web: `web/src/pages/forum/CategoryListPage.tsx`, `web/src/services/forumService.ts`, `ThreadListPage.tsx`, `ThreadDetailPage.tsx`.
- Pattern docs: `backend/docs/patterns/domain/forum.md`, `domain/wagtail.md`, `performance/query-optimization.md`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [x] Migration test: boards become forums with **identical ids** under one "General" category; a non-live or view-restricted board becomes `is_hidden=True`; no `ForumBoard` page rows remain.
- [x] Migration test: a board whose slug equals the default category's slug (`general`) migrates without a constraint error.
- [x] `manage.py fixtree --noinput` reports no problems after the migration, and the Wagtail page explorer lists no orphan ForumBoard pages.
- [x] Test: an existing topic URL `/forum/{board.id}-{slug}/{topic.id}-{slug}` still resolves after migration.
- [x] Test: `GET /forum/boards/` and `/forum/boards/{slug}/topics/` responses keep their previous keys and list only forums — never categories or links (Flutter contract).
- [x] Test: the new categories endpoint returns categories in `position` order with forums nested, counts aggregated, hidden forums excluded, categories with zero visible forums omitted, and a fixed query count.
- [x] Test: deleting a forum that has topics raises `ProtectedError` (no cascade).
- [x] Test: model validation rejects a category with a parent, a forum without a category, and a forum as a parent.
- [x] Test: forum slugs are unique forum-wide (DB constraint).
- [x] `seed_default_forum` creates a category and a forum, idempotently.
- [x] Web Vitest: the index renders one header per category with its forums beneath; breadcrumbs show the category.
- [x] Full backend pytest, `manage.py spectacular --validate --fail-on-warn`, mypy gate and web `tsc`/Vitest pass.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).

### 2026-10-28 - Implemented by the todo sweep (run 2026-10-28-1737)

- Boards are a plain `Forum` model (category / forum / link, `parent`, `position`, interim `is_hidden`); slugs are unique forum-wide for forums and links, per-category for categories. `Topic.board` keeps its name and now points at `Forum` with `PROTECT`. Four migrations (0041 create + copy with the page ids, 0042 repoint, 0043 delete the board pages and their revisions and fix `numchild`, 0044 drop the table), split so no DDL runs after pending deferred-FK triggers.
- `_visible_boards()` is the one visibility rule (forum rows, not hidden, category not hidden); `/forum/boards/` keeps its keys (`title` now reads `name`) and lists forums only; new `GET /forum/categories/` returns categories with nested forums, read-time sums, empty categories omitted, two queries. Board-rename redirects moved from `page_slug_changed` to `pre_save`/`post_save` on `Forum`. Dropping `.public()` removed one query from every pinned count that went through it, so those pins went down by one with a comment each.
- Tests build boards with `make_forum()` / `hide_forum()` in `wagtail_forum/tests/factories.py` (one script rewrote 156 call sites in 91 files). Tests of removed behaviour were replaced: the 409 slug-ambiguity test (now a DB constraint), board page serving and its userbar case, the admin publish-path rename (no revisions now), the board-page link in the intro test.
- Web naming (owner decision): the board types are now `Forum` / `ForumCard` / `fetchForums` / `fetchForum`, and `Category` / `fetchCategories` mean real categories. `CategoryListPage` renders one header per category with its forums beneath (flat list if the categories fetch fails); the thread list and thread pages show Forum / Category / board breadcrumbs through `useForumCategory`.
- `apps/core/tests/test_env_example_placeholders.py` (2 tests) fails in a worktree: its clean-environment subprocess drops `PYTHONPATH` and imports the main checkout's `wagtail_forum`, which has no `Forum` yet. CI installs the package from the checkout, so it should pass there; the full-suite evidence deselects those two. On the verifier retry both were run by hand with only `PYTHONPATH=backend/packages/wagtail_forum` added to the subprocess environment, and both passed: the failure is the worktree's import path, not this change.

### 2026-10-28 - Verified by the todo sweep (run 2026-10-28-1737)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_model_migration.py::test_boards_become_forums_with_their_ids_and_leave_no_pages` — evidence `.sweep-evidence/g1/665-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 20.21s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_model_migration.py::test_boards_become_forums_with_their_ids_and_leave_no_pages` — evidence `.sweep-evidence/g1/665-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 19.77s ========================
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_model_migration.py::test_boards_become_forums_with_their_ids_and_leave_no_pages` — evidence `.sweep-evidence/g1/665-ac2.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 19.71s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_model_migration.py::test_boards_become_forums_with_their_ids_and_leave_no_pages packages/wagtail_forum/wagtail_forum/tests/test_forum_model_migration.py::test_a_topic_url_resolves_through_the_api_after_the_move` — evidence `.sweep-evidence/g1/665-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 20.21s ========================
  ```

- AC 5: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_board_list_keeps_its_keys_and_lists_only_forums packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_board_topics_keep_their_keys_and_never_resolve_a_category_or_link` — evidence `.sweep-evidence/g1/665-ac4.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 3 warnings in 19.19s ========================
  ```

- AC 6: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_categories_nest_visible_forums_in_position_order_with_summed_counts packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_a_category_with_no_visible_forum_is_omitted packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_a_hidden_category_hides_its_forums_everywhere packages/wagtail_forum/wagtail_forum/tests/test_forum_categories_api.py::test_categories_query_count_is_flat` — evidence `.sweep-evidence/g1/665-ac5.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 4 passed, 3 warnings in 19.10s ========================
  ```

- AC 7: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_deleting_a_forum_with_topics_is_protected` — evidence `.sweep-evidence/g1/665-ac6.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 1 passed, 2 warnings in 19.09s ========================
  ```

- AC 8: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_validation_rejects_a_category_with_a_parent packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_validation_rejects_a_forum_without_a_category packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_validation_rejects_a_forum_as_a_parent` — evidence `.sweep-evidence/g1/665-ac7.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 2 warnings in 19.15s ========================
  ```

- AC 9: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_forum_slugs_are_unique_forum_wide packages/wagtail_forum/wagtail_forum/tests/test_boards.py::test_category_slugs_share_a_namespace_only_with_categories` — evidence `.sweep-evidence/g1/665-ac8.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 2 passed, 2 warnings in 19.01s ========================
  ```

- AC 10: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -p no:cacheprovider --create-db -o addopts=-v apps/forum_host/tests/test_seed_command.py` — evidence `.sweep-evidence/g1/665-ac9.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: aiohttp (pinned 3.14.4, installed 3.14.3), brotli (pinned 1.2.1, installed 1.2.0), djangorestframework (pinned 3.18.2, installed 3.18.0), pillow (pinned 13.0.0, installed 12.3.0), pyjwt (pinned 2.15.0, installed 2.13.0), setuptools (pinned 84.1.0, installed 83.0.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 6 passed, 3 warnings in 19.96s ========================
  ```

- AC 11: `cd web && npx vitest run src/pages/forum/CategoryListPage.test.tsx src/pages/forum/ThreadListPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx` — evidence `.sweep-evidence/g1/665-ac10.txt` (not committed), last lines:

  ```text

   Test Files  3 passed (3)
        Tests  151 passed (151)
     Start at  13:02:57
     Duration  4.47s (transform 472ms, setup 383ms, import 3.17s, tests 3.53s, environment 1.55s)
  ```

- AC 12: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest -q -p no:cacheprovider --create-db -o addopts=--tb=short --deselect apps/core/tests/test_env_example_placeholders.py::test_optional_integration_placeholders_only_warn_under_debug --deselect apps/core/tests/test_env_example_placeholders.py::test_a_legacy_placeholder_only_warns_under_debug && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python manage.py spectacular --validate --fail-on-warn --file /dev/null && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m mypy && cd ../web && npx tsc --noEmit && npx vitest run` — evidence `.sweep-evidence/g1/665-ac11.txt` (not committed), last lines:

  ```text

   Test Files  128 passed (128)
        Tests  1971 passed (1971)
     Start at  13:29:27
     Duration  23.52s (transform 5.41s, setup 13.76s, import 46.39s, tests 62.70s, environment 69.60s)
  ```

### 2026-10-28 - Completed by the todo sweep (run 2026-10-28-1737)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-28 - Repaired by the todo sweep (run 2026-10-28-1737)

- Round-1 finding (ForumIndex privacy): `_visible_boards` in `backend/packages/wagtail_forum/wagtail_forum/api/views.py` now hides every forum while a ForumIndex is unpublished or has a `PageViewRestriction` on itself or an ancestor page, as `.public()` did for board pages. It is a single `~Exists` in the same SQL query, so no pinned query count moves. With no ForumIndex at all, nothing closes the forum (index-less test fixtures depend on this). On main, `.live()` checked only the board's own flag. Gating on the index's `live` is new.
- `apps/forum_host/tests/test_seo.py`: the ancestor test is back to restricting only the ForumIndex. The hidden-category case is now a separate test. New API tests in `test_forum_categories_api.py` cover a restricted index, a restricted ancestor and an unpublished index (boards, board topics, topic detail, categories), plus a live public index that keeps the forum visible.
- Round-1 finding (Topic board select): `Topic.board` gets `limit_choices_to={"forum_type": "forum"}` (migration `0045_topic_board_forums_only`), so the CMS snippet select offers forums only. `ForeignKey.validate` applies the limit on every `full_clean()`, which `save_revision()` runs, so no `Topic.clean` was added. A mutation check showed it would be dead code. Test: `test_boards.py::test_a_topic_cannot_sit_on_a_category_or_link`.

### 2026-10-28 - Review round 3 (owner-approved) and non-blocking findings

- Round 2 blocked on a regression from the round-1 fix: `_visible_boards` hid every forum when *any* ForumIndex was closed, so a stray draft copy of the index emptied the API, sitemap and feeds. The owner approved a round 3 (2026-10-28). The gate is now "an open index exists, or no index at all": `Exists(open_index) | ~Exists(ForumIndex)`, still inside the one query. Test: `test_forum_categories_api.py::test_a_stray_closed_forum_index_does_not_hide_the_forum` (draft and restricted). Mutation check: with the round-2 condition put back, both cases fail (2 failed, 10 passed). The file was restored from a copy and the guard line grepped.
- Non-blocking, fixed:
  - `ForumIndex.get_context` did not check `parent__is_hidden`, so the server-rendered fallback page listed forums under a hidden category. It now does. `test_page_serving.py::test_forum_index_lists_only_visible_forums` covers a forum under a hidden category.
  - The `ForumIndexPayload` doc comment in `web/src/types/forum.ts` sat above `Category`. It is now back above `ForumIndexPayload`.
- Non-blocking, declined:
  - 0041's slug de-dupe suffix `{slug}-{pk}` is not re-checked against `taken` or the length limit. A collision needs a board whose literal slug is `<other slug>-<that board's pk>`. The migration is atomic on Postgres, so a collision aborts the deploy loudly and loses no data.
  - 0041 bakes an index or ancestor restriction into `is_hidden`. That fails closed. Until the Forum admin lands (todo 666), you unhide in a shell with `Forum.objects.update(is_hidden=False)`.
  - 0043 leaves board-page `WorkflowState` and search `IndexEntry` rows behind. They are inert rows for a deleted content type; boards were never submitted to a workflow (topics and posts are snippets).
  - `apps/users/views.py` imports the private `_visible_boards`, which host modules already do elsewhere. A public alias belongs with the permissions slice (todo 676), which rewrites that rule.
  - A Forum with `parent=NULL` has no DB CHECK. `clean()` enforces it, and the admin forms arrive in todo 666, the slice that owns validation.
  - Board-rename redirects ride on `Forum.save()`, so a queryset `.update(slug=…)` makes none. Nothing calls one.
  - `seed_demo_content` filters by `forum_type=forum`, so a future link with the same slug would collide. Links arrive in todo 670.
  - The web category crumb makes one extra uncached `GET categories/` per thread page, and that crumb is plain text. It is a performance/UX polish for the category slices, and correctness is unaffected.
  - `CategoryListPage` drops a forum that is in `boards/` but not in `categories/` (skew between endpoints). Both read `_visible_boards`, so they cannot disagree.

## Notes

Largest slice — most of the effort is the mechanical test-fixture migration. Subforums are deliberately out of scope (owner, 2026-10-28).
