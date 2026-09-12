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
- [ ] Each key restricted to the APIs the app actually calls, with the app still
      working afterwards
- [ ] Release-cert SHA-1 registered before any distribution (or explicitly
      deferred again, in writing, with the reason)
- [ ] Sign-in verified on a physical Android device and a physical iOS device
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
options are delete it or knowingly leave it. **Deletion is reversible for 30 days**
via `gcloud services api-keys undelete`. Owner decision.

### 7. NEW — the "distributed to nobody" premise is about to expire

Found 2026-09-12 in the working tree, not in a document: `pubspec.yaml` is bumped
to `1.0.0+2`, and two new untracked scripts stage an App Store Connect upload —
`run_archive.sh` (`xcodebuild archive`) and `run_upload.sh`
(`xcrun altool --upload-app`).

Items 3 and 4 above, and acceptance criteria 4 and 5, all trade on the app being
installed by nobody. A TestFlight build ends that. Before the first build reaches
a tester:

- **AC 5 (device sign-in) stops being deferrable for iOS.** The TestFlight build
  is itself the physical-device test — sign in on it and the AC is discharged
  honestly rather than traded away.
- **Item 3 (release-cert SHA-1) stays Android-only and stays open.** iOS keys are
  restricted by bundle id, which a TestFlight build carries unchanged, so the iOS
  key needs nothing here. Android is still signing release with the debug key.

Note that an API key's restrictions live in GCP, not in the binary: the key string
is baked into the build but the allowlist is server-side and can be changed or
reverted at any time without rebuilding. So item 2 is safe to land before or after
an upload — but if sign-in breaks in TestFlight, this is the first thing to check.

## Notes

p2, not p1: nothing here is a live exposure. Item 1 is empty-bucket latent, items
2-5 are hardening and pre-distribution gates. It becomes p1 the moment the app is
distributed or anything writes to the Storage prefixes.

**That moment now looks imminent** — see item 7. An iOS TestFlight upload is being
prepared in the working tree, which retires the zero-blast-radius assumption that
items 3/4 and ACs 4/5 were deferred on.

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
