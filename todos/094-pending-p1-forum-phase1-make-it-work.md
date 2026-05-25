---
status: pending
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

- [ ] `npm run test`, `npm run type-check`, `npm run lint` green in `web/`.
- [ ] Golden path works end-to-end against the live backend (categories → category
      → topic → reply → react → upload image), verified by e2e + manual.
- [ ] No references remain to the old imagined endpoints (`/threads/`,
      `/reactions/{id}/`, `/upload_image/`, slug-based `fetchCategoryTree`).

## Work Log

### 2026-05-25 - Created

- Spec + Phase 1 plan written and committed on `feat/forum-web-modernization`.
  Todo created to execute Phase 1 in a fresh session.

## Notes

First of three sequential phases (1 work → 2 security → 3 responsive). Phase 2
([todo 095]) and Phase 3 ([todo 096]) depend on this. Priority p1: nothing in the
forum works until this lands.
