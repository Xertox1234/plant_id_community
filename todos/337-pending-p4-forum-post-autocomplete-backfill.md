---
status: pending
priority: p4
issue_id: "337"
tags: [forum, wagtail, search, ops, deploy]
dependencies: []
source_review: "docs/audits/2026-09-04-forum.md"
source_finding: "L10"
---

# Backfill the Post autocomplete search index in production

## Problem

Audit 2026-09-04 L10 added `index.AutocompleteField("body")` to `Post`, so the
CMS post listing search matches word prefixes again. The DB search backend
populates the autocomplete column from the post-save indexing signal, so only
posts saved AFTER the deploy are prefix-searchable; every existing row stays
whole-word-only until `manage.py update_index` runs once. Nothing wires that
run today.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/models/posts.py` — the new
  `AutocompleteField("body")` (audit PR).
- `modelsearch/backends/database/postgres/postgres.py::ObjectIndexer` — the
  autocomplete column is written by `add_items`, i.e. on save / `update_index`,
  not lazily at query time (Phase 6 wagtail-reviewer trace).
- `backend/railway.json` `preDeployCommand` runs `migrate` + `seed_default_forum`
  only; a per-deploy `update_index` would rebuild the whole site index every
  deploy, which is the wrong cost for a one-off backfill.

## Recommended Action

1. After the audit PR deploys, run once against production (Railway shell or a
   one-shot service): `python manage.py update_index` (the whole index — the
   forum's `Topic`/`Post` and the blog share one backend; a scoped variant is
   `update_index --backend default`).
2. Verify in `/cms/snippets/wagtail_forum/post/?q=<prefix>` that a pre-deploy
   post matches on a word prefix.
3. Record the run date here and archive.

## Technical Details

- Pinned by `tests/test_admin.py::test_post_listing_search_matches_a_body_prefix`
  for rows created after the field exists.
- Same class of follow-through as todo 276 / audit L8 (Topic title).

## Acceptance Criteria

- [ ] `update_index` has been run once in production after the L10 deploy.
- [ ] A post created before that deploy is found by a body-word prefix in the
      CMS post listing search.

## Work Log

### 2026-09-04 - Filed from the forum audit's Phase 6 review

- The manifest noted the backfill; the wagtail reviewer pointed out nothing
  owns it. Filed rather than adding a per-deploy `update_index`.

## Notes

p4: cosmetic for moderators (whole-word search still works); no user-facing
surface reads the admin autocomplete index.
