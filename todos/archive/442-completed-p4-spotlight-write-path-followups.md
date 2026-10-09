---
status: completed
priority: p4
issue_id: "442"
tags: [blog, backend, web, licensing]
dependencies: []
source_review: "PR #825"
triage: ready
triaged: 2026-10-02
owner_decision: "A refused write KEEPS the images it fetched; only a write that raised with the page unchanged deletes them (2026-10-09, narrowing 2026-09-28); the backfill may call the Unsplash API (GET /photos/:id) for the real photographer name (2026-09-28)"
---

# Spotlight write path: non-blocking review findings (todo 438)

## Problem

The bundled `/code-review` of PR #825 raised these as non-blocking.

## Findings

- **Orphaned images.** `populate_plant_images` fetches/generates every
  spotlight image for a page, then writes one revision. If that write is
  refused (changed during run, block gone) or fails, the fetched Wagtail
  Images stay in the library unreferenced, and a re-run fetches (and spends
  AI budget) again. Delete them on a refused write, or reuse them.
- **Username, not name.** Rebuilt Unsplash credits read "Photo by
  anniespratt"; the `unsplash_id:` tag could fetch the photographer's real
  name and profile (`GET /photos/:id`). Pexels names with `_` are lossy.
- **Cache invalidation before commit.** `revision.publish()` runs inside the
  command's `transaction.atomic()`, so the blog `page_published` handler
  invalidates `BlogCacheService` before the commit; a concurrent GET can
  re-cache the old response. The handler should use `transaction.on_commit`.
- **Two sources for the Unsplash link.** The web hard-codes the
  " on Unsplash" suffix and the UTM params; expose a vetted
  `unsplash_href` in the block's API representation instead.
- **Double page load**: `populate_plant_images` iterates full posts, then
  `load_spotlight_base` reloads each; iterate ids like the backfill.
- **Duplicated outcome reporting** in both commands; a shared
  `describe_outcome()` helper.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #825 review round 1

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Orphaned images: `populate_plant_images` deletes the Wagtail images it
  fetched for a page whose write was refused (owner decision 2026-09-28). After
  a write that RAISED it deletes them only while the page's revision pointers
  are unchanged (`page_unchanged_since`): another app's `on_commit` hook can
  raise after the revision committed (forum_host registers one on
  `page_published`), and a revision may then reference the images.
- Username, not name: the backfill asks Unsplash for the photo
  (`UnsplashImageService.get_photo`, `GET /photos/:id` via the `unsplash_id:`
  tag, cached 24h) through `PlantImageService.rebuild_attribution` and credits
  the real name with a profile link; the tag-only username credit stays as the
  fallback. The Pexels `_` lossiness is declined: the owner decision scoped the
  API call to Unsplash, and the credit still names the photographer.
- Cache invalidation before commit: every blog cache handler now invalidates
  from `transaction.on_commit(..., robust=True)`. Wagtail's admin edit/delete
  views and `save_spotlight_updates` are all atomic, so the admin had the same
  race. Existing signal and command tests wrap their triggers in
  `captureOnCommitCallbacks(execute=True)`; an `execute=False` test pins the
  deferral.
- Two sources for the Unsplash link: `PlantSpotlightBlock.get_api_representation`
  adds `credit_lead` and `unsplash_href` (the template context's names); the
  web renders them and no longer carries the suffix/UTM constants. Detail
  responses cached before the backend deploy lack the fields for up to 24h and
  render an Unsplash credit as a single photographer link meanwhile.
- Double page load and duplicated reporting: the command iterates pks and
  loads each page once via `load_spotlight_base` (pinned by counting
  `content_blocks` selects); both commands report through the shared
  `describe_outcome()` / `page_label()`.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 4 -- backend/venv/bin/python -m pytest backend/apps/blog/tests/test_populate_plant_images.py backend/apps/blog/tests/test_plant_spotlight_writes.py backend/apps/blog/tests/test_plant_spotlight_credit.py backend/apps/blog/tests/test_backfill_spotlight_credits.py backend/apps/blog/tests/test_blog_signals.py backend/apps/plant_identification/tests/test_stock_photo_attribution.py --create-db -p no:cacheprovider && cd web && npx vitest run src/components/StreamFieldRenderer.test.tsx` — evidence `.sweep-evidence/g4/442-ac0.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  62 passed (62)
     Start at  06:40:21
     Duration  1.11s (transform 85ms, setup 100ms, import 272ms, tests 197ms, environment 465ms)
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-02 - Repaired by the todo sweep (run 2026-10-02-0335)

- Round-1 review (high): a write refused mid-run (`skipped_changed_during_run`)
  deleted every image the run had fetched, although the editor whose save
  refused it may have picked one from the library — that revision then kept
  `"image": <pk>` of a deleted row, which resolves to None.
- `_discard_fetched_images` now partitions before deleting: the new
  `referenced_image_pks` (`plant_spotlight_writes`) reloads the page row and
  its latest revision as an object and walks both `content_blocks` with the
  StreamField's `extract_references`, so an image either one references is
  Kept and reported and the rest are Discarded. The raise branch is unchanged.
- Tests: an editor publishing a revision that picks the first of two fetched
  images (one Kept, one Discarded, the live block still resolves it), an
  editor drafting one (only the latest revision references it), and helper
  tests for the draft, live, rich-text-embed and deleted-page cases.
  Mutation-checked: ignoring the check fails both command tests (2 failed /
  18 passed); reading only the page row fails the three draft-shaped tests
  (3 / 17); both files restored byte-identical.

### 2026-10-02 - Round-3 repair by the todo sweep (run 2026-10-02-0335)

- Round-2 review (high, `plant_spotlight_writes.py`): `referenced_image_pks`
  walked only `content_blocks`, so a fetched image the editor set as the
  page's `featured_image` or `social_image` (SET_NULL foreign keys) counted as
  unreferenced; deleting it nulled the live column and left the revision's
  value resolving to None. Owner pre-approved a third round ("3 rounds max").
- `referenced_image_pks` now also collects every concrete forward foreign key
  from `BlogPostPage` to the image model (inherited `social_image` included)
  on both the live row and the latest revision object.
- Tests: `featured_image` set only in a draft revision, `social_image` set on
  the live row, and a command test where the refusing save sets the fetched
  image as `featured_image` (Kept, column still resolves). 23 passed.
  Mutation-checked: removing the foreign-key scan fails exactly the three new
  tests (3 failed / 20 passed); file restored from a copy and grep-verified.

### 2026-10-09 - Narrowed after the round-3 hand-off (owner decision)

- Round-3 review (high): `referenced_image_pks` still skipped
  `BlogPostPage.introduction`, a `RichTextField` whose features allow image
  embeds. Each round had found another reference path the keep check missed.
- Owner chose the narrow design over patching generically: a REFUSED write
  now keeps every image it fetched (as `main` did before this todo), and only a
  write that raised while the page's revision pointers are unchanged deletes
  them. `referenced_image_pks` and `_image_foreign_keys` are removed.
- Tests: the refused-write command tests now expect Kept (including both
  images in the two-block case), plus a new one where the refusing save embeds
  the fetched image in the introduction. Helper tests for the removed function
  are gone. 61 passed across the four spotlight test files.
  Mutation-checked: restoring delete-on-refusal fails exactly the five
  refused-write tests (5 failed / 5 passed); file restored from a copy and
  grep-verified.
