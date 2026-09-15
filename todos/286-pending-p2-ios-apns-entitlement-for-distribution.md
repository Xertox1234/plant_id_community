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

- [x] Release (and TestFlight/Profile, if used for distribution) builds resolve
      `aps-environment` = `production`, verified by `codesign -d --entitlements`
      against a real archive — not by reading the source file
      — **2026-09-15**: Distribution-signed `Runner.xcarchive` inspected;
      `aps-environment=production`, `get-task-allow=false`, authority
      `Apple Distribution: William Tower (3442937R38)`, embedded profile
      `Plant Community Mobile App Store`. See the 2026-09-15 work-log entry.
- [x] The Debug configuration still resolves `development` (dev push loop intact)
      — `xcodebuild -showBuildSettings`, 2026-07-31; Profile too
- [ ] APNs authentication key uploaded to the Firebase console for the iOS app
- [ ] A device push is received end-to-end from a distribution build
      (TestFlight), closing todo 253 AC6's "receives a push" for iOS
      — **BLOCKED (2026-09-15) on a prerequisite outside iOS**: production has
      neither `FIREBASE_CREDENTIALS_PATH` nor `GOOGLE_APPLICATION_CREDENTIALS`,
      so `is_firebase_available()` is `False` and every push returns early at
      `logger.debug` — silently. Affects Android identically. See the
      2026-09-15 work-log entry; fix that first, then this AC and AC3 close
      together on one probe.
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

### 2026-07-31 - Run terminated `skip-todo` by operator decision

The code half shipped as PR #529 (commits `a2db795`, `1c419ec`). The todo stays
**open and unarchived** — 4 of 5 acceptance criteria are unmet, and per
`completing-todos` acceptance criteria are gospel: there is no force-complete.

Offered the operator three paths (do the portal work now and let the run retry
AC1/AC3 / `skip-todo` / add `DEVELOPMENT_TEAM` first). **Chose `skip-todo`.**

Correction to an earlier statement in this log's first pass: the operator *is*
in the Apple Developer Program. The initial "no provisioning profiles" reading
was wrong — it checked the legacy `~/Library/MobileDevice/Provisioning Profiles/`
path instead of Xcode's actual
`~/Library/Developer/Xcode/UserData/Provisioning Profiles/`. The corrected
finding is above; the conclusion (AC1/AC3/AC4 unreachable here) survived, but for
a narrower reason.

**To resume:** do AC3 first (enable Push Notifications on the App ID for
`com.plantcommunity.plantCommunityMobile`, create the APNs auth key, upload it to
the Firebase console), then create an Apple Distribution cert + App Store
profile, then AC1 (`flutter build ipa --release` + `codesign -d --entitlements`),
then AC4 (TestFlight device push). AC5 ticks last. `DEVELOPMENT_TEAM` =
`3442937R38` will need adding to the pbxproj for automatic signing — deliberately
left out of scope here.

### 2026-09-04 - Signing state re-checked; operator steps handed over (run 2026-09-04-0350)

Unchanged since 2026-07-31, re-verified on this Mac:

```
$ security find-identity -v -p codesigning
  1) … "Apple Development: william.tower@gmail.com (8YMA4779DD)"   ← still no Apple Distribution
$ ~/Library/Developer/Xcode/UserData/Provisioning Profiles/  → 3 decodable profiles:
  com.williamtower.ocrecipes, com.luma.tuner, 3442937R38.*   — none for
  com.plantcommunity.plantCommunityMobile, none carries aps-environment
$ DEVELOPMENT_TEAM in ios/Runner.xcodeproj/project.pbxproj → 0 occurrences
$ PlistBuddy :aps-environment → Runner.entitlements=development, RunnerRelease.entitlements=production
```

Firebase project for the upload: `plant-community-prod` (from
`GoogleService-Info.plist`). The user chose to do the portal work now; the
ordered steps (App ID push capability → APNs key → Firebase upload → Xcode
team + Push capability → `flutter build ipa --release` → TestFlight push)
were handed over in-session. AC1 gets verified with `codesign -d
--entitlements :-` against the produced archive once it exists; AC5 ticks
last. Xcode will write `DEVELOPMENT_TEAM` into the pbxproj on the main
checkout — that change rides the closing PR with the checklist tick.

