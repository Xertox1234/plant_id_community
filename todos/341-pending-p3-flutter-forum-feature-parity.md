---
status: pending
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
