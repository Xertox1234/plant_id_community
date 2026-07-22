---
status: pending
priority: p2
issue_id: "260"
tags: [forum, flutter, mobile]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H11"
---

# Forum epic: Flutter mobile forum client

## Problem

The mobile forum is a hardcoded 3-post visual stub ("Live posting coming soon",
empty `onPressed`) — 0% forum parity on the project's PRIMARY platform. The
backend contract built specifically for mobile (delta `/sync/` cursor,
tombstones, idempotency keys, FCM push task) has no consumer. Single-finding
epic (H11) from the 2026-07-11 forum-modernization audit — small finding count,
large scope.

## Findings

- **H11** — `plant_community_mobile/lib/features/forum/forum_screen.dart:11-71`
  is a hardcoded stub; verified by direct read during the audit.
- Backend readiness (from the audit's strengths inventory): cursor-paginated
  lists, compound `(updated_at, id)` `/sync/` cursor + `TopicDeletedLog`
  tombstones, Idempotency-Key contract on writes, 4-layer-validated image
  upload, `send_forum_push` FCM task (fixed for permanent-error handling in
  audit M33) — all unconsumed.

## Recommended Action

Phased to ship value early:

1. **Read path**: boards → topics → posts screens (Riverpod 3.x providers per
   the project pattern doc), StreamField body renderer with block parity
   (paragraph/image/quote/heading/code) matching the web renderer contract.
2. **Offline sync**: consume `/sync/` with the compound cursor + tombstone
   deletions — the contract the backend already ships.
3. **Write path**: create/reply/edit/delete/react with Idempotency-Key retry
   semantics; surface pending-moderation state (web PR-2b's notify-and-return
   pattern is the reference).
4. **FCM registration**: ~~populate `ForumProfile.fcm_token` via the existing
   `/me/profile` endpoint~~ — DONE by todo 253 slice 6 (2026-07-16):
   `lib/services/push_registration_service.dart` registers/rotates/clears the
   token through the auth flow, live-verified on an Android emulator against
   the dev backend (`integration_test/fcm_registration_e2e_test.dart`). What
   remains for THIS todo: deep-linking a push tap into the native forum UI
   once it exists, and the iOS APNs provisioning residue (todo 272 item 1).
5. **Image upload** against `POST /forum/images/`.

## Technical Details

- Follow `plant_community_mobile/docs/patterns/` (riverpod.md,
  flutter-patterns.md, firebase-auth.md for the JWT exchange).
- Codegen gate: editing `@riverpod`/freezed sources requires `build_runner`
  regen — local `flutter analyze` won't catch stale `.g.dart`, CI does.
- Prefer landing todo 258's M35/M36 idempotency fixes before the mobile write
  path ships (mobile retries are exactly the trigger for the duplicate-push
  bug traced there).

## Acceptance Criteria

- [ ] Boards/topics/posts browsable natively with StreamField bodies rendered
      (all 5 block types)
- [ ] Delta sync consumes `/sync/` including tombstoned deletions (test with
      fake backend fixtures)
- [ ] Reply/create retries are idempotent; pending-moderation surfaced in UI
- [x] Device registers an FCM token and receives a forum push end-to-end
      — PROVEN 2026-07-22 (see todo 253 Work Log 2026-07-22). On an Android
      emulator: a fresh 142-char token registered via the real auth+PATCH
      chain, a genuine `reply_added` publish sent through
      `send_forum_push_batch` → `messaging.send()` (real Certificate,
      returned a real FCM message id, not `NotRegistered`), and the
      notification was RECEIVED + rendered in the device tray (`dumpsys
      notification` record + screenshot). This also satisfied todo 253's AC6.
      NB: verified with a throwaway `flutter run` harness
      (`tool/fcm_e2e_hold.dart`) since `flutter test` uninstalls the app on
      teardown and invalidates the token; this todo's own native forum UI +
      push-tap deep-linking are still open below.
- [ ] `flutter analyze` + `flutter test` green including regenerated codegen

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Single-finding epic per the manifest's Phase 4 grouping table (H11).

## Notes

p2 by grouping, but note the tension: mobile is the project's primary platform
and this is the largest single gap — promote when the p1 epics' backend
surfaces (notifications, solved marking) stabilize, so the client consumes
final contracts rather than chasing them.
