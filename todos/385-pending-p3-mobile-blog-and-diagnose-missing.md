---
status: pending
priority: p3
issue_id: "385"
tags: [mobile, flutter, feature-parity]
dependencies: []
source_review: "todos/384-mobile-navigation-shell-missing"
---

# Mobile has no Blog (Diagnose split to todo 444)

## Problem

`web/src/layouts/AppShell.tsx:39-46` lists six top-level destinations:
Home, Identify, Forum, **Blog**, My garden, **Diagnose**. The Flutter app has
routes and screens for four of them. Blog and Diagnose have **no mobile route,
no screen and no model** — they were never started, as opposed to built and
left unreachable.

Found while building the navigation shell (todo 384). The owner's call at the
time was "out of scope for the shell, file separately" — this is that file, so
the gap is recorded rather than rediscovered.

## Context

Backends already exist for both:

- Blog — `backend/apps/blog/` (Wagtail CMS + AI content generation), consumed
  by the web app at `/blog` and `/blog/:slug`.
- Diagnose — the web's `/diagnose` (`DiseaseDiagnosePage`) is auth-protected
  and sits behind the plant-identification app.

So this is client work, not new API work. Confirm the endpoints before
estimating; neither was checked in depth here.

## Acceptance Criteria

- [x] A decision is recorded on whether each belongs on mobile at all — parity
      with web is a reason, not a requirement (completed 2026-09-24: owner
      decision, build both; Diagnose moved to todo 444)
- [x] If built: routes registered, screens implemented, and each reachable —
      `python3 scripts/check_flutter_route_reachability.py` must still exit 0
      (completed 2026-09-27: `/blog` + `/blog/:slug`; checker exits 0)
- [x] If built: a destination is added to `MainShell.destinations`, or the
      screen nests under an existing tab with a documented entry point.
      (completed 2026-09-27: nested under Home; the "Plant Journal" feature
      card is the entry point)
      Note the shell is at **four tabs plus a centre action**; a fifth tab is
      the iOS convention limit and would force a "More" tab

## Notes

p3: nothing is broken. This is absent functionality, not a defect — unlike
todo 384, where the UI existed and could not be opened.

## Work Log

### 2026-09-24 - Owner decision: build both, as two slices (gate removed)

The owner wants both built, as separate slices. **This todo is now the Blog
slice** (mobile `/blog` list + `/blog/:slug` detail against the existing
Wagtail API). **Diagnose moved to todo 444.** Ready for a sweep.

### 2026-09-27 - Mobile blog built (Blog slice)

- `lib/features/blog/`: models for the v2 list and detail payloads, an
  `HttpBlogApi` on the app's `ApiService` (absolute `/api/v2` URLs from the
  base URL's origin), `blogPostsProvider(tag)` with offset `loadMore`, and
  `blogPostProvider(slug)`.
- Detail fetch is two requests, like the web: the list route resolves the
  slug, and the id-addressed detail route has the body.
- Screens: `BlogListScreen` (`/blog`, optional `?tag=`) and `BlogPostScreen`
  (`/blog/:slug`). Blocks render heading, paragraph, quote, code, plant
  spotlight (with its required photo credit) and call to action. Unknown
  blocks are skipped. Rich text goes through `ForumHtmlText`, so no raw
  markup is ever rendered.
- Links: a relative `/blog/<slug>` opens in the app; anything else goes
  through the forum allowlist (absolute http/https) to the in-app browser.
- Media URLs are rebased like the web's `mediaUrl`: relative and `/media/`
  paths go onto the API origin; R2 URLs pass through.
- A 4xx is not retried. Riverpod 3 otherwise retries for about 40 s behind a
  spinner, so a deleted post never said it was gone.
- Entry point: a "Plant Journal" card on the Home feature grid; the routes
  live in the Home branch and keep the nav bar.
- Tests: 17 blog tests plus a Home → Plant Journal → post reachability test
  on the production router; 7 mutations all red. Full suite: 854 passed.
