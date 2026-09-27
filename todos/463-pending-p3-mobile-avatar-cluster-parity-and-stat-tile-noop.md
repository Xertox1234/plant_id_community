---
status: pending
priority: p3
issue_id: "463"
tags: [mobile, flutter, forum, parity, dead-code]
dependencies: []
source_review: "todos/archive/403-completed-p3-flutter-decorative-semantics-sites-followup.md"
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

- [ ] The cluster leaves the viewer out and shows "+N" past the web's cap,
      matching `ParticipantStack`, and its semantics label counts the other
      members. A widget test covers both.
- [ ] The zero `Padding` is removed, and the forum stats grid's semantics
      are unchanged (a VoiceOver check or a semantics-tree test).
