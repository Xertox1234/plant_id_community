---
status: pending
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

- [ ] Owner: upgrading over an installed build keeps the user signed in on a
      real iPhone (TestFlight) and the Samsung (Android) — record the date,
      build numbers and devices.

## Work Log

### 2026-11-19 - Filed

- Moved here from todo 715's upgrade criterion (owner decision 2026-11-19:
  "Separate device todo").
