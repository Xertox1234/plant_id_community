---
status: pending
priority: p1
issue_id: "382"
tags: [security, firebase, mobile, gcp]
dependencies: []
---

# Split `FIREBASE_API_KEY` per platform — one shared key cannot be restricted

## Problem

`plant_community_mobile/lib/firebase_options.dart` uses a **single**
`FIREBASE_API_KEY` for every platform. Google permits exactly **one** application
restriction per API key, so a key shared by Android and iOS **cannot be restricted
at all** without breaking one of them. This is the root cause of the unrestricted
production keys found in todo 360 — not a missed checkbox, a structural block.
Todo 360 cannot be finished until this ships.

## Findings

Measured 2026-09-11 while fetching the Android signing SHA-1 for todo 360.

- All four getters read the same key — `firebase_options.dart` `android` (line 61),
  `ios` (69), `web` (78), `desktop` (88) each call
  `_required('FIREBASE_API_KEY')`.
- `grep -cE "FIREBASE_(ANDROID|IOS|WEB)_API_KEY"` returns **0** in both
  `lib/firebase_options.dart` and `.env.example`. No per-platform key var exists.
- `plant_community_mobile/.env.local` sets `FIREBASE_API_KEY` to the **iOS** key
  (sha256 prefix `0fe0dd78a1`), so **the Android app authenticates with the iOS
  key** at runtime.
- The Android key (`ef0dbb8e17`) in `android/app/google-services.json` is **not
  used at runtime at all**: `com.google.gms.google-services` is not applied
  anywhere in the Gradle build, so that file is inert.
- **`appId` is already split per platform** (`FIREBASE_ANDROID_APP_ID`,
  `FIREBASE_IOS_APP_ID`, `FIREBASE_WEB_APP_ID`) via `_required(..., fallbackKey:)`.
  The api key is the one field that was not — so the pattern to copy already
  exists in the same file.
- Google's application restriction is a single choice (None / HTTP referrers / IP
  addresses / Android apps / iOS apps), which is why one key serving two app
  platforms is unrestrictable rather than merely unrestricted.

## Recommended Action

1. Add `FIREBASE_ANDROID_API_KEY`, `FIREBASE_IOS_API_KEY`, `FIREBASE_WEB_API_KEY`
   to `.env.example` and the dart-define plumbing.
2. Change each getter to `_required('FIREBASE_<PLATFORM>_API_KEY', fallbackKey:
   'FIREBASE_API_KEY')` — mirroring exactly how `appId` already does it. The
   fallback keeps every existing build and CI invocation working unchanged, so
   this is not a breaking change for anyone who has not set the new vars.
3. Point each platform at its own existing key: Android → the key in
   `google-services.json`, iOS → the key in `GoogleService-Info.plist`.
4. Update `.env.local` (untracked, developer machines) and any CI
   `--dart-define` set. Grep the workflows for `FIREBASE_API_KEY` before assuming
   there are none.
5. Verify on a real Android device and a real iOS device — this is auth plumbing,
   so a passing unit test proves nothing about it.
6. Hand back to **todo 360** step 3 to apply the iOS restriction.

## Technical Details

- `_required(key, {fallbackKey})` already implements the per-platform-with-
  fallback shape; read it before writing anything new.
- Web: the React app does not use Firebase; the `web` getter is Flutter web. Give
  it its own var anyway so a browser-referrer restriction stays possible later.
- Desktop shares the Android/iOS problem in principle but is not shipped; give it
  the generic fallback.
- **Do not** rotate any key while doing this (owner decision, todo 360).

## Acceptance Criteria

- [x] Per-platform api key vars exist in `.env.example` and are read by the
      matching getters, each with a `FIREBASE_API_KEY` fallback (2026-09-11)
- [x] `grep -cE "FIREBASE_(ANDROID|IOS|WEB)_API_KEY" lib/firebase_options.dart`
      returns a non-zero count — **weak AC, it passed under the mutant too**; see
      the Work Log
- [x] A build with only the OLD `FIREBASE_API_KEY` set still starts (fallback
      proven, not assumed) — asserted by value with real `--dart-define` values;
      `web` is deliberately left unset in the CI invocation so the same run
      proves the fallback
- [x] A build with the new vars set resolves a DIFFERENT key per platform —
      asserted by value, not by the var name being present
- [ ] **Auth works on a real Android device and a real iOS device** — NOT done;
      this is what still blocks closing 382, and it cannot be closed from CI
- [ ] todo 360 step 3 unblocked — **still blocked.** Merging the code does not
      unblock it; see "Ordering" below

## Ordering — merging this is safe, the env flip is the risky step

These are two separate events and conflating them is the outage path:

1. **Merging the code** changes no behavior for anyone. Every platform var falls
   back to `FIREBASE_API_KEY`, which is what every existing build, CI invocation
   and `.env.local` sets. Safe to merge with no coordination.
2. **Setting `FIREBASE_ANDROID_API_KEY`** is the first time the Android app
   authenticates with the Android key — which is **already restricted** to
   package + *debug* SHA-1 (todo 360 step 1, 2026-09-12). That restriction has
   never been on a live auth path. It depends on the Android Firebase SDK sending
   `X-Android-Package` / `X-Android-Cert` that match.

