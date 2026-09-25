---
status: pending
priority: p3
issue_id: "444"
tags: [mobile, flutter, feature-parity]
dependencies: []
source_review: "todos/385-pending-p3-mobile-blog-and-diagnose-missing.md"
---

# Mobile has no Diagnose; the web has one

## Problem

Split from todo 385 on 2026-09-24 (owner: build both, as two slices). The web
has an auth-protected `/diagnose` (`DiseaseDiagnosePage`) behind the
plant-identification app. The Flutter app has no route, screen or model for it.

## Recommended Action

Confirm the diagnosis API the web page calls, then add a mobile `/diagnose`
route + screen reachable from the nav shell (todo 384), reusing the camera /
image picker the identify flow already has. Keep
`scripts/check_flutter_route_reachability.py` at exit 0.

## Acceptance Criteria

- [ ] A signed-in mobile user can submit a plant photo for diagnosis and see
      the result, reachable from the app's navigation.
- [ ] Widget tests cover the screen's loading, result and error states.
- [ ] `python3 scripts/check_flutter_route_reachability.py` exits 0.

## Work Log

### 2026-09-24 - Split from todo 385
