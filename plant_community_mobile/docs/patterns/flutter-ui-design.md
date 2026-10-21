# Flutter UI/UX Design Reference (Canopy on mobile)

Reference for the `flutter-ui-designer` agent and anyone doing UI work in
`plant_community_mobile/`. Written 2026-10-18. Part 1 is how THIS project is set up
(verified against the code). Part 2 is current Flutter practice. Part 3 is a catalog
of patterns that fit Canopy. Verify any API in Part 2/3 against current docs before
relying on it (Context7 library `/flutter/website`, or flutter.dev) — Flutter moves.

## Part 1 — Where the project stands

**Design language: Canopy** (spec: `docs/superpowers/specs/2026-08-13-canopy-design.md`).
Thesis: *liveliness comes from light, not noise* — one green world, raised surfaces are
gradients (never flat fills), three warm accents (pollen/bloom/orchid) confined to small
elements, dark mode is the identity, light mode is derived. Type: Bricolage Grotesque 600
(display), Geist 400-600 (body/UI), Geist Mono (data, eyebrows, tabular numbers).

**Already done in Flutter** (do not redo, do not hand-edit):

- Token contract `design/canopy-tokens.json` is GENERATED from `web/src/index.css`
  (`scripts/design/extract_canopy_tokens.mjs`). Colours, type scale and spacing in
  `lib/core/theme/` are pinned to it by `test/core/theme/canopy_parity_test.dart`.
- `AppTheme.build()` themes every Material control (buttons, inputs, nav bar, tabs...).
- `GreenThumbExtension` (legacy name, Canopy values) holds what ColorScheme cannot:
  ink2/ink3, line/line2, accents, gradients, 3 shadow levels, density spacing.
  Read it via `context.canopy`.
- Shared widgets: `ClayButton` (gradient CTA + secondary/outline/ghost), `CanopyCard` and
  `CanopyGround` (`canopy_surfaces.dart`), `CanopyLabel`, `CanopyNotice`, `FeatureCard`,
  `BrandMark`, `LoadingIndicator`.

**What is NOT done**: the web Canopy spec listed Flutter as out of scope, so the Flutter
*screens* never had a Canopy redesign pass. The foundation is sound; screens and
interaction design are where the gap is.

