---
status: in_progress
priority: p3
issue_id: "315"
tags: [web, react, home]
dependencies: []
---

# Personalize Home with a real activity feed for logged-in users

## Problem

Canopy PR 4 restyled Home onto the new primitives (`HeroCard` + `Tile`/`Card`
feature row) but deliberately kept it a static marketing page — same hero and
three feature cards for every visitor, logged in or not. The parent spec's
per-area treatment (`docs/superpowers/specs/2026-08-13-canopy-design.md` §6)
called for "activity modules" on Home; PR 4's own spec
(`docs/superpowers/specs/2026-08-16-canopy-areas-design.md` §2) deferred that
explicitly to avoid scope creep — no new backend endpoints, no client-side
data composition, in a PR that was otherwise a pure restyle.

## Findings

- `web/src/pages/HomePage.tsx` has zero personalization today — no
  `useAuth()` branch, no data fetching beyond the static feature-card copy.
- The closest existing precedent for a personalized "recent activity"
  surface is the forum's `topics/recent/` endpoint (built in PR 2.5) and
  `me/stats/` (also PR 2.5) — either could seed a Home activity module
  without new backend work, or a genuinely new aggregation endpoint could be
  built (closer to how PR 2.5 added `me/stats` and `topics/recent`
  specifically for this kind of surface).
- Garden (`plantIdService.getMyPlants`) and Diagnose have no "recent"
  variant today — only full paginated history.

## Recommended Action

1. Decide the personalization split: reuse existing endpoints
   (`topics/recent/`, `me/stats/`) client-side, or add new aggregation
   (closer to `me/stats`'s shape) if a cross-domain "recent identifications +
   recent garden saves + recent forum activity" feed is wanted.
2. Home renders the activity modules only when `useAuth().isAuthenticated`
   is true; anonymous visitors keep the current static marketing hero and
   feature cards unchanged.
3. Follow the spec's brainstorming path for this (this is new scope, not a
   restyle) — brainstorm → design doc → plan, same as PR 4 itself.

## Acceptance Criteria

- [x] Logged-in Home shows real recent activity (specifics decided during
      brainstorming for this todo).
- [x] Logged-out Home is unchanged from PR 4's restyle.
- [x] No new backend work beyond what's decided in Recommended Action step 1.

## Work Log

### 2026-08-16 - Filed

- Deferred out of Canopy PR 4 (`docs/superpowers/specs/2026-08-16-canopy-areas-design.md`
  §2, §8) to keep that PR a pure restyle with no new data dependencies.

### 2026-09-02 - Started by completing-todos skill (run 2026-09-02-0458)

