---
status: pending
priority: p2
issue_id: "360"
tags: [security, firebase, mobile, github]
dependencies: []
---

# Resolve the two open Firebase secret-scanning alerts (todo 011's unfinished half)

## Problem

Two GitHub secret-scanning alerts (#1, #2, both "Google API Key") have been open
since **2025-10-22** on a public repo. Todo 011 addressed them in code and then
stalled: it sits at `status: code-complete` with **all 12 acceptance criteria
unchecked**, its Work Log ending "Code changes complete, deployment actions
required." Nobody re-opened it, so the alerts have simply aged.

The alerts cannot be closed by more code. They need a **disposition decision**
that depends on a fact only the Google Cloud Console can supply.

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
   SHA-1 certificate fingerprint; iOS bundle ID). **Unverified — this is the
   open question.**
2. **Firebase Security Rules** — `firebase/firestore.rules` and
   `firebase/storage.rules` both exist, and todo 011 confirmed they are
   deny-by-default with authenticated-only access.

If (1) is in place, the alerts are false positives and should be dismissed with
a written reason. If (1) is absent, an unrestricted key is genuinely abusable
for quota/billing exhaustion against the project, and restriction — not
rotation — is the fix.

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

- [ ] Console restriction state recorded for both the Android and iOS keys
- [ ] Restrictions applied if they were missing, with the app still building
      and authenticating afterwards
- [ ] Both secret-scanning alerts closed with a written resolution comment
- [ ] `gh api .../secret-scanning/alerts?state=open` returns an empty list
- [ ] Todo 011's acceptance criteria rewritten to match reality and the todo
      moved off `code-complete`

## Notes

p2, not p0 as todo 011 was rated. The original p0 assumed these were live
credentials. They are client identifiers shipped in every install of the app,
behind existing deny-by-default security rules — real exposure depends entirely
on the unverified restriction state, which is why step 1 gates everything else.
Not p3 because an open, un-triaged secret alert on a public repo for 10+ months
is itself a signal-quality problem: it trains everyone to ignore the alert list.

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
