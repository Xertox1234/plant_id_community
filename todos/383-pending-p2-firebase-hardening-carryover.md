---
status: pending
priority: p2
issue_id: "383"
tags: [security, firebase, gcp, mobile]
dependencies: []
---

# Firebase hardening carried over from todos 360/382

## Problem

Todo 360 closed the exposure it was filed for — both published Firebase client
keys are now restricted and probe-verified, and secret-scanning alerts #1/#2 are
resolved. Four items in its plan were **not** satisfiable at that time and are
carried here rather than checked off falsely. One is a new finding.

## Findings

### 1. NEW — deployed Storage security rules have drifted from the repo

Found 2026-09-12 while verifying todo 011's "Storage security rules deployed" AC
against the live project instead of the repo.

`firebase/storage.rules` in git **tightens** three read rules from
`isAuthenticated()` (any signed-in user) to `isOwner(userId)`:

- `/plant-identifications/{userId}/{imageId}`
- `/disease-diagnoses/{userId}/{imageId}`
- `/user-plants/{userId}/{imageId}`

That tightening was committed **2026-05-23** (PR #285, "resolve deferred audit
findings") and **has never been deployed**. Production still serves the ruleset
released 2025-11-14, in which any authenticated user can read any other user's
images under those prefixes. Verified through the Firebase Rules API:
`releases` → `cloud.firestore` and `…firebasestorage.app`; deployed vs committed
compared line by line (Firestore matches; Storage: deployed 63 lines, committed
66).

**Nothing is exposed today.** The bucket
`plant-community-prod.firebasestorage.app` contains **0 objects**, and no code
path writes to any of the four governed prefixes —
`FirebaseStorageService` writes to `plant_images/<imageId>` only
(`lib/services/firebase_storage_service.dart:69`), and forum image uploads go to
the Django backend (`forum_api.dart`), not Firebase Storage. So this is latent,
not a live leak. It must be fixed **before** anything writes there.

Deploying is therefore zero-impact: it tightens prefixes nothing uses. The only
other difference is an explanatory comment on `/avatars/`, whose `allow read: if
true` is deliberate (audit L16).

### 2. API restrictions per key (was todo 360 step 4)

**This finding was filed on a false premise. Correcting it in place rather than
working from it.** The original text read: *"Both keys have application
restrictions but no API restrictions, so each can still call any enabled API in
the project."*

Measured 2026-09-12 with `gcloud services api-keys list --project=plant-community-prod`
— possible only now that `gcloud` is installed and authenticated as Owner — **both
mobile keys already carried 24 `apiTargets`**. That is Firebase's auto-generated
default breadth, not an absence of restriction. The premise was inferred from the
Console, which hides the *API restrictions* section entirely until
`apikeys.googleapis.com` is enabled, and it was never checked against the project.

So the work is to **narrow** an over-broad allowlist, not to create one. That is a
smaller security win than the todo implied, and it changes the failure mode: the
risk is no longer "forgot to restrict", it is "cut something the SDK needs", which
surfaces at runtime as a broken sign-in rather than as a configuration error.

#### The keep-list comes from Firebase's documented table, not from inference

The obvious inference — map the four plugins in use to six services — is **wrong**,
and would have broken things. `https://firebase.google.com/docs/projects/api-keys`
publishes the product-to-API mapping, and it requires four services that no plugin
name suggests:

| service | required by | inference would have… |
|---|---|---|
| `firebase.googleapis.com` | all products | **dropped it** |
| `logging.googleapis.com` | all products | **dropped it** |
| `identitytoolkit.googleapis.com` | Authentication | kept |
| `securetoken.googleapis.com` | Authentication | kept |
| `firebaserules.googleapis.com` | Firestore **and** Storage | **dropped it** |
| `datastore.googleapis.com` | Cloud Firestore | **dropped it** |
| `firestore.googleapis.com` | Cloud Firestore | kept |
| `firebasestorage.googleapis.com` | Cloud Storage | kept |
| `firebaseinstallations.googleapis.com` | Cloud Messaging | kept |
| `fcmregistrations.googleapis.com` | Cloud Messaging | kept |

Ten services, down from 24. Dropped: `sqladmin` (Cloud SQL Admin),
`firebasevertexai`, `firebaseml`, `mlkit`, `firebasedataconnect`,
`firebaseapphosting`, `firebasedatabase` (RTDB — this project uses Firestore),
`firebasehosting`, `firebaseappcheck`, `firebaseappdistribution`,
`firebaseapptesters`, `firebaseinappmessaging`, `firebaseremoteconfig`,
`firebaseremoteconfigrealtime`.

#### Traffic could not validate the keep-list, and saying so matters

The instruction carried into this work was "confirm against real traffic before
cutting." That was run and it came back **empty**: in 30 days of
`serviceruntime.googleapis.com/api/request_count`, the only API-key traffic on
either mobile key is `identitytoolkit`, and the 2026-09-12 spike there is *this
project's own verification probes* from todos 360/382. `securetoken`, `firestore`,
`firebaseinstallations` and `fcmregistrations` show **zero**. (The 128 Firestore
200s belong to a service account — the Django admin SDK — not to a key.)

That is what "distributed to nobody" looks like in the metrics, and the trap is
reading zero traffic as "not needed." Cutting `securetoken` on that reasoning
would leave sign-in working for exactly one hour, until the first token refresh.
**Traffic was therefore used in one direction only: it may add a service to the
keep-list, never remove one.**

#### Found while measuring: both keys are being probed daily from outside

The traffic query surfaced something not previously known. Every single day, both
mobile keys receive Google **Maps** API calls — `geocoding-backend` once a day on
each key in lockstep, with full-suite bursts across `directions`, `places`,
`static-maps`, `street-view`, `timezone`, `elevation` and `distance-matrix` on
2026-08-16, 09-09 and 09-10.

This cannot be the app: it uses no Maps API, and the Flutter `geocoding` plugin
calls platform-native geocoders with no key. The counts are symmetric across two
keys, which no single client would produce. It is an automated scanner exercising
the keys that were committed to this public repo — the same exposure that raised
secret-scanning alerts #1/#2. All of it returns **403**, so nothing is being
spent or read.

Two consequences worth keeping:

1. **Never enable a Maps API on this project** while a client key carries a broad
   allowlist. The probing is already in place and would start succeeding the day
   the service is turned on.
2. `gcloud services api-keys update` defaults to `--check-existing-usage`, which
   **counts those blocked 403s as "active usage" and refuses the tightening**:

   ```
   FAILED_PRECONDITION: Unable to update key restrictions. Active usage in the
   last 7 days was detected for service(s): directions-backend…, geocoding-backend…
   ```

   The guard is inverted for a leaked key — the more an attacker probes it, the
   harder it is to lock down. `--no-check-existing-usage` is required, and is only
   safe because every removed service was verified to have **zero 2xx responses**
   across 30 days. That check is the precondition for the override, not a
   formality.

### 3. SHA-1 must be re-checked against a real release signing cert

The Android key's restriction names the **debug** SHA-1
`06:8A:6F:6A:4F:F9:15:59:A9:D0:3B:5B:BD:8F:9F:0E:3B:2A:7D:C2`, because
`android/app/build.gradle.kts:40-44` still signs release with the debug key and
there is no `android/key.properties` and no release keystore. The moment a real
keystore exists — or the app is uploaded to Play, which re-signs with its own
App Signing cert — that SHA-1 stops matching and Android sign-in breaks.

### 4. Real-device auth verification

Todo 382's device AC was consciously not met. The owner confirmed 2026-09-12 that
the app is **not distributed to anyone** — no Play track, no TestFlight, no
sideloaded builds (corroborated by the missing release keystore and, on iOS, no
distribution cert or provisioning profile). With no installs, the restriction
change had no user-facing blast radius, and the risk it was gating was retired
another way: a black-box probe proved each key admits only its own platform's
legitimate client headers and rejects wrong-id / no-header / other-platform
shapes.

What the probe cannot prove is that the Firebase **SDK** sends those headers at
sign-in. That is standard SDK behaviour and instantly revertible (unset
`FIREBASE_ANDROID_API_KEY` and Android falls back), but it is unproven and must
be closed before the first real distribution.

## Recommended Action

1. `firebase deploy --only storage` from the repo root, then re-compare deployed
   vs committed through the Rules API. **Owner action** — deploying production
   security rules is not an automated step.
2. Add a CI or scripted drift check so "committed" and "deployed" cannot diverge
   silently again. This is the second time a rules deploy has been assumed rather
   than verified (see also todo 224 / `firebase deploy --only firestore:rules`).
3. Apply API restrictions per key once the API list is confirmed against traffic.
4. When a release keystore is created: add its SHA-1 to the Android key
   restriction (and Play's App Signing SHA-1 if shipping to Play) **before**
   distributing, then re-run the probe.
5. Before the first real distribution, run the app on a physical Android device
   and a physical iOS device and confirm sign-in.

## Acceptance Criteria

- [x] Deployed Storage rules byte-match `firebase/storage.rules`, verified through
      the Rules API and not by "the deploy command exited 0" (2026-09-12 — owner ran
      `firebase deploy --only storage`; release updated 14:03:15Z, and a fresh
      Rules API fetch confirms `deployed == committed` for **both** rulesets, with
      all three reads now `allow read: if isOwner(userId)` and `/avatars/` still
      deliberately `if true`)
- [x] A drift check exists that fails when deployed rules differ from committed
      (2026-09-12 — `scripts/check_firebase_rules_drift.py`, 29 offline tests in
      Harness CI, plus `.github/workflows/firebase-rules-drift.yml` daily at 07:20
      UTC and on every push to `main` touching a rules file. Exit codes are
      0 match / 1 drift / 2 INDETERMINATE, so "could not look" can never read as
      clean. Authenticated by **Workload Identity Federation, no key file
      anywhere** — SA `firebase-rules-reader` with `roles/firebaserules.viewer`
      only, pool `github-actions`, provider `github` whose attribute-condition
      pins `assertion.repository` to this repo; the SA's `workloadIdentityUser`
      binding is scoped to the matching principalSet. Both halves asserted, not
      assumed — without the condition any GitHub repo could mint tokens for the
      pool. Credentials are two repo *variables*, `GCP_WIF_PROVIDER` and
      `GCP_RULES_READER_SA`; neither is sensitive and no owner step remains.
      **Residual:** the OIDC exchange itself is unproven until the workflow is on
      `main` — GitHub refuses to dispatch a workflow absent from the default
      branch — but the merge touches a rules file and so runs it immediately)
- [x] Each key restricted to the APIs the app actually calls, with the app still
      working afterwards (2026-09-12 — both mobile keys narrowed **24 -> 10
      `apiTargets`**: Firebase's own documented product-to-API set for
      Authentication + Firestore + Storage + Messaging. Dropped `sqladmin`,
      `firebasevertexai`, `firebaseml`, `mlkit`, `firebasedataconnect`,
      `firebaseapphosting`, `firebasedatabase`, `firebasehosting`,
      `firebaseappcheck`, `firebaseappdistribution`, `firebaseapptesters`,
      `firebaseinappmessaging` and both remoteconfig services.
      **Both halves restated deliberately**, because `--api-target` *replaces* the
      whole `restrictions` object and passing it alone would have silently deleted
      the application restriction todos 360/382 exist to provide: the read-back
      shows 10 targets **and** `iosKeyRestrictions` / `androidKeyRestrictions`
      still present, and an 8/8 live probe confirms each key still admits only its
      own platform's headers while rejecting no-header, wrong-bundle-id and
      other-platform shapes.
      **Enforcement proven live, not inferred:** `firebaseremoteconfig` — enabled
      project-wide, so a block there can only come from the key — returned
      `API_KEY_SERVICE_BLOCKED` on both keys after the change, having returned a
      plain `PERMISSION_DENIED` before it; and while only the iOS key was narrowed,
      the untouched Android key still returned the old response to the identical
      call, which is the control that rules out "the service just became
      unreachable". Re-runnable: `python3 scripts/check_firebase_key_restrictions.py`.
      **Residual, stated rather than implied:** "the app still working" is *not*
      proven by execution — nothing runs the app, the same condition that produced
      zero usable traffic (item 2). What is proven is that the three kept services
      whose endpoints actually evaluate an API key — `identitytoolkit`,
      `securetoken`, `firebaseinstallations` — still answer on both keys; the other
      seven rest on the read-back of the key resource, which is the authoritative
      statement of what is permitted. The TestFlight build was expected to be the
      first real execution and the place to confirm sign-in; it is not, because
      build `1.0.0+2` has no Firebase configuration compiled in and never calls a
      key at all (item 8). Restrictions are server-side, so a revert needs no
      rebuild)
- [ ] Release-cert SHA-1 registered before any distribution (or explicitly
      deferred again, in writing, with the reason) — **deferred again 2026-09-12,
      reason: there is nothing to register.** Re-verified rather than copied from
      the earlier text: `android/app/build.gradle.kts:40-44` still reads
      `signingConfig = signingConfigs.getByName("debug")` under `buildTypes {
      release { ... } }`, there is no `android/key.properties`, no `.jks` anywhere
      in the tree, and no `.aab`/`.apk` artifact has been produced. A release
      certificate is a prerequisite of this AC, not a step within it. **Left
      unchecked on purpose:** `- [x]` in this repo means shipped, and a box that
      is checked because it was deferred is one nobody re-audits — the exact
      failure the Review Doc Tracking convention exists to prevent. The trigger to
      revisit is the creation of a release keystore, or the first Play upload
      (Play re-signs with its own App Signing certificate, which is a *third*
      SHA-1, matching neither the debug key nor a local release keystore).
      Today's iOS distribution does not move this: iOS keys restrict by bundle
      id, not by certificate
- [ ] Sign-in verified on a physical Android device and a physical iOS device —
      **iOS is now blocked on a rebuild, not on distribution.** The premise this
      was deferred under ("the app is distributed to nobody") expired 2026-09-12
      when two uploads of `com.plantcommunity.plantCommunityMobile` succeeded to
      App Store Connect, so the deferral no longer holds. But the build that got
      there cannot discharge it either: `1.0.0+2` was archived without any
      `--dart-define`, so it shows the configuration-error screen and never
      reaches a sign-in screen (item 8). Discharging this needs an archive built
      through Flutter with the defines, re-uploaded, then an actual sign-in on the
      installed build. Android remains deferred with the original reason — still
      no release keystore, still nothing installed anywhere
- [x] Dead `isAuthenticated()` helper removed from `firebase/storage.rules`
      **and deployed in the same motion** (see item 5) — 2026-09-12, deployed
      from the todo-383 branch before merge, so the repo never went ahead of
      prod. Ruleset `ade11cca` -> `90fc82d6`, release updated 20:47:05Z, 66 ->
      62 lines. Verified through the Rules API, not the CLI exit code: the diff
      against the previous ruleset is exactly the four helper lines, and the
      set of `match` / `allow` clauses is byte-identical before and after, so
      no access rule changed. The two compiler warnings the deploy used to emit
      (`Unused function: isAuthenticated`, `Invalid variable name: request`) are
      gone. `check_firebase_rules_drift.py` returns 0 for both releases.

### 5. NEW — dead `isAuthenticated()` helper in storage.rules

The 2026-09-12 deploy surfaced two compiler warnings:

```
[W] 6:14 - Unused function: isAuthenticated.
[W] 7:14 - Invalid variable name: request.
```

Both come from the same three lines. `grep -n isAuthenticated firebase/storage.rules`
returns exactly **one** hit — the definition, with zero call sites — because the
2026-05-23 tightening replaced every use with `isOwner(userId)`. The second warning
is the linter objecting to `request` inside a function nothing calls.

Worth deleting, and not merely for tidiness: this is the precise loose predicate
(`request.auth != null`, i.e. any signed-in user) whose presence is what the drift
re-exposed for 3.5 months. Leaving it sitting there invites its reuse. It is still
used 7× in `firestore.rules` — leave that one alone.

**Deliberately not changed on 2026-09-12.** Repo and prod match for the first time
since May; editing the file without deploying would put the repo ahead again, which
is exactly the drift state item 1 just closed. Do the edit and the deploy together,
then re-verify through the Rules API.

### 6. NEW — a THIRD API key exists, and it is application-unrestricted

The "both keys" framing throughout todos 360/382/383 counted **shipped configs**,
not keys on the project. `gcloud services api-keys list` returns three:

| key | uid | application restriction |
|---|---|---|
| iOS key | `86cc165f-8927-4b9f-a2ef-b242fd96ba35` | bundle id |
| Android key | `9f90a089-47a4-4098-bc3c-0eac12ebc673` | package + SHA-1 |
| **Browser key** | `289f8af0-7f29-49be-b58d-f57312930011` | **`browserKeyRestrictions: {}` — none** |

It never raised a secret-scanning alert because it is committed nowhere, which is
exactly why it stayed invisible: every previous check looked at tracked config
files, and this key is in none of them.

Evidence that nothing uses it, gathered 2026-09-12:

- **No Web app is registered on the Firebase project at all** —
  `firebase.googleapis.com/v1beta1/projects/plant-community-prod/webApps` returns
  empty, while `androidApps` and `iosApps` each return one app bound to its own key.
- `web/package.json` has no `firebase` dependency, and `web/src` contains no
  `firebase` import. The React app authenticates against the Django backend.
- `FIREBASE_WEB_API_KEY` is set **nowhere** — not in `.env.local`, not in
  `mobile-ci.yml` (where it is deliberately unset to prove the fallback path),
  only as a placeholder in `.env.example`.
- `firebase.json` declares no `hosting` block; the web app deploys to Cloudflare.
- Zero attributed traffic in 30 days.

So it is an orphan created by Firebase at project setup on 2025-10-21 and never
wired to anything. There is no referrer to restrict it *to* — an allowlist of
referrers for a client nobody ships is a guess, not a control — so the honest
options were delete it or knowingly leave it.

**RESOLVED 2026-09-12: deleted by the owner.** `deleteTime`
`2026-09-12T22:14:51Z`; it remains visible under `--show-deleted` and is
recoverable for 30 days with
`gcloud services api-keys undelete 289f8af0-7f29-49be-b58d-f57312930011 --project=plant-community-prod`.
The project now holds exactly two keys, one per registered Firebase app.

Re-checked immediately before deleting, because the owner chose on evidence
gathered *before* item 7 surfaced and an in-flight build meant something in the
checkout had recently changed: a tree-wide scan for `AIzaSy[A-Za-z0-9_-]{33}`
returned only the two mobile keys, this script's own fake-key constant, and a
placeholder in `google-services.json.example`. The browser key string appeared
nowhere, so nothing could break.

Note for whoever registers a Firebase **web** app later: doing so auto-creates a
new browser key with the same wide-open default. `scripts/check_firebase_key_restrictions.py`
prints a NOTE line for any key that is neither the iOS nor the Android key, so a
re-created one will show up rather than blend in.

### 7. NEW — the "distributed to nobody" premise has EXPIRED

Found 2026-09-12 in the working tree, not in a document: `pubspec.yaml` is bumped
to `1.0.0+2`, and two new untracked scripts stage an App Store Connect upload —
`run_archive.sh` (`xcodebuild archive`) and `run_upload.sh`
(`xcrun altool --upload-app`).

**They already ran, and the upload succeeded — twice.** This is no longer a
pending event to prepare for. `~/Library/Logs/ContentDelivery/com.apple.itunes.altool/`
records `UPLOAD SUCCEEDED` / `No errors uploading archive at
'build/ios/ipa/plant_community_mobile.ipa'` for bundle id
`com.plantcommunity.plantCommunityMobile` at **14:37** and again at **14:56** on
2026-09-12. Chain of custody for the second one is unbroken:
`ios/Flutter/Generated.xcconfig` written 14:48:51, `Runner.xcarchive` 14:52:33,
the `.ipa` 14:54:46, upload 14:56 — so the artifact still on disk *is* the one
Apple received. (The 14:37 upload used an earlier `.ipa` that has since been
overwritten and cannot be inspected; it came from the same script.)

Items 3 and 4 above, and acceptance criteria 4 and 5, all trade on the app being
installed by nobody. A TestFlight build ends that. Before the first build reaches
a tester:

- **AC 5 (device sign-in) stops being deferrable for iOS.** The TestFlight build
  is itself the physical-device test — sign in on it and the AC is discharged
  honestly rather than traded away. **But not with build `1.0.0+2`**, which
  cannot reach a sign-in screen at all — see item 8.
- **Item 3 (release-cert SHA-1) stays Android-only and stays open.** iOS keys are
  restricted by bundle id, which a TestFlight build carries unchanged, so the iOS
  key needs nothing here. Android is still signing release with the debug key.

Note that an API key's restrictions live in GCP, not in the binary: the key string
is baked into the build but the allowlist is server-side and can be changed or
reverted at any time without rebuilding. So item 2 is safe to land before or after
an upload — but if sign-in breaks in TestFlight, this is the first thing to check.

### 8. NEW — the uploaded build has no Firebase configuration compiled into it

**Build `1.0.0+2`, now in App Store Connect, shows the configuration-error screen
instead of the app.** It cannot sign in, and the reason is not any item above —
it never reaches Firebase at all.

`lib/firebase_options.dart` resolves every value from `String.fromEnvironment`
(the `_dartDefines` map), which is a **compile-time** constant supplied by
`--dart-define`. `run_archive.sh` invokes `xcodebuild archive` directly instead of
`flutter build ipa --dart-define-from-file=...`, so no define ever reaches the
Dart compiler. `_optional` treats the resulting empty string as absent,
`_required('FIREBASE_IOS_API_KEY', fallbackKey: 'FIREBASE_API_KEY')` throws
`StateError`, `main()` catches it and calls `runApp(ConfigurationErrorApp(...))`
and returns. `plant_community_mobile/README.md:100` already lists this exact
behaviour as an expected smoke-test outcome: *"Missing Firebase `--dart-define`
values show the configuration error screen."*

**The mechanism is not inferred — the repo's own suite asserts it.**
`test/firebase_options_test.dart:97-114` is a green test in `mobile-ci.yml`
named *"a missing key throws and names both the platform var and the fallback"*,
asserting `throwsA(isA<StateError>())` for exactly this input. So the only thing
that needed establishing was whether the defines were absent from the shipped
build, which is what the snapshot check below settles.

**Proven from the shipped artifact, not inferred from the script.** Unpacking the
uploaded `.ipa` and running `strings` over the AOT snapshot
(`Payload/Runner.app/Frameworks/App.framework/App`) finds **zero** `AIzaSy`-shaped
strings, while the same `strings | grep` finds the key in the bundle's own
`GoogleService-Info.plist` — the positive control that makes the zero meaningful,
without which "no hits" would only have proven the method was blind. The same
snapshot *does* contain the literal `Missing Firebase configuration value` and
`Firebase configuration is required`: one Dart string from that file survived
compilation and the key never existed. `ios/Flutter/Generated.xcconfig` carries no
`DART_DEFINES` line, and `grep 'DART_DEFINES\|FIREBASE_'` over `project.pbxproj`
and every `ios/Flutter/*.xcconfig` returns nothing, so there was no other route.

**This is not caused by the API-key restrictions of item 2, and reverting them
would not fix it.** The restriction is keyed on bundle id; the shipped
`CFBundleIdentifier` is `com.plantcommunity.plantCommunityMobile`, matching the
iOS key exactly; and the app never gets far enough to call a Google endpoint. An
identical archive built the day before PR #726 would have failed identically.
Worth stating explicitly because a key-hardening change landing hours before a
broken build invites exactly that misattribution.

**The fix is the owner's and the repo already documents it.** `.env.local` (git-
ignored) already holds every needed `FIREBASE_IOS_*` value, and
`FIREBASE_KEY_ROTATION.md:529` shows the form: build through Flutter with
`--dart-define-from-file`, so the defines land in `Generated.xcconfig` *before*
`xcodebuild archive` runs. Then re-upload with an incremented build number —
`ExportOptions.plist` sets `manageAppVersionAndBuildNumber: true`, so check App
Store Connect for which build numbers the two uploads actually became. Not done
here: `run_archive.sh` / `run_upload.sh` are another session's untracked files,
and re-uploading to Apple is an outward-facing action.

**Standing consequence:** a green `xcodebuild archive` and a successful
`altool --upload-app` say nothing about whether the app can start. Both succeeded
here on a build that shows an error screen. That is the same shape as this todo's
item 1 — a green deploy log is compatible with production serving something else.

## Notes

p2, not p1: nothing here is a live exposure. Item 1 is empty-bucket latent, items
2-5 are hardening and pre-distribution gates. It becomes p1 the moment the app is
distributed or anything writes to the Storage prefixes.

**That moment has arrived** — see item 7. The iOS upload to App Store Connect
succeeded twice on 2026-09-12, which retires the zero-blast-radius assumption that
items 3/4 and ACs 4/5 were deferred on. It does not make this todo p1 today, for
one reason only: the uploaded build has no Firebase configuration compiled in and
therefore touches nothing (item 8). It becomes p1 with the first build that
actually runs.

## Work Log

### 2026-09-12 - Filed

Split out of todos 360 and 382 on close-out, so their open items stay visible
instead of being checked off or silently dropped. Item 1 was found by verifying a
todo's claim against the live project rather than the repo — the same failure mode
as the rest of that pair.

### 2026-09-12 - Item 1 DONE: storage rules deployed and verified

Owner ran `firebase deploy --only storage`. Verified the way the AC demands —
through the Rules API, not from the command's exit code:

| release | deployed == committed | updated |
|---|---|---|
| `cloud.firestore` | yes | 2026-06-22T23:04:38Z |
| `plant-community-prod.firebasestorage.app` | yes | **2026-09-12T14:03:15Z** |

`/plant-identifications/`, `/disease-diagnoses/` and `/user-plants/` now read
`allow read: if isOwner(userId)` in production; `/avatars/` remains `if true` by
design (audit L16). The 3.5-month window in which any signed-in user could read any
other user's images under those prefixes is closed. Nothing was ever exposed through
it — the bucket held 0 objects throughout.

Still open here: the drift check (item 1's second AC — nothing yet prevents this
recurring), API restrictions, the release-cert SHA-1, the device check, and the new
item 5.

### 2026-09-12 - Item 2 DONE: both mobile keys narrowed 24 -> 10 APIs

Detail in the acceptance criterion above and in the rewritten item 2. Three things
are worth carrying forward as method, not just as result.

**The probe was lying, and only a self-check caught it.** The first pass reported
seven services ALLOWED on both keys. Three of those seven never evaluated the API
key at all, so they would have read ALLOWED no matter what the restriction said:
`firebaseappdistribution` is OAuth-only and answers *"API keys are not supported by
this API"*; `firestore` REST and `firebasestorage` v0 both deny on **security
rules** before the key is considered. Sending a *syntactically valid but fabricated*
key to each endpoint and requiring `API_KEY_INVALID` back is what separates "the key
may call this" from "nobody was checking". Targets that fail that screen are now
reported INCONCLUSIVE instead of counted as evidence. Same family as the vacuous
test in PR #725 that passed because the dependency was absent — and it also flushed
out two bugs in the probe itself (an unencoded `(default)`, and a `__probe__`
collection id that Firestore reserves).

**A verification script can fail the wrong way too.** The application-restriction
check first reported 6 of 8 cases FAILING. All six were correct blocks: the matcher
looked for the token `BLOCKED` while the API's prose says *"...are blocked."* in
lower case. A checker that reads prose instead of the machine-readable reason
manufactures both false alarms and, in the other direction, false greens.

**`--check-existing-usage` protects the attacker.** It refused the first update
because the daily Maps probing counted as "active usage in the last 7 days" — all of
it 403. Overriding it is correct here but only because every removed service was
first confirmed to have **zero 2xx** responses across 30 days. That confirmation is
the precondition for the override, not paperwork.

**The probe is now a committed artifact**, `scripts/check_firebase_key_restrictions.py`,
because items 3 and 4 both say "re-run the probe" and todo 360's probe lived only in
a scratchpad that no longer exists — an instruction pointing at a vanished script is
not tracking. It checks all three halves (config read-back, application restriction,
API targets), exits 2 rather than 0 when it cannot look, and carries a deliberate
**canary**: an OAuth-only endpoint that must report INCONCLUSIVE. Without the canary,
deleting the fake-key screen entirely changed nothing and the run still passed —
the guard was dormant. Mutation-checked three ways: wrong expectation, a service
missing from the expected set, and the neutered self-check all exit 1.

Still open here: the release-cert SHA-1 (item 3, Android-only, still signing release
with the debug key), the physical-device sign-in (item 4 / AC 5, now reachable via
the pending TestFlight build), and the Browser-key decision (item 6).

### 2026-09-12 - The TestFlight upload happened, and the build it shipped is inert

Went looking for whether the staged upload had run, on the assumption that if it
had, AC 5 could finally be discharged by signing in on the installed build. It had
run — twice, both `UPLOAD SUCCEEDED` — and the build cannot sign in. Recorded as
items 7 (rewritten) and 8 (new). No code changed; this entry and those items are
the deliverable.

**The check that mattered was of the artifact, not of the script.** Reading
`run_archive.sh` and noticing it calls `xcodebuild archive` rather than
`flutter build ipa` predicts the bug but does not establish it — plenty of routes
could have supplied the defines anyway (a prior `flutter build` leaving them in
`Generated.xcconfig`, an xcconfig override, a scheme setting). The uploaded `.ipa`
is on disk, so the question is directly answerable: unzip it and look in the AOT
snapshot for the key. Zero `AIzaSy` strings.

**That zero only counts because of the positive control.** `strings` over a
compiled Dart snapshot could easily have been blind to const strings, in which
case "no hits" would have meant nothing while looking exactly like a finding —
the same false-green shape as the API probes earlier today, where three of seven
targets never evaluated a key and all three read as passes. So the same
`strings | grep` was run against the bundle's `GoogleService-Info.plist`, which
provably contains the key: one hit. Method sighted, result trustworthy. The
snapshot also carries `Missing Firebase configuration value` — a Dart literal
from the very file whose key came back absent, so the compilation unit is
readable and the key genuinely was never in it.

**A green build and a green upload prove nothing about whether the app starts.**
`xcodebuild archive` succeeded, `xcrun altool --upload-app` reported *"No errors
uploading archive"*, Apple accepted it. All true of a build that opens to an error
screen. This is item 1's lesson in a second costume: a file in git, a green deploy
log and a successful upload are each compatible with the thing that actually runs
being wrong. The only statements worth anything are about the artifact and the
live system.

**Watch for the misattribution.** Item 2 narrowed both API keys hours before this
build was uploaded, so "sign-in is broken in TestFlight" will read as key
restrictions until someone checks. It is not: the shipped bundle id matches the
iOS key's restriction exactly, restrictions are server-side and were verified by
read-back, and the app never reaches a Google endpoint. Item 8 states this so the
next person does not spend the afternoon reverting the wrong change. If sign-in
ever does misbehave in a build that *starts*, the order is still:
`python3 scripts/check_firebase_key_restrictions.py` first.

**AC 4 re-deferred in writing rather than checked off.** The AC permits discharge
by written deferral, and the reason is solid — no release keystore exists, so
there is no certificate to register. It stays `- [ ]` anyway: in this repo `- [x]`
means shipped, and a box checked for a deferral is a box nobody re-audits. The
facts behind it were re-verified in the tree, not copied forward from the earlier
entry, because this todo has already carried a confidently-wrong finding once
(item 2's "no API restrictions", which were 24 all along).
