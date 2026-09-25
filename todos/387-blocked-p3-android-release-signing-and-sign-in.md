---
status: blocked
priority: p3
issue_id: "387"
tags: [android, firebase, signing, mobile, security]
dependencies: []
source_review: "todos/383-firebase-hardening-carryover"
source_finding: "AC4,AC5-android"
blocked_on: "no physical Android device is available (held 2026-09-14)"
unblock_when: "a physical Android device with a Google account can be connected over adb"
---

# Android: release signing, SHA-1 registration, and a verified sign-in

> **ON HOLD since 2026-09-14.** The engineering is done and merged (#772); the
> two remaining criteria need hardware and a Play account that do not exist yet.
>
> `status: blocked` makes this file **invisible to every sweep skill** —
> `todo-sweep`, `todo-next`, `todo-batch` and `completing-todos` all select on
> `^status: pending`. Nothing will resurface it automatically. Flip the status
> and the filename back to `pending` when a device is available.

## Problem

Two acceptance criteria were carried through todo 383 and **re-pointed here
rather than checked off**, because each is genuinely unmet and `- [x]` in this
repo means shipped. A box ticked because it was deferred is one nobody
re-audits — the exact failure the Review Doc Tracking convention exists to
prevent.

iOS is finished and shipped: sign-in was verified on a physical iPhone against
production on 2026-09-13 (todo 384, TestFlight build 7, Railway logs show
`Existing user authenticated`). **None of that moves Android**, because iOS API
keys restrict by bundle id while Android restricts by package + certificate
SHA-1, and the two platforms share nothing here.

## Findings

### 1. Release builds are signed with the DEBUG key

`android/app/build.gradle.kts:40-44` still reads
`signingConfig = signingConfigs.getByName("debug")` inside
`buildTypes { release { ... } }`. There is no `android/key.properties`, no
`.jks` anywhere in the tree, and no `.aab`/`.apk` artifact has ever been
produced.

A release certificate is a **prerequisite** of registering a release SHA-1, not
a step within it. That is why todo 383 AC 4 could never be discharged there:
there is nothing to register.

Note there are ultimately **three** distinct SHA-1s in play, and conflating them
is the usual way this goes wrong:

| certificate | where it comes from |
|---|---|
| debug | `~/.android/debug.keystore` |
| local release | the `.jks` that does not exist yet |
| Play App Signing | Google re-signs on upload — matches neither of the above |

**Correction (2026-09-14):** this table originally said the debug certificate was
"already registered in `google-services.json`". It was not.
`firebase apps:android:sha:list` returned *No SHA certificate hashes found*, and
the committed config carried `certificate_hash: null`. Google Sign-In was
therefore broken on Android in **debug** builds too, not only release — so the
failure was never gated behind the missing keystore the way this todo assumed.

### 2. Google Sign-In cannot work on Android at all

`android/app/google-services.json` contains exactly one `oauth_client` entry and
it is `client_type: 3` (web). There is **no Android OAuth client**
(`client_type: 1`), which is what binds package name + certificate SHA-1.

So the "Continue with Google" button shipped in #736 is iOS-only in practice.
It is present in the Android build and will fail there. This is a direct
consequence of finding 1: an Android OAuth client cannot be registered without a
certificate to register.

### 3. Sign-in has never been exercised on a physical Android device

Todo 383 AC 5 required a physical Android **and** a physical iOS device. The iOS
half is discharged. The Android half has no path to being discharged until
findings 1 and 2 are resolved, and nothing has ever been installed on an Android
device.

### 4. The `google-services` Gradle plugin was never applied (found 2026-09-14)

Not in the original filing, and an **independent** blocker that fires before any
certificate is checked.

`com.google.gms.google-services` appeared in neither `settings.gradle.kts` nor
either `build.gradle.kts`, so `android/app/google-services.json` was inert —
never processed into resources. Flutter reads its Firebase config from
`--dart-define` via `firebase_options.dart`, so nothing about starting Firebase
ever needed the plugin, which is why the omission survived unnoticed.

`google_sign_in` is the exception. On Android it resolves the server client id
by looking up the `default_web_client_id` **string resource** by name
(`GoogleSignInPlugin.java:204`, `resources.getIdentifier(...)`), falling back to
it whenever no `serverClientId` is passed in Dart — and `AuthService` passes
none, deliberately, because on iOS the value comes from `Info.plist`. With no
plugin there is no resource, so `authenticate()` threw *serverClientId must be
provided on Android*.

So fixing findings 1 and 2 alone would not have produced a working sign-in.

## Recommended Action

1. Create a release keystore and wire `android/key.properties` (gitignored) into
   `build.gradle.kts`, replacing the debug `signingConfig` in the release block.
2. Register the release SHA-1 on the Firebase Android app, and add an Android
   OAuth client so Google Sign-In can work.
3. If shipping through Play, register the **Play App Signing** SHA-1 as well —
   it is a third certificate and is the one that actually signs what users
   install.
4. Build a release `.aab`, install on a physical Android device, and sign in
   against production. Verify server-side in the Railway logs
   (`[FIREBASE AUTH] ... authenticated`), not from the UI — see todo 383's
   lesson that both failure modes return an identical client-side 401.

## Acceptance Criteria

- [x] Release builds are signed with a release keystore, not the debug key
      (`build.gradle.kts` release block no longer references
      `signingConfigs.getByName("debug")`) (completed 2026-09-14)
- [x] The release-certificate SHA-1 is registered on the Firebase Android app
      (completed 2026-09-14). **Play App Signing is deliberately not registered**
      — nothing is distributed through Play yet, and that certificate does not
      exist until first upload. See the re-pointed criterion below.
- [x] `google-services.json` contains an Android OAuth client
      (`client_type: 1`), so Google Sign-In is capable of working on Android
      (completed 2026-09-14)
- [ ] Sign-in verified on a physical Android device against production,
      confirmed in the server logs rather than from the UI
      — **2026-09-23: verified on a `google_apis_playstore` EMULATOR, not a
      physical device**, so this stays open by its own wording. The emulator
      run proves the whole configuration chain (see the 2026-09-23 entry); the
      remaining gap is hardware only.
- [ ] The Play App Signing SHA-1 is registered on the Firebase Android app
      (new 2026-09-14; blocked until a first Play upload exists to generate it)

## Progress 2026-09-14

Findings 1, 2 and 4 are fixed and verified. Setup and the remaining runbook live
in `plant_community_mobile/docs/android-release-signing.md`.

- Release keystore at `~/keys/houseplant-md-release.jks` (**outside the repo** —
  it is public; `android/key.properties` is the gitignored pointer). Release
  SHA-1 `6E:13:1B:9B:BF:15:F6:82:B9:CB:31:89:CF:3B:5F:6E:1F:B1:8A:5D`.
- Both release and debug SHA-1s registered. `firebase apps:android:sha:create`
  **auto-provisions the `client_type: 1` OAuth client** — the console was not
  needed. Verified by re-fetching the config, not assumed.
- `com.google.gms.google-services` applied; `default_web_client_id` confirmed
  present in the built APK via `aapt2 dump resources`, with a value matching the
  json's web client exactly.
- Artifact verified with `apksigner verify --print-certs`: signed with the
  release certificate, **and not** with the debug one. Both controls asserted —
  the failure being guarded against is a release silently signed with the debug
  key, and only the negative assertion can see it.
- `test/core/android_release_signing_test.dart` guards findings 1 and 2. Both
  halves mutation-checked: restoring the debug `signingConfig` and stripping the
  Android OAuth clients each produce exactly one failure.
- A release build with no `key.properties` now **fails** rather than emitting an
  unsigned artifact; a debug build still configures normally, so CI (which has
  no keystore) is unaffected. Verified by moving the file aside and running both
  Gradle task graphs: debug exit 0, release exit 1.

### Why AC 4 is still open

The emulator run got as far as the configuration being *accepted*: logcat shows
`CredentialManager: starting executeGetCredential with callingPackage:
com.plantcommunity.plant_community_mobile`, then `GetGoogleIdOperation
succeeded` and `CREDENTIALS_RECEIVED`. That is the certificate + OAuth client +
web client id path all validating against the release-signed install — the
`serverClientId` error cannot occur past that point.

It stops there because the emulator has **no Google account** (`dumpsys account`
→ `Accounts: 0`), so Credential Manager went to `MinuteMaidActivity`, the
add-an-account web view. Completing it means typing real Google credentials.

Backing out produced exactly the predicted trap: `Account addition canceled` →
`Flow failed` → **the app displayed no error at all**, because
`AuthService.signInWithGoogle` swallows `canceled` by design. This is why AC 4
requires the *server* log, not the UI: a broken configuration and a user
changing their mind are indistinguishable on screen.

To discharge it: `adb install -r` the release APK on a device with a Google
account, sign in, and confirm `[FIREBASE AUTH] ... authenticated` in the Railway
logs for `plant_id_community`.

## Progress 2026-09-23 — sign-in AND push verified on a release-signed emulator build

Operator chose the emulator route (no physical Android device available), with
the explicit understanding that it does **not** tick the physical-device AC.

**Build.** `flutter build apk --release --dart-define-from-file=.env.production`
(API `https://api.houseplant-md.com/api/v1`). `apksigner verify --print-certs`:
SHA-1 `6e131b9b…8a5d` = release, and **not** the debug `068a6f6a…`. Installed
on `Medium_Phone_API_36.1` (`google_apis_playstore`, arm64), operator added
their own Google account in Settings.

**Finding 5 — the Android API key never allowed the release certificate.**
First tap of *Continue with Google* showed, in the app:
*"Requests from this Android client application
com.plantcommunity.plant_community_mobile are blocked."* The Google Cloud key
`9f90a089-…` (Android, auto-created by Firebase) was app-restricted on
2026-09-12 to package + **debug** SHA-1 only — two days before the release
keystore existed. The 2026-09-14 work registered the release SHA-1 on the
Firebase **app** (OAuth client) but not on the **API key**'s allowlist; those
are separate lists, and nothing checked the second. Fixed 2026-09-23 01:00 UTC
by the operator (`gcloud services api-keys update`, Owner-only; restating all
10 `--api-target`s because the update replaces the whole `restrictions`
object, and `--no-check-existing-usage` because the "active usage" it cited was
`geocoding-backend` — the daily internet scanner, already 100% refused since
geocoding is not an allowed target). Read back: both SHA-1s, 10 APIs.
`scripts/check_firebase_key_restrictions.py` → all PASS — but note it probes
**only the debug SHA-1**, which is why it stayed green while release builds
were blocked. Follow-up below.

**Sign-in, confirmed three ways, same uid, seconds apart** (emulator clock is
MDT = UTC−6):

```
emulator 19:06:37  GetGoogleIdOperation succeeded … CREDENTIALS_RECEIVED
emulator 19:06:43  FirebaseAuth: auth state listeners about user ( QY7lYq7n… )
server   01:06:50  POST /api/v1/auth/firebase-token-exchange/ 200
server   01:06:50  [FIREBASE AUTH] Existing user authenticated: wi***@gmail.com
```

**Push — a trap worth recording.** The first session registered no token: the
app had first launched at 18:53 MDT, *before* the key fix, and Firebase
Installations got a 403 (`PERMISSION_DENIED … are blocked`) and logged
*"invalid configuration"*. The SDK then refused to retry for the life of that
process — every later `getToken()` failed locally with *"Firebase
Installations Service is unavailable. Please try again later."*, even after the
key was fixed and a direct REST probe of FIS with the release cert headers
returned 200. Signing out and back in did **not** clear it (same pid 5096).
`adb shell pm clear` + relaunch did. **An FIS 403 poisons the process; after
fixing a key, restart the app with cleared data before re-testing.**

After the clean relaunch:

```
server 01:17:20  POST /api/v1/auth/firebase-token-exchange/ 200
server 01:17:21  PATCH /api/v1/forum/me/profile/ 200        ← token registered
send   01:19:14  >>> dYJHiljlRxCw True projects/plant-community-prod/messages/0:1790126354654190%…
emulator         NotificationRecord pkg=com.plantcommunity.plant_community_mobile
                   tag=FCM-Notification:1733528  android.title=String (387)
```

A first send at 01:18 was also accepted and *received* (the app's
FirebaseMessaging logged the arrival), but the app was in the foreground, where
Android delivers to the app without drawing a notification — so the send was
repeated with the app backgrounded to get a notification record as evidence.

**Side effects / follow-ups found (not fixed here):**

- ~~`check_firebase_key_restrictions.py` probes the Android key with the debug
  SHA-1 only~~ — **fixed 2026-09-23** (branch `fix/key-checker-release-sha1`):
  probes debug + release + an unregistered cert, read-back asserts both SHA-1s
  on the key, and an app-level refusal no longer scores as "reachable".
- `ForumProfile.fcm_token` holds **one** token per user, so the emulator's
  registration silently replaced the operator's iPhone token. Last signed-in
  device wins; multi-device push does not exist.
- Notifications land on `fcm_fallback_notification_channel`: the app declares
  no default channel (`com.google.firebase.messaging.default_notification_channel_id`),
  so Android users cannot manage forum notifications as a named category.

## Notes

Re-pointed from todo 383 on 2026-09-13 when that todo was archived. Todo 383's
AC 4 and the Android half of its AC 5 are **left `- [ ]` there and rewritten to
name this todo**, per the Review Doc Tracking convention: a finding that MOVED
is re-pointed, never checked off.

Deliberately filed p3: nothing is distributed on Android, so there is no
exposure and no user waiting on it. The trigger to raise the priority is the
decision to ship an Android build.

## Work Log

### 2026-09-24 - Owner action needed: release keystore

Owner steps (signing secrets stay with the owner): create an upload keystore
(`keytool -genkey -v -keystore ~/houseplant-upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload`),
keep it and its passwords out of the repo, write `android/key.properties`
(gitignored), and register the release SHA-1 (`keytool -list -v -keystore ...`)
in Firebase. A physical Android device is needed for AC 5. After the keystore
exists, the build.gradle signing wiring is sweep work — flip this todo to
`pending` then.
