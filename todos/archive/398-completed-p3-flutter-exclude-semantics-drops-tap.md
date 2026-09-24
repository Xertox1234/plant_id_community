---
status: completed
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

- [x] Every listed site is classified as tappable or decorative, with a note in
      the Work Log. All 8 are in the 2026-09-23 table: 2 tappable, 6 decorative.
- [x] Every tappable site exposes a semantics tap action, pinned by a test.
      `_ExpertTile` and `_EmbedCard`: each new test failed first (`Actual:
      <false>`), passes with the fix, and fails again when the `onTap` is
      mutated out.

## Work Log

### 2026-09-23 - Filed from todo 374's review

Raised by bundled `/code-review` as a side note on the photo-grid finding.
Filed here under the two-round review budget rather than widened into that PR.

### 2026-09-23 - Classified all sites; fixed the 2 tappable ones

`grep -rn "excludeSemantics" plant_community_mobile/lib` on origin/main
`aff97ed1` finds the 8 listed sites plus the photo grid (already fixed in
todo 374). There are no new sites. **Found 8, tappable 2, fixed 2.**

Each site was classified from its widget tree: does the excluded subtree
contain an `InkWell`, `GestureDetector`, button or `onTap`?

| Site | Class | Why |
|------|-------|-----|
| `forum_experts_strip.dart:54` (`_ExpertTile`) | **tappable, fixed** | Wraps an `InkWell(onTap:)`. `button:` was set but there was no tap action. |
| `forum_body_renderer.dart:417` (`_EmbedCard`) | **tappable, fixed** | Wraps `Material > InkWell(onTap:)`. |
| `post_card.dart:336` (`_SolutionChip`) | decorative | A `Container`, `Row`, `Icon` and `Text` only. |
| `poll_card.dart:226` (`_ResultRow`) | decorative | Text and a `LinearProgressIndicator`. Voting uses the option list tiles built in `_PollCardState`, which do not exclude semantics. |
| `forum_avatar_cluster.dart:47` | decorative | A `Stack` of `AuthorAvatar`s, and `AuthorAvatar` has no tap handler. Any tap target sits outside the cluster. |
| `forum_stats_grid.dart:120` (`_StatTile`) | decorative | `CanopyCard` gets no `onTap`; its `InkWell` exists only when one is passed. |
| `forum_stats_grid.dart:188` (`ForumBadgeChips`) | decorative | A `Chip` with no `onPressed`. The `Tooltip`'s description is already in the node's label. |
| `shared/widgets/brand_mark.dart:37` | decorative | Gradient tile, icons and a badge (`image: true`). |

**The bug was proven before the fix.** At both tappable sites, the new test
failed with `hasAction(SemanticsAction.tap)` giving `Expected: true, Actual:
<false>`. The fix passes the same callback to the `Semantics` node as to the
`InkWell`.

**Same-defect edge, also fixed.** An embed with a title but an empty URL was
flagged `button: onOpenLink != null` while its tap was null, so it was announced
as a button that does nothing. `button` now follows the tap. A test pins it.

**Tests:**

- `forum_experts_strip_test.dart`: "a screen reader can open a member: it
  carries a tap action".
- `forum_body_renderer_test.dart`:
  - "a screen reader can open an embed card: it carries a tap action";
  - "an embed card with no URL is not announced as a button".

The first two follow the template: `ensureSemantics()`, then `hasAction(tap)`,
then `node.owner!.performAction(node.id, SemanticsAction.tap)`, then assert the
callback fired.

**Mutation checks.** Each file was copied aside, mutated, then restored from the
copy.

- Removing the `Semantics` `onTap` fails both screen-reader tests (`[E]`, `-2`).
- Reverting `button:` to `onOpenLink != null` fails the no-URL test.

**Verification:**

- `flutter analyze`: "No issues found!"
- `dart format`: 0 changed.
- Full `flutter test`: `+763 ~9: All tests passed!`
- No `@riverpod` or freezed files were touched, so codegen did not need to run.
- No real VoiceOver check in the iOS simulator was done. The semantics tree is
  asserted in widget tests only.

### 2026-09-23 - Completed

- Verification: both acceptance criteria are met (evidence above). Full
  `flutter test` reports `+763 ~9: All tests passed!`; `flutter analyze` is
  clean.
- Review: bundled `/code-review` round 1 found 0 blocking and 0 non-blocking.
  No round 2 was needed.

### 2026-09-24 - Verified on a device (TestFlight build 13)

The owner tested both fixed sites with VoiceOver on an iPhone, on build 13.
That build was made from `main` `277a1d6d` and was VALID in App Store Connect
at 07:47 PT; its delivery id is `48accf3f-c1f1-4037-978e-1c901559b72e`. This
closes the gap noted above ("no real VoiceOver check").

- **Experts strip (`_ExpertTile`): passes.** On the forum home, a single tap
  selects an expert and a double-tap opens their profile.
- **Embed card (`_EmbedCard`): passes.** A single tap reads the video title
  once, not twice. A double-tap now runs the card's tap action. Before the
  fix, VoiceOver's double-tap did nothing.
- **Separate from this todo, found while testing:** the tap action goes to
  `_showLink` (`forum_thread_screen.dart`), which only shows the raw URL in a
  SnackBar, and VoiceOver then spells the URL out. That is how the app handles
  every forum link: it has no `url_launcher`, so links in posts never open for
  anyone. Tracked as todo 424.
- Also found getting a video post to test with: todo 421 (video links posted
  from the mobile app never become embeds), 422 (approving a topic leaves its
  opening post pending) and 423 (streamline moderation).