- Picked up by automated workflow.
- **Recommended Action step 1 decided by empirical check, not brainstorming.**
  The todo offered two branches: reuse the existing `topics/recent/` +
  `me/stats/` endpoints client-side, or build a new cross-domain aggregation
  endpoint. Grepped before designing:
  - `packages/wagtail_forum/wagtail_forum/api/urls.py:46,94` and
    `apps/forum_host/api_urls.py:95,153` — both endpoints are mounted.
  - `web/src/services/forumService.ts:559,564` — `fetchMyStats()` and
    `fetchRecentTopics(limit)` already exist and are typed
    (`ForumMyStats`, `RecentTopic` in `web/src/types/forum.ts:446,464`).
  - `web/src/pages/forum/CategoryListPage.tsx` already renders both shapes.

  Both endpoints exist, are wired, and are already rendered elsewhere, so the
  reuse branch is the one the todo pre-approved ("No new backend work beyond
  what's decided in Recommended Action step 1", AC3). That makes this a
  compose-existing-data pass, not new scope needing its own design round — no
  new endpoint, no new serializer, no backend diff at all.

### 2026-09-02 - Implemented (run 2026-09-02-0458)

**What shipped**

- **new** `web/src/components/home/HomeActivity.tsx` — the logged-in feed.
  Fetches `fetchMyStats()` and `fetchRecentTopics(5)` in one effect under a
  single `ignore` race guard, and renders two independently self-hiding
  sections: "Your season" (the four stat cards) and "Active now" (up to five
  recent topics in a Card, each row one `<Link>`, with an "All discussions →"
  link to `/forum`). Returns `null` when both halves are empty, so a still-
  loading, both-failed, or brand-new-install Home renders no empty shell and
  no spinner — this is a nice-to-have on top of the marketing page, never a
  dependency of it. Same fetch/ignore/self-hide shape as the forum rail
  modules.
- **new** `web/src/components/forum/SeasonStatsGrid.tsx` — the four-card
  "Your season" grid, extracted from `CategoryListPage` rather than copied.
  Home and the forum landing page now render one component; the tone/label/
  sublabel/badge-progress rules exist in exactly one place.
- `web/src/pages/HomePage.tsx` — `useAuth()` + `{isAuthenticated &&
  <HomeActivity />}`, placed between the hero and the feature-card row. Stale
  docstring ("no personalized activity feed (deferred, todo 308)" — wrong todo
  number too) rewritten.
- `web/src/pages/forum/CategoryListPage.tsx` — 48-line inline block replaced by
  `<SeasonStatsGrid stats={myStats} className="mt-6" />`; `Check`, `Flame` and
  `ScanSearch` dropped from the lucide import (the anonymous branch still uses
  `Layers`/`MessagesSquare`/`Reply`, which stay).

**Two design decisions worth naming**

1. *The gate is on mounting, not on rendering.* `HomeActivity` is only mounted
   when `isAuthenticated`, so an anonymous visitor's Home issues **zero** extra
   requests — AC2 is enforced at the network layer, not just visually, and the
   HomePage test asserts exactly that (`expect(fetchMyStats).not
   .toHaveBeenCalled()`).
2. *The insertion point is `gap-8`, not `space-y-8`.* Per `docs/rules/react.md`,
   adding a child to a Tailwind v4 `space-y-*` container silently gives the
   previous last child a trailing margin. HomePage's wrapper is
   `flex flex-col gap-8`, so inserting a sibling cannot shift any neighbour's
   spacing. Checked before writing the JSX, not after; noted inline so the next
   edit doesn't have to re-derive it.

**Verification**

AC1 — logged-in Home shows real recent activity:

```
$ ./node_modules/.bin/vitest run src/pages/HomePage.test.tsx \
    src/components/home/HomeActivity.test.tsx \
    src/components/forum/SeasonStatsGrid.test.tsx \
    src/pages/forum/CategoryListPage.test.tsx
 Test Files  4 passed (4)
      Tests  50 passed (50)
```

Covering, among the 50: "shows the logged-in activity feed for an authenticated
visitor" (both headings + a real topic link + the feature row still present),
"links each row to the topic and the section to the forum"
(`/forum/7-care-problems/42-monstera-leaf-curl`), "caps the list at five rows
even when the API returns more", and the three degradation cases (stats fails →
Active now survives; topics fails → Your season survives; both fail →
`toBeEmptyDOMElement`).

AC2 — logged-out Home unchanged: the two pre-existing HomePage tests (hero
headline/CTAs, three feature cards) pass **unmodified**, plus a new one that
asserts the negative at the network layer:

```
✓ renders no activity feed and issues no requests for an anonymous visitor
```

AC3 — no new backend work:

```
$ git diff --name-only HEAD -- . ':!web/' ':!todos/'
(empty)
$ git ls-files --others --exclude-standard | grep -v '^web/' | grep -v '^todos/'
(empty)
```

Zero files outside `web/` — no endpoint, no serializer, no migration. Both
feeds are pre-existing endpoints (`me/stats/`, `topics/recent/`) already
wired in `forumService.ts`.

No regressions — full web suite and type-check:

