---
status: pending
priority: p3
issue_id: "304"
tags: [forum, backend, web]
dependencies: []
---

# Drive the forum event hero from a backend signal, not client-side inference

## Problem

The landing page's "Community event" hero is inferred client-side:
`recentTopics.find(t => t.is_pinned && t.slug.startsWith('bloom-watch'))`
over a 20-row recency window, with hardcoded "Every August" copy. Three
drift modes (PR #538 round-2 review): 20 newer topics evict the still-live
pinned event mid-event (backend orders by `-last_post_at`, no pinned boost);
the August copy persists into winter while the topic stays pinned; and the
window size silently diverges if ops tune `RECENT_TOPICS_MAX_LIMIT` down.
The slug+copy coupling was the PR 2.5 spec's locked decision — fine for
launch, wrong shape long-term.

## Findings

- Hero code: `web/src/pages/forum/CategoryListPage.tsx` (~167), constant
  `RECENT_TOPICS_FETCH_LIMIT` mirrors the backend default client-side.
- Backend has no notion of a "current event"; `is_pinned` is per-board
  ordering, not a sitewide flag.

## Recommended Action

1. Backend "current event" signal — smallest honest shape: either a
   `?pinned=1` filter on `topics/recent/`, or a tiny
   `forum/event/` endpoint returning the currently-featured topic (id,
   slug, title, hero copy fields) sourced from a Wagtail setting or an
   admin-pickable chooser.
2. Web: hero renders from that signal (topic title/copy from the API);
   fall back to the evergreen "Ask the canopy" hero when absent.
3. Retire the slug-prefix inference and the hardcoded seasonal copy.

## Acceptance Criteria

- [ ] Hero survives arbitrary forum activity while the event is live and
      disappears when the event is unfeatured — no recency-window coupling.
- [ ] Hero copy comes from data, not a client string tied to one seed slug.
- [ ] Evergreen fallback unchanged.

## Work Log

### 2026-08-15 - Filed

- Deferred out of PR #538's fix rounds: conflicts with nothing, but larger
  than a review one-liner and touches spec-locked copy. Cheap parts (window
  = server max, named constant) done in-PR.
