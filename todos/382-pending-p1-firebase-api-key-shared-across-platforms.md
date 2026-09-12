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

- [ ] Per-platform api key vars exist in `.env.example` and are read by the
      matching getters, each with a `FIREBASE_API_KEY` fallback
- [ ] `grep -cE "FIREBASE_(ANDROID|IOS|WEB)_API_KEY" lib/firebase_options.dart`
      returns a non-zero count
- [ ] A build with only the OLD `FIREBASE_API_KEY` set still starts (fallback
      proven, not assumed)
- [ ] A build with the new vars set resolves a DIFFERENT key per platform —
      asserted by value, not by the var name being present
- [ ] Auth works on a real Android device and a real iOS device
- [ ] todo 360 step 3 unblocked

## Notes

p1 because it is the blocking dependency of a p1 security todo, and for no other
reason — on its own this is a small, low-risk refactor of one file. The
`fallbackKey` shape means it can ship without coordinating any env change.

## Work Log

### 2026-09-11 - Filed

- Split out of todo 360 after the SHA-1 question exposed that the restriction
  work was architecturally blocked, not merely unstarted.
