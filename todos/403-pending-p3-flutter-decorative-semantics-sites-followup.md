---
status: pending
priority: p3
issue_id: "403"
tags: [flutter, accessibility, forum, ux]
dependencies: []
---

# Flutter: decide whether the 6 "decorative" excludeSemantics sites should be interactive

## Problem

Todo 398 checked every Flutter `Semantics(excludeSemantics: true)` site. Six
have nothing tappable in the part the screen reader skips, so they got no fix.
Several of them still **look** like buttons:

- chips (badge chips, the accepted-answer chip);
- cards (stat tiles);
- an avatar stack that sits beside tappable content.

This todo covers two decisions for each site:

1. Should it be interactive? If it should, it needs a real tap target and a
   semantics tap action. If it stays static, confirm that nothing about it
   invites a tap.
2. Is what a screen reader announces for it correct?

## Findings

From todo 398's classification (see
`todos/archive/398-completed-p3-flutter-exclude-semantics-drops-tap.md`), under
`plant_community_mobile/lib/`:

| Site | Looks like | Candidate action (unverified) |
|------|-----------|-------------------------------|
| `features/forum/widgets/post_card.dart` `_SolutionChip` | chip | jump to the accepted answer? |
| `features/forum/widgets/forum_stats_grid.dart` `_StatTile` | card | open the matching activity or badge progress? |
| `features/forum/widgets/forum_stats_grid.dart` `ForumBadgeChips` | chip plus `Tooltip` | open the badge's details? |
| `features/forum/widgets/forum_avatar_cluster.dart` | avatar stack | open the participant list? |
| `features/forum/widgets/poll_card.dart` `_ResultRow` | results bar | none. It is a result; voting is the list tiles |
| `shared/widgets/brand_mark.dart` | logo | none, unless a caller links it home |

Two gaps, both **hypotheses, not verified**:

- **`ForumBadgeChips` wraps a `Tooltip`.** On touch devices, a `Tooltip` opens
  on long-press. With `excludeSemantics: true` a screen-reader user may not be
  able to open it. The node's label already carries the description, so this
  may not matter.
- **No real VoiceOver or TalkBack pass has been done** on any of these sites.
  Todo 398 asserted the semantics tree in widget tests only.

## Recommended Action

1. For each site, decide *static* or *interactive*. This is a product and UX
   call. Record the decision and the reason in the Work Log.
2. For a site that becomes interactive:
   - add the tap target;
   - pass the same callback to the `Semantics` node's `onTap`, and set
     `button: true` only when that callback is non-null;
   - add a test in the todo 398 shape: `ensureSemantics()`, then
     `hasAction(SemanticsAction.tap)`, then `node.owner!.performAction`, then
     assert the callback fired;
   - mutation-check it.
3. For a site that stays static, make sure it is not announced as a button and
   has no tap-like affordance, such as an ink ripple or a pointer cursor.
4. Run VoiceOver in the iOS simulator over the forum home (stats and badges),
   a topic with an accepted answer and a poll, and the experts strip. Record
   what is announced, and whether double-tap works where it should.

## Technical Details

- The tap pattern to copy: `forum_my_images_grid.dart`, and the todo 398
  fixes in `forum_experts_strip.dart` (`_ExpertTile`) and
  `forum_body_renderer.dart` (`_EmbedCard`).
- `SemanticsData.hasFlag` is deprecated; use `flagsCollection.isButton`.
  `SemanticsAction` needs `import 'package:flutter/semantics.dart'`.
- Pattern doc: `plant_community_mobile/docs/patterns/flutter-patterns.md`.

## Acceptance Criteria

- [ ] Each of the 6 sites has a recorded decision (static or interactive) with
      a reason in the Work Log.
- [ ] Every site made interactive exposes a semantics tap action, pinned by a
      mutation-checked test.
- [ ] No static site is announced as a button.
- [ ] VoiceOver has been run in the iOS simulator over the sites above, with
      the date and what was announced quoted in the Work Log.

## Work Log

### 2026-09-23 - Filed from todo 398

Todo 398 (PR #796) classified these 6 sites as decorative and left them
unchanged. The user asked for a follow-up to address them.
