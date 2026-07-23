---
status: in_progress
priority: p1
issue_id: "256"
tags: [forum, seo, search, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H8, H9"
---

# Forum epic: Q&A, discovery & SEO

> **RE-SCOPED 2026-07-23** (user triage: "top-value slices only"). This todo now
> covers only **H8 (search end-to-end)** and **H9 (SEO surface)** — the two High
> findings — delivered as per-slice PRs off fresh `main`. Descoped:
>
> - **H6** (solved/accepted answer) → moved to **todo 273** (Wave 2, slice 2) per
>   the app-loop roadmap's "Todo bookkeeping" — it was never mine to do.
> - **M1, M5, M11, L8** → split into new **todo 276**.
>
> Residual below is stated against **current `main`** (post Wave 1 #473); the
> original audit line numbers described pre-Wave-1 state and are stale.

## Problem

Forum content cannot be found or crawled: `/forum/:board` renders a search form
and sort select that don't drive any request (decorative, actively misleading),
the dedicated `/forum/search` page has no pagination and a silent 50-cap, and
the SPA has zero SEO surface (crawlers and unfurlers get an empty `<div>`).

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

- **H8** — Decorative filters + capped search. Wave 1 (#473) added the header
  search link (`/forum/search` — no longer undiscoverable). Still broken:
  ThreadListPage's sort select + search form drive nothing (`fetchThreads`
  destructures only `{board, cursor}` — `web/services/forumService.ts:126`);
  `SearchView` caps topics+posts at `MAX_RESULTS = 50` each with no pagination
  or `has_more` (`W/api/views.py` SearchView); `forumService` tests mock the
  service and assert only chip UI, so nothing catches the dead filters.
- **H9** — Zero SEO surface: no per-route `document.title`/meta/OG anywhere in
  the SPA (static `<title>web</title>`, `web/index.html:7`), no sitemap, no RSS.

## Recommended Action

1. **H8 search end-to-end** (slice 1): wire a `sort` param through
   `forumService.fetchThreads` → `TopicListView`/`TopicCursorPagination`
   `get_ordering` (the 5 UI sort options); make the ThreadListPage search box
   honest (submit → `/forum/search?q=…&category={board}`, drop the dead chip);
   add pagination + an honest `has_more` to `SearchView` (kill the silent
   50-cap); replace the mocked service tests with unmocked assertions that
   sort/filters alter the outgoing request.
2. **H9 SEO** (slice 2): per-route `document.title` + meta description (React 19
   native document metadata or a tiny head hook); backend
   `wagtail.contrib.sitemaps` for live topics/boards + an RSS feed of live
   topics; OG tags for topic detail. **OG decision:** accept JS-capable crawlers
   - serve sitemap/RSS/meta (cheap correct path) rather than a Cloudflare
   prerender — record rationale in the work log.

## Technical Details

- Search backend is already Postgres FTS with GIN indexes (audit H22 empirical
  result) — this epic is about exposure/wiring, not engine work.
- The audit fixed the search excerpt N+1 + dangling-HTML slice (H24) — search
  work here builds on `_plain_text_excerpt` in `W/api/views.py`.
- Sitemap needs live-only, public-only querysets — `ForumBoard.get_context`
  (added in audit fix H17) shows the filter shape.

## Acceptance Criteria

_(H8 + H9 only — see the re-scope note at the top. H6 → todo 273; M1/M5/M11/L8 → todo 276.)_

- [x] **H8** Search reachable from forum navigation (Wave 1); changing sort/filters
      provably changes the outgoing request (unmocked service test) — done slice 1
- [x] **H8** Search results paginated with an honest `has_more` (no silent 50-cap) — done slice 1
- [ ] **H9** Every forum route sets a descriptive title + meta; sitemap lists live
      topics/boards; RSS feed available; OG decision recorded

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 7 open findings per the manifest's Phase 4 grouping table
  (user-approved: Q&A + discovery + SEO selected as a p1 theme).

### 2026-07-23 - Started + re-scoped by completing-todos skill (run 2026-07-23-0217)

- Orientation found the todo's line citations were pre-Wave-1 (#473 merged
  2026-07-15, after this todo was written): header search link now exists; the
  deep-link-past-page-1 chase + scroll is already shipped (M11 reduced to
  copy-link-only).
- **H6 descoped**: the app-loop roadmap's "Todo bookkeeping" says solved answers
  moved to the Wave 2 epic (todo 273, slice 2). The audit's `#H6 → todo 256`
  line was stale; re-pointed to 273.
- **User triage** ("top-value slices only"): retain H8 + H9 here (2 slices);
  split M1/M5/M11/L8 into new todo 276.
- Slice 1 = H8 search end-to-end (branch `forum-256-h8-search`).

### 2026-07-23 - Slice 1 (H8) implemented + verified

- **Backend**: `TopicCursorPagination.get_ordering` maps a whitelisted `?sort=`
  (the 5 ThreadListPage select options) to a deterministic ordering (pinned-first,
  id tiebreak); an unknown value falls back to default (no 500). `SearchView`
  replaced the silent `MAX_RESULTS=50` cap with `PAGE_SIZE=20` windowed paging
  (`[offset:offset+SIZE+1]` lookahead) + `topics_has_more`/`posts_has_more`/`page`.
- **Web**: `fetchThreads` appends `?sort=` on first-page requests (cursor requests
  pass through unchanged — the cursor already encodes ordering). ThreadListPage
  sort select re-fetches with the new sort; the search box now redirects to
  `/forum/search?q=…&category={board}` (honest — the decorative chip/param is
  gone). `searchForum` sends `?page=` (>1) and parses `has_more_*`; SearchPage
  gained a "Load more results" button. Replaced the tautological mocked tests with
  unmocked service-level assertions (sort/page alter the request).
- **Verification**:
  - `npm run type-check` → clean (`tsc --noEmit`, no errors).
  - `npx vitest run` (full web suite) → `Test Files 47 passed`, `Tests 649 passed`, exit 0.
  - Backend `pytest test_search_sync.py test_topics_list.py --create-db` → `33 passed`.
  - Backend `pytest forum_host/tests/test_ratelimits.py test_schema_429.py wagtail_forum/tests/api/ --create-db` → `223 passed`.
  - `manage.py check` → "no issues"; `manage.py spectacular` → schema OK.

### 2026-07-23 - Slice 1 (H8) code review + fixes

- Reviewed by 4 domain reviewers (django-drf, react-typescript, cross-cutting,
  wagtail) + an advisor pass. **No critical/high; security clean** (board
  visibility intact, `page` guarded, `?sort=` is a closed-dict lookup).
- Fixes applied (all low/medium findings worth closing):
  - **Race guards** (react-ts M): ThreadListPage + SearchPage now use a
    generation ref so a stale sort/query response can't append old rows or
    corrupt the cursor/page counter (mirrors ThreadDetailPage's guard).
  - **Wasted re-fetch** (react-ts/cross-cutting M): ThreadListPage caches the
    resolved category, so a pure sort change no longer re-fetches the boards list.
  - **Honest copy** (react-ts/cross-cutting): search summary "Found N" →
    "Showing N … (more below)" — a per-page count no longer masquerades as a total.
  - **Offset-drift dedup** (wagtail L): SearchPage dedups by id on Load More;
    SearchView documents the tradeoff + `page` capped at `MAX_PAGE=50`.
  - **Docs** (cross-cutting/django-drf L): TopicListView schema lists `?sort=`
    values; pagination.py records the sort-field index scale tradeoff.
  - **Test coverage**: added the untested `has_more_posts` Load-More operand,
    a cursor-stability-across-pages test, a page-cap test, and the page-identity
    (disjoint + union) assertion (cross-cutting verified stable via the `-pk`
    tiebreak).
- Re-verified: web **650 tests** pass + `tsc` clean; backend **225** forum-api
  tests pass; `spectacular` schema OK.

## Notes

p1 by user triage decision. M11 was rated High by the react-typescript reviewer
(triage kept it Medium in the manifest but it should be scheduled early within
this epic).
