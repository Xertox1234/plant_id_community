---
status: blocked
priority: p3
issue_id: "691"
tags: [android, firebase, signing, mobile, release, owner]
dependencies: []
source_review: "todos/archive/387-completed-p3-android-release-signing-and-sign-in.md"
source_finding: "AC5"
blocked_on: "The decision to ship Android through Google Play; no launch date yet (owner, 2026-11-03)"
unblock_when: "the owner starts the first Play Console upload"
---

# First Play Store release: register the Play App Signing certificate

> `status: blocked` keeps this out of every sweep (they select `^status: pending`).
> Flip status and filename to `pending` when Play release work starts.

## Problem

Play re-signs every app it distributes with a key Google holds (Play App
Signing). Builds installed from Play therefore carry a **third** certificate,
different from the debug and release keys we hold (see
`plant_community_mobile/docs/android-release-signing.md`). Google Sign-In and the
Firebase Android API key both admit only certificates they have been told about,
and today they know debug + release only.

If the Play SHA-1 is not registered, sign-in and push break for **every Play
user** while continuing to work on our own sideloaded builds. On screen, a
broken configuration and a cancelled sign-in look the same (todo 387, 2026-09-14).

The certificate does not exist until the first upload, so this cannot be done
in advance. Re-pointed from todo 387 AC 5 on 2026-11-03.

## Recommended Action

1. Owner: Play developer account, app listing for
   `com.plantcommunity.plant_community_mobile`, Play App Signing enabled, first
   `.aab` (`flutter build appbundle --release --dart-define-from-file=.env.production`)
   uploaded to the **internal testing** track.
2. Copy the SHA-1 from **Play Console → Release → Setup → App signing** (the
   *app signing key* certificate, not the upload key, which is our release key).
3. Register it on the Firebase Android app (`firebase apps:android:sha:create`)
   and re-fetch `android/app/google-services.json`.
4. **Also add it to the Android API key's allowlist** (`gcloud services api-keys update`,
   Owner-only). Registering on the Firebase app does not do this: those are
   separate lists, and missing the key was finding 5 on todo 387 (2026-09-23).
   The update replaces the whole `restrictions` object, so restate every
   existing SHA-1 and `--api-target`.
5. Add the SHA-1 to `ANDROID_SHA1S` in `scripts/check_firebase_key_restrictions.py`
   so the read-back asserts it, and run the script.
6. Install from the internal testing track on a physical device, sign in, and
   confirm in the Railway logs (`[FIREBASE AUTH] ... authenticated`, token
   exchange 200), not from the UI. Send a test push. If the app first launched
   before the key fix, `pm clear` before re-testing (an FIS 403 poisons the
   process; todo 387, 2026-09-23).

## Acceptance Criteria

- [ ] The Play App Signing SHA-1 is registered on the Firebase Android app
      (re-pointed from todo 387 AC 5)
- [ ] The same SHA-1 is on the Android API key's allowlist, and
      `scripts/check_firebase_key_restrictions.py` asserts it and passes
- [ ] A Play-installed build signs in against production, confirmed in the
      server logs, and receives a push

## Work Log

### 2026-11-03 - Filed

Owner plans to ship through Play but launch is not close, so this waits on the
first upload rather than forcing a Play account now.