### 2026-09-15 - The recorded blocker was STALE; re-measured from scratch

**Every signing fact this file asserted from 2026-07-31 through 2026-09-04 is
now false.** The 2026-09-04 entry says "still no Apple Distribution", "none for
`com.plantcommunity.plantCommunityMobile`", "none carries aps-environment",
"`DEVELOPMENT_TEAM` → 0 occurrences". All four became false when the operator
did the portal work and shipped TestFlight build 12 (on device 2026-09-14), and
nothing re-audited this log. A session reading it would have gone off to redo
Apple-portal work that was already done. Re-measured on this Mac:

```
$ security find-identity -v -p codesigning
  1) …8YMA4779DD "Apple Development: william.tower@gmail.com"
  2) …2B12B1C2   "Apple Distribution: William Tower (3442937R38)"     ← NEW
     2 valid identities found
```

Profiles, decoded rather than guessed at (note the Xcode path, *not* the legacy
`~/Library/MobileDevice/` one — reading the wrong path is what produced the
false "no profiles exist" in this log's first pass):

```
$ for f in ~/Library/Developer/Xcode/UserData/Provisioning\ Profiles/*.mobileprovision; do
    security cms -D -i "$f" | plutil -extract Entitlements.aps-environment raw - ; done
Plant Community Mobile App Store            → production     ← NEW
iOS Team Provisioning Profile: …Mobile      → development    ← NEW
(ocrecipes / luma.tuner / 3442937R38.*      → no aps-environment)
```

**That first profile settles AC3's App-ID half on its own.** A profile cannot
carry `aps-environment` unless Push Notifications is enabled on the App ID, so
the artifact is the proof — no portal access needed to establish it.

`DEVELOPMENT_TEAM = 3442937R38` is now in the pbxproj at 3 sites (504/688/714),
so automatic signing resolves. And the Release configuration is wired for
manual Distribution signing, which is what makes AC1 reachable here at all:

```
$ xcodebuild -workspace Runner.xcworkspace -scheme Runner -configuration Release \
    -showBuildSettings | grep -E 'CODE_SIGN|PROVISIONING_PROFILE_SPECIFIER|DEVELOPMENT_TEAM'
CODE_SIGN_ENTITLEMENTS        = Runner/RunnerRelease.entitlements
CODE_SIGN_IDENTITY            = Apple Distribution
CODE_SIGN_STYLE               = Manual
DEVELOPMENT_TEAM              = 3442937R38
PROVISIONING_PROFILE_SPECIFIER = Plant Community Mobile App Store
```

**Checked this BEFORE building, deliberately.** Had Release been on automatic
signing it could have resolved the *development* profile, and the archive would
either have failed to sign ("provisioning profile doesn't include the
aps-environment entitlement") or produced an artifact that cannot satisfy AC1 —
20 minutes spent on unusable evidence.

**AC1 CLOSED — a real Distribution-signed archive was produced and inspected.**

```
$ flutter build ipa --release --export-options-plist ios/ExportOptions.plist
Running pod install...                                             16.6s
Xcode archive done.                                               354.3s
✓ Built build/ios/archive/Runner.xcarchive (486.3MB)
✓ Built IPA to build/ios/ipa (48.4MB)
```

The evidence is a **triple**, not just the entitlement string — grepping the
dump for `production` and stopping there would pass just as happily on a
Development-signed archive, which is worthless for this AC:

```
$ APP=build/ios/archive/Runner.xcarchive/Products/Applications/Runner.app
$ codesign -d --entitlements :- "$APP"
  aps-environment                        = production     ← the AC
  get-task-allow                         = false          ← distribution, not dev
  beta-reports-active                    = true           ← TestFlight-eligible
  application-identifier                 = 3442937R38.com.plantcommunity.plantCommunityMobile
$ codesign -dv --verbose=4 "$APP"
  Authority = Apple Distribution: William Tower (3442937R38)
  TeamIdentifier = 3442937R38
$ security cms -D -i "$APP/embedded.mobileprovision" | plutil -extract Name raw -
  Plant Community Mobile App Store       (its own aps-environment: production)
```

`get-task-allow = false` is the independent corroboration: a development-signed
build always carries `true`. So the archive is Distribution-signed, embeds the
App Store profile, and requests the **production** APNs environment — which is
exactly what AC1 asked for and what `-showBuildSettings` alone could never show.

**Where this was built, and why it matters.** The main checkout was sitting on a
peer's branch (`feat/todo-393-circuit-alert-verified`), whose diff is
backend-only — zero `plant_community_mobile/` files — so its iOS tree is
byte-identical to `origin/main` and the archive is valid evidence for main.
Building there also reused the warm `ios/Pods` (16.6 s instead of a ~10 min cold
`pod install` in a fresh worktree). `git status` in the main checkout was clean
before and after, so the `pod install` did not rewrite the tracked `Podfile.lock`
and the peer's tree was never touched. All doc edits were made in a worktree.

**Disk nearly ended this.** Free space fell 5.5 GiB → 896 MiB during the build
(DerivedData 425 MB → ~2 GB, archive 486 MB). Worth recording because the
obvious remedy is wrong: `xcrun simctl delete unavailable` frees **nothing**
here — all 11 simulators are *available*, and the 11 GB is two of them holding
5.5 GB and 4.9 GB of accumulated app data. `xcrun simctl erase all` is the lever
that actually reclaims it. And per `docs/LEARNINGS.md`, never `rm -rf
plant_community_mobile/build` to make room — that orphans `native_assets/ios/`
while `.dart_tool/hooks_runner` still claims the hook ran, and the resulting
error names DerivedData, which is the wrong suspect. `flutter clean` is the fix.

**Build number note (does not affect AC1, does block any upload):**
`pubspec.yaml` is at `1.0.0+10`, but build 12 already shipped to TestFlight. The
IPA produced here is therefore un-uploadable as-is. Deliberately NOT bumped —
AC1 needs an archive, not a submission, and picking the next free build number
is an App Store Connect fact, not a local one.

**AC3 deliberately NOT ticked on attestation.** The operator reports the APNs
authentication key is uploaded to Firebase. That is very likely right — but this
todo is the case study in what an unverified recorded claim costs: its own log
carried four false signing facts for six weeks and would have sent a session to
redo finished portal work. An assertion about a console is not an artifact, so
AC3 stays open until a push actually lands.

**The empirical test that closes AC3 and AC4 together**, and why one test does
both: FCM returns `THIRD_PARTY_AUTH_ERROR` when no APNs key is configured for
the project, so a push that is actually delivered *is* the proof the upload
happened. Run against prod (the Claude session cannot — the auto-mode classifier
blocks `railway ssh`, so this is handed to the operator as a `!` command):

```bash
railway ssh --service plant_id_community -- bash -lc 'cd /app && \
  /opt/venv/bin/python manage.py shell -c "…send_test_notification(p.fcm_token)"'
```

Read three things from it, not one:

- `FirebaseNotificationService.is_available()` — `False` means
  `FIREBASE_CREDENTIALS_PATH` is unset on Railway and prod push is off
  *entirely*, a blocker with nothing to do with APNs.
- whether any `ForumProfile` carries an `fcm_token` at all (the Flutter client
  registers it via `PATCH /forum/me/profile/`; no token, no test).
- **which build registered that token.** AC4 says "from a distribution build
  (TestFlight)". A token registered by a Debug/Profile build is bound to the
  *development* APNs environment, so a delivery to it proves the plumbing but
  not this AC. The phone must be on the TestFlight copy.

Note the Python in that command is written with **no quote characters at all**
(`chr(62)*3` as the grep marker, `str()` for the empty string) — `railway ssh
-- bash -lc '…python -c "…"'` is already two levels of nesting deep, and a third
level of quoting inside the Python is what breaks it.

**AC5 stays open by design.** It ticks last, after AC3 and AC4. Per `CLAUDE.md`
→ Review Doc Tracking a checked box means shipped and nobody re-audits it —
ticking it now would assert end-to-end push delivery on the strength of an
archive that has never been installed on a phone.

### 2026-09-15 - AC4 has a second blocker nobody had named: prod has no Firebase credentials

Found while chasing why the AC3/AC4 probe returned nothing. **Production cannot
send an FCM message at all**, independent of APNs, the entitlement, or the
device.

`settings.py` (~line 1019) resolves the credentials in two tiers, and the
comment is explicit that **"FCM sending always needs FIREBASE_CREDENTIALS_PATH"**:

```python
_firebase_credentials_path = config("FIREBASE_CREDENTIALS_PATH", default=None)
if _firebase_credentials_path is None:
    _firebase_credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
FIREBASE_CREDENTIALS_PATH = _firebase_credentials_path or None
```

The production service (`plant_id_community`, project `PlantID Community`,
environment `production`) lists **43 variables, and neither name is among them**.
`FIREBASE_PROJECT_ID` *is* set — which is why this hides so well: that feeds the
auth exchange's "projectId-only init tier", so **Firebase sign-in works while FCM
is dead**, and the two look like one capability from the outside.

Consequence, traced to the line: `is_firebase_available()` returns
`FIREBASE_CREDENTIALS_PATH is not None` → `False`, so `send_forum_push`
(`forum_host/tasks.py:182`) and `send_forum_push_batch` (`:294`) both return at

```python
if not is_firebase_available():
    logger.debug("[FCM] Firebase not configured — skipping forum push (%s)", event)
    return
```

**at `logger.debug`** — below the deployed level, so it emits nothing. The task
succeeds, the queue drains, and no push is sent. Corroborating: a log query for
`Firebase OR FCM OR firebase_admin OR credentials` across the running deployment
returns **zero lines**.

**What this does NOT block, checked rather than assumed.** I suspected the Celery
worker was also dead, because `get-service-config` reports the *dashboard*
start command (plain gunicorn, builder RAILPACK) rather than
`backend/railway.json`'s `bash bin/start.sh` + DOCKERFILE. The deploy log
disproves it — config-as-code wins at deploy time:

```
[start] worker pid 2 (celery -A plant_community_backend worker -B …); web pid 3 (gunicorn …)
[2026-09-15 19:55:26: INFO/Beat] beat: Starting...
[2026-09-15 19:55:26: INFO/MainProcess] celery@28ca4a101b2d ready.
```

So the worker and beat are alive; the queue is drained. **Read the deploy log,
not `get-service-config`, for what a Railway service actually runs.**

**Confirm with one command** (`printenv`-style, deliberately with no `grep` —
the earlier probe piped `2>&1` into `grep`, so a railway auth failure or a
traceback printed *nothing* and empty output was indistinguishable from "no
tokens"):

```bash
railway ssh --service plant_id_community -- sh -c \
  'echo CRED=[${FIREBASE_CREDENTIALS_PATH:-UNSET}] GAC=[${GOOGLE_APPLICATION_CREDENTIALS:-UNSET}]'
```

These are file *paths*, not secrets.

**CONFIRMED in the running container, 2026-09-15:**

```
$ railway ssh --service plant_id_community -- sh -c 'echo CRED=[...] GAC=[...]'
CRED=[UNSET] GAC=[UNSET]
```

So the diagnosis is measured inside the deployment, not merely inferred from the
service's variable list. Worth the extra step: a Railway service can receive
variables that the config API does not enumerate (shared/environment-level), so
the variable list alone is suggestive and `printenv` inside the container is
proof. The same run also showed `railway ssh` itself works fine — the earlier
blank output was the `grep` swallowing the probe's own failure, not an access
problem.

**Revised AC4 ordering.** The device and the TestFlight build were never the
first blocker:

1. Put the service-account JSON on the prod service and point
   `FIREBASE_CREDENTIALS_PATH` at it (a Railway volume or a baked file — the
   value is a path, so the JSON has to exist in the container).
2. *Then* the push probe becomes meaningful, and it settles AC3 and AC4 together.

**Scope note: this is not an iOS problem.** `send_forum_push` is platform-neutral,
so Android push is equally dead in production. Todo 253 AC6 ("receives a push")
cannot close on either platform until step 1 happens.

## Notes

Deliberately NOT fixed during todo 272's closure: flipping the string with no
APNs provisioning behind it would break the development push loop and buy
nothing, since no archive is being cut. Related: todo 279 item 3 (FCM push-tap
deep-linking — the rest of the iOS push surface), todo 253 (forum notifications
epic, the origin).
