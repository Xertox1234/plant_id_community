---
status: pending
priority: p2
issue_id: "286"
tags: [flutter, ios, firebase, notifications, release]
dependencies: []
source_review: "todo 272 item 1 (spun out 2026-07-29)"
---

# iOS `aps-environment` is `development` in every build config

## Problem

`plant_community_mobile/ios/Runner/Runner.entitlements` declares
`aps-environment` = `development`, and `CODE_SIGN_ENTITLEMENTS` wires that
single file into **all three** build configurations. A Distribution-signed
archive therefore ships a development APNs entitlement, which App Store Connect
validation rejects — this blocks the first TestFlight/App Store submission
outright.

## Findings

- `plant_community_mobile/ios/Runner/Runner.entitlements` — the only
  entitlements file in the iOS project (`find ios -name "*.entitlements"`
  returns exactly one); `<key>aps-environment</key><string>development</string>`.
- `plant_community_mobile/ios/Runner.xcodeproj/project.pbxproj` lines **495,
  678, 701** — three `CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;`
  assignments, i.e. Debug, Profile and Release all point at the same file.
  There is no per-config entitlements split today.
- Discovery source: todo 253 slice 6's 15-agent review (2026-07-16), deferred
  as item 1 of todo 272; re-verified by grep on 2026-07-29 during 272's closure.
- The slice that added this shipped iOS push groundwork **explicitly
  unverified** — no real APNs provisioning exists yet, which is why
  `development` was correct at the time and is still correct for the dev loop.

## Proposed Solutions

### Option 1: Split per-config entitlements (Recommended)

- **Implementation:** add `Runner/RunnerRelease.entitlements` with
  `aps-environment` = `production`; point only the Release (and Profile, if it
  is used for TestFlight builds) `CODE_SIGN_ENTITLEMENTS` at it, leaving Debug
  on the existing `development` file.
- **Pros:** the dev loop keeps working on-device without edits; correct value
  per configuration; no "remember to flip it back" step.
- **Cons:** two files to keep in sync if other entitlements are added later.
- **Effort:** ~30 min (plus APNs provisioning, which dominates).
- **Risk:** low — additive, and Debug behavior is unchanged.

### Option 2: Flip the single file to `production`

- **Implementation:** change `development` → `production` in place.
- **Pros:** one-line change.
- **Cons:** breaks development push on device (a dev-signed build with a
  production APNs entitlement cannot receive dev pushes), so the dev loop needs
  a manual local revert — exactly the state that rots.
- **Effort:** ~2 min.
- **Risk:** medium — silently degrades the dev push loop.

## Recommended Action

1. Do this **together with real APNs provisioning** — the entitlement value has
   to match the certificate/key the archive is signed with, so flipping it
   before provisioning exists just moves the failure.
2. Create the APNs key in the Apple Developer account and upload it to the
   Firebase console (iOS app → Cloud Messaging → APNs Authentication Key).
3. Apply Option 1 (per-config entitlements).
4. Verify with an actual archive: `flutter build ipa --release`, then confirm
   the built app's entitlements:

   ```bash
   codesign -d --entitlements :- build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app
   ```

5. Tick the checklist line in `docs/DEPLOYMENT_SECURITY_CHECKLIST.md` →
   **Mobile (Flutter)**.

## Technical Details

- `plant_community_mobile/ios/Runner/Runner.entitlements` — carries an inline
  XML comment pointing here (added during todo 272's closure). Note Xcode may
  strip that comment if the file is ever edited through the UI; the deployment
  checklist is the durable marker.
- `plant_community_mobile/ios/Runner.xcodeproj/project.pbxproj` — the three
  `CODE_SIGN_ENTITLEMENTS` sites.
- `docs/DEPLOYMENT_SECURITY_CHECKLIST.md` → `### Mobile (Flutter)` — the
  release-time checklist item, placed immediately before the
  `flutter build ios --release` step.
- Push pipeline context: `backend/apps/forum_host/tasks.py` (`send_forum_push`),
  `plant_community_mobile/lib/services/push_registration_service.dart`.

## Acceptance Criteria

- [ ] Release (and TestFlight/Profile, if used for distribution) builds resolve
      `aps-environment` = `production`, verified by `codesign -d --entitlements`
      against a real archive — not by reading the source file
- [ ] The Debug configuration still resolves `development` (dev push loop intact)
- [ ] APNs authentication key uploaded to the Firebase console for the iOS app
- [ ] A device push is received end-to-end from a distribution build
      (TestFlight), closing todo 253 AC6's "receives a push" for iOS
- [ ] `docs/DEPLOYMENT_SECURITY_CHECKLIST.md` iOS APNs line ticked

## Work Log

### 2026-07-29 - Spun out of todo 272 (item 1)

- Promoted rather than re-deferred: todo 272 is a parking todo, and per
  `CLAUDE.md` → Review Doc Tracking, promote-all is the only terminal state for
  one. Todo 272's own text called this "MUST be switched before the first
  TestFlight/App Store archive", so it is real, scheduled work, not a monitor
  item.
- Re-verified by grep before promoting: one entitlements file, three
  `CODE_SIGN_ENTITLEMENTS` sites (pbxproj 495/678/701).
- p2 rather than p3 (272's own priority): this is a hard blocker on the first
  iOS submission, not a nice-to-have. It stays unscheduled only because no iOS
  release is scheduled yet.

## Notes

Deliberately NOT fixed during todo 272's closure: flipping the string with no
APNs provisioning behind it would break the development push loop and buy
nothing, since no archive is being cut. Related: todo 279 item 3 (FCM push-tap
deep-linking — the rest of the iOS push surface), todo 253 (forum notifications
epic, the origin).
