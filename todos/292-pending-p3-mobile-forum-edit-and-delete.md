---
status: pending
priority: p3
issue_id: "292"
tags: [forum, flutter, mobile]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile forum: post edit and delete

## Problem

The Flutter forum client can create topics and replies but cannot edit or
delete them — the backend endpoints and the per-post capability flags both
exist and are simply unused by the mobile client. A user who typos a reply on
mobile has to open the web app to fix it.

## Findings

- Deferred item 2 of todo 279 (from todo 260's Recommended Action).
- Backend is ready: `PATCH /forum/posts/{id}/` returns `moderation_status`, and
  `DELETE /forum/posts/{id}/` returns 204. Opening posts cannot be deleted.
- The serializer already ships `can_edit` / `can_delete` per post — the client
  has the gating data and ignores it.
- The frozen-topic guard is deliberately symmetric: PATCH and DELETE are both
  409 on a closed/locked topic **including for moderators** (a product
  decision, see `docs/rules/forum.md`). The mobile UI must surface that 409,
  not treat it as an error to retry.

## Recommended Action

1. Add `editPost` / `deletePost` to `ForumApi` plus their fakes.
2. Gate the affordances on `post.canEdit` / `post.canDelete` — do not
   re-derive ownership client-side.
3. Edit reuses the idempotency pattern already used by create. Per
   `docs/rules/flutter.md`: one `Idempotency-Key` per action, **rotated when
   the composed content changes** — an edit-then-retry with a stale key wedges
   a permanent 422.
4. Surface `moderation_status` on the edit response the way the create path
   already surfaces pending moderation; an edit can send a post back to the
   queue.

## Technical Details

- Client lives in `plant_community_mobile/lib/features/forum/` — `models/`,
  `providers/`, `screens/` (`forum_topics_screen.dart`,
  `forum_thread_screen.dart`, `forum_composer_screen.dart`), `services/`
  (`forum_api.dart`, `forum_composer_controller.dart`, `forum_sync_service.dart`,
  `forum_sync_store.dart`), `widgets/`.
- `ForumApi` (`services/forum_api.dart`) is the seam to extend: add the method
  plus its fake, mirroring the existing endpoints.
- Codegen gate: editing a `@riverpod` source needs
  `flutter pub run build_runner build --delete-conflicting-outputs` and a
  committed `.g.dart`. CI blocks on this; local `flutter analyze` does NOT
  catch it. A clean rebuild is required — incremental can miss the hash.
- Read `plant_community_mobile/docs/patterns/riverpod.md` and
  `.../flutter-patterns.md` before writing.

## Acceptance Criteria

- [ ] Edit and delete are reachable from a post the user owns, and absent on
      one they do not — widget test asserting both
- [ ] An edit that returns `moderation_status: pending` surfaces that state
      rather than silently showing the old body — test
- [ ] A 409 on a frozen topic surfaces as a clear message, not a retry — test
- [ ] Editing then retrying with changed content does not 422 (key rotation) —
      test
- [ ] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

## Notes

p3. Promoted from todo 279 on 2026-07-31. Related: todo 291 (the same write
path's visibility defect).