```
$ npx tsc --noEmit
TypeScript: No errors found
$ ./node_modules/.bin/vitest run
 Test Files  88 passed (88)
      Tests  1022 passed (1022)
$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # block-navigation.js, a coverage
                                          # artifact, pre-existing and untouched
```

The `CategoryListPage` "Your season" tests (4 of them, including the badge-
complete, singular-day-streak, zero-streak and stats-fetch-rejects edges) pass
unchanged through the extracted component — the refactor is behaviour-
preserving, which is the point of extracting rather than copying.

### 2026-09-02 - Code review + repair (run 2026-09-02-0458)

Bundled `/code-review high` over the working tree. Three findings, all real;
the two correctness ones are repaired, the third is recorded below.

**Finding 1 (MEDIUM) — repaired. An identity swap left the previous account's
stats on screen.** `isAuthenticated` is `!!user` (`AuthContext.tsx:424`,
verified), so it stays `true` across an identity change. React therefore reused
the `HomeActivity` instance, and its mount-once (`[]`) effect never refetched.
Concrete: tab 1 on `/` as account A; tab 2 logs out and in as B; focus tab 1 →
`revalidateIdentity()` (mounted unconditionally on focus for exactly this case,
todo 297) updates the header to B while "Your season" still shows A's posts,
solutions, streak and badge progress. Same class as the 2026-08-13 prod
incident 297 was written for. Fix: `key={user?.id}` on the mount, so an
identity change remounts and refetches instead of showing A's numbers under
B's name. Pinned by `refetches when the identity changes underneath a
still-authenticated session`, which rerenders with a different `user.id` and
asserts both fetches ran twice.

**Finding 2 (LOW/MEDIUM) — repaired. A stale session still fired both
requests.** `AuthProvider.initAuth` seeds `user` from `getStoredUser()`
(sessionStorage) *before* `getCurrentUser()` verifies with the backend, so a
visitor whose refresh cookie has expired briefly reads as authenticated. The
gate was `isAuthenticated` alone, so that visitor mounted the feed, fired
`me/stats/` (401) and `topics/recent/`, and could flash their stale numbers
before `setUser(null)` unmounted it — contradicting this todo's own AC2 claim
of zero extra requests. Fix: gate on `!isLoading && isAuthenticated`. Pinned by
`issues no requests while auth is still being verified`.

**Finding 3 (LOW) — accepted, not repaired. Layout shift on authenticated
Home.** The section sits above the feature-card row, so for a logged-in
visitor the marketing row renders first and is pushed down when the two
fetches resolve. The reviewer's two options are reserving height while in
flight, or moving the section below the feature grid. Not taken in this pass,
per `CLAUDE.md` → Review loop budget (round 1 repairs blocking findings only;
this one is LOW and is a layout-polish trade-off, not a correctness bug).
Reserving height means a guaranteed empty gap for the cases where the section
legitimately renders nothing; moving it below the marketing row defeats the
point of the todo, which is that a returning member sees their own activity
first. Recorded here and in the PR body rather than filed as a new todo —
whoever tunes Home's above-the-fold layout next should weigh it with the
skeleton question together.

**Not findings** (reviewer checked and dismissed): `ProgressBar` already guards
`max <= 0`; `boardIdentity()` has a `Leaf` fallback so an unknown board slug
cannot crash a row; the three dropped lucide imports are genuinely unused while
`Layers`/`MessagesSquare`/`Reply` are still needed; the `SeasonStatsGrid`
extraction changes only Tailwind class *order* on the `mt-6` wrapper, which has
no CSS effect; `AuthProvider` wraps `App` in `main.tsx:79`, so `useAuth()` in
HomePage cannot throw.

**Post-repair verification**

```
$ npx tsc --noEmit
TypeScript: No errors found
$ ./node_modules/.bin/vitest run
 Test Files  88 passed (88)
      Tests  1028 passed (1028)
$ npm run lint
ESLint: 0 errors, 1 warnings in 1 files   # block-navigation.js, pre-existing
```
