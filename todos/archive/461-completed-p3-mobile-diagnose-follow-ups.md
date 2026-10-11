---
status: completed
priority: p3
issue_id: "461"
tags: [mobile, flutter, diagnosis, follow-up]
dependencies: []
source_review: "todos/archive/444-completed-p3-mobile-diagnose-missing.md"
triage: ready
triaged: 2026-10-10
owner_decision: "Raise the receive timeout above 60s per request (Options override) for the diagnose/identify uploads only; the Dio client default stays 30s (2026-10-10)"
---

# Mobile Diagnose: non-blocking follow-ups from the PR #857 review

## Problem

Round 1 of the PR #857 review (todo 444) found two blocking issues, both
fixed in the PR: unbounded photo picks, and the missing iOS camera and
photo-library usage strings. The non-blocking findings are listed here
instead of a third round.

## Findings

Paths are under `plant_community_mobile/lib/features/diagnose/`.

- **Stale results** (`diagnose_screen.dart` `_pick`): a new photo or edited
  symptoms clear the error but not `_outcome`, so the old diagnosis stays
  under the new inputs until the user taps Diagnose.
- **Preview decode** (`diagnose_screen.dart`): `Image.file` decodes the full
  picked bitmap for a small preview. Pass `cacheWidth`.
- **Timeout vs a synchronous diagnosis:** Dio's `receiveTimeout` is 30 s, but
  the server's plant.health call allows 60 s (`plant_health_service.py`). A
  slow diagnosis is finished and billed on the server while the app says
  "unavailable", and a retry spends the 5/min rate limit. The identify flow
  has the same gap.
- **`pending` / `processing`** (`diagnose_api.dart` `DiagnosisOutcome.failed`):
  both are unreachable today because `perform_create` diagnoses
  synchronously. The day the view's "enqueue a Celery task" TODO ships, the
  screen shows an empty result. Poll `status/` or document the coupling.
- **After sign-in:** signing in from the `/diagnose` redirect lands on
  `/profile`, not back on Diagnose. This matches `/garden`'s documented
  design.
- **EXIF:** image_picker keeps EXIF (GPS included) in the upload, the same as
  identify. Whether imagekit strips it server-side is unverified.
- **Test gaps:**
  - the result fixture never uses `severity_assessment`,
    `symptoms_identified` or `immediate_actions`;
  - no screen test shows the chosen condition and the trimmed location
    reaching `diagnose()`;
  - the real multipart path is never exercised.
- **Android HEIC** (round 2): image_picker_android copies a HEIC gallery
  pick as `*.heic` (`FileUtils.java`), and the resized file keeps the name
  although it is now JPEG. The upload uses the path's basename
  (`api_service.dart` `uploadFile`), and the backend refuses a `.heic`
  extension. This predates the resize fix. Send a `.jpg` filename.
- **Nit:** `home_page.dart`'s doc comment still counts "4 feature cards".

## Acceptance Criteria

- [x] A new photo or edited symptoms clear the previous result.
- [x] The preview decodes at display size.
- [x] The client timeout covers a slow synchronous diagnosis, or the flow
      moves to create-then-poll.
- [x] `pending`/`processing` are handled or the coupling is documented.
- [x] The EXIF question is answered (strip on the server, or record why not).
- [x] An Android HEIC pick uploads with a `.jpg` name.
- [x] The test gaps above are covered.

## Work Log

### 2026-10-10 - Implemented by the todo sweep (run 2026-10-11-0053)

