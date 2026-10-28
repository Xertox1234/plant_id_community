---
status: pending
priority: p2
issue_id: "665"
tags: [forum, forum-categories, backend, web, migration]
dependencies: []
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

1. Add `Forum` model (spec §4): `forum_type`, `parent` (self FK, null), `position`, `name`, forum-wide unique `slug`, `description`, the existing counters, interim `is_hidden`. Model validation: categories have no parent; forums/links must have a category parent; only categories may be parents.
2. Data migration: create category "General"; copy each `ForumBoard` into `Forum` **keeping its id**; set `is_hidden=True` for any board that was non-live or carried a `PageViewRestriction`; reset the id sequence; repoint `Topic.board` (and any other FK) at `Forum`, switching to `on_delete=PROTECT`; delete the old ForumBoard page rows (`wagtailcore_page`) and set `ForumIndex.subpage_types = []`.
3. Replace `_visible_boards()` with a `Forum`-based equivalent (`forum_type=forum`, not hidden); keep `/forum/boards/` and `/forum/boards/{slug}/topics/` response shapes byte-compatible for Flutter; add a new additive endpoint (or field) that returns categories with their forums, category rows summing their visible forums' counts and newest last post at read time.
4. Update the touch list: seed commands (`seed_default_forum` must create a category + forum), `redirects.py` (board rename redirects no longer come from `page_slug_changed`), `sitemaps.py` (decide: list forums from the new model), `apps/users/views.py`, serializers, signals.
5. Add a shared test factory (e.g. `make_forum(category=..., ...)`) and migrate the 94 test files to it mechanically (one script, verify once).
6. Web: `CategoryListPage.tsx` renders a header per category with its forums under it; breadcrumbs show Category › Forum on the thread list and thread pages.

## Technical Details

- Forum package: `backend/packages/wagtail_forum/wagtail_forum/models/boards.py`, `api/views.py`, `api/serializers.py`, `signals.py`.
- Host: `backend/apps/forum_host/{redirects.py,sitemaps.py,management/commands/seed_default_forum.py,management/commands/seed_demo_content.py}`, `backend/apps/users/views.py`.
- Web: `web/src/pages/forum/CategoryListPage.tsx`, `web/src/services/forumService.ts`, `ThreadListPage.tsx`, `ThreadDetailPage.tsx`.
- Pattern docs: `backend/docs/patterns/domain/forum.md`, `domain/wagtail.md`, `performance/query-optimization.md`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Migration test: boards become forums with **identical ids** under one "General" category; a non-live or view-restricted board becomes `is_hidden=True`; no `ForumBoard` page rows remain.
- [ ] Test: an existing topic URL `/forum/{board.id}-{slug}/{topic.id}-{slug}` still resolves after migration.
- [ ] Test: `GET /forum/boards/` and `/forum/boards/{slug}/topics/` responses keep their previous keys (Flutter contract).
- [ ] Test: the new categories endpoint returns categories in `position` order with forums nested, counts aggregated, hidden forums excluded, and a fixed query count.
- [ ] Test: deleting a forum that has topics raises `ProtectedError` (no cascade).
- [ ] Test: model validation rejects a category with a parent, a forum without a category, and a forum as a parent.
- [ ] Test: forum slugs are unique forum-wide (DB constraint).
- [ ] `seed_default_forum` creates a category and a forum, idempotently.
- [ ] Web Vitest: the index renders one header per category with its forums beneath; breadcrumbs show the category.
- [ ] Full backend pytest, `manage.py spectacular --validate --fail-on-warn`, mypy gate and web `tsc`/Vitest pass.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

## Notes

Largest slice — most of the effort is the mechanical test-fixture migration. Subforums are deliberately out of scope (owner, 2026-10-28).
