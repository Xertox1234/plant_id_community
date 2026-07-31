---
status: in_progress
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
- [x] The Debug configuration still resolves `development` (dev push loop intact)
      — `xcodebuild -showBuildSettings`, 2026-07-31; Profile too
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

### 2026-07-31 - Per-config entitlements split landed (run 2026-07-31-2118)

Applied **Option 1**. Code work is complete; the todo stays open on operator
gates (see "Blocked on" below).

**Line→config mapping was verified, not assumed.** The todo cited pbxproj lines
495/678/701; reading each enclosing `XCBuildConfiguration` block's `name =` line
shows they are **Profile (495), Debug (678), Release (701)** — *not* the
Debug/Profile/Release order the line numbers suggest. Exactly one line changed
(701, Release).

**Profile deliberately stays on `development`.** The todo hedged "(and Profile,
if it is used for TestFlight builds)". It is not: `flutter build ipa` uses
Release, while Profile is the `flutter run --profile` on-device path, which needs
a development APNs entitlement to receive pushes. Flipping it would have
reintroduced the exact dev-loop breakage Option 2 was rejected for. Confirmed,
not assumed — `flutter build ipa --help` → `--release  Build a release version
of your app (default mode).`

Changes:

- **new** `plant_community_mobile/ios/Runner/RunnerRelease.entitlements` —
  `aps-environment` = `production`.
- `plant_community_mobile/ios/Runner.xcodeproj/project.pbxproj` line 701 only —
  Release `CODE_SIGN_ENTITLEMENTS` → `Runner/RunnerRelease.entitlements`. No
  `PBXFileReference` was hand-added; the build setting is a path and resolves
  without one (proven below).
- `plant_community_mobile/ios/Runner/Runner.entitlements` — inline comment
  rewritten; it described the removed all-three-configs wiring and told the
  reader to flip this file to `production`, which is now wrong.
- `docs/DEPLOYMENT_SECURITY_CHECKLIST.md` — entry body rewritten for the same
  reason. **Left `- [ ]` on purpose** (see AC5 below).

**Verification — per-config resolution through the pbxproj:**

```
$ for c in Debug Profile Release; do xcodebuild -workspace Runner.xcworkspace \
    -scheme Runner -configuration $c -showBuildSettings | grep CODE_SIGN_ENTITLEMENTS; done
Debug    CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements
Profile  CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements
Release  CODE_SIGN_ENTITLEMENTS = Runner/RunnerRelease.entitlements
```

This doubles as the pbxproj-corruption check — it parsed and resolved all three.

```
$ plutil -lint Runner/Runner.entitlements Runner/RunnerRelease.entitlements
Runner/Runner.entitlements: OK
Runner/RunnerRelease.entitlements: OK
$ /usr/libexec/PlistBuddy -c "Print :aps-environment" <each>
Runner/Runner.entitlements         development
Runner/RunnerRelease.entitlements  production
```

`grep -rn` across the repo confirms no CI workflow, script, or Dart source
references the entitlements path — the split is self-contained.

**Verification — a real Release build completes with the new file:**

```
$ flutter build ios --release --no-codesign
Running pod install...                                            629.6s
Xcode build done.                                                 418.7s
✓ Built build/ios/iphoneos/Runner.app (52.9MB)
```

The `CODE_SIGN_ENTITLEMENTS` change also survives the `pod install` that
`flutter build` runs (re-grepped mid-build; still line 701 → RunnerRelease).
`--no-codesign` means no entitlements are embedded in the binary, so this proves
build integrity, **not** AC1.

`scripts/check_flutter_security.py` → `✅ PASS: No security issues found`.

**Signing state on this machine (2026-07-31)** — the operator *is* in the Apple
Developer Program (team **3442937R38**, "William Tower"), so the blocker is
narrower than "no account". What is missing is push provisioning *for this app*:

- `security find-identity -v -p codesigning` → exactly one identity, *Apple
  Development*. **No Apple Distribution certificate.**
- The four installed profiles (in
  `~/Library/Developer/Xcode/UserData/Provisioning Profiles/` — note: *not* the
  legacy `~/Library/MobileDevice/` path) are all **development** profiles, for
  `com.williamtower.ocrecipes`, `com.luma.tuner`, and a `3442937R38.*` wildcard.
  None is for `com.plantcommunity.plantCommunityMobile`, and **none declares
  `aps-environment` at all** — i.e. no App ID here has the Push Notifications
  capability enabled.
- `DEVELOPMENT_TEAM` is still absent from the pbxproj (0 occurrences), so
  automatic signing has no team to resolve against.

Consequence for AC1: the primary gap is that **no provisioning profile for
`com.plantcommunity.plantCommunityMobile` exists at all** — the four decoded
above were never candidates for signing this app. Beyond that, whatever profile
is created must carry `aps-environment`, because a profile lacking it cannot
sign a binary requesting it ("provisioning profile doesn't include the
aps-environment entitlement"), and that requires Push Notifications enabled on
the App ID — AC3's territory. So AC3 is a hard prerequisite for AC1, not a
parallel task. The correct order is AC3 → AC1 → AC4.

**Not attempted deliberately:** driving Xcode automatic signing to mint a
Distribution certificate + App Store profile. That mutates the operator's Apple
Developer account (distribution certs are capped per team) and needs an
authenticated Xcode session — an outward-facing action, so it is the operator's
call, not something to do unattended.

**Acceptance criteria status — 1 of 5 flipped:**

- **AC1 not flipped.** Deliberate. The criterion demands `codesign -d
  --entitlements` against a real archive, "not by reading the source file". This
  machine has no Distribution certificate and no provisioning profile
  (`security find-identity -v -p codesigning` → one *Apple Development* identity;
  `~/Library/MobileDevice/Provisioning Profiles/` empty; zero `DEVELOPMENT_TEAM`
  in the pbxproj), so a Distribution-signed archive cannot be produced here at
  all. The `-showBuildSettings` output above is strictly stronger than reading
  the source file — it proves resolution *through* the pbxproj — but it is not
  what AC1 asks for, so the box stays unflipped.
- **AC2 flipped** — Debug resolves `Runner.entitlements` (`development`), quoted
  above. Profile likewise, which AC2 does not require but the dev loop does.
- **AC3 / AC4 not flipped** — operator actions. AC3 is an Apple Developer account
  - Firebase console upload; AC4 needs a TestFlight build on a real device. Both
  require the Apple Developer Program, which is not set up.
- **AC5 not flipped** — deliberate, and this is the one judgment call worth
  stating plainly. Ticking it would assert the APNs provisioning is done when
  only the entitlement half is. Per `CLAUDE.md` → Review Doc Tracking, a checked
  box means shipped and nobody re-audits it. The entry body was rewritten instead
  (stale-doc fix), and now enumerates the three remaining gates.

**Blocked on (operator, not code):** APNs authentication key in the Apple
Developer account → uploaded to Firebase console → Distribution archive →
TestFlight device push. Nothing further can be verified locally without an Apple
Developer Program membership.

## Notes

Deliberately NOT fixed during todo 272's closure: flipping the string with no
APNs provisioning behind it would break the development push loop and buy
nothing, since no archive is being cut. Related: todo 279 item 3 (FCM push-tap
deep-linking — the rest of the iOS push surface), todo 253 (forum notifications
epic, the origin).