- A new photo, edited symptoms, a new condition or an edited location clear the previous result and error; the listeners compare the text, so a cursor move does not. The preview decodes at its laid-out width (`cacheWidth` from a `LayoutBuilder`, `previewCacheWidth`).
- Timeout (owner decision 2026-10-10): `ApiService.uploadFile` takes a per-request `receiveTimeout` and a `filename`; the diagnose and identify uploads pass `slowAnalysisReceiveTimeout` (90 s, above plant.health's 60 s and identify's 35 s + 20 s); the client default stays 30 s. The other `uploadFile` overrides in the tests took the new signature only.
- `pending` / `processing`: `DiagnosisOutcome.inProgress` makes the screen say the diagnosis is still being prepared instead of showing an empty result, and the `DiagnoseApi` doc records the coupling to `perform_create`'s synchronous diagnosis (an async server means polling `status/`).
- EXIF answered, stripped on the server: `PlantDiseaseRequest.image_1` is a `ProcessedImageField` that re-encodes before storing, and plant.health is sent the stored copy, re-encoded again by `_prepare_image`. New `backend/apps/plant_identification/tests/test_exif_strip.py` posts a GPS-tagged JPEG through the API and finds no EXIF in the stored file or in what the service reads. Outside this todo: identify still forwards the raw upload to Plant.id (`plant_id_service.identify_plant`) and mobile uploads it raw to Firebase Storage.
- An Android HEIC/HEIF pick uploads as `.jpg` (`diagnoseUploadName`): image_picker_android re-encodes at quality 85 but keeps the name. Tests: the full results fixture and card fields, condition and trimmed location reaching `diagnose()`, a real multipart upload over loopback HTTP (field, `.jpg` filename, form fields), and the per-request timeout firing. The home page doc comment now counts six cards.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-11-0053)

- AC 1: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart --name "a new photo clears|edited symptoms clear"'` — evidence `.sweep-evidence/g5/461-ac0.txt` (not committed), last lines:

  ```text
  00:00 +0: todo 461 a new photo clears the previous result
  00:00 +1: todo 461 edited symptoms clear the previous result, a cursor move does not
  00:00 +2: All tests passed!

  [exit 0]
  ```

- AC 2: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart --name "preview decodes"'` — evidence `.sweep-evidence/g5/461-ac1.txt` (not committed), last lines:

  ```text
  00:00 +0: loading plant_community_mobile/test/features/diagnose/diagnose_test.dart
  00:00 +0: todo 461 the preview decodes at its laid-out width, not the photo's
  00:00 +1: All tests passed!

  [exit 0]
  ```

- AC 3: `bash -c 'grep -n "slowAnalysisReceiveTimeout" plant_community_mobile/lib/services/api_service.dart plant_community_mobile/lib/services/plant_identification_service.dart plant_community_mobile/lib/features/diagnose/diagnose_api.dart && cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart --name "receive timeout|receiveTimeout overrides"'` — evidence `.sweep-evidence/g5/461-ac2.txt` (not committed), last lines:

  ```text
  [API] uri: http://127.0.0.1:56313/up/
  [API]
  00:00 +2: All tests passed!

  [exit 0]
  ```

- AC 4: `bash -c 'grep -n "COUPLING" -A7 plant_community_mobile/lib/features/diagnose/diagnose_api.dart && cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart --name "pending or processing"'` — evidence `.sweep-evidence/g5/461-ac3.txt` (not committed), last lines:

  ```text
  00:00 +0: loading plant_community_mobile/test/features/diagnose/diagnose_test.dart
  00:00 +0: todo 461 a pending or processing outcome says it is still running, not an empty result
  00:00 +1: All tests passed!

  [exit 0]
  ```

- AC 5: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest apps/plant_identification/tests/test_exif_strip.py --create-db -p no:cacheprovider -q -v'` — evidence `.sweep-evidence/g5/461-ac4.txt` (not committed), last lines:

  ```text
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 3 passed, 3 warnings in 18.47s ========================

  [exit 0]
  ```

- AC 6: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart --name "HEIC|real multipart upload"'` — evidence `.sweep-evidence/g5/461-ac5.txt` (not committed), last lines:

  ```text
  [API] uri: http://127.0.0.1:56424/api/v1/plant-identification/disease-requests/r-1/results/
  [API]
  00:00 +2: All tests passed!

  [exit 0]
  ```

- AC 7: `bash -c 'cd plant_community_mobile && flutter test --no-pub -r expanded test/features/diagnose/diagnose_test.dart'` — evidence `.sweep-evidence/g5/461-ac6.txt` (not committed), last lines:

  ```text
  [API] uri: http://127.0.0.1:56451/up/
  [API]
  00:01 +23: All tests passed!

  [exit 0]
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-11-0053)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
