---
status: completed
priority: p1
issue_id: "360"
completion_date: 2026-09-12
carried_to: ["383"]
tags: [security, firebase, mobile, github, gcp]
dependencies: ["382"]
---

# Resolve the two open Firebase secret-scanning alerts (todo 011's unfinished half)

## Problem

Two GitHub secret-scanning alerts (#1, #2, both "Google API Key") have been open
since **2025-10-22** on a public repo. Todo 011 addressed them in code and then
stalled: it sits at `status: code-complete` with **all 12 acceptance criteria
unchecked**, its Work Log ending "Code changes complete, deployment actions
required." Nobody re-opened it, so the alerts have simply aged.

The alerts cannot be closed by more code. **Answered 2026-09-11: both keys are
UNRESTRICTED** (see the Work Log). That resolves the disposition question in the
*bad* direction — the one control the whole assessment rested on is absent — so
this is now remediation work, not a triage decision, and the alerts stay open
until the restrictions are applied.

## Findings

Measured 2026-09-06 during a GitHub cleanup sweep.

**The remediation was half-applied.** Todo 011 rewrote `firebase_options.dart`
to read from env, but never touched the two native config files:

| File | Tracked | Literal `AIza` key in HEAD |
| --- | --- | --- |
| `plant_community_mobile/lib/firebase_options.dart` | yes | **0** — fixed |
| `plant_community_mobile/android/app/google-services.json` | yes | **1** |
| `plant_community_mobile/ios/Runner/GoogleService-Info.plist` | yes | **1** |

**Why "rotate and purge" is probably the wrong fix.** `google-services.json`
and `GoogleService-Info.plist` are *designed* to be compiled into the shipped
app binary. Anyone can extract them from a published APK or IPA, so they are
not secrets in Google's model — they are client identifiers. The controls that
actually matter are:

1. **API key restrictions** in the Google Cloud Console (Android package name +
   SHA-1 certificate fingerprint; iOS bundle ID). **ABSENT — measured
   2026-09-11.** Both keys accept a plain REST call, and the Android key accepts
   a deliberately wrong `X-Android-Package`. See the Work Log for the probe and
   its positive control.
2. **Firebase Security Rules** — `firebase/firestore.rules` and
   `firebase/storage.rules` both exist, and todo 011 confirmed they are
   deny-by-default with authenticated-only access.

(1) is absent, so the second branch is the live one: these keys are genuinely
abusable for quota/billing exhaustion against the project, and **restriction —
not rotation — is the fix**. The "dismiss as a false positive" branch is dead;
do not take it.

**Rotation does not clear the alerts on its own.** The keys are in git history
across at least five paths (including two archived todo files and two historical
remediation reports). Rotating changes which key is live; it does not remove the
old strings from history. Only a decision on disposition closes the alerts.

## Recommended Action

1. **Check the Cloud Console first** — Google Cloud → APIs & Services →
   Credentials, for both the Android and iOS keys. Record whether an
   Application restriction (package + SHA-1 / bundle ID) and an API restriction
   are set. Everything below branches on this.
2. **If restricted:** dismiss both alerts as **`wont_fix`** with a comment naming
   the restriction and linking `firebase/firestore.rules`. Not `used_in_tests`
   (these are production keys, not fixtures) and not `false_positive` (they are
   genuine API keys — the point is that a Firebase client key is not a *secret*,
   and `false_positive` would misrepresent that to whoever reads the alert next).
   Then close todo 011 properly rather than leaving it `code-complete`.
3. **If unrestricted:** apply the restrictions, confirm the mobile app still
   builds and authenticates, then dismiss as above. **Do not rotate** — owner
   decision, 2026-09-10. Rotation is not a remediation here: the keys are in git
   history across five paths, so it changes which key is live without removing
   anything from history, and it forces a mobile release for no gain in the
   threat model that actually applies. This rules rotation out as *remediation*;
   it does not pre-empt incident response if a usage audit ever shows real
   abuse, which is a different trigger and a different decision.
4. **Either way**, reconcile todo 011: its 12 unchecked ACs describe work that
   is partly done, partly obsolete, and partly never needed. Rewrite them to
   match the decision instead of leaving a p0 todo permanently half-open.

## Technical Details

- Alert locations (metadata only — values never printed):
  `firebase_options.dart:53,61`, `google-services.json:18`,
  `GoogleService-Info.plist:6`, plus historical copies in
  `todos/archive/011-completed-p0-firebase-api-keys-exposed.md` and two
  remediation reports.
- Read the alerts with
  `gh api repos/{owner}/{repo}/secret-scanning/alerts?state=open`.
- Dismissal is `PATCH .../secret-scanning/alerts/{n}` with `state=resolved` and
  a `resolution` + `resolution_comment`.
- Prior decision record: `todos/archive/011-completed-p0-firebase-api-keys-exposed.md`.

## Acceptance Criteria

- [x] Console restriction state recorded for both the Android and iOS keys
      (2026-09-11: BOTH UNRESTRICTED, measured by black-box probe + control)
- [x] Android key restricted to package + SHA-1 (2026-09-12 — verified by probe;
      the attack shape that previously succeeded now returns
      `API_KEY_ANDROID_APP_BLOCKED`)
- [x] todo 382 shipped: `FIREBASE_API_KEY` split per platform, each platform
      pointed at its own key (2026-09-12: code merged in PR #722 AND
      `.env.local` now sets `FIREBASE_ANDROID_API_KEY` + `FIREBASE_ANDROID_APP_ID`,
      so Android resolves the Android key — verified 7/7 by running the resolution
      suite with `--dart-define-from-file=` pointed at the real `.env.local`).
      **Note the distinction that mattered:** The code is a
      pure fallback and changes nothing until `FIREBASE_ANDROID_API_KEY` is
      actually set AND Android auth is proven on a real device with the Android
      key. Until then the Android app is still authenticating with the
      unrestricted iOS key, and step 3 below would take that key away.
- [x] iOS key restricted to bundle id `com.plantcommunity.plantCommunityMobile`
      (2026-09-12, applied by the owner in the Console)
- [ ] SHA-1 re-checked against the real release signing cert once one exists
      (today, release signs with the DEBUG key — build.gradle.kts:40-44).
      **Not satisfiable: there is no release keystore and no `key.properties`, so
      no release cert exists to check against. Carried to todo 383, not dropped.**
- [x] Probe re-run: both keys return a `*_BLOCKED` reason, not `MISSING_ID_TOKEN`
      (2026-09-12, 8/8 rows — each key ADMITS its own platform's legitimate client
      and BLOCKS wrong-id, no-headers, and the other platform's headers)
- [ ] App still authenticates on a real Android device AND a real iOS device.
      **Deliberately not met — carried to todo 383.** The owner confirmed
      2026-09-12 the app is distributed to no one (no Play track, no TestFlight,
      no sideloads; corroborated by the absent release keystore and, on iOS, no
      distribution cert). With zero installs the restriction had no user-facing
      blast radius, and the risk this AC was gating was retired by the probe
      instead. The residue — that the Firebase SDK really sends the client headers
      — must be closed before the first distribution.
- [x] Both secret-scanning alerts closed with a written resolution comment
      (2026-09-12, #1 Android / #2 iOS, both `wont_fix`). Note for next time:
      `resolution_comment` is capped at **280 characters** — over that, the API
      returns a misleading `422 "Can't set a resolution_comment without a new
      resolution"` rather than naming the length, and `gh api` reports the failure
      on stderr while still printing an unchanged-alert body to stdout.
- [x] `gh api .../secret-scanning/alerts?state=open` returns an empty list
      (2026-09-12: `open alerts: 0`)
- [x] Todo 011's acceptance criteria rewritten to match reality and the todo
      moved off `code-complete` (2026-09-12 — rewritten against the LIVE project,
      which is how the undeployed Storage rules in todo 383 were found)

## Notes

**p1 as of 2026-09-11** (was p2; originally p0 on todo 011). The rating tracked
what was known at the time, and the restriction state was the whole variable:

- p0 (todo 011) assumed these were live secret credentials. They are not — they
  are client identifiers shipped in every install, and confidentiality was never
  the control.
- p2 was correct while the restriction state was *unknown*: a restricted key
  would have made the alerts dismissible paperwork.
- p1 now that it is measured **absent**. The key values are published on a public
  repo and nothing bounds their use, so the quota/billing abuse path is open to
  any reader. Data is still protected by the rules, so this is spend exposure,
  not a data leak — which is why p1 and not a p0 incident.

Also still a signal-quality problem: an un-triaged secret alert open for 10+
months trains everyone to ignore the alert list.

## Work Log

### 2026-09-06 - Filed

- Surfaced during a GitHub cleanup sweep: 0 open PRs, 0 Dependabot alerts,
  0 CodeQL alerts, but 2 secret-scanning alerts open since 2025-10-22.
- Verified the split state of the three config files against HEAD (counts above)
  rather than trusting todo 011's completion claim.

### 2026-09-10 - Re-verified; rotation ruled out; false premise corrected

Re-measured against `origin/main` rather than trusting the 2026-09-06 findings.
They held, with two additions.

**State confirmed.** Exactly **two** real keys, both 39 chars, one per shipped
mobile config (values never printed — compared by SHA-256 prefix):

| File | Keys | Alert |
| --- | --- | --- |
| `lib/firebase_options.dart` | **0** (env-driven — todo 011's fix held) | — |
| `android/app/google-services.json` | 1 (`ef0dbb8e17`) | **#1** |
| `ios/Runner/GoogleService-Info.plist` | 1 (`0fe0dd78a1`) | **#2** |

The same two keys appear in three archived docs
(`docs/archive/2025-11/{FIREBASE_SECURITY_REMEDIATION_PLAN,P0_FIREBASE_SECURITY_FIX_REPORT}.md`,
`todos/archive/011-*`). No third key exists.
`google-services.json.example` is a genuine placeholder (`YOUR_PROJECT_NUMBER`,
dummy `AIzaSy…CHARACTERS`) — **not** a finding, contrary to what a bare
`grep AIza` count suggests.

**Control #2 verified by reading it, not by citing todo 011.**
`firebase/firestore.rules` and `firebase/storage.rules` are auth-required and
owner-scoped on every path (`isOwner(userId)`, `allow delete: if false` on user
docs). That control is real.

**New finding — the disposition was already made, on a false premise.**
`plant_community_mobile/.gitignore` already said these files "are intentionally
tracked … contain public project identifiers, **not API keys**." They *do* each
contain an API key (`current_key` / `API_KEY`). So someone decided to keep them
tracked for a reason that is factually wrong, and nobody closed the alerts —
which is how they aged 10+ months. Corrected in this branch: the comment now
states the real reason (a Firebase client key ships in every APK/IPA, so
confidentiality was never the control) and names the two controls that are.

**Rotation ruled out (owner decision).** Not a remediation for these alerts:
the keys are in git history across five paths, so rotating changes which key is
live without removing anything from history, and it forces a mobile release for
no gain. Does not pre-empt incident response if a usage audit ever shows abuse.

**Still blocked on the same single fact** — are the two keys application-
restricted? `gcloud` is not installed on this machine and the `firebase` CLI
does not expose key restrictions, so this cannot be answered from a session.
Public identifiers needed for the check, so nobody has to dig them out again:

- project: `plant-community-prod` (number `190351417275`)
- Android package: `com.plantcommunity.plant_community_mobile`
- iOS bundle: `com.plantcommunity.plantCommunityMobile`
- Console: <https://console.cloud.google.com/apis/credentials?project=plant-community-prod>
- CLI: `gcloud services api-keys list --project=plant-community-prod --format=json`

Dismissal, once restrictions are confirmed or applied, is `wont_fix` — **not**
`false_positive`. These are real API keys; the point is that they are not
secrets, and `false_positive` would misrepresent that for whoever reads the
alert next.

### 2026-09-11 - ANSWERED: both keys are UNRESTRICTED. Escalated p2 -> p1

The fact this todo was blocked on is now measured, not unknown. **Neither key
carries an application restriction.** Control (1) above is absent, so the "if
restricted, dismiss" branch does not apply and the alerts must **not** be
dismissed until restrictions are in place.

**How it was measured, without Console access.** The API Keys API
(`apikeys.googleapis.com`) is **not enabled** on project `190351417275`, so the
metadata route returns `403 SERVICE_DISABLED` even with valid credentials —
enabling it is a GCP config change and was deliberately not done. Instead the
restriction was tested black-box: Google enforces a key's application
restriction **before** validating the request body, so
`POST identitytoolkit.googleapis.com/v1/accounts:lookup` with an **empty** body
discriminates cleanly and mutates nothing (it cannot succeed).

| Probe | Result | Reading |
| --- | --- | --- |
| bogus key `AIzaB…` | 400 `API_KEY_INVALID` | key policy IS evaluated before the body — the detector can fail |
| no `key=` param | 403 "unregistered callers" | key presence enforced |
| android key, no headers | 400 `MISSING_ID_TOKEN` | no app restriction |
| **android key + `X-Android-Package: com.attacker.not.our.app`** | **400 `MISSING_ID_TOKEN`** | **a wrong package is accepted — this is the attack shape** |
| ios key, no bundle header | 400 `MISSING_ID_TOKEN` | no app restriction |

The first two rows are the positive control and they matter: without them, a 400
`MISSING_ID_TOKEN` would be consistent with "this endpoint never checks key
policy at all", and the probe would be a check that cannot fail. It can.
Scripts: `probe_key_restriction.py` / `probe_control.py` (session scratchpad);
both scrub key-shaped strings from all output, and `getKeyString` was never called.

**Why p1 now.** Not because the keys are exposed — that was always true and is
by design. Because the one control that the whole disposition rests on is
confirmed **absent**, on a **public** repo where the key values are published, so
the abuse path is open to anyone who reads the tree: unmetered calls to
Identity Toolkit and any other API the key can reach, i.e. quota and **billing**
exhaustion against `plant-community-prod`. If email/password sign-up is enabled,
unsolicited account creation and password-reset email/SMS spend are also reachable.
That was NOT probed — it would create data — so treat it as an unverified
risk, not a demonstrated one.

Data confidentiality is still protected by `firestore.rules` / `storage.rules`
(auth-required, owner-scoped, verified 2026-09-10). This is a spend/abuse
exposure, not a data-leak exposure. Proportionate, but no longer speculative.

**The footgun to avoid when applying the Android restriction.** The SHA-1 must be
the certificate that actually signs the shipped artifact. If Play App Signing is
enabled, Google re-signs the upload, so the *upload* cert SHA-1 is the wrong
value and restricting to it breaks auth for **every installed user** while
working perfectly in local debug builds. Take the SHA-1 from Play Console →
Release → Setup → App signing (both "App signing key certificate" and "Upload
key certificate"), and add the local debug cert too or debug builds stop
authenticating. Verify on a real device build before closing this out.

### 2026-09-11 (later) - ROOT CAUSE: one key serves every platform, so it CANNOT be restricted

The order of work in the previous entry said "restrict the Android key, restrict
the iOS key." Following it literally **breaks Android authentication.** Found
while fetching the signing SHA-1, which sent me into the Gradle and
`firebase_options.dart` wiring that the earlier entry never opened.

**`firebase_options.dart` uses ONE api key for every platform.** The `android`,
`ios`, `web` and `desktop` getters all read the same
`_required('FIREBASE_API_KEY')` — grep for `FIREBASE_(ANDROID|IOS|WEB)_API_KEY`
returns **0** hits in both `firebase_options.dart` and `.env.example`. And
`plant_community_mobile/.env.local` sets `FIREBASE_API_KEY` to the **iOS** key.
So the Android app authenticates with the iOS key at runtime.

**Google permits exactly ONE application-restriction type per key** — None /
HTTP referrers / IP addresses / Android apps / iOS apps is a single choice, not a
set. A key shared by Android *and* iOS therefore **cannot be restricted at all**
without breaking one of them.

That is the root cause of the unrestricted state. Not an ops oversight where
somebody forgot to tick a box — it is forced by the shared key, and the fix is a
**code** change that must land before any Console change. Filed as **todo 382**,
which this todo now depends on for step 3 onward.

The asymmetry shows it was an oversight in one field only: `appId` **is** already
split per platform (`FIREBASE_ANDROID_APP_ID` / `FIREBASE_IOS_APP_ID` /
`FIREBASE_WEB_APP_ID`). The api key is the single field that was not.

**There is also no release keystore.** `android/app/build.gradle.kts:40-44`:

```kotlin
release {
    // TODO: Add your own signing config for the release build.
    // Signing with the debug keys for now, so `flutter run --release` works.
    signingConfig = signingConfigs.getByName("debug")
}
```

No `key.properties` either. So there is no upload cert and no Play App Signing
cert yet — the Play-re-signing footgun in the previous entry is real but **does
not apply today**, because nothing has ever been signed for release. It also
means the app cannot currently ship to Play at all (Play rejects debug-signed
uploads). The debug cert SHA-1 on the maintainer's machine is

```
06:8A:6F:6A:4F:F9:15:59:A9:D0:3B:5B:BD:8F:9F:0E:3B:2A:7D:C2
```

read with `keytool -list -v -alias androiddebugkey -keystore
~/.android/debug.keystore -storepass android -keypass android`. A cert
fingerprint ships in every APK, so it is not a secret — but it is **per-machine**,
so re-read it rather than trusting this value, and redo step 1 against the real
signing cert once one exists.

**Corrected order of work** (supersedes both Recommended Action steps 1-2 and the
order in the previous Work Log entry):

1. **Restrict the ANDROID key now — zero breakage risk, do it first.** Package
   `com.plantcommunity.plant_community_mobile` + the debug SHA-1 above. Nothing
   reads this key at runtime: the `com.google.gms.google-services` plugin is
   **not applied anywhere** in the Gradle build, so `google-services.json` is
   inert and the app takes its key from `--dart-define` instead. This closes the
   abuse path on one of the two published keys for free, and it is the only step
   available before the code change.
2. **Ship todo 382** — split `FIREBASE_API_KEY` into per-platform vars following
   the existing `appId` pattern, and point each platform at its own key. Both
   keys already exist, one per platform. **Nothing below this line is possible
   until 382 lands.** Split into two events, because only the second one carries
   risk:
   - **2a. Merge the code** — done 2026-09-11. Zero behavior change: every
     platform var falls back to `FIREBASE_API_KEY`.
   - **2b. Set `FIREBASE_ANDROID_API_KEY` to the Android key and prove Android
     auth on a real device.** This is the first time the Android key's
     restriction (step 1) is on a live auth path. Set
     `FIREBASE_ANDROID_APP_ID` in the same change — `.env.local` currently has
     only the generic `FIREBASE_APP_ID`, set to the **iOS** app id, so Android
     would otherwise pair an Android key with an iOS `appId`.
3. Restrict the iOS key to bundle id `com.plantcommunity.plantCommunityMobile`.
   **Do not start this until 2b is proven on a device.** Android falls back to the
   iOS key today; restricting it before Android is verified on its own key signs
   out every Android user.
4. Add API restrictions so each key can only call the Firebase APIs actually used.
5. Re-run the probe: both keys must return a `*_BLOCKED` reason instead of
   `MISSING_ID_TOKEN`. That is the acceptance test — the same command that found
   the problem.
6. Rebuild and authenticate on a real Android device **and** a real iOS device.
   Step 3 is the step that breaks Android if 382 was done wrong, so test both.
7. Only then dismiss alerts #1 and #2 as `wont_fix`, citing the restrictions.

~~`apikeys.googleapis.com` returning 403 `SERVICE_DISABLED` only matters if you
want to set restrictions via API; the Console UI does not require it.~~
**WRONG — corrected 2026-09-12.** The Console UI *does* require it: without the
API enabled the key's edit page renders with **no Application restrictions section
at all**, while the Credentials list still shows the key and its "unrestricted"
warning. Enabling `apikeys.googleapis.com` is a prerequisite for step 1 by either
route. See the 2026-09-12 Work Log entry.

### 2026-09-12 - STEP 1 DONE: Android key restricted and verified

Applied by the maintainer in the Cloud Console (Application restrictions → Android
apps → package `com.plantcommunity.plant_community_mobile` + the debug SHA-1
`06:8A:...:7D:C2`). Verified with the same probe that found the problem — the
acceptance test, not a fresh one:

| Request | Before (2026-09-11) | After (2026-09-12) |
| --- | --- | --- |
| android key, no headers | 400 `MISSING_ID_TOKEN` | **403 `API_KEY_ANDROID_APP_BLOCKED`** |
| android key + `X-Android-Package: com.attacker.not.our.app` | 400 `MISSING_ID_TOKEN` | **403 "Requests from this Android client application com.attacker.not.our.app are blocked."** |
| ios key, no bundle header | 400 `MISSING_ID_TOKEN` | 400 `MISSING_ID_TOKEN` (unchanged, intended) |

The second row is the proof. An identical request — another app claiming our
package name — succeeded before and is now rejected *by name*, so the restriction
is real rather than the endpoint failing for an unrelated reason. The third row is
the proof the app is unaffected: the iOS key is what both builds actually
authenticate with, and it is untouched.

No propagation delay was observed; the change was live on the first probe.

**Two operational facts for whoever does step 3, so they are not rediscovered:**

- **The `firebase-adminsdk` service account cannot do any of this.** It has no
  `apikeys.keys.*` permission at all: `apikeys.keys.list` and `apikeys.keys.lookup`
  both return `403 PERMISSION_DENIED` even with the API enabled. That is correct
  least-privilege (`docs/rules/firebase.md`: "no broad Editor/Owner service
  accounts") — do **not** widen the runtime SA to script this. It needs a human
  with Owner, or `roles/serviceusage.apiKeysAdmin`.
- **`apikeys.googleapis.com` must be enabled for the Console UI to render the
  restriction editor.** An earlier note in this todo claimed the UI did not need
  it; that was wrong. Symptom: the Credentials page lists the key and shows the
  "unrestricted" warning triangle, but the key's edit page has no *Application
  restrictions* section at all. Enabling the API makes it appear. The tell that
  you have the right diagnosis: the API error changes from
  `403 SERVICE_DISABLED` to `403 PERMISSION_DENIED` on a *named* permission.

**Remaining on this todo — all blocked on todo 382:** steps 3-7. The iOS key stays
unrestricted deliberately, because the Android app authenticates with it, and
restricting it before 382 breaks Android sign-in for every user. Alerts #1 and #2
stay open until then.

### 2026-09-12 - CLOSED. Both keys restricted and verified; alerts resolved

**iOS key restricted** by the owner in the Console (iOS apps → bundle id
`com.plantcommunity.plantCommunityMobile`), which only became possible once todo
382 split the shared key. Probe re-run over both keys, 8/8 rows as expected:

| key | legitimate client | wrong id | no headers | other platform's headers |
|---|---|---|---|---|
| iOS | ADMITTED (`MISSING_ID_TOKEN`) | `API_KEY_IOS_APP_BLOCKED` | blocked | blocked |
| Android | ADMITTED | `API_KEY_ANDROID_APP_BLOCKED` | blocked | blocked |

Both fields of each restriction are load-bearing, and neither key works for the
other platform. The abuse path on both published keys is closed.

**Alerts #1 (Android) and #2 (iOS) resolved `wont_fix`** with per-key comments
naming the control and its verification. `open alerts: 0`.

**The device AC was consciously traded away, not forgotten.** The owner confirmed
nothing is distributed, so restricting the iOS key could at worst break a local
build (revertible by one `.env.local` line). See todo 383 for the residue.

**Found while verifying todo 011 against the live project:** the deployed Storage
security rules are **3.5 months behind the repo**. `firebase/storage.rules`
tightened three read rules from `isAuthenticated()` to `isOwner(userId)` on
2026-05-23 (PR #285) and was never deployed; prod still serves the 2025-11-14
ruleset. Nothing is exposed — the bucket holds **0 objects** and no code writes to
those prefixes — but a todo was closed on a commit that never reached production.
Filed as todo 383 item 1.

**Method note worth keeping.** Every real finding in this todo came from probing
the live system, and every wrong belief came from reading a file:

- "both keys unrestricted" — found by probe, not by the Console.
- "the iOS key cannot be restricted at all" — found by asking why a SHA-1 was
  needed, after a remediation plan that would have broken Android had already
  passed my own review and a PR body.
- "the Storage rules are deployed" — a repo file said yes; the Rules API said the
  repo is three months ahead.

A green checkbox describing production is worth exactly as much as the last time
someone asked production.
