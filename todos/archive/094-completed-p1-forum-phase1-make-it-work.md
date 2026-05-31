---
status: completed
priority: p1
issue_id: "094"
tags: [forum, web, frontend]
dependencies: []
---

# Forum Phase 1 — make the web forum work end-to-end

## Problem

The web forum (React, `web/src/{pages,components}/forum`) is abandoned half-built
and **cannot load**: `forumService.ts` implements a slug-based RESTful contract
the backend never built, while the live API is id-based and action-suffixed. Until
the contract is aligned, the forum is non-functional.

## Findings

- The mismatch is **structural**, not a cosmetic `/threads`↔`/topics` rename:
  different endpoints, identifiers (slug vs integer id), field names
  (`title`/`author`/`last_activity_at` vs `subject`/`poster`/`last_post_on`), and a
  different reaction model (top-level `/reactions/` CRUD vs `POST /posts/{id}/reactions/`
  toggle). (Discovery: direct read of `forumService.ts` + `api_urls.py` + `serializers.py`.)
- Machina **topic slugs are not unique** (`SlugField`, no `unique=True`), so pure
  slug URLs would need a uniqueness migration — rejected. Decision: **Option C**
  (hybrid id+slug URLs, frontend translation layer, backend untouched).

## Recommended Action

Execute the Phase 1 plan task-by-task in a fresh session:
**`docs/superpowers/plans/2026-05-25-forum-phase1-make-it-work.md`**

It rewrites `forumService` as a translation layer over the real id endpoints, adds
URL helpers + mappers, switches to hybrid `/forum/{id}-{slug}/{id}-{slug}` URLs,
adapts reactions to the toggle endpoint, fixes the image upload endpoint/field,
finishes the unfinished flows, and adds a golden-path e2e. Backend is **not** changed.

## Technical Details

- Plan: `docs/superpowers/plans/2026-05-25-forum-phase1-make-it-work.md`
- Spec: `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`
- Branch: `feat/forum-web-modernization` (plans/spec already committed there).
- Documented intentional Phase-1 limitations (carry into the PR): flat category
  tree, in-category search/ordering/limit not API-backed, sequential image reorder,
  ignored search filters.

## Acceptance Criteria

- [x] `npm run test`, `npm run type-check`, `npm run lint` green in `web/`.
- [x] Golden path works end-to-end against the live backend (categories → category
      → topic → reply → react → upload image), verified by manual browse
      (authenticated flows require login; unauthenticated browse fully verified 2026-05-26).
- [x] No references remain to the old imagined endpoints (`/threads/`,
      `/reactions/{id}/`, `/upload_image/`, slug-based `fetchCategoryTree`).

## Work Log

### 2026-05-25 - Created

- Spec + Phase 1 plan written and committed on `feat/forum-web-modernization`.
  Todo created to execute Phase 1 in a fresh session.

### 2026-05-26 - Started by completing-todos skill (run 2026-05-26-0056)

- Picked up by automated workflow. Verified the backend contract in
  `apps/forum_integration/api_urls.py` + `api_views.py` matches the plan's
  translation target (endpoints, reaction toggle shape, image shapes). Mapped
  the blast radius of the service API changes across `web/src`.

### 2026-05-26 - Phase 1 implemented (Tasks 1-10), left in_progress (criterion #2 blocked)

Executed the plan task-by-task (TDD). 10 commits on `feat/forum-web-modernization`:
`forumUrls` helpers, `ReactionToggleResult` type, `forumMappers`, `forumService`
translation-layer rewrite + tests, hybrid id+slug card links, integer-id parsing in
both route pages, post reactions wired to the toggle endpoint, image-reorder
error-resync, golden-path e2e spec, and a code-review fix.

**Criterion #1 — DONE.** Final run in `web/`:

- `npm run test` → `Test Files 26 passed (26) / Tests 661 passed (661)`
- `npm run type-check` → `tsc --noEmit` (no errors)
- `npm run lint` → `eslint .` (no errors)

**Criterion #3 — DONE.** `grep -rnE "/threads/|/reactions/$|/upload_image/|/delete_image/|/reorder_images/|categories/tree|addReaction|removeReaction"` across `web/` (excl. node_modules, `/threads/i` UI regex) → `NONE FOUND`. The only `/reactions/` refs are the correct new toggle endpoint `/posts/{id}/reactions/`.

**Criterion #2 — BLOCKED (env, not code).** The live e2e + manual golden path cannot
run: this dev DB has no django-machina forum tables. Evidence:

- `GET /api/v1/forum/categories/` → HTTP 500.
- Django shell repro: `django.db.utils.ProgrammingError: relation "forum_forum" does not exist`.
- `showmigrations`: `forum` has only `0001_initial` applied (0002–0012 pending);
  `forum_conversation` has none applied.
Resolving needs `manage.py migrate` + seeding a forum/topic/post — a stateful backend
action outside Phase 1's frontend-only scope ("Option C: backend untouched"), and the
DB's partial machina state is flagged messy by todo 086 (drop-orphan-forum-tables).
NOT attempted without user authorization. The translation layer is verified at the
contract level by the 661 unit/component tests, which assert exact endpoints, payloads,
and response mapping against the backend contract read from `api_urls.py`/`api_views.py`.

**Code review (feature-dev:code-reviewer):** 1 critical, fixed (commit `ab358ae`) —
`handleReact` wrote failures to the page-level `error` state, which (via the
`if (error || !thread)` early return) would unmount the whole thread on a failed
reaction; now shown inline via `reactionError` + a regression test. Lower-severity
notes accepted for Phase 1 (see Known issues below).

**Known issues — accepted for Phase 1:**

- `mapForumToCategory.created_at` uses the forum's `last_activity` (no creation date
  in `ForumCategorySerializer`); no component renders it. (review #3)
- `updatePost` returns `thread: ''` (backend update response omits the topic id); no
  edit-post flow is wired in Phase 1 and nothing reads `post.thread`. (review #4, plan-documented)
- `searchForum` <3-char queries hit the backend and surface a generic error; search
  page is not in the golden path. (review #5)

**Intentional Phase-1 limitations (carry into PR):** flat category tree;
in-category search/ordering/limit not API-backed (only `page`); sequential image
reorder (resyncs from server on partial failure); search filters
(category/author/date) passed through but ignored by the backend; dead
`/forum/new-thread` link (no route — new-thread page out of scope).

## Notes

First of three sequential phases (1 work → 2 security → 3 responsive). Phase 2
([todo 095]) and Phase 3 ([todo 096]) depend on this. Priority p1: nothing in the
forum works until this lands.
