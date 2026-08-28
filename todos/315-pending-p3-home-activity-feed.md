---
status: pending
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

- [ ] Logged-in Home shows real recent activity (specifics decided during
      brainstorming for this todo).
- [ ] Logged-out Home is unchanged from PR 4's restyle.
- [ ] No new backend work beyond what's decided in Recommended Action step 1.

## Work Log

### 2026-08-16 - Filed

- Deferred out of Canopy PR 4 (`docs/superpowers/specs/2026-08-16-canopy-areas-design.md`
  §2, §8) to keep that PR a pure restyle with no new data dependencies.
