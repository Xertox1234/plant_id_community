---
status: pending
priority: p4
issue_id: "334"
tags: [forum, wagtail, redirects, backend]
dependencies: []
---

# Board slug edits leave topic paths without redirects

## Problem

`Topic.get_absolute_url()` is `/forum/{board.id}-{board.slug}/{id}-{slug}`, so
renaming a `ForumBoard` page's slug in `/cms/` (promote tab) moves every topic
path beneath it. `apps/forum_host/redirects.py` only hooks `Topic` saves, and
Wagtail's own `WAGTAILREDIRECTS_AUTO_CREATE` only covers the Page `url_path`
(`/forum/general/`), never the topic shape — so a board rename writes zero
redirect rows while a single topic-slug edit does.

## Findings

- `backend/apps/forum_host/redirects.py` — receivers on `pre_save`/`post_save`
  of `wagtail_forum.Topic` only; the module docstring now states board slugs
  as a non-goal and points here. Source: bundled `/code-review` on the
  Wagtail quick-wins branch, 2026-09-04 (finding 3 of 8).
- `backend/packages/wagtail_forum/wagtail_forum/models/topics.py:186` —
  the URL shape that embeds `board.slug`.
- `wagtail/contrib/redirects/signal_handlers.py:106-186` — Wagtail's
  auto-create walks child *Pages* only.

## Recommended Action

1. Receive `wagtail.signals.page_slug_changed` (kwargs `instance`,
   `instance_before`) filtered to `isinstance(instance, ForumBoard)`.
2. For each **live** topic under the board, compute the old path from
   `instance_before.slug` and call `redirect_topic_path(old, new)`.
3. Do it as a bulk write, not N×3 statements inside the admin save: collect
   `(old, new)` pairs, one `delete()` for shadowing rows, one chain-collapse
   `update()` per batch, then `bulk_create(ignore_conflicts=True)` mirroring
   Wagtail's `BatchRedirectCreator`. A board with thousands of topics must
   not turn the promote-tab save into a multi-second request; consider a
   Celery task if the count is large.
4. Tests: board rename creates one row per live topic and none for drafts;
   the 301 is served for an old topic path; repeated renames collapse chains.

## Technical Details

- Reach today is limited: the SPA resolves topics by leading id, so these
  rows serve origin hits and `/api/v2/redirects/find/?html_path=` lookups.
  That is why this is p4 rather than a blocker on the quick-wins PR.
- `redirect_topic_path` is already loop- and duplicate-safe for a single
  pair; the batch version must keep both properties.

## Acceptance Criteria

- [ ] Renaming a `ForumBoard` slug in the admin creates a permanent redirect
      for every live topic's previous path.
- [ ] Draft/unpublished topics get no rows.
- [ ] A board with 1,000 topics completes the admin save in bounded queries
      (pinned with `CaptureQueriesContext`, flat in N).
- [ ] Existing `test_topic_redirects.py` stays green.

## Work Log

### 2026-09-04 - Filed

- Surfaced by code review of the Wagtail quick-wins branch; scoped out of
  that PR (the brief covered topic slug changes only) and documented as a
  non-goal in the module docstring.

## Notes

Related: the quick-wins PR mounted `wagtail.contrib.redirects`' headless API
at `/api/v2/redirects/`; if the web app ever consumes it, this gap becomes
user-visible and the priority should rise.