**Audit baseline (rough greps, 2026-10-18 — re-measure, don't trust blindly):**

| Signal | Count | Reading |
|---|---|---|
| Raw `Elevated/Filled/Outlined/TextButton` outside theme | ~111 uses | Most screens bypass `ClayButton`; they get flat primary, not the gradient CTA |
| `ClayButton(` call sites outside its file | 9 | Under-adopted |
| `CanopyCard(` call sites | 26 | Better, but 6 raw `Card(` and ~108 `Container(color:`/`color: cs.*` hits remain |
| Files using any animation API (AnimatedSwitcher, Hero, AnimatedContainer, TweenAnimationBuilder, PageTransitionsTheme...) | 0 | App is static: no transitions, no state animation |
| Files using `HapticFeedback` | 0 | No tactile feedback |
| `textScaler` / clamped text scaling | 0 | Nothing handles large system fonts deliberately |
| Files using `Semantics` | 23 | Partial |
| Hardcoded `Color(0x` / `Colors.*` outside theme | 2 | Colour discipline is already good |

The user-reported symptoms (button text not fitting, poor text colours, looks only
vaguely like web) are consistent with: raw Material buttons + fixed type sizes + no
text-scale handling + screens built from flat containers instead of Canopy materials.
Reproduce visually before assuming — this audit was code-only.

**Tension to manage:** the user wants the app "more interesting and engaging"; Canopy's
motion rule is restraint ("one orchestrated moment, nothing scattered", micro
interactions <=200ms, everything gated by reduced-motion). Mobile can carry more motion
than web because touch needs feedback — but get engagement from *light, depth,
transitions and tactile feedback*, not from decoration. Keep the ambient background static
(already a deliberate battery decision in `CanopyGround`).

## Part 1b — Observed on a real device (6 screenshots, 2026-10-18, dark mode)

Screens seen: Profile, Community (boards), board topic list, thread detail, My Collection (empty).
Cause analysis below is from the code (`lib/core/routing/main_shell.dart` etc.), not guesswork.

1. **The Identify camera FAB covers content on every screen.** `MainShell` puts a
   `FloatingActionButton` at `centerFloat` over a `StatefulShellRoute` body, and the
   screens inside are *nested Scaffolds* that each add their own FAB (`New topic`, `Reply`,
   garden). Result: the shell FAB hides the last row of every scrollable (Profile's email
   notification text, Forum "Recent activity", the link card in a thread) and **collides
   with the screen FABs** — the "New topic" extended FAB is crushed/clipped to "New to",
   and "Reply" is half-hidden. Scrollables also reserve no bottom padding for it.
   Fix direction: remove the floating camera button; make Identify a prominent centre
   destination in the bottom bar (camera is the product's core action) or an in-flow
   action; screen-level primary actions become inline/sticky bottom bars, never competing
   FABs. Every scrollable gets bottom inset = nav height + safe area.
   **DECISION (user, 2026-10-18): option 2.** The Identify camera FAB moves to the
   bottom-right (`endFloat`, like the user's OCRecipes app) and is shown ONLY on screens
   with no primary action of their own. Screens that own a primary action (forum topics ->
   "New topic", thread -> "Reply", and any other screen with its own FAB) show that action
   in the corner instead; the camera is simply absent there and reachable from the other
   tabs. One floating button per screen, never two. Implementation notes: drive visibility
   from one place (the shell, by route/branch, or a single FAB slot screens fill) rather
   than nested Scaffolds each declaring one — this also removes the `heroTag` workaround.
   Every scrollable reserves bottom padding for the FAB (56 + 16 + safe area). Update
   `test/routing/app_router_test.dart` ('the Identify FAB never covers a tab selection
   indicator') to assert: shell FAB at end, hidden on own-FAB screens, no two FABs
   overlap, last list item scrolls clear of the FAB, at 320pt and 375pt.
   **IMPLEMENTED (#1174, 2026-10-21).** The shell hides its FAB by route
   (`MainShell.ownsPrimaryAction`); screens keep their own FABs. The hide list also
   covers the composers (compose, new group, DM and group conversations; owner call
   2026-10-21). Two corrections to the notes above: `heroTag` is KEPT (indexedStack
   still keeps a garden or forum FAB alive in a branch you've left), and the tests live
   in `test/routing/navigation_shell_test.dart`, not `app_router_test.dart`.
2. **Everything is one teal.** Ground, cards, borders, and text are all low-contrast
   greens. The Canopy accents (pollen/bloom/orchid, and `leaf`/`sky`/`berry`/`clay` on
   `GreenThumbExtension`) are essentially unused, and the web's accent `Tile` icon squares,
   `StatCard`, status `Chip`s and `HeroCard` have no Flutter equivalent in use. The five
   forum boards are five identical text rows. Fix direction: build the missing primitives
   (`CanopyTile`, `CanopyChip`, `CanopyStatCard`, `CanopyHeroCard`, progress meter) mirroring
   `web/src/components/ui/`, then give each board/category/care-type its own accent tile.
3. **No brand presence.** Only the splash/home shows the logo. Fix direction: `BrandMark`
   in the profile header, empty states, and the primary app bar title where it fits.
4. **Low-contrast micro-text.** Section labels ("Profile Details", "Settings"), the
   "0 PLANTS IDENTIFIED" eyebrow and meta text use `ink3` at small sizes on `surface2`;
   verify against 4.5:1. Dates render as raw ISO (`2026-09-24`) — use relative time in
   Geist Mono. Thread meta rows truncate names ("William T...") — rebalance the row.
5. **Layout inconsistencies.** Profile stat tiles have different widths/heights
   ("Plants Identified" wraps and makes tile 1 wider); settings rows let long copy run
   under the toggle. Fix direction: equal-flex tiles with a fixed minimum height, text in
   `Expanded`, trailing control with reserved width.
6. **Empty state duplicates the FAB** ("Identify a plant" button + camera FAB) and is
   visually bare: add an illustration (Canopy art / BrandMark), animate it in.
7. **No motion anywhere** (confirmed on device): no transitions, no list entrance, no press
   feedback, no animated numbers, no haptics. See Part 3C.

## Part 2 — Current Flutter practice (researched 2026-10-18)

**Material 3 Expressive (M3E).** Google announced it at I/O 2025 (spring-based motion,
35 morphable shapes, bolder type/colour, ~15 new/updated components). As of this research
Flutter core has NOT shipped it; coverage said the Flutter team is applying lessons from
the M3 rollout with no date. A third-party `material_expressive` package exists
(v0.8.0, pre-1.0, tiny adoption, no stability guarantees). **Recommendation: do not add it
as a dependency.** Borrow the ideas using core APIs: spring physics
(`SpringSimulation`), shape morphing (`ShapeBorder.lerp` / `AnimatedContainer` with
`ShapeDecoration`), emphasised type for hero moments. Re-check status at the start of any
big UI task — this may change.

**Navigation & transitions.** Recent Flutter defaults Android to
`PredictiveBackPageTransitionsBuilder` (back gesture animates the route and can be
cancelled) with `FadeForwardsPageTransitionsBuilder` for ordinary pushes. Set
`pageTransitionsTheme` deliberately in `AppTheme` rather than inheriting whatever the
SDK defaults to; confirm Android 14+ opt-in (`enableOnBackInvokedCallback`) in the manifest.
For list-to-detail, use `Hero` (plant photos are ideal) or the first-party `animations`
package (`OpenContainer`, shared axis, fade through).

**Adaptive layout.** Decide on *window size*, not device type. Material window classes:
compact <600dp, medium 600-839dp, expanded >=840dp. Compact uses `NavigationBar`, medium+
`NavigationRail`. Use `MediaQuery.sizeOf(context)` (not `MediaQuery.of`) so a widget only
rebuilds when size changes; use `LayoutBuilder` for component-level decisions.

**Motion tokens.** Flutter ships M3 `Durations` and `Easing` (`flutter/material.dart`,
e.g. `Easing.emphasizedDecelerate`, `Durations.short4`) — use these instead of ad-hoc
millisecond literals so motion reads as one system.

**Accessibility (and this is what fixes "text doesn't fit").**

- Tap targets: 48x48dp Android / 44x44pt iOS. Test with `meetsGuideline(
  androidTapTargetGuideline)`, `iOSTapTargetGuideline`, `labeledTapTargetGuideline`,
  `textContrastGuideline` after `tester.ensureSemantics()`.
- Contrast: 4.5:1 body, 3:1 for large text (>=18pt regular / 14pt bold) and UI components.
- Text scale: users can set 200%+. Layouts must flex. `MediaQuery.withClampedTextScaling(
  minScaleFactor:, maxScaleFactor:)` exists but is a trade-off: clamp only dense chrome
  (nav labels, chips, badges), never body copy, and never below ~1.3 globally.
- Reduced motion: `MediaQuery.disableAnimationsOf(context)` -> durations to zero / skip.
- Bold text: `MediaQuery.boldTextOf(context)`.

**Performance.** `const` constructors; `ListView.builder`/slivers for long lists;
`RepaintBoundary` around gradient+shadow cards inside scrolling lists and around anything
repainting every frame; animate with `FadeTransition`/`ScaleTransition`/`AnimatedBuilder`
(compositing-only) rather than `Opacity` in an animation; size images to their slot
(`cacheWidth`/`memCacheWidth` with `cached_network_image`); never rebuild the camera
preview subtree on UI state changes. Impeller is the default renderer on current iOS/Android,
so shader-compilation jank is largely a solved problem — profile on a real mid-range
Android device in profile mode, not a simulator.

## Part 3 — Pattern catalog (Canopy-compatible)

**A. Buttons that fit.** Root causes of overflow: label in a `Row` without `Flexible`,
fixed `SizedBox(width:)`/`height:` around a button, side-by-side buttons in a `Row` that
should wrap, ellipsising an *action* label (hides meaning), no text-scale headroom.

- Size with `minimumSize`/`ConstrainedBox(minHeight:)`, never a fixed height.
- Primary CTA = `ClayButton`. Let labels wrap to 2 lines before ellipsis for actions;
  keep labels short (verb + noun, <=2 words ideal — see `design:ux-copy` skill).
- Button groups: `Wrap(spacing:, runSpacing:)` or stack vertically at compact width;
  full-width stacked CTAs on phones are normal.
- If `ClayButton` itself needs wrap/`maxLines`/scale-down support, fix it there once.

**B. Surfaces & depth.** Cards = `CanopyCard`; page backdrop = `CanopyGround`; interactive
rows = `CanopyCard(onTap:)`. A `Container(color: surface2)` reads off-system. Accent
colours only on small elements (icon tiles, badges, progress) and never for body text.

**C. Feedback & delight (cheap, high impact).**

- Press feedback: slight scale (0.97) with a spring or `Easing.emphasizedDecelerate`;
  `HapticFeedback.selectionClick()` on chip/tab changes, `lightImpact()` on primary
  actions, `mediumImpact()` for confirmations. Respect OS haptics settings (the API does).
- State changes animate: `AnimatedSwitcher` for loading -> content -> empty,
  `AnimatedContainer` for selected chips, `AnimatedSize` for expanding sections.
- Skeleton loaders shaped like the real content (e.g. `skeletonizer`) instead of spinners
  for lists; keep `LoadingIndicator` for short blocking waits.
- Staggered entrance for the first render of a list/grid (`Interval` curves, ~40-50ms
  stagger, once per screen visit, skipped under reduced motion).
- Empty states: Canopy illustration + one sentence + one action.

**D. Scroll & structure.** `CustomScrollView` with `SliverAppBar.large`/`.medium` for
primary screens (title collapses on scroll); sticky filter-chip header via
`SliverPersistentHeader`; pull-to-refresh with `RefreshIndicator.adaptive`; bottom sheets
(`showModalBottomSheet`, `DraggableScrollableSheet`) for secondary actions instead of
new routes; `SafeArea` + generous thumb-zone placement of primary actions.

**E. Plant-ID / camera surfaces (the product's centre).**

- Viewfinder: scanning reticle / corner brackets drawn with `CustomPainter` over the
  preview, isolated in a `RepaintBoundary`; shutter button with haptic + brief flash.
- Result reveal: Hero the captured photo into the result screen, then fade/slide the
  specimen card in; confidence as a `ProgressBar`-style gradient meter with Geist Mono
  percentage (tabular figures).
- Specimen cards: photo, common name (display face), Latin name (italic/mono eyebrow),
  status chips for care state.
- Care/garden: status chips + a small accent `Tile` per care type (water = orchid/sky).

**F. M3E ideas worth borrowing, with core APIs.**

```dart
// Spring-driven press scale (feels physical; no package needed)
const _spring = SpringDescription(mass: 1, stiffness: 420, damping: 30);
void _animateTo(AnimationController c, double target) =>
    c.animateWith(SpringSimulation(_spring, c.value, target, c.velocity));

// Reduced-motion-aware duration
Duration motion(BuildContext c, Duration d) =>
    MediaQuery.disableAnimationsOf(c) ? Duration.zero : d;

// Clamp text scale for dense chrome only (wrap the chrome, not the app)
MediaQuery.withClampedTextScaling(
  maxScaleFactor: 1.3,
  child: const _FilterChipRow(),
);
```

**G. Testing UI work.** The repo already has golden tests
(`test/core/theme/canopy_visual_golden_test.dart`) and the rule that the default 800x600
test surface hides overflow. For every UI change: pump at 320x640 and 375x812, at text
scale 1.0 and 2.0, in dark AND light; assert no overflow exceptions; run the four
accessibility guidelines above. Add/refresh goldens for changed shared widgets.

## Sources

- Flutter docs via Context7 (`/flutter/website`): accessibility testing, tap targets,
  clamped text scaling, adaptive/responsive window sizes, default Android page transition
  (PredictiveBack / FadeForwards), animation cookbook.
- [Material 3 Expressive — Google](https://m3.material.io/blog/building-with-m3-expressive)
- [Android 16 x Material 3 Expressive, incl. Flutter status](https://proandroiddev.com/android-16-x-material-3-e-biggest-ui-change-yet-updates-for-android-jetpack-compose-and-flutter-35d6b53a5242)
- [material_expressive on pub.dev](https://pub.dev/packages/material_expressive) (third-party, v0.8.0)
- [Modern Flutter UI in 2026 (ExpertAppDevs)](https://medium.com/@expertappdevs/how-to-build-modern-ui-in-flutter-design-patterns-64615b5815fb) — generic; used only for layout/theming basics
