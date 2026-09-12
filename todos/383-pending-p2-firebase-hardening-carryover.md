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

Both keys have **application** restrictions but no **API** restrictions, so each
can still call any enabled API in the project. The plugins actually in use are
`firebase_auth`, `cloud_firestore`, `firebase_storage`, `firebase_messaging`
(`plant_community_mobile/pubspec.yaml:39-43`), so the allowlist is approximately:
Identity Toolkit, Token Service, Cloud Firestore, Firebase Installations, FCM
Registration, Cloud Storage for Firebase. Verify against real traffic before
applying — an omitted API fails at runtime, not at configuration time.

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

- [ ] Deployed Storage rules byte-match `firebase/storage.rules`, verified through
      the Rules API and not by "the deploy command exited 0"
- [ ] A drift check exists that fails when deployed rules differ from committed
- [ ] Each key restricted to the APIs the app actually calls, with the app still
      working afterwards
- [ ] Release-cert SHA-1 registered before any distribution (or explicitly
      deferred again, in writing, with the reason)
- [ ] Sign-in verified on a physical Android device and a physical iOS device

## Notes

p2, not p1: nothing here is a live exposure. Item 1 is empty-bucket latent, items
2-5 are hardening and pre-distribution gates. It becomes p1 the moment the app is
distributed or anything writes to the Storage prefixes.

## Work Log

### 2026-09-12 - Filed

Split out of todos 360 and 382 on close-out, so their open items stay visible
instead of being checked off or silently dropped. Item 1 was found by verifying a
todo's claim against the live project rather than the repo — the same failure mode
as the rest of that pair.
