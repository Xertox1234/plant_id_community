---
status: pending
priority: p2
issue_id: "291"
tags: [forum, flutter, mobile, bug]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile: a new reply is invisible after posting on a multi-page thread

## Problem

On a thread long enough to paginate, posting a reply lands it on the LAST
page, but the mobile client only refetches page 1 — so the user sees no trace
of the reply they just wrote. The write succeeded; the UI says nothing
happened, which reads as a failure and invites a duplicate post.

Promoted out of todo 279 (deferred scope from todo 260) as its own todo, at a
higher priority than its siblings: this is the only item in that list that is a
**defect** rather than absent functionality.

## Findings

- Deferred item 8 of todo 279, itself deferred from todo 260's Recommended
  Action to keep that epic's first PR reviewable.
- The web client already solved this: it has a `collectAllPosts` /
  deep-link-to-post path. Mirror that rather than inventing a mobile-only
  approach.
- Related, already fixed on web: the I1 "deep-link past page 1" chain
  documented in `docs/LEARNINGS.md` — read it before implementing, the
  page-bound edge cases are enumerated there.
- The `/forum/topics/{id}/posts/` endpoint is cursor-paginated
  (`PostCursorPagination`), so "jump to the last page" is not an offset — the
  web fix is the reference for how it is actually done.

## Recommended Action

1. Mirror the web client's post-collection behaviour: after a successful
   reply, land the user on the new post rather than refetching page 1.
2. Reuse the existing idempotency pattern on the write — do not add a second
   write path for this.
3. Cover the multi-page case specifically. A single-page thread passes either
   way, so a one-page test proves nothing.

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

- [ ] After posting a reply to a thread with more than one page of posts, the
      new reply is visible without a manual refresh — widget test on a
      multi-page fixture
- [ ] A single-page thread still behaves as before — test
- [ ] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

## Notes

p2, not p3 like its siblings: a user-visible defect on the primary platform's
write path, and the failure mode (invisible successful write) actively invites
duplicate posts. Promoted from todo 279 on 2026-07-31.
