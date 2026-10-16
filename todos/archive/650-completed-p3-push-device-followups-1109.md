---
status: completed
priority: p3
issue_id: "650"
tags: [push, notifications, mobile, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-16
owner_decision: "Device cap: evict the account's oldest PushDevice above N=10, silently (2026-10-16)"
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1109 review (todo sweep run 2026-10-12-1736)

Filed by the closing step of the run from `state.py followups-md g2`.

### 2026-10-16 - Implemented by the todo sweep (run 2026-10-16-1135)

- #1 fixed: every due task is now the same `_TaskTile(key: ValueKey(id))` highlighted or not (the `KeyedSubtree`/`GlobalKey` wrapper is gone), and the tile scrolls itself into view when highlighted, so an in-flight Mark done/Skip keeps its busy state. Tests in `plant_community_mobile/test/features/garden/garden_screen_test.dart` (the first fails on the old code).
- #2 fixed for the single path: `send_forum_push` now guards each per-device `token=` re-enqueue and logs only the exception type. The batch path was already guarded on main (`send_forum_push_batch`, the todo 643 #1 `try` around the hand-off). #3 fixed: per-account 429 tests for both endpoints (separate buckets, 30/h each).
- #4 fixed: `MeProfileView.perform_update` runs the column write and its `PushDevice` mirror in one `transaction.atomic()`; a caught `IntegrityError` still keeps the column (`register_device`'s own savepoint rolls back), any other error rolls both back.
- #5/#6 fixed per the owner decision: `PUSH_DEVICE_MAX_PER_ACCOUNT = 10`; `register_device` evicts the account's oldest devices (by `created_at`; superseded by `updated_at` in review round 1 below) past it, silently, never the device being registered, and clears an evicted token from the legacy column. `device_tokens_for_users` also targets only the newest 10, so rows from before the cap cannot stretch a forum push or the care sweep. The token format check is declined: FCM publishes no token grammar, so a check could drop real devices, and the cap already bounds the loop.
- #7 fixed: the installation id moves to a new key in `FlutterSecureStorage` with `first_unlock_this_device`, which a backup restore never carries to another phone; the old key is deleted, never reused. A new key, because the iOS plugin matches accessibility on read. An existing install mints one new id once, and the backend updates that device's row in place (same token).

### 2026-10-16 - Verified by the todo sweep (run 2026-10-16-1135)

- AC 1: `bash -c "cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/core/tests/test_push_devices.py apps/garden_calendar/tests apps/forum_host/tests --create-db -q -p no:cacheprovider && cd plant_community_mobile && flutter test test/features/garden/garden_screen_test.dart test/services/push_registration_service_test.dart test/services/push_care_target_test.dart && grep -n -A6 'Implemented by the todo sweep (run 2026-10-16-1135)' todos/archive/650-completed-p3-push-device-followups-1109.md"` — evidence `.sweep-evidence/g5/650-ac0.txt` (not committed), last lines:

  ```text
  55-- #1 fixed: every due task is now the same `_TaskTile(key: ValueKey(id))` highlighted or not (the `KeyedSubtree`/`GlobalKey` wrapper is gone), and the tile scrolls itself into view when highlighted, so an in-flight Mark done/Skip keeps its busy state. Tests in `plant_community_mobile/test/features/garden/garden_screen_test.dart` (the first fails on the old code).
  56-- #2 fixed for the single path: `send_forum_push` now guards each per-device `token=` re-enqueue and logs only the exception type. The batch path was already guarded on main (`send_forum_push_batch`, the todo 643 #1 `try` around the hand-off). #3 fixed: per-account 429 tests for both endpoints (separate buckets, 30/h each).
  57-- #4 fixed: `MeProfileView.perform_update` runs the column write and its `PushDevice` mirror in one `transaction.atomic()`; a caught `IntegrityError` still keeps the column (`register_device`'s own savepoint rolls back), any other error rolls both back.
  58-- #5/#6 fixed per the owner decision: `PUSH_DEVICE_MAX_PER_ACCOUNT = 10`; `register_device` evicts the account's oldest devices (by `created_at`) past it, silently, never the device being registered, and clears an evicted token from the legacy column. `device_tokens_for_users` also targets only the newest 10, so rows from before the cap cannot stretch a forum push or the care sweep. The token format check is declined: FCM publishes no token grammar, so a check could drop real devices, and the cap already bounds the loop.
  59-- #7 fixed: the installation id moves to a new key in `FlutterSecureStorage` with `first_unlock_this_device`, which a backup restore never carries to another phone; the old key is deleted, never reused. A new key, because the iOS plugin matches accessibility on read. An existing install mints one new id once, and the backend updates that device's row in place (same token).
  ```

### 2026-10-16 - Completed by the todo sweep (run 2026-10-16-1135)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-16 - Review round 1: non-blocking findings (run 2026-10-16-1135)

- Fixed, medium x3 + low (`backend/apps/core/push_devices.py`): eviction and the send-path cap ranked
  devices by `created_at`, which re-registration never changes. A phone in daily use therefore looked oldest
  and was evicted, or skipped, ahead of newer stale rows. Both now rank by `-updated_at, -pk` (auto_now, bumped
  on every registration). The new `test_a_device_in_use_outlives_newer_stale_ones` fails with `created_at`
  ranking and passes now. The send-path test now sets `updated_at`.
- Fixed, medium + low x2 (`plant_community_mobile/lib/features/garden/garden_screen.dart`): the tile revealed
  itself on every `initState`, so a highlighted tile rebuilt on scrolling back yanked the list mid-drag. A
  repeat reminder for the highlighted task also no longer scrolled back to it. Each reminder now bumps a token
  that a tile must claim from the list (`_claimReveal`), once. A lazily rebuilt tile reuses the list's last
  widget, so the claim, not the widget, carries the "once". Two new widget tests (repeat tap, scroll back)
  each fail under a mutation of the claim or the token and pass now.
- Fixed, medium (`backend/apps/core/tests/test_push_devices.py`): the two count-to-limit rate-limit loops
  now run inside `with freeze_time():`, so the ratelimit window cannot roll over mid-loop.
- Fixed, low x2 (`plant_community_mobile/lib/services/push_registration_service.dart`): the legacy key is
  deleted with the default `FlutterSecureStorage()` it was written with, in its own try, so a failed delete
  never discards the new id. The mock storage cannot make the delete throw, so that path is unit-untested.
- Fixed, low x2 (send path returns cap + 1): `device_tokens_for_users` now documents that the legacy column
  adds at most one token.
- Declined, low (cap tests derive fixtures from the constant): `test_the_cap_is_ten` pins the literal, so a
  shrink of the constant fails on that test.

### 2026-10-16 - Review round 2: non-blocking findings (run 2026-10-16-1135)

- Fixed, medium x2 + low (`garden_screen.dart`): the round-1 claim was taken only in a tile's `initState`, so a
  reminder for a tile past the cache extent stayed unclaimed. The first build as the user scrolled toward it
  then yanked the list. `_consume` now claims the token in a post-frame callback, after any tile built that
  frame has claimed it. The new `a reminder for a tile not yet built never yanks the list later` test fails
  without that claim and passes now. Not scrolling to an unbuilt tile is unchanged from main: reveal needs a
  built tile.
- Fixed, low (`backend/apps/forum_host/api.py` legacy PATCH): a rotation registered the new token before
  unregistering the old one, so at the cap it evicted a live phone. The old token now goes first. The new
  `test_a_legacy_rotation_at_the_cap_evicts_no_live_device` fails with the old order and passes now.
- Fixed, low x2 (`device_tokens_for_users` docstring): it now says least to most recently registered.
- Fixed, low x2 (`test_a_failed_release_rolls_back_the_replacing_write`): now asserts the 500.
- Fixed, low (this Work Log): the Implemented entry's "by `created_at`" is marked as superseded.
- Fixed, low (`garden_screen_test.dart`): the scroll loops are bounded at 200 drags and assert the tile is
  found.
- Declined, low (`test_the_cap_is_ten` checks no behaviour): it is a deliberate tripwire on the owner's number
  (2026-10-16); the behavioural cap tests read the constant.
- Declined, low (the legacy keychain delete is not retried): a leftover item is clutter only, since nothing
  reads the old key.
- Declined, low (the this-device-only test re-reads the constant): the plugin's mock storage ignores
  `IOSOptions`, so no unit test can observe the options in use. The constant is the only seam.
