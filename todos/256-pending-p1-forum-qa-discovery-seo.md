---
status: pending
priority: p1
issue_id: "256"
tags: [forum, seo, search, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H6, H8, H9, M1, M5, M11, L8"
---

# Forum epic: Q&A, discovery & SEO

## Problem

Forum content cannot be found, shared, or crawled: search is undiscoverable and
its filters are decorative (actively misleading UI), the SPA has zero SEO
surface (crawlers and unfurlers get an empty div), there is no solved/accepted-
answer marking for what is fundamentally a plant-ID Q&A forum, no per-post
permalinks, and no tags. p1 epic from the 2026-07-11 forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

- **H6** — No solved/accepted-answer marking — the highest-value missing content
  feature for a plant-ID Q&A forum (`W/models/topics.py` anchor).
- **H8** — Search undiscoverable + decorative filters: nothing links to
  `/forum/search`; ThreadListPage renders a working-looking search form, sort
  select, and "Searching for: X" chip while `fetchThreads` destructures only
  `{board, cursor}` — same unfiltered list every time; SearchPage filters
  dropped by the service; backend 50-cap with no pagination/sort; tests mock
  `fetchThreads` and assert only chip UI, so nothing catches it
  (`web/pages/forum/ThreadListPage.tsx:28-30,187-241`,
  `web/services/forumService.ts:115-134,259-262`, `W/api/views.py:623-659`).
  3-way agent convergence.
- **H9** — Zero SEO surface: no per-route `document.title`/meta/OG anywhere in
  the SPA (static `<title>web</title>`), no sitemap, no RSS — link unfurlers and
  non-JS crawlers get an empty `<div id="root">` (`web/index.html:7`).
- **M1** — No quote-reply: BlockQuoteBlock exists in schema + renderer, but the
  composer can't produce it (nh3 flattens; toolbar omits) (`W/blocks.py:25`).
- **M5** — No tags/taxonomy beyond boards — species/genus/symptom tags are the
  natural discovery axis for this domain.
- **M11** — No per-post permalinks/share: DOM anchors exist but no copy-link
  control; async fetch means native hash-scroll silently no-ops; posts beyond
  page 1 aren't in the DOM at all (react-ts reviewer rates this High)
  (`web/pages/forum/ThreadDetailPage.tsx:82-117,366`).
- **L8** — `index.AutocompleteField("title")` declared on Topic but nothing
  calls `backend.autocomplete()` — dead index cost; wire a typeahead or drop it
  (`W/models/topics.py:67`; `.autocomplete()` API verified current).

## Recommended Action

1. **H6 solved marking**: `Topic.accepted_post` FK, settable by topic author +
   moderators (endpoint + capability flag), badge in lists/detail, "unsolved"
   filter.
2. **H8 search end-to-end**: wire filter/sort params through
   `forumService.fetchThreads` → backend (q, sort, board); add search
   pagination + sort server-side (kill the silent 50-cap — `has_more`
   contract); link search from forum nav; replace the mocked tests with
   service-level assertions that filters alter the request.
3. **L8 typeahead**: wire `backend.autocomplete()` into a lightweight
   suggest endpoint for the search box (or delete the field — decide here).
4. **H9 SEO**: per-route `document.title` + meta description; backend
   `wagtail.contrib.sitemaps` (ForumIndex/Board pages now serve — audit fix
   H17) + an RSS feed of live topics; OG tags for topic detail — evaluate a
   crawler-facing prerender path (Cloudflare) vs accepting JS-capable crawlers
   only, and record the decision.
5. **M11 permalinks**: copy-link control per post + a `/posts/{id}` resolver
   (returns topic + page/cursor position) + scroll-after-load handling.
6. **M1 quote-reply**: toolbar Quote button emitting the quote block; extend
   the nh3/composer contract accordingly (renderer preset tightening for quote
   blocks lives in todo 259 — coordinate the contract).
7. **M5 tags**: `TaggableManager` on Topic (django-taggit is a Wagtail
   dependency already) + tag filter UI; keep board taxonomy primary.

## Technical Details

- Search backend is already Postgres FTS with GIN indexes (audit H22 empirical
  result) — this epic is about exposure/wiring, not engine work.
- The audit fixed the search excerpt N+1 + dangling-HTML slice (H24) — search
  work here builds on `_plain_text_excerpt` in `W/api/views.py`.
- Sitemap needs live-only, public-only querysets — `ForumBoard.get_context`
  (added in audit fix H17) shows the filter shape.

## Acceptance Criteria

- [ ] Accepted answer settable by author/mod, visible in list + detail,
      filterable ("unsolved"); permission-tested
- [ ] Search reachable from forum navigation; changing filters/sort provably
      changes the request and results (unmocked service test)
- [ ] Search results paginated with an honest `has_more` (no silent 50-cap)
- [ ] Every forum route sets a descriptive title + meta; sitemap lists live
      topics/boards; RSS feed available; OG decision recorded
- [ ] Copy-link on a post lands a fresh visitor on the correct page + anchor
      (including posts beyond page 1)
- [ ] Quote-reply produces a block that round-trips composer → API → renderer
- [ ] Topics taggable with a working tag filter (or descope recorded)

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 7 open findings per the manifest's Phase 4 grouping table
  (user-approved: Q&A + discovery + SEO selected as a p1 theme).

## Notes

p1 by user triage decision. M11 was rated High by the react-typescript reviewer
(triage kept it Medium in the manifest but it should be scheduled early within
this epic).
