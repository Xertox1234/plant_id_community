---
status: completed
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

- [x] Boards/topics/posts browsable natively with StreamField bodies rendered
      (all 5 block types) — native boards→topics→thread screens; body renderer
      dispatches heading/paragraph(HTML)/quote/code/image + deleted-image and
      unknown fallbacks. Proven by `forum_body_block_test` (parses all 5 types),
      `forum_body_renderer_test` (renders all 5 + fallbacks), and
      `forum_read_path_test` (home lists boards + recent; thread renders posts).
- [x] Delta sync consumes `/sync/` including tombstoned deletions (test with
      fake backend fixtures) — `ForumSyncService` pages the compound cursor,
      applies upserts + tombstone removals. `forum_sync_service_test` covers
      initial full sync, a delta with upsert+tombstone, multi-page `has_more`,
      and offline `cachedTopics`.
- [x] Reply/create retries are idempotent; pending-moderation surfaced in UI —
      `ForumComposerController` holds one `Idempotency-Key` across retries
      (`forum_composer_controller_test` asserts key reuse after a simulated
      failure); pending ("notify-and-return") surfaced via the composer notice
      and the post `Awaiting moderation` chip (`forum_read_path_test`).
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
- [x] `flutter analyze` + `flutter test` green including regenerated codegen —
      `flutter analyze` → "No issues found!"; `flutter test` → "All tests
      passed!" (213 passed, 3 pre-existing skips); `build_runner` re-run writes
      0 outputs (codegen current).

## Work Log

### 2026-07-25 - Completed by completing-todos skill (run 2026-07-25-0115)

- Verification: all 5 acceptance criteria pass (native read path + 5-block
  renderer, `/sync/` delta with tombstones, idempotent create/reply + pending
  UI, FCM already proven, `flutter analyze` clean + full suite 220 passed).
- Review: 4 review passes (bundled deep-correctness + orchestrator +
  flutter-dart-reviewer + cross-cutting-reviewer); 3 HIGH + 3 MEDIUM + 2 LOW
  findings all repaired with tests. No accepted/unaddressed blocking findings.
- Deferred (Recommended-Action extras beyond the AC): image composer,
  edit/delete, FCM deep-linking, subscriptions, notifications, search,
  profiles, reply-visibility — tracked in todo 279.

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Single-finding epic per the manifest's Phase 4 grouping table (H11).

### 2026-07-25 - Native forum client implemented (read + sync + write)

Scoped to the acceptance criteria (the epic's Recommended-Action extras —
image-in-composer, edit/delete, FCM deep-link routing, subscriptions,
notifications list, search, profiles — are deferred to a follow-up todo).

- **Models** (`lib/features/forum/models/`): hand-written (no freezed) —
  author, board, topic (list + detail), post, 5-type sealed body block, sync
  (stub/tombstone/page/cursor), cursor page, write results.
- **Services** (`lib/features/forum/services/`): `ForumApi` interface +
  `HttpForumApi` (dio via `apiServiceProvider`, `Idempotency-Key` on every
  write); `ForumSyncStore` (in-memory + JSON-file `path_provider` impls) with a
  pure `applyForumSyncDelta`; `ForumSyncService` pagination loop;
  `ForumComposerController` (one idempotency key per compose action).
- **Providers**: boards, board-topics (cursor `loadMore`), topic detail,
  topic-posts (`loadMore` + reaction toggle), recent-topics (sync consumer).
- **Widgets**: HTML paragraph renderer (`html` pkg over the FORUM allowlist),
  body renderer, post/topic cards, trust badge (level-0 hidden), reaction
  pills, notice banner.
- **Screens**: forum home (boards + sync-backed Recent), topics, thread
  (reactions + reply), composer (create/reply, pending notice). Routes
  `/forum/boards/:slug`, `/forum/topics/:id`, `/forum/compose` (first
  path-param routes — also the deep-link foundation for the FCM follow-up).
- Added dep `html: ^0.15.4` (pure Dart, no codegen) for safe paragraph HTML.
- 28 new forum tests; `flutter analyze` clean; full suite 213 passed.

- Picked up by automated workflow. Feature branch `todo-260-flutter-forum-client`.
- Mapping backend forum API contract, web client reference, and mobile
  infrastructure patterns in parallel before implementing.

### 2026-07-25 - Code review + repairs

Ran the bundled deep-correctness pass, `code-review-orchestrator`,
`flutter-dart-reviewer`, and `cross-cutting-reviewer`. All blocking findings
repaired and covered by new tests (full suite 220 passed, analyze clean):

- **HIGH** `TapGestureRecognizer` leak in `forum_html_text.dart` — recognizers
  accumulated across rebuilds → dispose+clear at the top of `build()`.
- **HIGH** `toggleReaction` unhandled async + stale-snapshot write — wrapped in
  try/catch, re-read state after the await, guarded the post lookup. Added
  happy-path + error-path provider tests.
- **HIGH** composer idempotency key wedged after an edit-then-retry (permanent
  422) — `ForumComposerController` now rotates the key when the composed
  content changes; retries of identical content still reuse it. Test added.
- **MEDIUM** `FileForumSyncStore` re-decoded the whole file 4×/sync — now caches
  the decoded map (one read per sync).
- **MEDIUM** reaction pill/add-reaction tap targets < 48×48 — wrapped to a
  48×48 minimum tap target.
- **MEDIUM** the 3 new forum routes weren't pinned in `app_router_test.dart` —
  added route→screen tests.
- **LOW** `loadMore` capture-before-await lost-update — re-read state after the
  await (both list providers). `state.extra` casts in two routes guarded.
- **LOW** renderer test now pumps a live `ForumImageBlock` (5th block type).

## Notes

p2 by grouping, but note the tension: mobile is the project's primary platform
and this is the largest single gap — promote when the p1 epics' backend
surfaces (notifications, solved marking) stabilize, so the client consumes
final contracts rather than chasing them.
