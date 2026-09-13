---
status: pending
priority: p1
issue_id: "384"
tags: [mobile, flutter, navigation, ux]
dependencies: []
---

# The mobile app has no primary navigation: ~16.8k lines of UI are unreachable

## Problem

The Flutter app ships **no navigation shell**. From the Home screen exactly two
destinations are reachable: Settings, and Identify -> Results. Everything else
that has been built — the forum, garden, collection, care, profile, and the
entire auth flow — is routed, compiled, and reachable from nothing.

Found 2026-09-12 by the owner opening TestFlight build 5, the first build that
has ever rendered a working screen on a device (see todo 383 items 8-11). The
owner's words: *"I do not see any way to log in or do anything else for that
matter"*, then *"this problem is bigger than that. The whole UI is missing."*

That framing is correct and the first diagnosis filed here was not: this was
initially read as a missing login button, which would have been a one-word fix
plus a Settings entry. That would have unblocked sign-in and left ~16,800 lines
stranded. The inventory below was produced only after the owner pushed back.

**Why it surfaced now, not earlier.** Builds 1-3 never got past Firebase init
and never drew a screen; build 4 drew one but `GrainOverlay` painted an opaque
sheet over it. Build 5 is the first build anyone could actually navigate. Each
fixed defect exposed the next.

## Findings

### CORRECTION (2026-09-12, during implementation)

**Findings 1 and 2 below are WRONG and are kept only for the record.** Findings
3, 4 and 5 survive as written. What was actually true:

- **forum, care and collection were already reachable.** `home_page.dart:183`
  dispatches `context.go(feature.route)` for four feature cards, with `route:`
  set at `:144/:152/:160/:168`. The forum's 14.7k lines were never stranded.
  The checker could not see it: it matched only a literal
  `context.<verb>(AppRoutes.X)`, so a route passed through a variable — or
  reached by `pushNamed('forumBookmarks')`, as the whole forum sub-tree is —
  was invisible. It reported **7 false orphans**. Fixed in PR #734.
- **The genuinely unreachable set was `garden`, `profile`, `register`** (and
  `login` transitively, reachable only from the orphaned profile screen).
- **`app_theme.dart:144` does NOT theme the shell's nav bar.** It is
  `BottomNavigationBarThemeData` — the Material 2 widget. There was no
  `navigationBarTheme`. The claim in Recommended Action #2 was false.
- **`login`, `register` and `garden` had no screens at all**, only
  `PlaceholderScreen`. So "make login reachable" required *building* it. That,
  not the shell, is what answered the owner's actual complaint.
- **AC 3's premise is false.** `forumGroups` is a redirect guard prefix for
  `/forum/groups/:id` (todo 350), not a destination; both its children are
  registered and no group-list screen exists. Registering it would point at
  nothing, and removing it from `protectedPrefixes` would un-protect group DM
  threads. Resolved a third way: the checker now reports it as a prefix via
  `PREFIX_CONSTANTS`, with a reason.

Shipped as **#734** (checker) and **#735** (shell + auth screens). Device
verification is the remaining step.

### 1. 12 of 17 routes have no inbound navigation — SUPERSEDED, see correction above

**Re-run this rather than trusting the table below:**
`python3 scripts/check_flutter_route_reachability.py`
(exit 0 all reachable / 1 orphans found / 2 could not analyse). It parses
`AppRoutes` against every `context.go/push/replace/*Named` in `lib/`. It reports
**11 unreachable** — the twelfth, `splash`, is `initialLocation` and is entered
by the router itself, so it is an allowed orphan carrying a written reason.
Today it exits 1, and it was mutation-checked: allowing every route flips it
to 0, so the verdict really is driven by reachability.

