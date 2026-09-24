---
status: pending
priority: p4
issue_id: "442"
tags: [blog, backend, web, licensing]
dependencies: []
source_review: "PR #825"
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

- [ ] Each finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #825 review round 1
