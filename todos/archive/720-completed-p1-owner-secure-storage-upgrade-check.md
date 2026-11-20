---
status: completed
priority: p1
issue_id: "720"
tags: [mobile, flutter, auth, security, device-check, owner]
dependencies: ["715"]
triage: ready
triaged: 2026-11-19
owner_decision: "Unblocked: owner said 'iPhone test successful' after updating to TestFlight build 27 (main 011f029c), and asked Claude to 'take care of the Android test' on the Samsung SM-A376B, which Claude verified over wireless adb (2026-11-19); criterion 0 confirmed by the owner (2026-11-19): iPhone: owner reported 'iPhone test successful' after the TestFlight upgrade to build 27 (main 011f029c). Samsung SM-A376B: at the owner's request ('Can you take care of the Android test?') Claude checked the profile APK from 011f029c installed with adb install -r over the Nov 5 build (firstInstallTime 2026-11-05 kept, lastUpdateTime 2026-11-19 16:19): cold launch came up signed in (Profile showed the owner's account), no auth or storage errors in logcat"
---

# Owner: check an upgrade keeps you signed in (secure-storage change)

## Problem

Todo 715 (M14) changes how the app stores its sign-in data: the iOS keychain
items move to `first_unlock_this_device`, the unused refresh token is no longer
stored, and Android backup is turned off. Signed-in users must stay signed in
when the new build installs over the old one. Tests can't show that; only a
real upgrade on a phone can (owner decision 2026-11-19: ship the code now, check
on the next TestFlight build and Android APK, like 717 → 719).

## Recommended Action

With an older build installed and signed in on each phone:

1. iPhone: install the first TestFlight build that contains todo 715 over it
   (do not delete the app first). Open it.
2. Samsung: install the profile APK from the same commit over the old one.
   Open it.
3. On each, confirm you are still signed in (profile shows your account, no
   login screen), then sign out and back in once.

## Acceptance Criteria

- [x] Owner: upgrading over an installed build keeps the user signed in on a
      real iPhone (TestFlight) and the Samsung (Android) — record the date,
      build numbers and devices.

## Work Log

### 2026-11-19 - Filed

- Moved here from todo 715's upgrade criterion (owner decision 2026-11-19:
  "Separate device todo").

### 2026-11-19 - Implemented by the todo sweep (run 2026-11-20-0142)

- No code change: the only criterion is an owner device check, confirmed by
  the owner on 2026-11-19 and recorded as owner-confirmed in the sweep evidence.
- iPhone: the owner upgraded to TestFlight build 27 (main 011f029c) over the
  installed build and reported "iPhone test successful".
- Samsung SM-A376B: at the owner's request, the profile APK from 011f029c was
  installed with `adb install -r` over the Nov 5 build (firstInstallTime
  2026-11-05 kept, lastUpdateTime 2026-11-19 16:19); a cold launch came up
  signed in (Profile showed the owner's account), with no auth or storage
  errors in logcat.

### 2026-11-19 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-20-0142)

- AC 1: confirmed by the owner on 2026-11-19: "iPhone: owner reported 'iPhone test successful' after the TestFlight upgrade to build 27 (main 011f029c). Samsung SM-A376B: at the owner's request ('Can you take care of the Android test?') Claude checked the profile APK from 011f029c installed with adb install -r over the Nov 5 build (firstInstallTime 2026-11-05 kept, lastUpdateTime 2026-11-19 16:19): cold launch came up signed in (Profile showed the owner's account), no auth or storage errors in logcat" (`state.py confirm`; no command or evidence)

### 2026-11-19 - Completed by the todo sweep (run 2026-11-20-0142)

- Archived by `land.py archive`; review is on the PR.

### 2026-11-19 - Review round 1 (clean; 2 lows handled here)

- Builds: Android versionName 1.0.0 / versionCode 10 before and after (a
  local profile APK does not bump it; firstInstallTime 2026-11-05 and the
  kept data show it was an upgrade, not a fresh install). iPhone: the owner
  updated to build 27 from the TestFlight build already installed; the
  from-build number was not recorded.
- Sign out and back in: not run on the Samsung (it needs the owner's
  password, and the criterion only asks that the upgrade keeps the user
  signed in). For the iPhone the owner was asked to do it and replied
  "iPhone test successful".
- The Samsung check was run by Claude at the owner's request ("Can you take
  care of the Android test?"), not by the owner in person.
