---
status: pending
priority: p3
issue_id: "387"
tags: [android, firebase, signing, mobile, security]
dependencies: []
source_review: "todos/383-firebase-hardening-carryover"
source_finding: "AC4,AC5-android"
---

# Android: release signing, SHA-1 registration, and a verified sign-in

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
| debug | `~/.android/debug.keystore`, already registered in `google-services.json` |
| local release | the `.jks` that does not exist yet |
| Play App Signing | Google re-signs on upload — matches neither of the above |

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

- [ ] Release builds are signed with a release keystore, not the debug key
      (`build.gradle.kts` release block no longer references
      `signingConfigs.getByName("debug")`)
- [ ] The release-certificate SHA-1 is registered on the Firebase Android app
      (and the Play App Signing SHA-1 too, if distributing through Play)
- [ ] `google-services.json` contains an Android OAuth client
      (`client_type: 1`), so Google Sign-In is capable of working on Android
- [ ] Sign-in verified on a physical Android device against production,
      confirmed in the server logs rather than from the UI

## Notes

Re-pointed from todo 383 on 2026-09-13 when that todo was archived. Todo 383's
AC 4 and the Android half of its AC 5 are **left `- [ ]` there and rewritten to
name this todo**, per the Review Doc Tracking convention: a finding that MOVED
is re-pointed, never checked off.

Deliberately filed p3: nothing is distributed on Android, so there is no
exposure and no user waiting on it. The trigger to raise the priority is the
decision to ship an Android build.
