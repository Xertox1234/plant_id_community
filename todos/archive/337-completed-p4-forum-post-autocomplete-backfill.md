---
status: completed
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

> **Premise correction (2026-09-05, see Work Log):** the second sentence is
> wrong for the CMS listing. Wagtail's `IndexView.search_queryset` passes
> `fields=self.search_fields`, and modelsearch's Postgres compiler then
> builds the tsvector from the model column at query time
> (`get_fields_vectors`) instead of reading `index_entries__autocomplete`
> (`get_index_vectors`, used only when `fields is None`). Pre-deploy posts
> were prefix-searchable in `/cms/` as soon as the field was declared. The
> stored autocomplete column WAS empty for all 138 posts, and that is what a
> fields-less `search_backend.autocomplete()` reads — the backfill fixes that
> path, which nothing in this repo calls today.

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

- [x] `update_index` has been run once in production after the L10 deploy.
- [x] A post created before that deploy is found by a body-word prefix in the
      CMS post listing search.

## Work Log

### 2026-09-04 - Filed from the forum audit's Phase 6 review

- The manifest noted the backfill; the wagtail reviewer pointed out nothing
  owns it. Filed rather than adding a per-deploy `update_index`.

### 2026-09-05 - Ran in production via `railway ssh` (service `plant_id_community`)

- Precondition: the live deployment `06be8bfe` was built from `f94753c`
  (PR #629, the L10 commit) — `railway deployment list --json`.
- Read-only probe first (Django shell over `railway ssh`): 138 posts, all
  created before the deploy; 138 `IndexEntry` rows for `Post`, all with
  `length(autocomplete) = 0`; 195 index entries in total.
- Replaying the CMS listing query
  (`get_search_backend().autocomplete("aski", Post.objects.all(), fields=["body"], order_by_relevance=True)`)
  found pre-deploy post 242 (`created_at` 2026-07-22, body starts "Asking…")
  BEFORE the backfill — which is what led to the premise correction above
  (`fields=` → on-the-fly vector, `postgres.py:652-656`).
- The stored-column path (`autocomplete("aski", Post.objects.all())`, no
  `fields`) before/after, and the run itself, in one SSH session:

  ```text
  BEFORE: Post rows with empty autocomplete 138 | stored-index prefix hits for aski 0 | post 242 found False
  Updating backend: default
  default: Rebuilding index <modelsearch.backends.database.postgres.postgres.PostgresIndex object at 0x7ff2e2b6ec10>
  default: wagtaildocs.Document
  default: wagtailimages.Image       .
  default: wagtailcore.Page          .
  default: wagtail_ai.Prompt         .
  default: plant_identification.PlantSpeciesPage
  default: plant_identification.PlantCategoryIndexPage
  default: blog.BlogIndexPage        .
  default: blog.BlogCategoryPage     .
  default: blog.BlogAuthorPage       .
  default: blog.BlogPostPage         .
  default: wagtail_forum.ForumIndex  .
  default: wagtail_forum.ForumBoard  .
  default: wagtail_forum.Post        .
  default: wagtail_forum.Topic       .
  default: indexed 195 objects
  AFTER: Post rows with empty autocomplete 0 | stored-index prefix hits for aski 2 | post 242 found True | total entries 195
  ```

- The Postgres rebuilder is `delete_stale_entries` + `ON CONFLICT` upsert
  (`postgres.py:364,434,914-922`), so search stayed available during the run.
- AC 1: the `update_index` output above. AC 2: post 242 (pre-deploy) is
  returned by the exact call the CMS listing makes (verified before and after;
  the `/cms/` page itself was not opened — the listing view calls that
  function verbatim, `wagtail/admin/views/generic/base.py:264`).

## Notes

p4: cosmetic for moderators (whole-word search still works); no user-facing
surface reads the admin autocomplete index.

`railway ssh` gotcha: it joins its arguments and hands them to the remote
`bash -c`, so an inline `manage.py shell -c "<python>"` must be wrapped as
`railway ssh -- "python manage.py shell -c '<python with \"double\" quotes>'"`;
an unwrapped command loses its quotes and fails with a bash syntax error.
