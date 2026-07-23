---
status: pending
priority: p2
issue_id: "276"
tags: [forum, web, drf, product-ux]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "M1, M5, M11, L8"
---

# Forum: content-authoring & discovery remainder (M1, M5, M11, L8)

## Problem

Split out of todo 256 on 2026-07-23 (user triage: "top-value slices only" —
256 retained H8 search + H9 SEO and was completed/archived; these four
lower-value or now-smaller findings moved here). Residual is stated against
**current `main`** (post Wave 1 #473 + the H8/H9 slices), not the original
2026-07-11 audit line numbers.

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `web` = `web/src`.

## Findings

- **M1** — No quote-reply: `BlockQuoteBlock` exists in schema + renderer, but the
  TipTap composer can't produce it (toolbar omits the control; nh3 sanitize
  contract must admit it) (`W/blocks.py`). **Coordinate the nh3 / renderer-preset
  contract with todo 259** (renderer preset tightening for quote blocks lives
  there).
- **M5** — No tags/taxonomy beyond boards — species/genus/symptom tags are the
  natural discovery axis for this domain. `TaggableManager` on `Topic`
  (django-taggit is already a Wagtail dependency) + migration + API serialization
  - a tag filter UI; keep board taxonomy primary.
- **M11** — Per-post permalink **copy-link control** only. NOTE: Wave 1 (#473)
  already shipped the deep-link chase + scroll-after-load (posts beyond page 1
  are pulled in and scrolled to — `web/pages/forum/ThreadDetailPage.tsx`
  arrival effect + `collectAllPosts`). The residual is just a copy-link button
  per post (build `…/forum/{cat}/{thread}#post-{id}` from the current thread
  URL). A `/posts/{id}` resolver is optional — the client-side chase already
  lands a fresh visitor correctly.
- **L8** — `index.AutocompleteField("title")` declared on `Topic` (`W/models/topics.py:67`)
  but nothing calls `backend.autocomplete()` — dead index cost. **Decide here**:
  wire a lightweight typeahead suggest endpoint for the search box, or drop the
  field. (The `searchForumUsers` @mention typeahead at `forumService.ts` is the
  wiring pattern if kept.)

## Recommended Action

1. **M11 copy-link** (smallest, do first): copy-link control per post in
   `PostCard`; builds the deep-link from the current thread URL + `#post-{id}`;
   relies on the existing Wave-1 chase to land the visitor.
2. **L8**: decide typeahead-vs-delete and record the rationale; wire or remove.
3. **M5 tags**: `TaggableManager` on Topic + migration + API + tag filter UI.
4. **M1 quote-reply** (last): TipTap toolbar Quote button emitting the quote
   block; extend the nh3/composer contract; coordinate with todo 259.

## Acceptance Criteria

- [ ] Copy-link on a post lands a fresh visitor on the correct page + anchor
      (including posts beyond page 1 — reuse the Wave-1 chase)
- [ ] Quote-reply produces a block that round-trips composer → API → renderer
- [ ] Topics taggable with a working tag filter (or descope recorded)
- [ ] L8 typeahead wired OR `AutocompleteField` removed — decision recorded

## Work Log

### 2026-07-23 - Created by splitting todo 256

- Todo 256 (Q&A/discovery/SEO epic) re-scoped by user to H8 (search) + H9 (SEO)
  only; H6 (solved marking) had already moved to todo 273 (Wave 2). These four
  findings (M1/M5/M11/L8) split here. M11 reduced to copy-link-only because Wave 1
  (#473) shipped the deep-link chase.