| route | path | registered | navigated to from |
|---|---|---|---|
| `splash` | `/` | yes | — (initialLocation only) |
| `home` | `/home` | yes | splash, push router service |
| `camera` | `/camera` | yes | home (**`go`**), collection |
| `results` | `/results` | yes | camera |
| `settings` | `/settings` | yes | home (`push`) |
| `login` | `/login` | yes | **profile only — and profile is itself orphaned** |
| `register` | `/register` | yes | **NOTHING** |
| `profile` | `/profile` | yes | **NOTHING** |
| `collection` | `/collection` | yes | **NOTHING** |
| `garden` | `/garden` | yes | **NOTHING** |
| `care` | `/care` | yes | **NOTHING** |
| `forum` | `/forum` | yes | **NOTHING** |
| `forumBookmarks` | `/forum/bookmarks` | yes | **NOTHING** |
| `forumMessages` | `/forum/messages` | yes | **NOTHING** |
| `forumNotifications` | `/forum/notifications` | yes | **NOTHING** |
| `forumNewGroup` | `/forum/groups/new` | yes | **NOTHING** |
| `forumGroups` | `/forum/groups` | **NO** | **NOTHING** |

`forumGroups` is declared and used as a protected prefix by the router's
`redirect`, but never registered as a `GoRoute` — so anything that did reach it
would fail.

### 2. The orphaned features are finished work, not stubs

| feature | files | lines |
|---|---|---|
| forum | 58 | **14,731** |
| garden | 5 | 918 |
| profile | 1 | 612 |
| collection | 1 | 376 |
| care | 1 | 139 |

**~16,776 lines** of built UI with no way to open it.

> SUPERSEDED: most of this was reachable from the Home feature grid. Only `profile` (612 lines) was genuinely orphaned. See the correction above.

### 3. No navigation shell exists anywhere

`BottomNavigationBar`, `NavigationBar`, `NavigationRail`, `TabBar`, `Drawer`,
`ShellRoute` and `StatefulShellRoute` are **never instantiated** anywhere in
`lib/`. The single match in the tree is `lib/core/theme/app_theme.dart:144`,
which defines a `bottomNavigationBarTheme` — the app has *styling* for a
navigation bar that was never built. That theme is the strongest evidence the
shell was always intended and simply never landed.

### 4. Sign-in is structurally unreachable

`login` is navigated to from exactly one place, `profile_screen.dart:591`, and
nothing navigates to `profile`. The router's `redirect` sends unauthenticated
users to `/login` only when they hit a protected route
(`forumMessages`, `forumGroups`) — both unreachable. `register` has no inbound
navigation at all. So there is no path from app launch to authentication.

This blocks todo 383 AC 5 (sign-in verified on a physical device): the criterion
cannot be met, not because the build is wrong, but because the app offers no way
to attempt it.

### 5. Home -> Identify strands the user

`home_page.dart:199` uses `context.go(AppRoutes.camera)`. `go` **replaces** the
navigation stack, so `Navigator.canPop()` is false and the `AppBar` on
`camera_screen.dart:175` draws no back button. Force-quitting is the only exit.
Confirmed against a device screenshot. The settings FAB two lines earlier
(`home_page.dart:29`) correctly uses `context.push`, so this is an inconsistency
rather than a convention.

## Proposed information architecture — DRAFT, needs the owner's correction

This is drafted from what exists in `lib/features/` plus the web app's route
table, which is the closest thing to a stated product IA. **It is a proposal, not
a decision** — which destinations are top-level is a product call.

The web app (`web/src/App.tsx`) routes: `/`, `/identify`, `/my-plants`,
`/diagnose`, `/forum` (+search, threads, users, new-thread), `/messages`,
`/blog`, `/profile`, `/settings`, `/login`, `/signup`.

Proposed mobile shell — `StatefulShellRoute.indexedStack` with a Material 3
`NavigationBar`, five destinations (iOS convention caps at five before a "More"
tab):

| # | tab | route | nests |
|---|---|---|---|
| 1 | Home | `/home` | — |
| 2 | Identify | `/camera` | `/results` |
| 3 | My Plants | `/collection` | `/garden`, `/care` |
| 4 | Forum | `/forum` | `/forum/bookmarks`, `/forum/messages`, `/forum/notifications`, `/forum/groups`, `/forum/groups/new` |
| 5 | Profile | `/profile` | `/settings`, `/login`, `/register` |

Rationale, so it can be argued with:

