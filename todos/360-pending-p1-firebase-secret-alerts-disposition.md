---
status: pending
priority: p1
issue_id: "360"
tags: [security, firebase, mobile, github, gcp]
dependencies: []
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
- [ ] `apikeys.googleapis.com` enabled on project 190351417275
- [ ] Android key restricted to package + the SHA-1 that signs the SHIPPED
      artifact (Play App Signing cert if enabled, not the upload cert)
- [ ] iOS key restricted to bundle id `com.plantcommunity.plantCommunityMobile`
- [ ] Probe re-run: both keys return a `*_BLOCKED` reason, not `MISSING_ID_TOKEN`
- [ ] App still authenticates on a real Android device AND a real iOS device
- [ ] Both secret-scanning alerts closed with a written resolution comment
- [ ] `gh api .../secret-scanning/alerts?state=open` returns an empty list
- [ ] Todo 011's acceptance criteria rewritten to match reality and the todo
      moved off `code-complete`

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

**Revised order of work** (supersedes Recommended Action steps 1-2, which assumed
the restriction state was unknown):

1. Enable `apikeys.googleapis.com` on the project (needed to read or set
   restrictions via API; the Console UI does not require it).
2. Restrict the Android key to `com.plantcommunity.plant_community_mobile` +
   the correct signing SHA-1(s) per the footgun above.
3. Restrict the iOS key to bundle id `com.plantcommunity.plantCommunityMobile`.
4. Add API restrictions so each key can only call the Firebase APIs actually used.
5. Re-run the probe: both keys must now return a `*_BLOCKED` reason instead of
   `MISSING_ID_TOKEN`. That is the acceptance test — it is the same command that
   found the problem.
6. Rebuild and authenticate on a real Android device and a real iOS device.
7. Only then dismiss alerts #1 and #2 as `wont_fix`, citing the restrictions.
