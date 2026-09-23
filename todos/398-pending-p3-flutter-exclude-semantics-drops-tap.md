---
status: pending
priority: p3
issue_id: "398"
tags: [flutter, accessibility, forum]
dependencies: []
---

# Flutter: `Semantics(excludeSemantics: true)` over a tappable child may drop its tap action

## Problem

`excludeSemantics: true` discards the child's semantics, and that includes the
tap action an `InkWell`/`GestureDetector` would contribute. If the wrapping
`Semantics` does not also pass `onTap`, a screen reader announces the element
(sometimes as a button) but double-tapping it does nothing.

This was **proven** in `forum_my_images_grid.dart` during todo 374's review.
The tile now passes `onTap`, and a test fires the tap through the semantics
owner. The same wrapper appears elsewhere. For those sites the defect is a
**hypothesis, not verified**; some of them may wrap nothing tappable.

## Findings

`grep -rn "excludeSemantics" plant_community_mobile/lib` (2026-09-23) lists
these sites to check:

- `features/forum/widgets/forum_experts_strip.dart:54`
- `features/forum/widgets/forum_body_renderer.dart:417`
- `features/forum/widgets/post_card.dart:336`
- `features/forum/widgets/poll_card.dart:226`
- `features/forum/widgets/forum_avatar_cluster.dart:47`
- `features/forum/widgets/forum_stats_grid.dart:120`, `:188`
- `shared/widgets/brand_mark.dart:37`

## Recommended Action

For each site, decide whether the excluded subtree is tappable. Where it is:

1. Add `onTap` to the `Semantics` node.
2. Add a test that runs `ensureSemantics()`, asserts
   `hasAction(SemanticsAction.tap)` and performs the action through
   `node.owner!.performAction`.

The test in `test/features/forum/widgets/forum_my_images_grid_test.dart`
("a screen reader can pick a tile") is the template.

## Acceptance Criteria

- [ ] Every listed site is classified as tappable or decorative, with a note in
      the Work Log.
- [ ] Every tappable site exposes a semantics tap action, pinned by a test.

## Work Log

### 2026-09-23 - Filed from todo 374's review

Raised by bundled `/code-review` as a side note on the photo-grid finding.
Filed here under the two-round review budget rather than widened into that PR.
