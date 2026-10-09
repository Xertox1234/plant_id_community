---
status: pending
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
