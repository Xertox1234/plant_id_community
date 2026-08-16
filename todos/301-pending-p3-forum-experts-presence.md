---
status: pending
priority: p3
issue_id: "301"
tags: [forum, web, backend, presence]
dependencies: []
---

# Experts-online presence (last_seen wiring for the experts rail)

## Problem

The Canopy artifact's right rail is "Experts online" with live presence dots.
PR 2.5 ships it as "Community experts" with no dots and no online claim,
because no presence data exists (spec §9 honesty ledger). Wiring real
presence lets the module say "online" truthfully.

## Findings

- `ForumProfile.last_seen` exists and is null-by-default
  (`backend/packages/wagtail_forum/wagtail_forum/models/profiles.py:45`) —
  nothing currently writes it.
- Experts endpoint: `users/experts/` (PR 2.5,
  `backend/packages/wagtail_forum/wagtail_forum/api/views.py` ExpertsView) —
  rows are `serialize_forum_author()` payloads.
- Client module: `web/src/components/forum/rail/CommunityExpertsModule.tsx`
  (renders no dot by design, comment points at this todo).

## Recommended Action

1. Throttled `last_seen` touch on authenticated forum API requests — write at
   most once per ~5 minutes per user (compare before writing, or cache-gate),
   so there is no per-request write amplification.
2. Add `online = last_seen within 15 min` to the experts payload (threshold
   in `conf.py` `DEFAULTS`).
3. Rename the module back to "Experts online" and render the presence dot
   only when `online` is true; keep the title "Community experts" as the
   fallback when nobody qualifies, or switch title with the data.

## Technical Details

- Touch point: the package's `UnversionedForumAPIMixin` (all forum API views
  pass through it) or a small DRF authentication-aware middleware.
- Anon-cached endpoints (60s `PublicForumReadCacheMixin`) mean the dot can lag
  up to a minute — acceptable at a 15-min freshness window.

## Acceptance Criteria

- [ ] Dot appears only for a user active in the last 15 minutes
      (tested with frozen time).
- [ ] `last_seen` writes are throttled (test: two rapid requests → one write).
- [ ] Module title/claim switches with the data — no online claim when the
      flag is absent.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR 2.5 (canopy forum content) by spec §9: no presence claim
  without presence data.
