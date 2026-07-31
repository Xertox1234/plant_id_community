---
status: pending
priority: p3
issue_id: "295"
tags: [forum, flutter, mobile]
dependencies: ["260"]
source_review: "todo 279 (promoted 2026-07-31)"
---

# Mobile forum: search and public profiles

## Problem

Two read-path gaps in the mobile client: there is no search, and author names
and avatars render inert — tapping one does nothing, even though a public
profile endpoint exists. Both are discovery features, both are read-only, and
both are backed by endpoints that already ship.

## Findings

- Deferred items 6 and 7 of todo 279 (from todo 260's Recommended Action),
  grouped: both are read-only discovery over existing endpoints.
- `GET /forum/search/?q=&board=` is offset-paged and returns `*_has_more`
  flags — a different pagination shape from the cursor-paged topic/post lists,
  so it needs its own paging code, not the existing helper.
- Search has a documented honesty contract from Wave 1 (PR #473): the response
  reports what was actually searched. Surface that rather than implying
  full-corpus coverage.
- The premium semantic section (`?semantic=1`) is gated by
  `FORUM_VECTOR_SEARCH_ENABLED` and reports `semantic_status: "unavailable"`
  when off — the client must handle that state, not treat it as an error.
- `GET /forum/users/{username}/` backs the profile screen. Author identity is
  serialized through one shared shape with a `[deleted]` sentinel OBJECT —
  a deleted author is not a null, and tapping one must not navigate.

## Recommended Action

1. Search screen: query + optional board filter, offset paging off
   `*_has_more`. Render the honesty/`semantic_status` state rather than
   hiding it.
2. Make author names/avatars tappable through to a profile screen, EXCEPT the
   `[deleted]` sentinel.
3. Reuse the existing author widget so the identity shape stays single-sourced
   with the thread and topic lists.

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

- [ ] Search returns results and pages via `*_has_more` — test
- [ ] With vector search disabled, `semantic_status: "unavailable"` renders as
      a state, not an error — test
- [ ] Tapping an author opens their profile; tapping a `[deleted]` author does
      nothing — test asserting both
- [ ] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

## Notes

p3. Promoted from todo 279 on 2026-07-31.
