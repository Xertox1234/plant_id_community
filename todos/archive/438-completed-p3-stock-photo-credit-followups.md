---
status: completed
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

- [x] Existing spotlight photos get their credit (a backfill), or it is
      established that production has none.
- [x] Each other finding is fixed with a test, or declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #820 review round 1

### 2026-09-24 - Done: backfill command, revision-based writes, Unsplash link, one URL check

**1. Backfill (AC1).** New `manage.py backfill_spotlight_credits [--dry-run]`
walks every `BlogPostPage` for `plant_spotlight` blocks with an image and an
empty `image_credit`, and rebuilds the credit from the image's taggit tags via
the new `PlantImageService.attribution_from_image_tags`. Tag shapes were read
from each service's `download_and_create_wagtail_image`, not assumed:
Unsplash writes `unsplash`, `photographer:<username>`, `unsplash_id:<id>`, so
the credit is "Photo by <username> on Unsplash" linking
`https://unsplash.com/@<username>` plus the UTM params (through the existing
`get_attribution_url`, so `safe_http_url` and `with_unsplash_utm` both apply;
a username outside `[A-Za-z0-9_]` gets text only). Pexels writes
`photographer:<name with spaces as _>` and no URL, so its credit is text only
(`_` goes back to a space, which is lossy for a real `_`). `ai_generated`
gets the same disclosure text a fresh AI image gets. `photographer:unknown`
(both services' fallback), no provider tag, or two providers means the block
is reported and left alone: the command never invents a credit. Blocks that
already have a credit are never touched. Credit text is truncated to the
block's 255. `get_attribution_text` became a `@staticmethod` so the backfill
reuses the one credit format without constructing the provider services.
**Running it in production is an owner step** (this session can neither
read nor write production): in the production container, run
`python manage.py backfill_spotlight_credits --dry-run`, then again without
the flag. Its summary line counts credited blocks, skipped pages, and images
that could not be credited.

**2. Writes go through a revision.** Both commands now write through
`apps/blog/services/plant_spotlight_writes.py` instead of a bare
`post.save()`. It loads a fresh instance, applies all of a page's spotlight
changes in memory, and makes ONE `save_revision(log_action=True)` per page.
Then:
- **A live page with no draft** gets `.publish()`. The latest revision now
  carries the image and credit, and `page_published` fires, which is what
  invalidates `BlogCacheService`.
- **A live page with unpublished changes is SKIPPED and reported** ("has
  unpublished draft changes; publish or discard the draft in the CMS, then
  re-run"). The alternatives are both wrong. A revision built from the live
  row would stop the editor's draft being the latest revision, which
  discards it. One built from the draft would publish work the editor has
  not approved. `populate_plant_images` checks this before fetching, so a
  skipped page costs no API call and no AI spend.
- **A page that is not live** gets `save_revision()` only, built from its
  latest revision (the content the admin edits). The draft gains the change
  and nothing goes live. Before, `--post-id` on a draft wrote the row, which
  the admin never reads.
- **Pages in a moderation workflow, and alias pages, are skipped.** A new
  revision would bypass the review of the submitted one, and Wagtail refuses
  revisions on aliases.
- **An editor who saves during a slow image fetch is never overwritten.**
  Under `select_for_update`, the page's `live`, `has_unpublished_changes`,
  `latest_revision_id` and `live_revision_id` are re-read, and the write is
  refused if any of them moved.
- **Block ids are preserved** by the `(type, value, id)` 3-tuple. The old
  2-tuple re-id'd the block.

No user exists in a management command, so the revision and publish are
system-attributed (`user=None`, which also skips the publish permission
check). This is a programmatic publish that bypasses workflows by design
(`docs/rules/wagtail.md`). The content is built by code, not user input.

**3. "Unsplash" is linked.** This is done in the renderers, with no schema
change. When the credit ends with " on Unsplash" (the exact
`get_attribution_text` format, now the constant `UNSPLASH_CREDIT_SUFFIX`),
the lead ("Photo by Jane Doe") links to the photographer as before, and
"Unsplash" links to `UNSPLASH_HOME_URL` (`https://unsplash.com/` plus the
UTM). The Wagtail template gets `credit_lead`/`unsplash_href` from
`PlantSpotlightBlock.get_context`, and the web `StreamFieldRenderer` mirrors
both constants. Why not a stored `image_credit_source_url` child block:
that would take a block def, a migration, both commands, the serializer,
the template, the web type and the renderer. It would also leave every
existing credit (including backfilled ones) without the link until
rewritten. The renderer split takes 3 files and covers old credits at once.
If an editor rewrites the text, it degrades to today's single link.

**4. One URL check.** `forumBody.ts` `validPreviewUrl` and
`forumService.ts` `fetchLinkPreview` now use `safeExternalUrl` as their
check. The http(s)/host/no-credentials predicate is identical, so behaviour
is unchanged. Two deliberate differences stay, each documented at its call
site and pinned by a test:
- Both still return or send the author's trimmed string, never
  `safeExternalUrl`'s normalised form (`https://EXAMPLE.com` must not become
  `https://example.com/`).
- `validPreviewUrl` keeps its `<>"'`/whitespace refusal (todo 353), which
  `new URL` would otherwise percent-encode rather than reject.

**Evidence.**
- Backend, DB-free (plain `unittest` with no test DB, 25 tests): the 8 new
  `SimpleTestCase` tests went red against the pre-change sources (17
  errors), then green. Mutations were each caught: the `unknown` guard, the
  username regex, the single-provider check, and the context suffix guard.
- A DB-free template render with a mocked rendition showed four cases:
  photographer plus Unsplash links, `javascript:` giving only the Unsplash
  link, a Pexels link, and Pexels text.
- **The DB-backed tests are written but not run here.** Another process owned
  the test DB. They are `PopulatePublishesThroughRevisionTest` (5 tests),
  `PlantSpotlightTemplateCreditTest` (3 new, 3 moved to a Pexels credit so
  "no link" stays meaningful), and
  `test_backfill_spotlight_credits.py` (6 tests). The backfill images there
  are made by the real `download_and_create_wagtail_image` with only HTTP
  mocked, so a change to the tag shapes breaks those tests.
- Web: the 4 new renderer and dedup tests went red before and green after.
  Mutations were each caught:
  - no UTM on the Unsplash link;
  - `rel` dropped;
  - the photographer lead left unlinked;
  - the preview detector bypassing the shared rule;
  - the detector returning the normalised form;
  - the quote pre-check removed;
  - `fetchLinkPreview` sending the normalised form;
  - `safeExternalUrl`'s protocol check broken.
- The protocol-check mutation first passed every test, because a
  `javascript:` URL has no host. `ftp://` cases were added and now catch it.
- The touched suites pass 237/237, and `src/components/forum` passes
  474/474. `type-check`, `lint` and `check:classes` are clean.

### 2026-09-24 - Review round 1 (bundled /code-review, PR #825): 3 repaired

- **Locked and scheduled pages were written.** `load_spotlight_base` now
  skips any page with `get_lock()`: an editor lock, a workflow lock, or a
  revision scheduled to go live (a new draft revision would be superseded by
  the older scheduled one publishing WITHOUT the credit). Test red with the
  check removed.
- **A page deleted mid-run aborted both commands.** `load_spotlight_base`
  returns None for a missing page; both commands skip it. Test red with the
  old `.get()`.
- **Id-less legacy blocks collided on the key `"None"`.** Both commands skip
  spotlight blocks without an id, and the writer never targets one. Test red
  with the populate filter removed.
- Orchestrator note: the backfill tests' `make_post` passed the raw spotlight
  dict as a native `(type, value)` tuple (`'int' object has no attribute
  'pk'`); switched to the raw JSON form before the first DB run.
- Deferred to todo 442: images fetched for a page whose write is then
  refused are orphaned; rebuilt Unsplash credits show the username (the
  photo id could fetch the name); `page_published` cache invalidation runs
  inside the command's transaction; the web duplicates the Unsplash
  suffix/UTM constants; a redundant full-page load per post; duplicated
  outcome reporting.
