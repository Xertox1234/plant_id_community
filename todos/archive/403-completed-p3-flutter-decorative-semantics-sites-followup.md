---
status: completed
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

- [x] Each of the 6 sites has a Work Log verdict, **decorative by design** or
      **omission**, backed by evidence from steps 1–6: a commit, a caller
      grep, a route listing, the web counterpart, or a spec reference.
      (completed 2026-09-27: all 6 decorative by design, see the Work Log)
- [x] Every omission is either wired, with a mutation-checked semantics tap
      test, or re-pointed to a new todo when the destination doesn't exist.
      (completed 2026-09-27: no omissions; the two possible taps were declined
      by the owner)
- [x] Other dead code found in these files is reported as a count of found
      vs. fixed, with anything not fixed filed as a todo. (completed
      2026-09-27: 4 found, 2 fixed, 1 filed as todo 463, 1 not dead code)
- [x] Every changed site has had a VoiceOver check in the iOS simulator, with
      the date and what was announced quoted in the Work Log. (completed
      2026-09-27: vacuous. None of the 6 sites changed; the one fix inside a
      site was deferred to todo 463 so that it gets its own check)

## Work Log

### 2026-09-23 - Filed from todo 398

Todo 398 (PR #796) classified these 6 sites as decorative from what the code
does today. The user asked for a deeper look: why is each one decorative, and
is it meant to be, or is it a tap that was never wired up?

### 2026-09-24 - Owner: cleared for a sweep

Not blocked — investigation work. The owner cleared it for the next sweep.
Where a site's intent is genuinely unclear after the checklist, record the
question in this Work Log for the owner instead of guessing.

### 2026-09-27 - Verdicts: all 6 decorative by design

Method:

- History: `git log -p --follow` over the five files, grepping removed
  `onTap`, `onPressed`, `InkWell` and `GestureDetector` lines. Every hit
  belonged to other widgets. None of the six ever had a tap.
- Dead wiring inside each widget: none. No unused callback, `button:` flag,
  key or router import.

| Site | Introduced | Verdict and evidence |
|------|------------|----------------------|
| `_SolutionChip` (`post_card.dart`) | 529d949f (#643, todo 341) | Rendered on the accepted post itself, so a tap would point where you already are. "Jump to answer" is a separate banner in `forum_thread_screen.dart`. The web shows the same label as a plain `<p>` (`PostCard.tsx`, "Accepted-answer banner (audit H6)"). Todo 341 excluded its semantics deliberately ("no double announce"). |
| `_StatTile` (`forum_stats_grid.dart`) | 549d0a3c (#644, todo 341) | `CanopyCard` accepts `onTap`, but the one caller (`_YourSeasonSection`) has no destination to pass. The web's `StatCard.tsx` is a bare card. The Canopy forum spec specifies "four `StatCard`s" with values and no action (`docs/superpowers/specs/2026-08-15-canopy-forum-content-design.md:235`). **Owner (2026-09-27): leave as readouts.** |
| `ForumBadgeChips` (`forum_stats_grid.dart`) | 549d0a3c | Neither caller has a handler. The web shows a `title` tooltip on an `<li>` (`UserProfilePage.tsx`). The long-press tooltip is the only gesture, and the Semantics label already carries the description. No badge-detail API exists (badges are an admin snippet). **Owner (2026-09-27): keep the tooltips; file nothing.** |
| `AuthorAvatarCluster` (`forum_avatar_cluster.dart`) | 622b58f6 (#649, todo 350) | Its only caller puts it in `ListTile(onTap:)`'s `leading:` slot, so the whole row is the tap target. The web's `ParticipantStack` is `aria-hidden` and documented "Decorative". Its non-tap parity gap is filed as todo 463. |
| `_ResultRow` (`poll_card.dart`) | 549d0a3c | Shown only after you vote or the poll closes. Voting is the separate ballot branch. The web's result rows have no handler (`PollCard.tsx`). A voters list would need an API that does not exist (`polls.py` only aggregates). |
| `BrandMark` (`brand_mark.dart`) | 315f1b98 (#764) | On the web it is a home link in the sidebar on every page (`AppShell.tsx`). On mobile it renders only on the splash screen and inside the home hero (already `/home`), and navigation is the tab bar. A home tap would do nothing wherever it appears. This becomes an omission if the mark ever moves into a shared app bar. |

**Other dead code in these files: 4 found, 2 fixed.**

1. Fixed: `BrandLockup`'s `Axis.vertical` branch and `axis` parameter had
   no caller; they were removed. Its doc comment claimed it was used on
   splash and auth, which was wrong; corrected.
2. Fixed: `_PendingChip` had no const constructor, so its call site
   could not be const; both are const now.
3. Filed as todo 463: a zero `Padding` inside `_StatTile`. Deferred so
   that none of the six audited sites changes here.
4. Not dead: `progressLabel` in `forum_stats_grid.dart` is passed when
   `progress` is null. It is only read under `if (progress != null)`, so
   it is harmless.

Also filed in todo 463: the avatar cluster includes the viewer and has no
"+N", unlike the web (a parity gap, not a tap).

**VoiceOver (AC 4):** no site's semantics or wiring changed, so there is
nothing to announce differently. `canopy_visual_golden_test.dart` and the
forum widget tests pass unchanged after the two fixes.

### 2026-09-27 - PR #858 reviewed; archived

The flutter-dart-reviewer found nothing blocking. It confirmed that no
caller uses the removed vertical variant, that `excludeSemantics` is
unchanged at all six sites, and it verified six of the verdict claims
independently (commits, `CanopyCard.onTap`, the `ListTile.leading`
placement, the zero `Padding`, the web's `aria-hidden` `ParticipantStack`,
and the `AppShell` home link). The one wrong path it found, in todo 463,
is fixed.
