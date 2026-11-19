---
status: completed
priority: p1
issue_id: "719"
tags: [mobile, ios, auth, apple, device-check, owner]
dependencies: ["717"]
triage: ready
triaged: 2026-11-19
owner_decision: "Owner 2026-11-19: device check done on TestFlight build 26 (main b865a814); owner answered 'Yes, close it' to whether it satisfies the criterion. Sign-up sends no email (an Apple-verified address is marked verified), so the relay email checked was the account-deletion email. (2026-11-19); criterion 0 confirmed by the owner (2026-11-19): Owner, TestFlight build 26, 2026-11-19: Apple Hide My Email sign-up made a new account ('no plants, this must be a new account'); deletion 'asked me to sign in with apple first, then continued successfully'; 'got the deletion email, and the app is gone from settings'. The relay email received was the deletion email: the app sends none at sign-up. Owner confirmed this satisfies the criterion ('Yes, close it')."
---

# Owner: check Sign in with Apple on a real iPhone (TestFlight)

## Problem

Todo 717 added "Continue with Apple" to the iOS app. Its device criterion can
only run on a TestFlight build that has the code, so it moved here (owner
decision 2026-11-19: "Build now", the iPhone check moves to a follow-up todo
for after the next TestFlight build).

Some things only a real device shows. Tests can't prove:

- that Apple's name reaches the backend token on the first sign-in;
- that Apple's private relay delivers the app's email (the sender
  domains were registered and SPF-verified on 2026-11-19);
- that the re-authentication on account deletion returns an authorization
  code that Firebase revokes.

## Recommended Action

Once a TestFlight build containing todo 717 is installed, use an Apple ID that has
never signed in to Houseplant MD:

1. Tap **Continue with Apple**, choose **Hide My Email**, accept the terms.
2. Confirm the welcome or verification email arrives in the real inbox.
3. Confirm the profile shows the Apple account's name.
4. Delete the account in the app.
5. In iPhone Settings → your name → Sign in with Apple, confirm Houseplant
   MD is no longer listed.

## Acceptance Criteria

- [x] Owner: on a real iPhone (TestFlight), sign up with Apple using "Hide My
      Email", receive the verification or welcome email at the relay address,
      then delete the account — record the date and build number.

## Work Log

### 2026-11-19 - Filed

- Moved here from todo 717's device criterion (owner decision 2026-11-19).

### 2026-11-19 - Implemented by the todo sweep (run 2026-11-19-1922)

- No code change: the only criterion is an owner device check, which the owner ran on
  TestFlight build 26 (main b865a814) on 2026-11-19.
- Owner's report: an Apple "Hide My Email" sign-up made a new account; deletion asked for
  Sign in with Apple again, then succeeded; the deletion email arrived at the relay address and
  Houseplant MD is gone from iPhone Settings → Sign in with Apple.
- The relay email checked was the account-deletion email, because the app sends no email at
  sign-up (an Apple-verified address is marked verified). The owner confirmed this satisfies the
  criterion ("Yes, close it").
- Criterion 0 recorded as owner-confirmed for Land to tick with the owner's words.

### 2026-11-19 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-19-1922)

- AC 1: confirmed by the owner on 2026-11-19: "Owner, TestFlight build 26, 2026-11-19: Apple Hide My Email sign-up made a new account ('no plants, this must be a new account'); deletion 'asked me to sign in with apple first, then continued successfully'; 'got the deletion email, and the app is gone from settings'. The relay email received was the deletion email: the app sends none at sign-up. Owner confirmed this satisfies the criterion ('Yes, close it')." (`state.py confirm`; no command or evidence)

### 2026-11-19 - Completed by the todo sweep (run 2026-11-19-1922)

- Archived by `land.py archive`; review is on the PR.
