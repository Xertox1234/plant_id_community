---
status: completed
priority: p3
issue_id: "463"
tags: [mobile, flutter, forum, parity, dead-code]
dependencies: []
source_review: "todos/archive/403-completed-p3-flutter-decorative-semantics-sites-followup.md"
triage: ready
triaged: 2026-09-28
---

# Mobile group-DM avatar cluster shows the viewer; a no-op Padding in `_StatTile`

## Problem

Found during the todo 403 investigation. Neither item is a tap omission.

### 1. The avatar cluster includes the viewer and has no "+N" (parity)

The web's `ParticipantStack` (`web/src/pages/forum/MessagesPage.tsx`, about
49–75) leaves the viewer out and folds overflow into a "+N" tile. Mobile's
only caller (`forum_conversations_screen.dart`, about line 166) passes
`conversation.participants` as-is to `AuthorAvatarCluster`
(`forum_avatar_cluster.dart`), which labels it `${authors.length} members`.
The serializer returns every member, the viewer included
(`wagtail_forum` serializers, about 1376–1382).

So mobile most likely shows your own avatar in every group row, and never
shows "+N". This is traced from the code only, not checked on a device.

### 2. `Padding(padding: EdgeInsets.zero)` in `_StatTile`

`forum_stats_grid.dart` (about 121–122) wraps the tile's `CanopyCard` in a
zero `Padding`: leftover from the Canopy restyle (315f1b98), which turned
`Card(margin: EdgeInsets.zero, child: Padding(...))` inside out. It does
nothing. It was left alone in todo 403 because `_StatTile` is one of that
todo's audited semantics sites, and its AC requires a VoiceOver pass for any
changed site.

## Acceptance Criteria

- [x] The cluster leaves the viewer out and shows "+N" past the web's cap,
      matching `ParticipantStack`, and its semantics label counts the other
      members. A widget test covers both.
- [x] The zero `Padding` is removed, and the forum stats grid's semantics
      are unchanged (a VoiceOver check or a semantics-tree test).

## Work Log

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- `AuthorAvatarCluster` takes an optional `viewerUsername`: it leaves the viewer out, draws the first three others, folds the rest into a same-size "+N" disc, and its label counts the others ("4 other members"). With no viewer it shows everyone, like the web `ParticipantStack` does when `viewerUsername` is undefined.
- `ForumConversationsScreen` reads the account profile's username (`userProfileServiceProvider`, the same source the group thread uses) and passes it to each group row's cluster; a loading or failed profile passes null and never holds the list.
- `_StatTile` loses its zero `Padding`. A new semantics-tree test (one node per tile, full label, no child nodes, node rect equal to its card) passed before the removal and passes after it.
- Tests: three new cluster widget tests, one inbox screen test (fails with `['me', 'ada', 'bob']` when the viewer is not passed), one stats-grid semantics test. `flutter test test/features/forum` is 546 green; `flutter analyze` is clean.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-1/plant_community_mobile && flutter test test/features/forum/widgets/forum_avatar_cluster_test.dart test/features/forum/screens/forum_conversations_screen_test.dart test/features/forum/screens/forum_conversations_group_test.dart` — evidence `.sweep-evidence/g6/463-ac0.txt`, last lines:

  ```text
  Read more about status codes at https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
  In order to resolve this exception you typically have either to verify and fix your request code or you have to fix the server code.

  [USER_PROFILE ERROR] Failed to fetch profile:
  00:01 +15: All tests passed!
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-1/plant_community_mobile && echo "EdgeInsets.zero in forum_stats_grid.dart: $(grep -c EdgeInsets.zero lib/features/forum/widgets/forum_stats_grid.dart)" && flutter test test/features/forum/widgets/forum_stats_grid_test.dart` — evidence `.sweep-evidence/g6/463-ac1.txt`, last lines:

  ```text
  00:00 +2: ForumStatsGrid (todo 341 wave 4) each tile is ONE semantics node carrying the whole label, sized to its card (todo 463: the zero Padding came out and the tree must not change)
  00:00 +3: ForumStatsGrid (todo 341 wave 4) one-day streak and a host with no badge track
  00:00 +4: ForumBadgeChips one chip per badge with the description as tooltip
  00:00 +5: ForumBadgeChips renders nothing for no badges
  00:00 +6: All tests passed!
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
