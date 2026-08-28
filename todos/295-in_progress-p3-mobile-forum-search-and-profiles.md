---
status: in_progress
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
2. ~~Make author names/avatars tappable through to a profile screen, EXCEPT
   the `[deleted]` sentinel.~~ Split to **todo 317** on 2026-08-28 — see
   Notes.
3. ~~Reuse the existing author widget so the identity shape stays
   single-sourced with the thread and topic lists.~~ This premise turned out
   to be **false** (no such widget exists today — see todo 317's Findings);
   folded into 317's corrected scope.

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

- [x] Search returns results and pages via `*_has_more` — test
- [x] With vector search disabled, `semantic_status: "unavailable"` renders as
      a state, not an error — test
- [ ] Tapping an author opens their profile; tapping a `[deleted]` author does
      nothing — test asserting both — split to **todo 317** on 2026-08-28
      (not done — see todo 317 for its own AC; the "reuse the existing
      author widget" premise this AC implied turned out to be false)
- [x] `flutter test` passes; `flutter analyze` clean

## Work Log

### 2026-07-31 - Promoted out of todo 279

- Todo 279 was a parking todo whose only AC was "prioritize the above into
  concrete slices". Per `CLAUDE.md` → Review Doc Tracking, promote-all is the
  only terminal state for a parking epic — re-deferring keeps it open forever.
  Its 9 deferred items were grouped into 5 todos by what ships together, not
  split 1:1.

### 2026-08-28 - Scoped to the search slice; profile split to todo 317

- Dispatched research before implementing (backend search/profile contracts,
  mobile `forum_api.dart` seam, and the "existing author widget" the
  Recommended Action referenced). The research disproved that premise: no
  shared author widget exists — `PostCard` and `TopicCard` each render
  author identity with their own independent inline code, one with an
  avatar, one without. Tap-to-profile is therefore a build-a-widget task,
  not a wire-up-an-onTap task — a materially different and larger scope
  than search. Split to todo 317 rather than bundled; this todo now covers
  only the search screen.
- Full research findings (backend response shapes, `semantic_status` state
  machine including the `premium_required` case which is MORE reachable
  than `unavailable` for a typical mobile user since the premium check
  runs before the feature-flag check, and the `ForumSyncPage` precedent to
  model the new search-page model on) are preserved in todo 317's Findings
  section and reused directly in this todo's own implementation below.

### 2026-08-28 - Search slice implemented

- **Model** (`models/forum_search.dart`): `ForumSearchTopicHit`,
  `ForumSearchPostHit`, `ForumSemanticStatus` enum
  (ok/premiumRequired/unavailable), `ForumSearchPage` — modeled on
  `ForumSyncPage`'s bespoke non-`results` envelope pattern per the research,
  not the cursor `CursorPage`/`PagedList` helpers every other list uses.
- **API** (`services/forum_api.dart`): `ForumApi.search({q, board, page,
  semantic})` + `HttpForumApi` impl (mirrors `sync()`'s conditional-query-
  param pattern) + `FakeForumApi` fixture (`searchResult`/`searchPages` for
  per-page fixtures, `searchCalls` log, `failSearchWith`).
- **Provider** (`providers/forum_providers.dart`): `ForumSearch` — a plain
  `Notifier<ForumSearchResult>` (NOT `AsyncValue`-wrapped) with its own
  idle/loading/loadingMore/data/error status enum, since search needs an
  idle "no query yet" state and a loadingMore that keeps existing results
  visible — neither maps cleanly onto `AsyncValue`'s own triad.
  `search()` resets to page 1 (empty/whitespace query resets to idle
  without calling the API); `loadMore()` fetches `page+1` and appends to
  BOTH topic and post lists, since the two `*_has_more` flags share one
  page cursor (confirmed via research — there's no way to advance one
  section independently).
- **Screen** (`screens/forum_search_screen.dart`): query field + optional
  board filter (`DropdownButtonFormField` fed by the existing
  `boardsProvider`), topics/posts sections, a `_SemanticSection` that
  renders `ok`/`premiumRequired`/`unavailable` as explicit states (not
  errors), load-more button. Wired a search icon into `forum_screen.dart`'s
  AppBar → new `/forum/search` route (`forumSearch`).
- **Caught during implementation**: the PostToolUse formatter silently
  stripped the new screen's import from `app_router.dart` on first add —
  the exact documented "import added before its first usage gets stripped"
  gotcha (`docs/LEARNINGS.md`) — because I added the import in one Edit and
  the `GoRoute` referencing it in a separate, later Edit. Caught by
  `flutter analyze` (`creation_with_non_type`), fixed by re-adding the
  import once the class was already in active use.
- **Mutation-tested** the "empty results still shows the semantic state,
  not a blanket 'No results.'" branch (todo 295's own AC2): reverted to the
  naive `topics.isEmpty && posts.isEmpty` check, confirmed the new
  "semantic_status unavailable renders as a state" widget test fails
  (0 widgets found instead of 1) with the state hidden behind "No
  results.", restored the fix, re-verified green.
- Verification:

  ```
  $ flutter analyze
  No issues found!

  $ flutter test
  00:07 +304 ~3: All tests passed!
  ```

  (290 → 304 mobile tests: +7 provider tests, +6 screen widget tests,
  +1 routing test for the new search entry point.)

### 2026-08-28 - Code review (flutter-dart-reviewer)

- **HIGH finding, fixed**: the "No results." empty-state gate required
  `semanticStatus == null`, but `search()` requests `semantic: true`
  unconditionally — so on every real response `semanticStatus` is non-null,
  making that branch dead code. A genuine zero-hit search with
  `semanticStatus: ok` and an empty `semantic` list fell through to the
  `ListView`, which rendered nothing at all (a blank screen) instead of any
  message. Fixed: the semantic section is now an always-checked sibling,
  and "No results." shows independently whenever topics/posts are both
  empty, regardless of semantic status. Added a regression test for the
  exact reported case (zero hits + `semanticStatus: ok`) and mutation-
  tested it (reverted to the old gate, confirmed the new test fails with
  0 widgets found instead of 1; restored, re-verified green).
- **MEDIUM finding, fixed**: no request-generation guard on
  `search()`/`loadMore()` — a double-tap Search (or a `loadMore()` racing a
  fresh `search()`) let whichever request resolved LAST win regardless of
  which was issued last, so a stale query's results could silently
  overwrite a newer query's state. Fixed with an incrementing `_generation`
  counter: each call captures its generation before awaiting and only
  commits if it's still current when the await resolves. Added a
  `Completer`-gated fake (`FakeForumApi.searchGates`, mirrors the existing
  `uploadImageGate` pattern from todo 294) to hold two overlapping searches
  in flight and resolve them out of order, proving the stale one is
  discarded. Mutation-tested (removed all 4 guard checks, confirmed the new
  test fails — `state.query` was `'first'` instead of `'second'`; restored,
  re-verified green).
- **LOW finding, accepted — not fixed**: the "Load more" button's
  `onPressed` doesn't await/catch `loadMore()`, so a failure becomes an
  unhandled Future error with no visible feedback beyond the button
  reappearing. The reviewer confirmed this mirrors the pre-existing
  `TopicPosts.loadMore()` call site in `forum_thread_screen.dart` — not a
  new anti-pattern this diff introduced, so left as-is for consistency
  rather than fixing one call site and not its sibling.
- **Self-caught gap while re-verifying**: none of the tests exercised
  `ForumSearchPage.fromJson` directly against wire-shaped JSON — the
  provider/screen tests all construct `ForumSearchPage` objects by hand.
  Added `test/features/forum/models/forum_search_test.dart` (4 cases)
  covering the real API shape, a missing `semantic` key (confirms the
  null-aware chain `semanticJson?.whereType(...)...` short-circuits to
  `null` rather than throwing — verified empirically with a standalone
  `dart run` snippet before trusting it), each `semantic_status` wire
  value, and an unrecognized status value degrading to `null` rather than
  crashing.
- Final re-verification:

  ```
  $ flutter analyze
  No issues found!

  $ flutter test
  00:08 +310 ~3: All tests passed!
  ```

## Notes

p3. Promoted from todo 279 on 2026-07-31. Profile/tap-to-author split to
todo 317 on 2026-08-28 — see Work Log.
