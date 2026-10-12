---
status: pending
priority: p3
issue_id: "650"
tags: [push, notifications, mobile, follow-ups]
dependencies: []
---

# Follow-ups from PR #1109 (todo 621, mobile push devices)

## Problem

Todo-sweep run 2026-10-12-1736 merged PR #1109 (todo 621, multi-device push registration and the in-app
foreground banner). The non-blocking review findings are below. The curator merged duplicates and checked
each item against main, and the refuter tried to refute what was left; the items that survived are listed.
Filed at p3, not p4: findings 5–7 (no per-account device cap, the care sweep stall it allows, and the iOS
keychain accessibility that a backup restore carries over) affect delivery for real accounts.

## Findings

PR #1109 (todo sweep run 2026-10-12-1736, group g2, todos 621); follow-ups: verified.

1. **medium** `plant_community_mobile/lib/features/garden/garden_screen.dart:163` The highlighted task is wrapped in a KeyedSubtree with a GlobalKey, so `_TaskTile`'s parent changes when highlighting toggles; its state is discarded and an in-flight mark-done/skip loses its busy flag and re-enables the button. | also: The highlighted task is wrapped in a KeyedSubtree with a GlobalKey, so the `_TaskTile`'s parent changes when highlighting toggles. Its state is discarded, and an in-flight mark-done or skip loses its busy flag and re-enables the button.
2. **medium** `backend/apps/forum_host/tasks.py:420` Per-device re-enqueue `send_forum_push.delay(..., token=...)` in the batch and single paths is unguarded; a broker error mid-loop escapes after earlier devices were sent. The care path wraps it in `_retry_device_later`; the forum path doesn't. | also: Per-device re-enqueue (`send_forum_push.delay(..., token=...)`) in the batch and single paths is unguarded. A broker error mid-loop escapes after earlier devices were sent. The care-reminder path wraps this in `_retry_device_later`; the forum path doesn't.
3. **medium** `backend/apps/core/tests/test_push_devices.py:726` Both new push-device endpoints are rate-limited (block=True, 429 in schema) but no test drives the 429; deleting the ratelimit decorator or mis-wiring the shared bucket keeps the suite green. | also: Both new endpoints are rate-limited (block=True, 429 documented in schema) but no test drives the 429. Deleting the ratelimit decorator, or mis-wiring the shared bucket, keeps the suite green.
4. **medium** `backend/apps/forum_host/api.py:135` The legacy fcm_token column write and the PushDevice mirror are not in one transaction. A crash or DB error between them leaves the column set but no PushDevice row, or a replaced token not unregistered. Only IntegrityError is handled. The send path still reads the column, so impact is small.
5. **medium** `backend/apps/core/push_devices.py:53` No per-account device cap and no token format check: a user can POST junk tokens with fresh installation_ids 30/hour; FCM's InvalidArgumentError is permanent but not dead, so the rows are never cleared and every forum push and care sweep loops over them. | also: No per-account device cap and no token format check. Any user can POST a junk token with a fresh installation_id 30 times an hour. FCM rejects junk with InvalidArgumentError, which counts as permanent but not dead, so those rows are never cleared. Every forum push and care sweep then loops over all of them.
6. **medium** `backend/apps/garden_calendar/tasks.py:297` Follows from the missing cap: `_push_to_owners` sends to each device in turn within the sweep's 4-minute soft limit, so an owner with thousands of junk rows can hit SoftTimeLimitExceeded every sweep, and the re-claimed claim stalls care reminders for everyone else. | also: Follows from the missing cap. `_push_to_owners` sends to each device one after another inside the sweep's 4-minute soft limit. One opted-in owner with thousands of junk rows can hit SoftTimeLimitExceeded every sweep. Their claim is released and picked up again oldest-first, so care reminders stall for every other owner.
7. **medium** `plant_community_mobile/lib/services/push_registration_service.dart:513` installation_id is stored with default FlutterSecureStorage (iOS WhenUnlocked, which a backup restore carries over), so a restored second phone shares the id and each phone's registration deletes the other's row through the installation clash. | also: installation_id is stored with default FlutterSecureStorage (iOS WhenUnlocked, which a backup restore carries over). A restored second phone shares the id, so each phone's registration deletes the other's row through the installation clash.

42 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/apps/forum_host/api.py:122 Legacy mirror never releases the profile's previous token when an old build PATCHes a new one; the rotated-away PushDevice row (installation_id null) stays targeted, gets duplicate pushes, and outlives an old-build sign-out. (fixed on main: MeProfileView.perform_update on main captures previous = fcm_token and, after register_device(legacy=True), calls unregister_device(user, previous) when previous != token.; the refuter agreed: origin/main MeProfileView.perform_update saves previous = fcm_token and, after register_device(legacy=True), calls unregister_device(user, previous) when previous != token. The rotated-away row is removed, so no duplicate pushes and nothing stale survives an old-build sign-out.)
- medium: backend/apps/forum_host/api.py:122 Legacy mirror never releases the profile's previous token when an old build PATCHes a new one. The rotated-away token's PushDevice row (migrated or mirrored, installation_id null) stays and is still targeted. An old-build sign-out clears only the newest token, so the stale one outlives sign-out. Before this change the column was overwritten. | also: Legacy-build token rotation: PATCH fcm_token=new registers the new PushDevice but never removes the previous token's row (migrated or earlier mirrored, installation_id NULL). Both stay targeted, so the device gets duplicate pushes until FCM reports the old token dead. | Legacy mirror registers the new token via register_device(platform='legacy') but never removes the account's previous token row when an old build rotates its token (no installation_id). The stale PushDevice row keeps getting sends and can duplicate pushes until FCM reports it dead. (refuted: origin/main MeProfileView.perform_update saves previous = fcm_token and, after register_device(legacy=True), calls unregister_device(user, previous) when previous != token. The rotated-away row is removed, so no duplicate pushes and nothing stale survives an old-build sign-out.)
- medium: backend/apps/forum_host/api.py:135 The legacy mirror unregisters `previous`, but that column token can belong to an upgraded device because register_device never clears the caller's own column, so a pre-621 phone's write or clear deletes the other upgraded phone's PushDevice row. | also: The legacy mirror unregisters `previous`, but that column token can belong to an upgraded device. register_device never clears the caller's own column. So a pre-621 phone writing or clearing its token deletes the PushDevice row of the account's other, upgraded phone, which then gets no pushes. (refuted: register_device(legacy=False) does clear the caller's own column (it excludes the user only when legacy=True), so the stated mechanism is wrong. also[1] holds: ATOMIC_REQUESTS is off and perform_update wraps the column save and mirror in no atomic block, catching only IntegrityError.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1109 review (todo sweep run 2026-10-12-1736)

Filed by the closing step of the run from `state.py followups-md g2`.
