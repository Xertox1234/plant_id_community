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

- [x] A signed-in mobile user can submit a plant photo for diagnosis and see
      the result, reachable from the app's navigation. (completed 2026-09-27:
      `/diagnose`, from the Home "Diagnose a Sick Plant" card)
- [x] Widget tests cover the screen's loading, result and error states.
      (completed 2026-09-27: `test/features/diagnose/diagnose_test.dart`)
- [x] `python3 scripts/check_flutter_route_reachability.py` exits 0.
      (completed 2026-09-27)

## Work Log

### 2026-09-24 - Split from todo 385

### 2026-09-27 - Mobile Diagnose built

- API: the web's own (`web/src/services/diseaseService.ts`). A multipart
  `POST /plant-identification/disease-requests/` with `image_1`,
  `symptoms_description` and the optional `plant_condition` and `location`
  diagnoses synchronously, then `GET …/<uuid>/results/` reads the results.
  Both are `IsAuthenticated`, so `/diagnose` is a protected route.
- `lib/features/diagnose/`: `DiagnoseApi` (`HttpDiagnoseApi` on
  `ApiService.uploadFile`), a camera/gallery `DiagnoseImagePicker` with the
  backend's 10 MB cap checked before upload, and `DiagnoseScreen`.
- The screen shows the photo, the symptoms (required), a condition dropdown
  with the model's five choices, and location. It has a loading state (no
  double submit), result cards, the `system_message` notice, and "no
  diagnosis" and error states. A 429 gets its own copy; no raw exception text
  is shown.
- Entry point: a "Diagnose a Sick Plant" card on the Home grid; the route
  lives in the Home branch. Signed out, the tap goes to sign-in.
- `plant_condition` is a choices field. The web sends free text, so any
  non-key value is a 400; filed as todo 459. Mobile uses a dropdown.
- Tests: 11 diagnose tests and 2 Home → Diagnose reachability tests (signed
  in and signed out) on the production router. 9 mutations, all red.
