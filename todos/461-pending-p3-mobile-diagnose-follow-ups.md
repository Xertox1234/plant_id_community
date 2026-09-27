---
status: pending
priority: p3
issue_id: "461"
tags: [mobile, flutter, diagnosis, follow-up]
dependencies: []
source_review: "todos/archive/444-completed-p3-mobile-diagnose-missing.md"
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

- [ ] A new photo or edited symptoms clear the previous result.
- [ ] The preview decodes at display size.
- [ ] The client timeout covers a slow synchronous diagnosis, or the flow
      moves to create-then-poll.
- [ ] `pending`/`processing` are handled or the coupling is documented.
- [ ] The EXIF question is answered (strip on the server, or record why not).
- [ ] An Android HEIC pick uploads with a `.jpg` name.
- [ ] The test gaps above are covered.
