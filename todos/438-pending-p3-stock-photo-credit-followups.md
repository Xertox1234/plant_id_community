---
status: pending
priority: p3
issue_id: "438"
tags: [blog, licensing, backend, web]
dependencies: []
source_review: "PR #820"
---

# Stock-photo credit follow-ups (todo 376 review)

## Problem

Todo 376 made new stock photos carry and show their credit. The bundled
`/code-review` of PR #820 raised these as non-blocking.

## Findings

- **Existing photos are still uncredited.** Spotlight blocks populated before
  #820 have an image and no `image_credit`; `populate_plant_images` skips them
  ("Already has image"), and `--force` fetches a different photo. The Wagtail
  images carry `photographer:<username>` (Unsplash, also `unsplash_id:`) and
  `photographer:<name>` (Pexels) tags a credit could be rebuilt from. Whether
  production has any such blocks is unknown (the command is manual).
- **The command writes with a bare `post.save()`.** No `save_revision()`, so
  the admin's latest revision lacks the image and credit and the next admin
  publish drops both; no `page_published`, so `BlogCacheService` keeps
  serving the old detail response for up to 24h. Predates #820
  (`docs/rules/wagtail.md` asks for `save_revision().publish()`).
- **Three copies of the web URL check**: `utils/externalUrl.ts`
  `safeExternalUrl`, `forumBody.ts` `validPreviewUrl`, `forumService.ts`
  `fetchLinkPreview`.
- **"Unsplash" is named but not linked.** Unsplash's guidelines ask for a link
  to the photographer AND to Unsplash (with UTM params).

## Acceptance Criteria

- [ ] Existing spotlight photos get their credit (a backfill), or it is
      established that production has none.
- [ ] Each other finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #820 review round 1
