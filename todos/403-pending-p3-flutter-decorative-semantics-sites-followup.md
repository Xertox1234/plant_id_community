---
status: pending
priority: p3
issue_id: "403"
tags: [flutter, accessibility, forum, dead-code, parity]
dependencies: []
---

# Flutter: find out WHY the 6 "decorative" excludeSemantics sites are decorative, and whether they should be

## Problem

Todo 398 classified 6 `Semantics(excludeSemantics: true)` sites as decorative.
The test was only "nothing inside the excluded subtree handles a tap". That
says what the code **does**. It does not say what the code was **meant** to do.

This codebase has a known pattern of half-finished wiring:

- unused variables and parameters;
- callbacks declared but never passed;
- routes and screens built but never linked;
- features that work on the web but were never connected on mobile.

A site can be "decorative" only because its tap was never hooked up. The goal
here is to find out, for each site, whether that is by design or by omission,
and to fix any omission.

## Findings

The 6 sites, from todo 398's classification (see
`todos/archive/398-completed-p3-flutter-exclude-semantics-drops-tap.md`). Paths
are under `plant_community_mobile/lib/`:

- `features/forum/widgets/post_card.dart`: `_SolutionChip` ("Accepted answer")
- `features/forum/widgets/forum_stats_grid.dart`: `_StatTile`. Note that
  `CanopyCard` accepts an `onTap`, but `_StatTile` never passes one.
- `features/forum/widgets/forum_stats_grid.dart`: `ForumBadgeChips` (a `Chip`
  with no `onPressed`, plus a long-press `Tooltip`)
- `features/forum/widgets/forum_avatar_cluster.dart`: the stacked
  `AuthorAvatar`s
- `features/forum/widgets/poll_card.dart`: `_ResultRow`
- `shared/widgets/brand_mark.dart`: `BrandMark`

**Nothing below has been investigated yet.** Every "maybe it should be
tappable" is a hypothesis, not verified.

## Recommended Action

Investigate each of the 6 sites through the same checklist, and write the
answers in the Work Log:

1. **History.** Was it ever tappable?
   - Run `git log -L` or `git log -S "onTap"` on the widget, and read the
     commit or PR that introduced it and the todo it names.
   - If a tap was removed, find out why.
2. **Dead wiring in the widget.** Look for things declared but never used:
   - `onTap`/`onPressed` parameters or fields;
   - a `VoidCallback` nobody reads;
   - a `button:` flag;
   - a `Key` meant for a tap test;
   - an unused import of a router or screen.
3. **Dead wiring at the callers.** Use `grep` for every construction site.
   - Does any caller have a handler it could pass but doesn't?
   - Is the widget placed inside an `InkWell` or `GestureDetector` that
     already makes it tappable from outside? That is a legitimate reason to
     be decorative. Record it.
4. **Destination exists?** Is there a route, screen or API that the tap would
   obviously open? Candidates:
   - a badge detail;
   - a participant or member list;
   - the accepted answer inside the topic;
   - stats or activity;
   - home, for the brand mark.

   Check `go_router` routes and `features/forum/screens/`. A destination that
   is built but unreachable is the strongest sign of an omission.
5. **Web parity.** Find the web counterpart under `web/src/`: the badge chips,
   stats grid, solution chip, avatar cluster, poll results and `BrandMark.tsx`.
   If the web version is a link or button and the mobile one is not, that is a
   parity gap. Either wire it or record why mobile differs.
6. **Design intent.** Check the design docs and specs (Canopy / Green Thumb /
   todo 341 parity) for whether the element is specified as interactive.
7. **Verdict:**
   - **Decorative by design:** record the evidence.
   - **Omission:** wire the tap. Pass the same callback to the widget and to
     the `Semantics` `onTap`, set `button:` only when the callback is
     non-null, and add a todo 398-style semantics test, mutation-checked.
   - **Bigger than a wire-up:** if the destination doesn't exist yet, file a
     separate todo rather than building it here.
8. While in these files, report any other unused variables or dead code
   found, with a count of found vs. fixed. Fix the trivial ones in the same
   PR; file the rest.
9. Finish with a real VoiceOver pass in the iOS simulator over every changed
   site, with the date and what was announced quoted in the Work Log.

## Technical Details

- The tap pattern to copy: todo 398's fixes in `forum_experts_strip.dart`
  (`_ExpertTile`) and `forum_body_renderer.dart` (`_EmbedCard`), and
  `forum_my_images_grid.dart`. The test template is "a screen reader can pick a
  tile" in `test/features/forum/widgets/forum_my_images_grid_test.dart`.
- `SemanticsData.hasFlag` is deprecated; use `flagsCollection.isButton`.
  `SemanticsAction` needs `import 'package:flutter/semantics.dart'`.
- `dart analyze` does not flag an unused **public** parameter or field, so
  step 2 needs a manual read and a `grep`, not just the analyzer.
- Pattern doc: `plant_community_mobile/docs/patterns/flutter-patterns.md`.

## Acceptance Criteria

- [ ] Each of the 6 sites has a Work Log verdict, **decorative by design** or
      **omission**, backed by evidence from steps 1–6: a commit, a caller
      grep, a route listing, the web counterpart, or a spec reference.
- [ ] Every omission is either wired, with a mutation-checked semantics tap
      test, or re-pointed to a new todo when the destination doesn't exist.
- [ ] Other dead code found in these files is reported as a count of found
      vs. fixed, with anything not fixed filed as a todo.
- [ ] Every changed site has had a VoiceOver check in the iOS simulator, with
      the date and what was announced quoted in the Work Log.

## Work Log

### 2026-09-23 - Filed from todo 398

Todo 398 (PR #796) classified these 6 sites as decorative from what the code
does today. The user asked for a deeper look: why is each one decorative, and
is it meant to be, or is it a tap that was never wired up?
