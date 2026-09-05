---
status: in_progress
priority: p3
issue_id: "341"
tags: [forum, flutter, parity, epic]
dependencies: []
---

# Flutter forum feature parity with the web frontend

## Problem

Flutter is the **primary platform** (repo CLAUDE.md), but the forum mobile
client trails the web on almost every feature shipped since the July 17
audit. The web/mobile asymmetry is backwards: members on the main platform
can't vote in polls, mark accepted answers, bookmark, report, or see
plant-ID cards.

## Findings

From the 2026-09-04 frontend catalog (read-only source inspection of
`plant_community_mobile/lib/features/forum/`):

| Feature | Web | Flutter |
|---|---|---|
| Reactions | mature | mature |
| Search + related topics | partial | mature |
| Notifications center | partial (popover) | mature |
| Profiles, trust badges | mature | mature |
| Poll display + voting | mature (`PollCard.tsx`) | **absent** |
| Topic bookmarks | partial (`ThreadDetailPage.tsx:489-517`) | **absent** |
| Accepted-answer marking | mature (`ThreadDetailPage.tsx:522`) | **absent** (API type present in `models/forum_search.dart:35`) |
| Plant-ID snapshot cards | mature (`IdentificationCard.tsx`) | **absent** |
| Block/report UI | mature (`PostCard.tsx:423-451`) | **absent** (`can_report` fields modeled, no UI) |
| Post edit history | mature (`EditHistoryDialog.tsx`) | **absent** (mobile shows static "edited" chip) |
| @mention autocomplete | mature | **absent** |
| Composer quote blocks / preview | implemented | read-only rendering, can't create |
| Badges/streaks UI | mature (`SeasonStatsGrid.tsx`) | **absent** |
| Online presence | implemented | **absent** |

All of the above already have backend APIs (see `apps/forum_host/api_urls.py:75-196`);
this is a pure client-parity gap.

## Recommended Action

Treat as an epic, execute in waves — each wave is a shippable PR:

1. **Wave 1 (safety):** report button on `post_card.dart`, block/unblock from
   `forum_user_profile_screen.dart`. Uses existing typed `can_report`/
   `can_edit` fields; verifies 403/429 envelopes.
2. **Wave 2 (thread experience):** accepted-answer mark/clear, bookmarks
   toggle + bookmarks list screen, edit-history dialog.
3. **Wave 3 (engagement):** poll display/vote, plant-ID snapshot card in
   `forum_thread_screen.dart`, quote-block creation in the mobile composer.
4. **Wave 4 (social):** @mention autocomplete, streak/badge UI, online dot.

DMs UI is **excluded** — tracked separately as todo 339 (web is missing too).

## Technical Details

- API contract: `wagtail_forum/api/pagination.py` cursor envelopes; the
  Flutter client already patterns cursor "Load more" in
  `forum_topics_screen.dart`.
- State: Riverpod 3.x per `plant_community_mobile/docs/patterns/riverpod.md`.
- Reference renderers to mirror: `PollCard.tsx`, `IdentificationCard.tsx`,
  `EditHistoryDialog.tsx` — keep mobile visually consistent with Material 3
  per `plant_community_mobile/docs/patterns/flutter-patterns.md`.

## Acceptance Criteria

- [ ] Wave 1: report + block/unblock usable from a thread and profile
- [ ] Wave 2: mark solution (as topic author), bookmark toggle + list,
      edit history view
- [ ] Wave 3: vote in a poll, see results, view an attached plant-ID card
- [ ] Wave 4: mention autocomplete in composer, streak/badge display
- [ ] Each wave: `flutter test` green + golden/widget tests for new widgets

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment, ranked gap #5:
  "Parity gaps on Flutter… the web/mobile asymmetry is backwards" for the
  primary platform.

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142)

- Picked up by automated workflow.

### 2026-09-05 - Waves 1 + 2 implemented (general-purpose agent against the backend contract; run 2026-09-05-1142)

Shipping as one PR for the two waves (safety + thread experience) — each
wave is independently usable, the review is per PR, and the stacked-branch
cost per PR is real; waves 3 + 4 follow as a second PR.

- **Wave 1:** shared `forum_report_sheet.dart` (extracted from the DM
  screen, which now reuses it) on `post_card.dart` when `can_report`;
  Block/Unblock in the profile app-bar menu (`can_block`, confirm dialog,
  blocked notice, Message hidden when blocked); blocked authors' posts
  collapse with a local "Show anyway" (`is_blocked` on `PostSerializer` —
  there is no `author_blocked`); a keepAlive `AuthorBlockChanges` notifier
  lets a mounted thread splice the flag after a block on the profile.
- **Wave 2:** `markSolution`/`clearSolution` (`topics/<id>/solution/`,
  non-optimistic — the server may refuse), "Accepted answer" chip derived
  from the topic's `solved_post_id` (no per-post flag exists), bounded
  "Jump to answer" (viewport steps + next-cursor pages); bookmark toggle
  (optimistic + revert) and `/forum/bookmarks` (protected route, load more,
  splice into the mounted feed); edit-history sheet on the "edited" chip
  (`posts/<id>/revisions/` + detail rendered by `ForumBodyRenderer`; 403 =
  moderator-only copy); `forumErrorMessage()` maps 429/403/400/409/422.
- Idempotency-Key only where the server consumes it (`reportPost`,
  `markSolution`; verified against the views) — block/bookmark/clear are
  naturally idempotent. Report route is `posts/<id>/reports/` (plural).

```text
$ dart run build_runner build --delete-conflicting-outputs → current (second run wrote 0 outputs)
$ flutter analyze → No issues found!
$ dart format --set-exit-if-changed … → 0 changed
$ flutter test → 00:25 +533 ~3: All tests passed!
mutation checks (cp backups, no git checkout; MUTANT residue 0): block confirm skipped → red; solution ignores server solved_post_id → red (provider + widget); bookmark splice no-op → red
```

### 2026-09-05 - Review round 1 (waves 1+2): flutter-dart reviewer — all repaired

- **[medium] no in-flight guard on the optimistic toggles** — a double-tap
  fired two opposite key-less writes whose last response won. Repaired:
  re-entrancy guards on `toggleBookmark`, `toggleBlock`, `markSolution`
  and `reportPost` (the second tap is dropped until the first settles);
  provider tests fire two calls and assert one API request.
- **[medium] a same-key twin (double-tap on Report / Mark as answer)
  surfaced the server's "Idempotency-Key is being processed" text** —
  repaired: 409 maps to "That's already in progress — give it a moment."
  and the guards above stop the twin in the first place.
- **[medium] 44 dp targets** (history chip, Jump to answer, revision tiles)
  → 48 dp per `flutter-patterns.md`; **[low]** the accepted-answer chip's
  `Semantics` now `excludeSemantics` (no double announce).

```text
dart run build_runner build --delete-conflicting-outputs → regenerated (guards changed the class hashes)
flutter analyze → No issues found!; dart format → 3 changed
flutter test (parity providers + thread parity + post card) → +44 all passed
```