- **My Plants** matches the web's `/my-plants`. `garden` and `care` are
  plant-management surfaces, so they nest rather than claim tabs of their own.
- **Forum** is by far the largest feature (14.7k lines) and owns its own
  sub-navigation already; messages and notifications nest under it rather than
  competing for top-level slots.
- **Profile** is where `login`/`register` become reachable — signed-out, the tab
  shows the auth entry. That fixes finding 4 without inventing a new screen.
- **Settings** moves under Profile. The existing Home FAB can stay as a shortcut
  or be dropped; it is currently the only reason Settings is reachable at all.

### Open questions the owner must answer

1. **Is Identify a tab, or a center action button?** It is the app's core verb.
   A tab is simpler; a prominent center FAB is the common pattern for a
   capture-first app and matches the current Home CTA.
2. **Does `/messages` deserve a top-level tab?** The web treats it as top-level,
   not nested under forum. If yes, something else must nest or move.
3. **Blog and diagnose exist on web but not in the mobile routes at all.**
   Out of scope, or missing features to file separately?
4. **What should an unauthenticated user see?** Current redirect protects only
   forum messages/groups. Should Home, Identify, Collection be usable
   signed-out (and the backend's `DEBUG`-gated anonymous identify allows it)?
5. **Is Garden distinct from Collection**, or are they the same idea built twice?

## Recommended Action

1. Owner corrects the IA above, or replaces it.
2. Build the `StatefulShellRoute.indexedStack` shell with a `NavigationBar`,
   wired to the agreed destinations. `app_theme.dart` already themes it.
3. Register the missing `forumGroups` route (finding 1).
4. Change `home_page.dart:199` `context.go` -> `context.push` (finding 5).
5. Make `login`/`register` reachable and verify the signed-out path end to end.
6. Verify on a device, not a simulator — the whole reason this was missed is that
   nothing had ever been navigated on real hardware.

## Acceptance Criteria

- [x] A primary navigation shell exists and every top-level destination in the
      agreed IA is reachable from a cold launch (#735)
- [x] Zero routes in `AppRoutes` are reachable from nothing, or each remaining
      orphan is deliberately documented as intentionally unreachable
      (#734/#735 — checker exits 0; `garden` documented in `ALLOWED_ORPHANS`)
- [ ] `forumGroups` is registered as a route, or removed from `AppRoutes` and
      from the router's protected-prefix set
      → **NOT checked off: the premise is false and neither branch is correct.**
      Resolved instead by reporting it as a guard prefix (#734). Left open
      deliberately rather than falsified — see the correction above.
- [ ] A signed-out user can reach sign-in and register from a cold launch, and
      sign-in succeeds against production (this also discharges todo 383 AC 5)
      → half done: LoginScreen and RegisterScreen built and reachable from the
      Profile tab, asserted by `navigation_shell_test.dart` (#735). The
      **against production** half needs TestFlight build 6 on a device.
- [x] Identify no longer strands the user: it can be left without force-quitting
      (#735 — `canPop()` asserted in `navigation_shell_test.dart`)
- [ ] A test asserts reachability rather than existence — the route inventory in
      finding 1 is re-runnable and fails when a destination becomes orphaned.
      Note the lesson from todo 383 item 11: `find.text` proves a widget is in
      the TREE, not that a user can get to it or see it

## Notes

p1, not p2: the app is installed on TestFlight and cannot be used for its stated
purpose. Nothing here is a security exposure, but it blocks todo 383 AC 5 and
blocks any further device testing.

The route inventory in finding 1 is `scripts/check_flutter_route_reachability.py`,
committed rather than left in a scratchpad — todo 383's work log records the cost
of the opposite (*"an instruction pointing at a vanished script is not
tracking"*). It is the check that would have caught this at any point in the last
several months, and it is a manual tool, not a CI gate: today it exits 1 by
design, so wiring it into CI before the shell exists would just block every PR.

Routing note: `python3 scripts/inject/route_domains.py` puts the script in
`security` only. There is no `*flutter*` filename glob the way there is a
`*firebase*` one, so write-time injection will not surface `docs/rules/flutter.md`
when editing it. Checked rather than assumed.