So: **do not mark 382 complete when the PR merges**, and **do not start todo 360
step 3 (restrict the iOS key) until Android has been proven working on the Android
key on a real device.** If 382 is checked off on merge, 360 step 3 looks unblocked
while Android has never actually run on the restricted key — and step 3 removes
the unrestricted key that Android is currently falling back to. That is exactly
the outage `project_firebase_key_restriction_state` exists to prevent.

Also: `.env.local` sets no `FIREBASE_ANDROID_APP_ID`, so Android currently uses
the **iOS `appId`** as well as the iOS key. Setting only the new api key would
pair an Android key with an iOS `appId`; set both together.

## Notes

p1 because it is the blocking dependency of a p1 security todo, and for no other
reason — on its own this is a small, low-risk refactor of one file. The
`fallbackKey` shape means it can ship without coordinating any env change.

## Work Log

### 2026-09-11 - Filed

- Split out of todo 360 after the SHA-1 question exposed that the restriction
  work was architecturally blocked, not merely unstarted.

### 2026-09-11 - Implemented (code only; device proof outstanding)

Shipped on `feat/todo-382-per-platform-firebase-api-key`.

**What changed**

- `lib/firebase_options.dart` — `android`/`ios`/`web` now read
  `FIREBASE_ANDROID_API_KEY` / `FIREBASE_IOS_API_KEY` / `FIREBASE_WEB_API_KEY`
  with `fallbackKey: 'FIREBASE_API_KEY'`, exactly as `appId` already did.
  `desktop` keeps the shared key deliberately. The three new vars were added to
  the `_dartDefines` map — the step that is easy to miss, see below.
- The option-building logic moved to a new `FirebaseOptionsResolver` class in the
  same file, constructed `const` from `_dartDefines`. `DefaultFirebaseOptions`'
  public API is unchanged (`currentPlatform`, `android`, `ios`, `web`, `desktop`
  all still resolve identically). This is a deliberate deviation from "minimal":
  the production values come from `String.fromEnvironment`, a compile-time
  constant, so without an injectable map a test can only ever exercise the single
  `--dart-define` set it was compiled with — and AC #4 demands value assertions.
- `test/firebase_options_test.dart` — new, 7 tests. Five drive the resolver with
  injected maps (split, full fallback, partial, empty-treated-as-unset, and the
  StateError naming both vars). Two drive `DefaultFirebaseOptions` itself with
  **real** `--dart-define` values.
- `.github/workflows/mobile-ci.yml` — a second `flutter test` step supplying those
  defines. The existing APK build keeps passing **only** the shared
  `FIREBASE_API_KEY`, on purpose: that is the standing regression guard that a
  build which never adopts the new vars still resolves.
- `.env.example`, `README.md` — per-platform vars documented, each pointing at the
  file its value comes from, plus the `FIREBASE_ANDROID_APP_ID` pairing warning.

**The AC that lied, and the check that caught it**

AC #2 (`grep` returns non-zero) is worthless on its own. A per-platform var can be
wired into a getter and left out of the `_dartDefines` map, in which case it is
never read, every platform silently falls back to the shared key — the exact bug
382 exists to fix — and the grep still passes. Verified by mutation: removed the
`FIREBASE_ANDROID_API_KEY` entry from `_dartDefines` and re-ran everything.

| check | under the mutant |
|---|---|
| `flutter analyze` | **clean** |
| `flutter test` (bare, as CI ran it before this PR) | **all 692 passed** |
| the 5 injected-map tests | **all passed** (they bypass `_dartDefines`) |
| `grep -cE "FIREBASE_(ANDROID\|IOS\|WEB)_API_KEY"` | **non-zero — AC #2 satisfied** |
| the new defines-driven step | **FAILED**: `Expected 'ci-android-api-key' / Actual 'ci-shared-api-key'` |

Four of five signals were blind. That is why the defines-driven run is a CI step
and not a skip-guarded test someone is supposed to remember to run.

**Verified**

- `flutter analyze` — no issues.
- `flutter test` — 692 passed, 5 skipped (2 of the skips are the defines-driven
  tests, which skip by design when no defines are supplied).
- `flutter test test/firebase_options_test.dart` with the CI define set — 7/7.
- `dart run build_runner build` then `git diff -- lib test` — only the hand-written
  `firebase_options.dart` differs, so CI's generated-code gate passes.
- `python scripts/check_flutter_security.py` — PASS, no issues.
- Mutation check restored from a file copy (not `git checkout --`), `rg MUTANT`
  clean, suite re-run green.

**Confirmed on the current tree, not taken from the findings above**

- `grep -rn "google-services\|com.google.gms" plant_community_mobile/android/`
  returns **nothing**, so `google-services.json` really is inert and
  `--dart-define` is the only runtime source. `README.md` documents this too.
- Key identities by sha256 prefix (never by value): `google-services.json`
  `ef0dbb8e17`, `GoogleService-Info.plist` `0fe0dd78a1`, `.env.local`
  `FIREBASE_API_KEY` → `0fe0dd78a1`. The iOS key, as the findings said.
- `.env.local` has no `FIREBASE_ANDROID_APP_ID`, and its `FIREBASE_APP_ID` is
  `1:190351417275:ios:41590963ad4f6bd969ae9e` — the **iOS** app id. So the local
  Android build currently runs as the iOS app on both fields, not just the key.

**Not done**

AC #5 — real-device auth on Android and iOS. It cannot be done from CI and it is
the AC that matters most here, because it is the only thing that proves the
restricted Android key works on a live auth path. 382 stays `pending` until then.
