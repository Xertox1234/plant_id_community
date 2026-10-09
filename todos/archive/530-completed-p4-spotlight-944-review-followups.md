---
status: completed
priority: p4
issue_id: "530"
tags: [blog, backend, web, follow-ups]
dependencies: []
source_review: "PR #944"
---

# PR #944 (todo 442) final review: non-blocking follow-ups

## Problem

The final review pass on PR #944 (bundled `/code-review` high plus the
wagtail, django-drf, react-typescript and cross-cutting checklist reviewers,
2026-10-09) found three blocking issues, repaired in the PR: a versioned blog
cache prefix, a crash-proof discard check in `populate_plant_images`, and
`execute=False` deferral tests for every blog invalidation receiver. The
non-blocking findings are below, most useful first. Re-check each against main
before acting on it; several are hypotheses.

## Findings

1. **Backfill silently persists a degraded Unsplash credit** (low, defect).
   `PlantImageService.rebuild_attribution` falls back to the username credit
   ("Photo by janedoe on Unsplash") whenever `get_photo` returns None,
   including when the demo rate limit (50/h) is used up partway through a
   run. `backfill_spotlight_credits` writes that credit, counts it as
   Credited, and a credited block is never a candidate again, so it is never
   upgraded. This is no worse than main (which always wrote the username
   credit), but the operator cannot tell which blocks were downgraded.
   Suggested: count and print fallback credits separately; when an access key
   is configured and `get_photo` returns None, warn (or stop) instead of
   writing the fallback. `rebuild_attribution` logs every failure cause on
   one `info` line; distinguish rate-limited from gone.

2. **`_make_request` rate counter can saturate on a response without the
   header** (low, hypothesis). `remaining = int(headers.get("X-Ratelimit-Remaining", 0))`
   sets the shared counter to 50 when the header is absent, blocking every
   Unsplash call for an hour. `get_photo` now sends expected 404s (deleted
   photos) through it. Unverified whether Unsplash 404s carry the header.
   Suggested: only update the counter when the header is present.
   Pre-existing code; the PR added a new caller.

3. **`get_photo` does not cache failures** (low, efficiency). A deleted photo is
   re-requested on every run, dry runs included, burning the 50/h budget and
   making finding 1 likelier. Suggested: a short-lived negative cache entry.

4. **A write that raised after committing is reported as "not written"**
   (low, defect). When `save_spotlight_updates` raises from a non-robust
   `on_commit` hook after the revision committed, `populate_plant_images`
   prints "Not written … could not be saved" and leaves the images out of
   `total_images_added`; `backfill_spotlight_credits` reports "pages failed".
   `page_unchanged_since(base)` already tells the cases apart. Suggested:
   when it is False after a raise, report "written, but a post-commit hook
   failed" instead.

5. **The "Kept … the page changed" message is wrong for some outcomes**
   (low, cosmetic). It also prints for `BLOCK_NOT_FOUND` and for a page that
   was deleted. Suggested: word it per outcome.

6. **Blog invalidation now shares the `on_commit` queue with other apps'
   hooks** (low, hypothesis). Django stops running the remaining commit hooks
   when a non-robust hook raises, so a failing hook queued before the blog's
   would skip its invalidation and leave keys stale for 24h. Before PR #944
   invalidation was synchronous. Suggested: check which receivers on
   `page_published` register non-robust hooks (forum_host's RAG enqueue) and
   make them robust.

7. **Bulk deletes repeat the full list/popular invalidation per post**
   (low, efficiency). Each receiver queues its own callback, so deleting a
   parent with 100 posts clears every list key 100 times. Suggested: collect
   dirty slugs per transaction and flush them in one `on_commit` hook.

8. **Nits.**
   - `get_photo` cache key `unsplash_photo_{id}` is not `app:feature:scope:id`
     (the neighbouring Unsplash keys share the old style).
   - `rebuild_attribution(self, tag_names)` lacks a type hint (`Iterable[str]`).
   - No test for an empty `unsplash_id:` tag (the `and photo_ids[0]` guard).
   - `_after_commit(..., robust=True)` is not pinned by a test (the callables
     catch their own errors, so it is redundant today).
   - Web: `credit_lead` is trusted as a prefix of `image_credit`; types could
     narrow to `string` (the server never sends null).

## Resolution (2026-10-09)

Each finding was re-checked against main before acting.

- [x] 1. Backfill fallback credit. A failed lookup the next run may not
  repeat (the rate limit, an API error, a malformed answer) now leaves the
  block uncredited and counts it as **deferred**, so a re-run can still name
  the photographer. A lookup that cannot help (no key, a 404, no name in the
  answer) still writes the username credit, now counted separately
  (`Credited: N (username only: M)`). `rebuild_attribution_with_basis` says
  which; `rebuild_attribution` keeps its tuple. The info log names the cause
  (rate limit, request failed, gone, no key). The old docstring credited
  "fallback on failure" to the 2026-09-28 owner decision, which only allowed
  the API call; reworded.
- [x] 2. Rate counter. Updated only from a present, numeric
  `X-Ratelimit-Remaining`; a missing or malformed header leaves it alone
  (the old `int(... , 0)` blocked Unsplash for an hour, and a non-numeric
  header raised past the `RequestException` handler).
- [x] 3. Negative cache. A 404 is remembered for an hour; transient
  failures are never cached. A 401 (rejected key) counts as no key, so it
  falls back instead of deferring on every run (PR #965 review). The
  positive cache check is now `is not None`.
- [x] 4. Raise after commit. `outcome_after_raise` checks whether the page's
  latest revision is a new one carrying every update; if so both commands
  report it written (the error came from a post-commit hook) and count it.
- [x] 5. The "Kept" line is worded per outcome: a page edited during the run,
  any other refusal, a page that changed or was deleted before a failed write
  was checked, or a check that failed.
- [x] 6. Checked: only `apps.blog` and `apps.forum_host` receive
  `page_published`, and forum_host's enqueue already catches its own errors,
  so the hypothesis is mostly moot. Its `on_commit` is now `robust=True`
  anyway, and both hooks are pinned by a test.
- [ ] 7. Declined. One flush hook per transaction has a savepoint trap: a
  hook registered inside a savepoint that rolls back is discarded while the
  dirty set survives, so later slugs never flush and lists stay stale for
  24h. Repeated invalidation is safe; missed invalidation is the bug this
  path exists to prevent.
- 8. Nits:
  - [x] Type hint `Iterable[str]` on `rebuild_attribution`.
  - [x] Tests for an empty and a blank `unsplash_id:` tag.
  - [x] `robust=True` pinned by a test (blog and forum_host).
  - [ ] Renaming `unsplash_photo_{id}` declined: the neighbouring Unsplash
    keys share the old style. The NEW negative key follows the rule
    (`plant_id:unsplash:photo_gone:{id}`, PR #965 review).
  - [ ] Web type narrowing declined: the fields are optional either way and
    the renderer already handles null and undefined with `?.trim() ?? ''`.
