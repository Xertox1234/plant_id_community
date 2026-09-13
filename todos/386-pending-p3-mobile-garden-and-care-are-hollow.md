---
status: pending
priority: p3
issue_id: "386"
tags: [mobile, flutter, dead-code]
dependencies: []
source_review: "todos/384-pending-p1-mobile-navigation-shell-missing.md"
---

# `/garden` is dead code and `/care` is a stub that promises navigation

## Problem

Two mobile surfaces look finished from the route table and are not.

### 1. `garden` — 918 lines of models nothing references

`AppRoutes.garden` renders `PlaceholderScreen(title: 'Garden')`. Behind it,
`lib/features/garden/models/` holds five files — `GardenBed`, `GardenPlant`,
`CareTask`, `WeatherData`, plus a barrel — each documented as mapping to
`backend/apps/garden_calendar/models.py`.

Verified during todo 384: grepping `GardenBed|GardenPlant|CareTask|WeatherData`
across `lib/` **excluding** `lib/features/garden/models/` returns **zero hits**,
and zero across `test/`. No screen, provider, service, widget or test. The five
files reference nothing but each other.

It is deliberately **not** a shell destination — there is nothing to show — and
carries a documented entry in the reachability checker's `ALLOWED_ORPHANS`.
Remove that entry when the feature lands.

### 2. `care` — a chevron that does nothing

`CareScreen` (`lib/features/care/care_screen.dart`) says so itself at `:5-6`:
*"Plant care guides hub (stub)"*. It renders four hardcoded category cards and
the footer "Full care guides coming soon".

`_CategoryCard` (`:107-138`) builds a `ListTile` with
`trailing: Icon(Icons.chevron_right)` at `:135` and **no `onTap`**. So it
renders the standard affordance for "this navigates" and does nothing when
tapped. It is reachable from the Home feature grid, so users will hit it.

## Recommended Action

Independent, either order:

1. **Care** (small): either drop the chevron so the cards stop promising
   navigation, or build the guides behind them. Dropping it is honest and
   costs one line.
2. **Garden** (large): build the garden-calendar feature against
   `apps/garden_calendar`, or delete the five model files and the `/garden`
   route. Do not leave it as-is — a route to a placeholder is exactly the
   declared-but-unreachable shape todo 384 was filed about.

## Acceptance Criteria

- [ ] `care`'s cards either navigate or stop showing a chevron
- [ ] `garden` is either built and wired into the shell, or removed along with
      its route, its models and its `ALLOWED_ORPHANS` entry
- [ ] `python3 scripts/check_flutter_route_reachability.py` still exits 0

## Notes

p3 for garden (invisible to users — unreachable), but the `care` chevron is a
live papercut on a reachable screen and is a one-line fix.
