---
status: pending
priority: p3
issue_id: "385"
tags: [mobile, flutter, feature-parity]
dependencies: []
source_review: "todos/384-pending-p1-mobile-navigation-shell-missing.md"
---

# Mobile has no Blog or Diagnose; the web has both

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

- [ ] A decision is recorded on whether each belongs on mobile at all — parity
      with web is a reason, not a requirement
- [ ] If built: routes registered, screens implemented, and each reachable —
      `python3 scripts/check_flutter_route_reachability.py` must still exit 0
- [ ] If built: a destination is added to `MainShell.destinations`, or the
      screen nests under an existing tab with a documented entry point.
      Note the shell is at **four tabs plus a centre action**; a fifth tab is
      the iOS convention limit and would force a "More" tab

## Notes

p3: nothing is broken. This is absent functionality, not a defect — unlike
todo 384, where the UI existed and could not be opened.
