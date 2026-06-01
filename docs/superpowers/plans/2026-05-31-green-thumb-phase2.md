# Green Thumb Phase 2 — Screen Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the Green Thumb design system to every Flutter screen and widget, replace all `AppColors` references with semantic tokens, add three stub screens (Care, Forum, Collection), and delete `app_colors.dart`.

**Architecture:** Widgets-first — `ClayButton` replaces `GradientButton` in Task 1 so every subsequent screen task can reference it. `GrainOverlay` (already built in Phase 1) is applied to Splash and Home `Scaffold.body` only. All screen/card padding uses `GreenThumbExtension` density tokens (`ext.padScreen`, `ext.padCard`, `ext.gapY`). The spec is at `docs/superpowers/specs/2026-05-31-green-thumb-phase2-design.md` — read it if you need colour mapping details.

**Tech Stack:** Flutter 3.x · Material 3 · Riverpod 3.x (`@riverpod`, `ConsumerWidget`) · go\_router · Phase 1 design system (`GreenThumbExtension`, `AppTheme.build()`, `GrainOverlay`, `PaletteNotifier`, `AppSpacing` radius tokens).

---

## Phase 1 APIs you will use throughout this plan

```dart
// Always destructure these two at the top of build():
final cs  = Theme.of(context).colorScheme;
final ext = Theme.of(context).extension<GreenThumbExtension>()!;

// ext fields: clay, onClay, berry, sky, leaf, ink2, ink3, statusOk, statusWarn,
//             shadow1, shadow2, shadow3 (List<BoxShadow>),
//             padCard, padScreen, gapY (double), showGrain (bool)

// Grain overlay — wrap Scaffold.body content (Splash + Home only):
GrainOverlay(child: myScrollableContent)

// Palette notifier (SettingsScreen):
ref.watch(paletteProvider)                              // → PaletteSettings
ref.read(paletteProvider.notifier).setPalette(choice)  // AppPaletteChoice
ref.read(paletteProvider.notifier).setDensity(density) // AppDensity

// Build a theme in tests:
AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
```

**AppSpacing radius tokens** (already in `lib/core/constants/app_spacing.dart`):
`rXs=6`, `rSm=10`, `rMd=16`, `rLg=22`, `rXl=28`, `rPill=999`

**All commands run from `plant_community_mobile/`.**

---

## Branch Setup

- [ ] Create the Phase 2 branch from `main` (after Phase 1 PR merges):

```bash
git checkout main && git pull
git checkout -b feat/green-thumb-phase2
cd plant_community_mobile
```

---

## Task 1: ClayButton

**Files:**

- Create: `lib/shared/widgets/clay_button.dart`
- Create: `test/shared/widgets/clay_button_test.dart`

- [ ] **Step 1 — Write the failing tests**

```dart
// test/shared/widgets/clay_button_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: Scaffold(body: Center(child: child)),
    );

GreenThumbExtension get _ext =>
    AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
        .extension<GreenThumbExtension>()!;

void main() {
  testWidgets('renders label', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'Tap me')));
    expect(find.text('Tap me'), findsOneWidget);
  });

  testWidgets('primary variant uses clay background', (tester) async {
    await tester.pumpWidget(
        _wrap(ClayButton(label: 'X', onPressed: () {})));
    final ext = _ext;
    final hasClay = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == ext.clay);
    expect(hasClay, isTrue);
  });

  testWidgets('secondary variant uses colorScheme.primary', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'X',
      variant: ClayButtonVariant.secondary,
      onPressed: () {},
    )));
    final primary = AppTheme.build(
            AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
        .colorScheme
        .primary;
    final hasPrimary = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == primary);
    expect(hasPrimary, isTrue);
  });

  testWidgets('outline variant has transparent background', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'X',
      variant: ClayButtonVariant.outline,
      onPressed: () {},
    )));
    final hasTransparent = tester
        .widgetList<Container>(find.byType(Container))
        .any((c) =>
            c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).color == Colors.transparent);
    expect(hasTransparent, isTrue);
  });

  testWidgets('disabled: InkWell.onTap is null', (tester) async {
    await tester.pumpWidget(_wrap(const ClayButton(label: 'X')));
    final inkWell = tester.widget<InkWell>(find.byType(InkWell));
    expect(inkWell.onTap, isNull);
  });

  testWidgets('fullWidth wraps in SizedBox with infinite width', (tester) async {
    await tester.pumpWidget(
        _wrap(const ClayButton(label: 'X', fullWidth: true)));
    expect(
      find.byWidgetPredicate(
          (w) => w is SizedBox && w.width == double.infinity),
      findsOneWidget,
    );
  });

  testWidgets('icon renders when provided', (tester) async {
    await tester.pumpWidget(_wrap(ClayButton(
      label: 'Go',
      icon: Icons.arrow_forward,
      onPressed: () {},
    )));
    expect(find.byIcon(Icons.arrow_forward), findsOneWidget);
  });
}
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/shared/widgets/clay_button_test.dart
# Expected: compilation error — ClayButton not found
```

- [ ] **Step 3 — Implement ClayButton**

```dart
// lib/shared/widgets/clay_button.dart
import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

enum ClayButtonVariant { primary, secondary, outline }

enum ClayButtonSize { small, medium, large }

class ClayButton extends StatelessWidget {
  const ClayButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.fullWidth = false,
    this.size = ClayButtonSize.large,
    this.variant = ClayButtonVariant.primary,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool fullWidth;
  final ClayButtonSize size;
  final ClayButtonVariant variant;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;
    final isDisabled = onPressed == null;

    final Color bg;
    final Color fg;
    final List<BoxShadow> shadow;

    switch (variant) {
      case ClayButtonVariant.primary:
        bg = isDisabled ? cs.surfaceContainerHighest : ext.clay;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : ext.onClay;
        shadow = isDisabled ? const [] : ext.shadow1;
      case ClayButtonVariant.secondary:
        bg = isDisabled ? cs.surfaceContainerHighest : cs.primary;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : cs.onPrimary;
        shadow = isDisabled ? const [] : ext.shadow1;
      case ClayButtonVariant.outline:
        bg = Colors.transparent;
        fg = isDisabled ? cs.onSurface.withValues(alpha: 0.38) : cs.primary;
        shadow = const [];
    }

    final (double vPad, double hPad, double fontSize) = switch (size) {
      ClayButtonSize.small  => (AppSpacing.sm,  AppSpacing.md, 14.0),
      ClayButtonSize.medium => (AppSpacing.md.toDouble(), AppSpacing.lg.toDouble(), 16.0),
      ClayButtonSize.large  => (AppSpacing.lg.toDouble(), AppSpacing.xl.toDouble(), 16.0),
    };

    final border = variant == ClayButtonVariant.outline
        ? Border.all(
            color: isDisabled
                ? cs.onSurface.withValues(alpha: 0.12)
                : cs.primary,
          )
        : null;

    final button = Container(
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppSpacing.rPill),
        border: border,
        boxShadow: shadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: isDisabled ? null : onPressed,
          borderRadius: BorderRadius.circular(AppSpacing.rPill),
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: hPad,
              vertical: vPad,
            ),
            child: Row(
              mainAxisSize:
                  fullWidth ? MainAxisSize.max : MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: fg,
                    fontSize: fontSize,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (icon != null) ...[
                  const SizedBox(width: AppSpacing.sm),
                  Icon(icon, color: fg, size: fontSize + 2),
                ],
              ],
            ),
          ),
        ),
      ),
    );

    if (fullWidth) {
      return SizedBox(width: double.infinity, child: button);
    }
    return button;
  }
}
```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/shared/widgets/clay_button_test.dart
# Expected: 7/7 PASS
```

- [ ] **Step 5 — Analyze**

```bash
flutter analyze lib/shared/widgets/clay_button.dart
# Expected: No issues found!
```

- [ ] **Step 6 — Commit**

```bash
git add lib/shared/widgets/clay_button.dart test/shared/widgets/clay_button_test.dart
git commit -m "feat: add ClayButton widget (replaces GradientButton)"
```

---

## Task 2: FeatureCard + LoadingIndicator token updates

**Files:**

- Modify: `lib/shared/widgets/feature_card.dart`
- Modify: `lib/shared/widgets/loading_indicator.dart`
- Modify: `test/shared/widgets/feature_card_test.dart` (update existing)

- [ ] **Step 1 — Add a failing test to feature_card_test.dart**

Open `test/shared/widgets/feature_card_test.dart`. Add these tests (keep all existing tests):

```dart
// Add these imports if not present:
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

// Add this helper if not present:
GreenThumbExtension get _ext =>
    AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
        .extension<GreenThumbExtension>()!;

// Add these new tests:
testWidgets('care type uses ext.sky accent', (tester) async {
  await tester.pumpWidget(_wrap(const FeatureCard(
    icon: Icons.book,
    title: 'Care',
    description: 'desc',
    type: FeatureType.care,
  )));
  final ext = _ext;
  // Icon container tint is sky at 0.12 opacity
  final containers = tester.widgetList<Container>(find.byType(Container));
  final hasSkyTint = containers.any((c) =>
      c.decoration is BoxDecoration &&
      (c.decoration as BoxDecoration).color ==
          ext.sky.withValues(alpha: 0.12));
  expect(hasSkyTint, isTrue);
});

testWidgets('community type uses ext.berry accent', (tester) async {
  await tester.pumpWidget(_wrap(const FeatureCard(
    icon: Icons.people,
    title: 'Community',
    description: 'desc',
    type: FeatureType.community,
  )));
  final ext = _ext;
  final containers = tester.widgetList<Container>(find.byType(Container));
  final hasBerryTint = containers.any((c) =>
      c.decoration is BoxDecoration &&
      (c.decoration as BoxDecoration).color ==
          ext.berry.withValues(alpha: 0.12));
  expect(hasBerryTint, isTrue);
});
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/shared/widgets/feature_card_test.dart
# Expected: new tests FAIL (FeatureType.care still maps to blue500/600)
```

- [ ] **Step 3 — Update FeatureCard**

In `lib/shared/widgets/feature_card.dart`:

Remove the `AppColors` import. Replace `FeatureCardColors.getIconColor` with:

```dart
static Color getIconColor(BuildContext context, FeatureType type) {
  final cs = Theme.of(context).colorScheme;
  final ext = Theme.of(context).extension<GreenThumbExtension>()!;
  return switch (type) {
    FeatureType.camera     => cs.primary,
    FeatureType.care       => ext.sky,
    FeatureType.community  => ext.berry,
    FeatureType.collection => cs.tertiary,
  };
}
```

In `FeatureCard.build`, replace the `Card` + `elevation` approach with shadow-based decoration. Replace:

```dart
return Card(
  elevation: AppSpacing.elevationSM,
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(AppSpacing.radiusLG),
  ),
  child: InkWell(
    onTap: onTap,
    borderRadius: BorderRadius.circular(AppSpacing.radiusLG),
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
```

With:

```dart
final ext = Theme.of(context).extension<GreenThumbExtension>()!;
final cs = Theme.of(context).colorScheme;
return Container(
  decoration: BoxDecoration(
    color: cs.surface,
    borderRadius: BorderRadius.circular(AppSpacing.rMd),
    boxShadow: ext.shadow1,
  ),
  child: Material(
    color: Colors.transparent,
    borderRadius: BorderRadius.circular(AppSpacing.rMd),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppSpacing.rMd),
      child: Padding(
        padding: EdgeInsets.all(ext.padCard),
```

Add `import '../../core/theme/green_thumb_extension.dart';` at the top.

- [ ] **Step 4 — Update LoadingIndicator**

In `lib/shared/widgets/loading_indicator.dart`, change:

```dart
// Before:
final effectiveColor = color ?? AppColors.green600;
// After:
final effectiveColor = color ?? Theme.of(context).colorScheme.primary;
```

Remove the `AppColors` import line.

- [ ] **Step 5 — Run tests**

```bash
flutter test test/shared/widgets/feature_card_test.dart
flutter test test/shared/widgets/loading_indicator_test.dart
# Expected: all PASS
```

- [ ] **Step 6 — Verify no AppColors references remain in these files**

```bash
grep "AppColors" lib/shared/widgets/feature_card.dart lib/shared/widgets/loading_indicator.dart
# Expected: no output
```

- [ ] **Step 7 — Analyze + commit**

```bash
flutter analyze lib/shared/widgets/
git add lib/shared/widgets/feature_card.dart lib/shared/widgets/loading_indicator.dart \
        test/shared/widgets/feature_card_test.dart
git commit -m "feat: migrate FeatureCard + LoadingIndicator to design tokens"
```

---

## Task 3: SplashScreen redesign

**Files:**

- Modify: `lib/features/splash/splash_screen.dart`
- Modify: `test/features/splash/splash_screen_test.dart`

- [ ] **Step 1 — Add failing tests**

Open `test/features/splash/splash_screen_test.dart`. Add:

```dart
testWidgets('GrainOverlay present in widget tree', (tester) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
    home: const SplashScreen(),
  ));
  expect(find.byType(GrainOverlay), findsOneWidget);
});

testWidgets('no LinearGradient background on Scaffold', (tester) async {
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
    home: const SplashScreen(),
  ));
  // The old gradient was in a Container BoxDecoration with LinearGradient
  final gradientContainers = tester
      .widgetList<Container>(find.byType(Container))
      .where((c) =>
          c.decoration is BoxDecoration &&
          (c.decoration as BoxDecoration).gradient is LinearGradient);
  expect(gradientContainers.isEmpty, isTrue);
});
```

Add required imports: `GrainOverlay` from `core/theme/grain_overlay.dart`.

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/splash/splash_screen_test.dart
# Expected: new tests FAIL
```

- [ ] **Step 3 — Rewrite SplashScreen**

Replace `lib/features/splash/splash_screen.dart` with the following. The animation controllers, timer, and navigation logic are **unchanged** — only the `build()` method changes:

```dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/grain_overlay.dart';
import '../../core/theme/green_thumb_extension.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {
  late AnimationController _rotationController;
  late AnimationController _scaleController;
  late AnimationController _fadeController;
  late Timer _progressTimer;
  double _progress = 0.0;

  @override
  void initState() {
    super.initState();

    _rotationController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat();

    _scaleController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );

    _scaleController.forward();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _fadeController.forward();
    });

    _progressTimer = Timer.periodic(const Duration(milliseconds: 30), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_progress >= 100) {
        timer.cancel();
        Future.delayed(const Duration(milliseconds: 300), () {
          if (mounted) context.go(AppRoutes.home);
        });
      } else {
        setState(() => _progress += 2);
      }
    });
  }

  @override
  void dispose() {
    _rotationController.dispose();
    _scaleController.dispose();
    _fadeController.dispose();
    _progressTimer.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    return Scaffold(
      backgroundColor: cs.surface,
      body: GrainOverlay(
        child: Center(
          child: ScaleTransition(
            scale: CurvedAnimation(
              parent: _scaleController,
              curve: Curves.easeOut,
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // Logo
                RotationTransition(
                  turns: _rotationController,
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: cs.primary,
                      boxShadow: ext.shadow2,
                    ),
                    child: const Icon(Icons.eco, size: 48, color: Colors.white),
                  ),
                ),
                SizedBox(height: ext.gapY * 2),

                // App name + tagline
                FadeTransition(
                  opacity: _fadeController,
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.2),
                      end: Offset.zero,
                    ).animate(CurvedAnimation(
                      parent: _fadeController,
                      curve: Curves.easeOut,
                    )),
                    child: Column(
                      children: [
                        Text(
                          'PlantID',
                          style: Theme.of(context)
                              .textTheme
                              .displayLarge
                              ?.copyWith(
                                fontSize: 48,
                                color: cs.onSurface,
                              ),
                        ),
                        SizedBox(height: ext.gapY),
                        Text(
                          'DISCOVER NATURE\'S SECRETS',
                          style:
                              Theme.of(context).textTheme.labelSmall?.copyWith(
                                    letterSpacing: 0.06 * 11,
                                    color: ext.ink3,
                                  ),
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: ext.gapY * 2),

                // Progress bar
                FadeTransition(
                  opacity: _fadeController,
                  child: SizedBox(
                    width: 200,
                    child: ClipRRect(
                      borderRadius:
                          BorderRadius.circular(AppSpacing.rPill),
                      child: LinearProgressIndicator(
                        value: _progress / 100,
                        minHeight: 4,
                        backgroundColor: cs.surfaceContainerLow,
                        valueColor:
                            AlwaysStoppedAnimation<Color>(cs.primary),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/splash/splash_screen_test.dart
# Expected: all PASS
```

- [ ] **Step 5 — Verify no AppColors references**

```bash
grep "AppColors\|app_colors" lib/features/splash/splash_screen.dart
# Expected: no output
```

- [ ] **Step 6 — Analyze + commit**

```bash
flutter analyze lib/features/splash/
git add lib/features/splash/splash_screen.dart test/features/splash/splash_screen_test.dart
git commit -m "feat: redesign SplashScreen — palette tokens, grain overlay, remove gradient"
```

---

## Task 4: HomePage redesign

**Files:**

- Modify: `lib/features/home/home_page.dart`
- Modify: `test/features/home/home_page_test.dart`

- [ ] **Step 1 — Add failing tests**

Open `test/features/home/home_page_test.dart`. Add:

```dart
testWidgets('ClayButton present for Get Started CTA', (tester) async {
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: const HomePage(),
    ),
  ));
  expect(find.byType(ClayButton), findsOneWidget);
});

testWidgets('GrainOverlay present in widget tree', (tester) async {
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: const HomePage(),
    ),
  ));
  expect(find.byType(GrainOverlay), findsOneWidget);
});

testWidgets('eyebrow label PLANT IDENTIFICATION present', (tester) async {
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: const HomePage(),
    ),
  ));
  expect(find.text('PLANT IDENTIFICATION'), findsOneWidget);
});
```

Add imports: `ClayButton`, `GrainOverlay`, `AppTheme`, `AppPaletteChoice`, `AppDensity`.

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/home/home_page_test.dart
# Expected: new tests FAIL
```

- [ ] **Step 3 — Update HomePage**

In `lib/features/home/home_page.dart`:

1. Remove `import '../../core/theme/app_colors.dart';`
2. Add imports:

   ```dart
   import '../../core/theme/grain_overlay.dart';
   import '../../core/theme/green_thumb_extension.dart';
   import '../../shared/widgets/clay_button.dart';
   ```

3. Replace the `build()` method padding:

   ```dart
   // Before:
   padding: const EdgeInsets.symmetric(
     horizontal: AppSpacing.lg,
     vertical: AppSpacing.xl2,
   ),
   // After:
   padding: EdgeInsets.symmetric(
     horizontal: ext.padScreen,
     vertical: ext.padScreen * 2,
   ),
   ```

   Add `final ext = Theme.of(context).extension<GreenThumbExtension>()!;` at the top of `build()`.

4. Wrap `SingleChildScrollView` content in `GrainOverlay`:

   ```dart
   body: SafeArea(
     child: SingleChildScrollView(
       child: GrainOverlay(
         child: Padding(
           padding: EdgeInsets.symmetric(...),
           child: Column(...),
         ),
       ),
     ),
   ),
   ```

5. Replace `_buildHeroSection` — remove `ShaderMask`, update inner circle, add eyebrow:

   ```dart
   Widget _buildHeroSection(BuildContext context) {
     final cs = Theme.of(context).colorScheme;
     final ext = Theme.of(context).extension<GreenThumbExtension>()!;
     return Column(
       children: [
         Text(
           'PLANT IDENTIFICATION',
           style: Theme.of(context).textTheme.labelSmall?.copyWith(
             letterSpacing: 0.06 * 11,
             color: ext.ink3,
           ),
         ),
         SizedBox(height: ext.gapY),
         Container(
           width: 128,
           height: 128,
           decoration: BoxDecoration(
             shape: BoxShape.circle,
             color: cs.surfaceContainerLow,
           ),
           child: Center(
             child: Container(
               width: 96,
               height: 96,
               decoration: BoxDecoration(
                 shape: BoxShape.circle,
                 color: cs.primary,
                 boxShadow: ext.shadow2,
               ),
               child: const Icon(Icons.camera_alt, size: 48, color: Colors.white),
             ),
           ),
         ),
         SizedBox(height: ext.gapY),
         Text(
           'Welcome to PlantID',
           style: Theme.of(context).textTheme.displayLarge?.copyWith(
             color: cs.onSurface,
           ),
           textAlign: TextAlign.center,
         ),
         SizedBox(height: ext.gapY),
         Text(
           'Your pocket botanist for identifying plants, learning care tips, and connecting with fellow plant enthusiasts',
           style: Theme.of(context).textTheme.bodyMedium?.copyWith(
             color: ext.ink2,
             height: 1.5,
           ),
           textAlign: TextAlign.center,
           maxLines: 3,
         ),
       ],
     );
   }
   ```

6. Replace gaps between feature cards: `SizedBox(height: ext.gapY)`

7. Replace `_buildCTAButton` — swap `GradientButton` for `ClayButton`:

   ```dart
   Widget _buildCTAButton(BuildContext context) {
     return ConstrainedBox(
       constraints: const BoxConstraints(maxWidth: 600),
       child: ClayButton(
         label: 'Get Started',
         icon: Icons.arrow_forward,
         fullWidth: true,
         onPressed: () => context.go(AppRoutes.camera),
       ),
     );
   }
   ```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/home/home_page_test.dart
# Expected: all PASS
```

- [ ] **Step 5 — Verify**

```bash
grep "AppColors\|GradientButton" lib/features/home/home_page.dart
# Expected: no output
```

- [ ] **Step 6 — Analyze + commit**

```bash
flutter analyze lib/features/home/
git add lib/features/home/home_page.dart test/features/home/home_page_test.dart
git commit -m "feat: redesign HomePage — palette tokens, grain overlay, ClayButton CTA"
```

---

## Task 5: CameraScreen redesign

**Files:**

- Modify: `lib/features/camera/camera_screen.dart`
- Modify: `test/features/camera/camera_screen_test.dart`

- [ ] **Step 1 — Add failing test**

```dart
testWidgets('ClayButton shown when image is selected', (tester) async {
  // This test pumps a CameraScreen with a pre-selected image path using
  // the existing test infrastructure in camera_screen_test.dart.
  // If no image-selection helper exists, just test that ClayButton is NOT
  // present initially (placeholder state).
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: const CameraScreen(),
    ),
  ));
  // No image selected → no identify button
  expect(find.byType(ClayButton), findsNothing);
});
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/camera/camera_screen_test.dart
# Expected: new test FAILS (ClayButton not yet in CameraScreen)
```

- [ ] **Step 3 — Update CameraScreen**

In `lib/features/camera/camera_screen.dart`:

1. Remove `import '../../core/theme/app_colors.dart';`
2. Add:

   ```dart
   import '../../core/theme/green_thumb_extension.dart';
   import '../../shared/widgets/clay_button.dart';
   ```

3. In `build()`, add at the top:

   ```dart
   final cs = Theme.of(context).colorScheme;
   final ext = Theme.of(context).extension<GreenThumbExtension>()!;
   ```

   Change `padding: const EdgeInsets.all(AppSpacing.lg)` → `padding: EdgeInsets.all(ext.padScreen)`.

4. Replace `_buildImageCard` — add shadow + rLg corners:

   ```dart
   Widget _buildImageCard() {
     final ext = Theme.of(context).extension<GreenThumbExtension>()!;
     return Container(
       decoration: BoxDecoration(
         borderRadius: BorderRadius.circular(AppSpacing.rLg),
         boxShadow: ext.shadow2,
       ),
       child: ClipRRect(
         borderRadius: BorderRadius.circular(AppSpacing.rLg),
         child: AspectRatio(
           aspectRatio: 1.0,
           child: _selectedImagePath != null
               ? _buildSelectedImage()
               : _buildPlaceholder(),
         ),
       ),
     );
   }
   ```

5. Replace `_buildPlaceholder` colour:

   ```dart
   color: Theme.of(context).colorScheme.surfaceContainerLow,
   // (remove the isDark ternary with AppColors)
   ```

6. Replace Identify button with ClayButton:

   ```dart
   if (_selectedImagePath != null) ...[
     const SizedBox(height: AppSpacing.md),
     ClayButton(
       label: _isIdentifying ? 'Identifying...' : 'Identify Plant',
       icon: _isIdentifying ? null : Icons.search,
       fullWidth: true,
       onPressed: _isIdentifying ? null : _identifyPlant,
     ),
   ],
   ```

7. Fix error snackbar background:

   ```dart
   backgroundColor: Theme.of(context).colorScheme.error,
   // (replaces AppColors.lightDestructive)
   ```

8. Fix ElevatedButton.styleFrom for Identify (now ClayButton — remove the old `backgroundColor: AppColors.green600` override from the original ElevatedButton).

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/camera/camera_screen_test.dart
# Expected: all PASS
```

- [ ] **Step 5 — Verify**

```bash
grep "AppColors" lib/features/camera/camera_screen.dart
# Expected: no output
```

- [ ] **Step 6 — Analyze + commit**

```bash
flutter analyze lib/features/camera/
git add lib/features/camera/camera_screen.dart test/features/camera/camera_screen_test.dart
git commit -m "feat: migrate CameraScreen to design tokens, ClayButton for Identify"
```

---

## Task 6: ResultsScreen redesign

**Files:**

- Modify: `lib/features/results/results_screen.dart`
- Modify: `test/features/results/results_screen_test.dart`

- [ ] **Step 1 — Add failing tests**

```dart
testWidgets('Identified badge uses ext.leaf background', (tester) async {
  final plant = Plant(
    name: 'Monstera',
    scientificName: 'M. deliciosa',
    description: 'Test',
    care: ['Water weekly'],
    imageUrl: null,
    timestamp: DateTime(2026, 1, 1),
    confidence: 0.95,
  );
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
    home: ResultsScreen(plant: plant),
  ));
  final ext = AppTheme.build(AppPaletteChoice.loam, Brightness.light, AppDensity.cozy)
      .extension<GreenThumbExtension>()!;
  final hasLeafBadge = tester
      .widgetList<Container>(find.byType(Container))
      .any((c) =>
          c.decoration is BoxDecoration &&
          (c.decoration as BoxDecoration).color == ext.leaf);
  expect(hasLeafBadge, isTrue);
});
```

Check `lib/models/plant.dart` for the exact Plant constructor signature and adjust if needed.

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/results/results_screen_test.dart
# Expected: new test FAILS
```

- [ ] **Step 3 — Update ResultsScreen**

In `lib/features/results/results_screen.dart`:

1. Remove `import '../../core/theme/app_colors.dart';`
2. Add `import '../../core/theme/green_thumb_extension.dart';`

3. In `build()` add:

   ```dart
   final cs = Theme.of(context).colorScheme;
   final ext = Theme.of(context).extension<GreenThumbExtension>()!;
   ```

   Change padding to `EdgeInsets.all(ext.padScreen)`.

4. "Identified" badge — replace colour:

   ```dart
   // Before:
   color: AppColors.green600,
   // After:
   color: ext.leaf,
   ```

   Badge text colour → `cs.onSurface`. Badge `BorderRadius` → `BorderRadius.circular(AppSpacing.rXs)`.

5. Plant info card — add `EdgeInsets.all(ext.padCard)` padding. Change common name style to `textTheme.headlineMedium`. Change scientific name to:

   ```dart
   style: Theme.of(context).textTheme.bodyMedium?.copyWith(
     fontFamily: 'GeistMono',
     fontStyle: FontStyle.italic,
     color: ext.ink2,
   ),
   ```

   Change description colour to `ext.ink2`.

6. Care header icon: `color: ext.sky` (replaces `AppColors.blue600`)

7. Care item icon circle:

   ```dart
   // Before:
   color: isDark ? AppColors.green900.withValues(alpha: 0.3) : AppColors.green100,
   // item icon color: isDark ? AppColors.green400 : AppColors.green700
   // After:
   color: ext.statusOk.withValues(alpha: 0.12),
   // item icon color: ext.statusOk
   ```

8. Image placeholders:

   ```dart
   // AppColors.green100 → cs.surfaceContainerLow
   // AppColors.lightCard → cs.surfaceContainerLow
   ```

9. Timestamp: `textTheme.bodySmall?.copyWith(color: ext.ink3)`

10. Remove `isDark` variable (no longer needed).

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/results/results_screen_test.dart
# Expected: all PASS
```

- [ ] **Step 5 — Verify**

```bash
grep "AppColors" lib/features/results/results_screen.dart
# Expected: no output
```

- [ ] **Step 6 — Analyze + commit**

```bash
flutter analyze lib/features/results/
git add lib/features/results/results_screen.dart test/features/results/results_screen_test.dart
git commit -m "feat: migrate ResultsScreen — leaf badge, sky care icon, statusOk care items"
```

---

## Task 7: ProfileScreen density padding + typography

**Files:**

- Modify: `lib/features/profile/profile_screen.dart`
- Modify: `test/features/profile/profile_screen_test.dart`

**Context:** `ProfileScreen` has no `AppColors` import — this task is pure density-token and typography adoption.

- [ ] **Step 1 — Add failing test**

```dart
testWidgets('padding uses ext.padScreen not hardcoded 16', (tester) async {
  // Pump with comfortable density (padScreen=18) to verify it's not always 16.
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.comfortable),
      home: const ProfileScreen(),
    ),
  ));
  // With comfortable density, the scroll view padding is 18, not 16.
  // Find the SingleChildScrollView and check its padding.
  final scrollView = tester.widget<SingleChildScrollView>(
      find.byType(SingleChildScrollView));
  final padding = scrollView.padding as EdgeInsets?;
  expect(padding?.left, equals(18.0));
});
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/profile/profile_screen_test.dart
# Expected: new test FAILS (hardcoded padding: const EdgeInsets.all(16))
```

- [ ] **Step 3 — Update ProfileScreen**

In `lib/features/profile/profile_screen.dart`:

1. Add `import '../../core/theme/green_thumb_extension.dart';`

2. In `ProfileScreen.build`, access ext and apply to the `SingleChildScrollView`:

   ```dart
   final ext = Theme.of(context).extension<GreenThumbExtension>()!;
   // Change: padding: const EdgeInsets.all(16),
   // To:
   padding: EdgeInsets.all(ext.padScreen),
   ```

3. Replace all `const SizedBox(height: 24)` section gaps with `SizedBox(height: ext.gapY * 2)`.

4. In `_ProfileHeader.build`:
   - Display name: change to `textTheme.headlineMedium`
   - Username `@...`: change to `textTheme.labelSmall?.copyWith(letterSpacing: 0.06 * 11, color: ext.ink3)`
   - Email: change to `textTheme.bodySmall?.copyWith(color: ext.ink2)`
   - Card padding `const EdgeInsets.all(16)` → `EdgeInsets.all(ext.padCard)`

5. In `_StatCard.build`:
   - Value: `textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)`
   - Label: `textTheme.bodySmall?.copyWith(color: ext.ink3)`
   - Card padding `const EdgeInsets.all(12)` → `EdgeInsets.all(ext.padCard * 0.75)`

6. In `_StatsSection.build`, change `const SizedBox(width: 12)` → `SizedBox(width: ext.gapY)`.

7. In `_ProfileDetailsSection.build`:
   - Section heading "Profile Details": change to eyebrow style

     ```dart
     style: Theme.of(context).textTheme.labelSmall?.copyWith(
       letterSpacing: 0.06 * 11,
       color: ext.ink3,
     ),
     ```

   - Card padding → `EdgeInsets.all(ext.padCard)`

8. In `_SettingsSection.build`:
   - "Settings" heading → same eyebrow style
   - Card padding → `EdgeInsets.all(ext.padCard)` (remove `const`)

9. In `ProfileScreen.build` `error:` branch:

   ```dart
   // Before: const Icon(Icons.error_outline, size: 64, color: Colors.red)
   // After:
   Icon(Icons.error_outline, size: 64,
       color: Theme.of(context).colorScheme.error)
   ```

**Note:** `_ProfileHeader`, `_StatsSection`, `_StatCard`, `_ProfileDetailsSection`, and `_SettingsSection` are private classes — they need to access `ext` via their own `Theme.of(context)` call inside their `build()` method. Each already receives `context`.

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/profile/profile_screen_test.dart
# Expected: all PASS
```

- [ ] **Step 5 — Analyze + commit**

```bash
flutter analyze lib/features/profile/
git add lib/features/profile/profile_screen.dart test/features/profile/profile_screen_test.dart
git commit -m "feat: ProfileScreen — density-responsive padding, ext typography tokens"
```

---

## Task 8: SettingsScreen — extract + palette/density controls

**Files:**

- Create: `lib/features/settings/settings_screen.dart`
- Create: `lib/core/routing/error_screen.dart`
- Create: `lib/core/routing/placeholder_screen.dart`
- Create: `test/features/settings/settings_screen_test.dart`
- Modify: `lib/core/routing/app_router.dart` (remove inline classes, add imports)

- [ ] **Step 1 — Write failing tests**

```dart
// test/features/settings/settings_screen_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';
import 'package:plant_community_mobile/features/settings/settings_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/config/palette_notifier.dart';

Widget _wrap(Widget child) => ProviderScope(
      child: MaterialApp(
        theme: AppTheme.build(
            AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
        home: child,
      ),
    );

void main() {
  testWidgets('renders 4 palette swatches', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    // Each palette name appears as text on a swatch
    expect(find.text('Loam'), findsOneWidget);
    expect(find.text('Garden'), findsOneWidget);
    expect(find.text('Forest'), findsOneWidget);
    expect(find.text('Heritage'), findsOneWidget);
  });

  testWidgets('density SegmentedButton renders 3 segments', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    expect(find.text('Comfortable'), findsOneWidget);
    expect(find.text('Cozy'), findsOneWidget);
    expect(find.text('Compact'), findsOneWidget);
  });

  testWidgets('tapping Garden swatch does not crash', (tester) async {
    await tester.pumpWidget(_wrap(const SettingsScreen()));
    await tester.tap(find.text('Garden'));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/settings/settings_screen_test.dart
# Expected: compilation error — SettingsScreen not found at new path
```

- [ ] **Step 3 — Create ErrorScreen**

```dart
// lib/core/routing/error_screen.dart
import 'package:flutter/material.dart';

class ErrorScreen extends StatelessWidget {
  const ErrorScreen({super.key, this.error});

  final Exception? error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 48,
                color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 16),
            const Text('Oops! Something went wrong'),
            if (error != null) ...[
              const SizedBox(height: 8),
              Text(
                error.toString(),
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4 — Create PlaceholderScreen**

```dart
// lib/core/routing/placeholder_screen.dart
import 'package:flutter/material.dart';

class PlaceholderScreen extends StatelessWidget {
  const PlaceholderScreen({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(child: Text('$title screen coming soon')),
    );
  }
}
```

- [ ] **Step 5 — Create SettingsScreen**

```dart
// lib/features/settings/settings_screen.dart
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../config/palette_notifier.dart';
import '../../config/theme_provider.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/app_palettes.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../core/theme/theme_preview_screen.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;
    final cs = Theme.of(context).colorScheme;
    final themeMode = ref.watch(themeModeProvider);
    final themeNotifier = ref.read(themeModeProvider.notifier);
    final palette = ref.watch(paletteProvider);
    final paletteNotifier = ref.read(paletteProvider.notifier);

    final eyebrowStyle = Theme.of(context).textTheme.labelSmall?.copyWith(
          letterSpacing: 0.06 * 11,
          color: ext.ink3,
        );

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: EdgeInsets.all(ext.padScreen),
          children: [
            // Appearance
            Text('APPEARANCE', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(value: ThemeMode.system,
                    icon: Icon(Icons.brightness_auto), label: Text('System')),
                ButtonSegment(value: ThemeMode.light,
                    icon: Icon(Icons.light_mode), label: Text('Light')),
                ButtonSegment(value: ThemeMode.dark,
                    icon: Icon(Icons.dark_mode), label: Text('Dark')),
              ],
              selected: {themeMode},
              onSelectionChanged: (s) {
                switch (s.first) {
                  case ThemeMode.light: themeNotifier.setLight();
                  case ThemeMode.dark: themeNotifier.setDark();
                  case ThemeMode.system: themeNotifier.setSystem();
                }
              },
            ),
            SizedBox(height: ext.gapY * 2),

            // Palette
            Text('PALETTE', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: AppPaletteChoice.values.map((choice) {
                final isSelected = palette.palette == choice;
                final swatchColor = _paletteSwatchColor(choice);
                return InkWell(
                  onTap: () => paletteNotifier.setPalette(choice),
                  borderRadius: BorderRadius.circular(AppSpacing.rSm),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: swatchColor,
                      borderRadius: BorderRadius.circular(AppSpacing.rSm),
                      border: isSelected
                          ? Border.all(color: cs.primary, width: 2)
                          : null,
                    ),
                    child: Text(
                      _paletteLabel(choice),
                      style: TextStyle(
                        color: _paletteTextColor(choice),
                        fontWeight: isSelected
                            ? FontWeight.bold
                            : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
            SizedBox(height: ext.gapY * 2),

            // Density
            Text('DENSITY', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            SegmentedButton<AppDensity>(
              segments: const [
                ButtonSegment(value: AppDensity.comfortable,
                    label: Text('Comfortable')),
                ButtonSegment(value: AppDensity.cozy, label: Text('Cozy')),
                ButtonSegment(value: AppDensity.compact,
                    label: Text('Compact')),
              ],
              selected: {palette.density},
              onSelectionChanged: (s) => paletteNotifier.setDensity(s.first),
            ),
            SizedBox(height: ext.gapY * 2),

            // About
            Text('ABOUT', style: eyebrowStyle),
            SizedBox(height: ext.gapY),
            const ListTile(
              leading: Icon(Icons.local_florist),
              title: Text('Plant Community'),
              subtitle: Text('Plant identification, care, and community features'),
            ),

            // Debug
            if (kDebugMode) ...[
              SizedBox(height: ext.gapY * 2),
              Text('DEBUG', style: eyebrowStyle),
              SizedBox(height: ext.gapY),
              ListTile(
                leading: const Icon(Icons.palette),
                title: const Text('Theme Preview'),
                subtitle: const Text('All 24 palette combinations'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push(ThemePreviewScreen.routePath),
              ),
            ],
          ],
        ),
      ),
    );
  }

  static Color _paletteSwatchColor(AppPaletteChoice c) => switch (c) {
        AppPaletteChoice.loam      => const Color(0xFF4A7034),
        AppPaletteChoice.garden    => const Color(0xFF2F6B3A),
        AppPaletteChoice.forest    => const Color(0xFFB8DC7C),
        AppPaletteChoice.heritage  => const Color(0xFF3D5A22),
      };

  static Color _paletteTextColor(AppPaletteChoice c) => switch (c) {
        AppPaletteChoice.forest => const Color(0xFF0F1A12),
        _                       => const Color(0xFFF4F1DF),
      };

  static String _paletteLabel(AppPaletteChoice c) => switch (c) {
        AppPaletteChoice.loam      => 'Loam',
        AppPaletteChoice.garden    => 'Garden',
        AppPaletteChoice.forest    => 'Forest',
        AppPaletteChoice.heritage  => 'Heritage',
      };
}
```

- [ ] **Step 6 — Update app_router.dart**

In `lib/core/routing/app_router.dart`:

1. Remove the inline `SettingsScreen`, `ErrorScreen`, `_PlaceholderScreen` class definitions.
2. Add imports:

   ```dart
   import '../features/settings/settings_screen.dart';
   import 'error_screen.dart';
   import 'placeholder_screen.dart';
   ```

3. Replace `_PlaceholderScreen(title: '...')` calls with `PlaceholderScreen(title: '...')`.

- [ ] **Step 7 — Run tests**

```bash
flutter test test/features/settings/settings_screen_test.dart
# Expected: all PASS
```

- [ ] **Step 8 — Run full suite**

```bash
flutter test
# Expected: all existing tests still PASS
```

- [ ] **Step 9 — Analyze + commit**

```bash
flutter analyze lib/features/settings/ lib/core/routing/
git add lib/features/settings/ lib/core/routing/ test/features/settings/
git commit -m "feat: extract SettingsScreen, add palette/density controls"
```

---

## Task 9: CareScreen stub

**Files:**

- Create: `lib/features/care/care_screen.dart`
- Create: `test/features/care/care_screen_test.dart`

- [ ] **Step 1 — Write failing tests**

```dart
// test/features/care/care_screen_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/care/care_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: child,
    );

void main() {
  testWidgets('renders 4 care category cards', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.text('Watering'), findsOneWidget);
    expect(find.text('Sunlight'), findsOneWidget);
    expect(find.text('Soil & Fertilising'), findsOneWidget);
    expect(find.text('Temperature'), findsOneWidget);
  });

  testWidgets('eyebrow CARE GUIDES present', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.text('CARE GUIDES'), findsOneWidget);
  });

  testWidgets('coming soon notice present', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(find.textContaining('coming soon'), findsOneWidget);
  });

  testWidgets('no crashes on pump', (tester) async {
    await tester.pumpWidget(_wrap(const CareScreen()));
    expect(tester.takeException(), isNull);
  });
}
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/care/care_screen_test.dart
# Expected: compilation error
```

- [ ] **Step 3 — Implement CareScreen**

```dart
// lib/features/care/care_screen.dart
import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

class CareScreen extends StatelessWidget {
  const CareScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    final eyebrowStyle = Theme.of(context).textTheme.labelSmall?.copyWith(
          letterSpacing: 0.06 * 11,
          color: ext.ink3,
        );

    return Scaffold(
      appBar: AppBar(title: const Text('Plant Care'), centerTitle: true),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(ext.padScreen),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('CARE GUIDES', style: eyebrowStyle),
              SizedBox(height: ext.gapY),
              Text(
                'Keep your plants happy',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              SizedBox(height: ext.gapY),
              Text(
                'Learn everything you need to help your plants thrive — from watering schedules to the perfect soil mix.',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: ext.ink2),
              ),
              SizedBox(height: ext.gapY * 2),
              ..._categories(cs, ext)
                  .map((c) => Padding(
                        padding: EdgeInsets.only(bottom: ext.gapY),
                        child: _CategoryCard(category: c, ext: ext),
                      )),
              SizedBox(height: ext.gapY),
              Text(
                'Full care guides coming soon',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: ext.ink3),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  static List<_Category> _categories(
      ColorScheme cs, GreenThumbExtension ext) => [
        _Category(
          title: 'Watering',
          subtitle: 'When and how much to water your plants',
          icon: Icons.water_drop,
          accent: ext.sky,
        ),
        _Category(
          title: 'Sunlight',
          subtitle: 'Light requirements for healthy growth',
          icon: Icons.wb_sunny,
          accent: cs.tertiary,
        ),
        _Category(
          title: 'Soil & Fertilising',
          subtitle: 'The right growing medium and nutrients',
          icon: Icons.grass,
          accent: cs.primary,
        ),
        _Category(
          title: 'Temperature',
          subtitle: 'Optimal conditions for your plants',
          icon: Icons.thermostat,
          accent: ext.clay,
        ),
      ];
}

class _Category {
  const _Category({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accent,
  });
  final String title;
  final String subtitle;
  final IconData icon;
  final Color accent;
}

class _CategoryCard extends StatelessWidget {
  const _CategoryCard({required this.category, required this.ext});
  final _Category category;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        contentPadding: EdgeInsets.all(ext.padCard),
        leading: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: category.accent.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppSpacing.rSm),
          ),
          child: Icon(category.icon, color: category.accent, size: 24),
        ),
        title: Text(category.title,
            style: Theme.of(context).textTheme.titleMedium),
        subtitle: Text(
          category.subtitle,
          style: Theme.of(context)
              .textTheme
              .bodySmall
              ?.copyWith(color: ext.ink2),
        ),
        trailing: Icon(Icons.chevron_right, color: ext.ink3),
      ),
    );
  }
}
```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/care/care_screen_test.dart
# Expected: 4/4 PASS
```

- [ ] **Step 5 — Analyze + commit**

```bash
flutter analyze lib/features/care/
git add lib/features/care/ test/features/care/
git commit -m "feat: add CareScreen stub — 4 care category cards"
```

---

## Task 10: ForumScreen stub

**Files:**

- Create: `lib/features/forum/forum_screen.dart`
- Create: `test/features/forum/forum_screen_test.dart`

- [ ] **Step 1 — Write failing tests**

```dart
// test/features/forum/forum_screen_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/forum_screen.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: child,
    );

void main() {
  testWidgets('renders 3 sample posts', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.textContaining('Monstera'), findsOneWidget);
    expect(find.textContaining('succulent'), findsOneWidget);
    expect(find.textContaining('fern'), findsOneWidget);
  });

  testWidgets('ClayButton New Post present', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.byType(ClayButton), findsOneWidget);
    expect(find.text('+ New Post'), findsOneWidget);
  });

  testWidgets('coming soon notice present', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(find.textContaining('coming soon'), findsOneWidget);
  });

  testWidgets('no crashes on pump', (tester) async {
    await tester.pumpWidget(_wrap(const ForumScreen()));
    expect(tester.takeException(), isNull);
  });
}
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/forum/forum_screen_test.dart
# Expected: compilation error
```

- [ ] **Step 3 — Implement ForumScreen**

```dart
// lib/features/forum/forum_screen.dart
import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../shared/widgets/clay_button.dart';

class ForumScreen extends StatelessWidget {
  const ForumScreen({super.key});

  static const _posts = [
    _Post(
      author: 'Sarah G.',
      authorInitial: 'S',
      tag: 'Help',
      title: 'Why are my Monstera leaves turning yellow?',
      upvotes: 12,
      replies: 4,
    ),
    _Post(
      author: 'Mark B.',
      authorInitial: 'M',
      tag: 'Share',
      title: 'My succulent collection after 2 years 🌵',
      upvotes: 48,
      replies: 11,
    ),
    _Post(
      author: 'Leaf Lover',
      authorInitial: 'L',
      tag: 'ID',
      title: 'Can anyone identify this fern I found?',
      upvotes: 7,
      replies: 2,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    return Scaffold(
      appBar: AppBar(title: const Text('Community'), centerTitle: true),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: ext.padScreen),
          child: Column(
            children: [
              Expanded(
                child: ListView.separated(
                  padding: EdgeInsets.only(
                      top: ext.padScreen, bottom: ext.gapY),
                  itemCount: _posts.length,
                  separatorBuilder: (_, __) =>
                      SizedBox(height: ext.gapY),
                  itemBuilder: (context, i) =>
                      _PostCard(post: _posts[i], ext: ext),
                ),
              ),
              SizedBox(height: ext.gapY),
              ClayButton(
                label: '+ New Post',
                fullWidth: true,
                onPressed: () {},
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Live posting coming soon',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: ext.ink3),
                textAlign: TextAlign.center,
              ),
              SizedBox(height: ext.padScreen),
            ],
          ),
        ),
      ),
    );
  }
}

class _Post {
  const _Post({
    required this.author,
    required this.authorInitial,
    required this.tag,
    required this.title,
    required this.upvotes,
    required this.replies,
  });
  final String author;
  final String authorInitial;
  final String tag;
  final String title;
  final int upvotes;
  final int replies;
}

class _PostCard extends StatelessWidget {
  const _PostCard({required this.post, required this.ext});
  final _Post post;
  final GreenThumbExtension ext;

  Color _tagBg(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return switch (post.tag) {
      'Help'  => ext.berry.withValues(alpha: 0.12),
      'Share' => cs.primary.withValues(alpha: 0.12),
      _       => ext.sky.withValues(alpha: 0.12),
    };
  }

  Color _tagFg(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return switch (post.tag) {
      'Help'  => ext.berry,
      'Share' => cs.primary,
      _       => ext.sky,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(ext.padCard),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 16,
                  backgroundColor:
                      Theme.of(context).colorScheme.primaryContainer,
                  child: Text(
                    post.authorInitial,
                    style: TextStyle(
                      color: Theme.of(context)
                          .colorScheme
                          .onPrimaryContainer,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  post.author,
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: ext.ink2),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _tagBg(context),
                    borderRadius:
                        BorderRadius.circular(AppSpacing.rXs),
                  ),
                  child: Text(
                    post.tag,
                    style: TextStyle(
                      color: _tagFg(context),
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(post.title,
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            Row(
              children: [
                Icon(Icons.arrow_upward, size: 14, color: ext.ink3),
                const SizedBox(width: 2),
                Text('${post.upvotes}',
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: ext.ink3)),
                const SizedBox(width: AppSpacing.sm),
                Icon(Icons.chat_bubble_outline, size: 14, color: ext.ink3),
                const SizedBox(width: 2),
                Text('${post.replies}',
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: ext.ink3)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/forum/forum_screen_test.dart
# Expected: 4/4 PASS
```

- [ ] **Step 5 — Analyze + commit**

```bash
flutter analyze lib/features/forum/
git add lib/features/forum/ test/features/forum/
git commit -m "feat: add ForumScreen stub — 3 sample posts, ClayButton CTA"
```

---

## Task 11: CollectionScreen stub

**Files:**

- Create: `lib/features/collection/collection_screen.dart`
- Create: `test/features/collection/collection_screen_test.dart`

- [ ] **Step 1 — Write failing tests**

```dart
// test/features/collection/collection_screen_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/collection/collection_screen.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: child,
    );

void main() {
  testWidgets('renders 3 sample plant cards', (tester) async {
    await tester.pumpWidget(_wrap(const CollectionScreen()));
    expect(find.text('Monstera'), findsOneWidget);
    expect(find.text('Golden Barrel'), findsOneWidget);
    expect(find.text('Peace Lily'), findsOneWidget);
  });

  testWidgets('add card present', (tester) async {
    await tester.pumpWidget(_wrap(const CollectionScreen()));
    expect(find.text('Identify a plant'), findsOneWidget);
  });

  testWidgets('eyebrow count text present', (tester) async {
    await tester.pumpWidget(_wrap(const CollectionScreen()));
    expect(find.text('3 PLANTS IDENTIFIED'), findsOneWidget);
  });

  testWidgets('coming soon notice present', (tester) async {
    await tester.pumpWidget(_wrap(const CollectionScreen()));
    expect(find.textContaining('coming soon'), findsOneWidget);
  });
}
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/collection/collection_screen_test.dart
# Expected: compilation error
```

- [ ] **Step 3 — Implement CollectionScreen**

```dart
// lib/features/collection/collection_screen.dart
import 'package:flutter/material.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

class CollectionScreen extends StatelessWidget {
  const CollectionScreen({super.key});

  static const _plants = [
    _PlantEntry(commonName: 'Monstera', scientificName: 'Monstera deliciosa'),
    _PlantEntry(commonName: 'Golden Barrel',
        scientificName: 'Echinocactus grusonii'),
    _PlantEntry(commonName: 'Peace Lily',
        scientificName: 'Spathiphyllum wallisii'),
  ];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final ext = Theme.of(context).extension<GreenThumbExtension>()!;

    final eyebrowStyle = Theme.of(context).textTheme.labelSmall?.copyWith(
          letterSpacing: 0.06 * 11,
          color: ext.ink3,
        );

    return Scaffold(
      appBar: AppBar(title: const Text('My Collection'), centerTitle: true),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: EdgeInsets.all(ext.padScreen),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Text('${_plants.length} PLANTS IDENTIFIED',
                      style: eyebrowStyle),
                  SizedBox(height: ext.gapY),
                ]),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.symmetric(horizontal: ext.padScreen),
              sliver: SliverGrid(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisSpacing: ext.gapY,
                  crossAxisSpacing: ext.gapY,
                  childAspectRatio: 0.8,
                ),
                delegate: SliverChildListDelegate([
                  ..._plants.map((p) => _PlantCard(plant: p, ext: ext)),
                  _AddCard(ext: ext),
                ]),
              ),
            ),
            SliverPadding(
              padding: EdgeInsets.all(ext.padScreen),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
                  Text(
                    'Sync & history coming soon',
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: ext.ink3),
                    textAlign: TextAlign.center,
                  ),
                  SizedBox(height: ext.gapY),
                ]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlantEntry {
  const _PlantEntry(
      {required this.commonName, required this.scientificName});
  final String commonName;
  final String scientificName;
}

class _PlantCard extends StatelessWidget {
  const _PlantCard({required this.plant, required this.ext});
  final _PlantEntry plant;
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 100,
            color: cs.surfaceContainerLow,
            width: double.infinity,
            child: Center(
              child: Icon(Icons.eco,
                  size: 32,
                  color: cs.primary.withValues(alpha: 0.4)),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plant.commonName,
                  style: Theme.of(context)
                      .textTheme
                      .labelMedium
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
                Text(
                  plant.scientificName,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontFamily: 'GeistMono',
                        color: ext.ink2,
                      ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: ext.leaf,
                    borderRadius:
                        BorderRadius.circular(AppSpacing.rXs),
                  ),
                  child: Text(
                    '✓ ID\'d',
                    style: TextStyle(
                      color: cs.onSurface,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AddCard extends StatelessWidget {
  const _AddCard({required this.ext});
  final GreenThumbExtension ext;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppSpacing.rMd),
        border: Border.all(color: cs.outlineVariant, width: 2),
        color: cs.surfaceContainerLow,
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.add, color: ext.ink3, size: 28),
            const SizedBox(height: 4),
            Text(
              'Identify a plant',
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: ext.ink3),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4 — Run tests**

```bash
flutter test test/features/collection/collection_screen_test.dart
# Expected: 4/4 PASS
```

- [ ] **Step 5 — Analyze + commit**

```bash
flutter analyze lib/features/collection/
git add lib/features/collection/ test/features/collection/
git commit -m "feat: add CollectionScreen stub — 2-column grid, 3 sample plants"
```

---

## Task 12: Router — new routes + wire home feature cards

**Files:**

- Modify: `lib/core/routing/app_router.dart`
- Modify: `lib/features/home/home_page.dart`
- Modify: `test/features/home/home_page_test.dart`

- [ ] **Step 1 — Add failing navigation tests**

In `test/features/home/home_page_test.dart`, add:

```dart
testWidgets('Care card has onTap wired', (tester) async {
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      theme: AppTheme.build(
          AppPaletteChoice.loam, Brightness.light, AppDensity.cozy),
      home: const HomePage(),
    ),
  ));
  final careCard = tester.widget<FeatureCard>(find.byWidgetPredicate(
      (w) => w is FeatureCard && w.title == 'Care Instructions'));
  expect(careCard.onTap, isNotNull);
});
```

- [ ] **Step 2 — Run to confirm FAIL**

```bash
flutter test test/features/home/home_page_test.dart
# Expected: FAIL — Care card onTap is null
```

- [ ] **Step 3 — Add routes to AppRoutes**

In `lib/core/routing/app_router.dart`, add to `AppRoutes`:

```dart
static const care       = '/care';
static const forum      = '/forum';
static const collection = '/collection';
```

Add imports at top of file:

```dart
import '../features/care/care_screen.dart';
import '../features/forum/forum_screen.dart';
import '../features/collection/collection_screen.dart';
```

Add GoRoutes inside the `routes:` list (after the existing garden route):

```dart
GoRoute(
  path: AppRoutes.care,
  name: 'care',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const CareScreen()),
),
GoRoute(
  path: AppRoutes.forum,
  name: 'forum',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const ForumScreen()),
),
GoRoute(
  path: AppRoutes.collection,
  name: 'collection',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const CollectionScreen()),
),
```

- [ ] **Step 4 — Wire home_page.dart feature card onTaps**

In `lib/features/home/home_page.dart`, update `_buildFeaturesGrid` — replace all 4 `FeatureCard` calls with:

```dart
FeatureCard(
  icon: Icons.camera_alt,
  title: 'Instant Identification',
  description:
      'Snap a photo and instantly identify any plant with AI-powered recognition',
  type: FeatureType.camera,
  onTap: () => context.go(AppRoutes.camera),
),
FeatureCard(
  icon: Icons.book,
  title: 'Care Instructions',
  description:
      'Get personalized care tips for watering, sunlight, and maintenance',
  type: FeatureType.care,
  onTap: () => context.go(AppRoutes.care),
),
FeatureCard(
  icon: Icons.people,
  title: 'Community Forum',
  description:
      'Connect with plant lovers, share experiences, and get expert advice',
  type: FeatureType.community,
  onTap: () => context.go(AppRoutes.forum),
),
FeatureCard(
  icon: Icons.auto_awesome,
  title: 'Track Your Collection',
  description:
      'Build your personal plant library and track identification history',
  type: FeatureType.collection,
  onTap: () => context.go(AppRoutes.collection),
),
```

- [ ] **Step 5 — Run tests**

```bash
flutter test test/features/home/home_page_test.dart
flutter test
# Expected: all PASS
```

- [ ] **Step 6 — Analyze + commit**

```bash
flutter analyze lib/core/routing/ lib/features/home/
git add lib/core/routing/app_router.dart lib/features/home/home_page.dart \
        test/features/home/home_page_test.dart
git commit -m "feat: add /care /forum /collection routes, wire home feature cards"
```

---

## Task 13: Delete `app_colors.dart` + delete `gradient_button.dart`

**Files:**

- Delete: `lib/core/theme/app_colors.dart`
- Delete: `lib/shared/widgets/gradient_button.dart`
- Delete: `test/shared/widgets/gradient_button_test.dart` (if it exists)

- [ ] **Step 1 — Verify zero remaining references**

```bash
grep -r "app_colors\|AppColors" lib/
# Expected: no output

grep -r "gradient_button\|GradientButton" lib/
# Expected: no output
```

If either command produces output, fix the remaining references before proceeding.

- [ ] **Step 2 — Check test directory for old imports**

```bash
grep -r "app_colors\|AppColors\|GradientButton\|gradient_button" test/
# Expected: no output (or only in gradient_button_test.dart which we'll delete)
```

- [ ] **Step 3 — Delete files**

```bash
git rm lib/core/theme/app_colors.dart
git rm lib/shared/widgets/gradient_button.dart
# If gradient_button_test.dart exists:
git rm test/shared/widgets/gradient_button_test.dart 2>/dev/null || true
```

- [ ] **Step 4 — Run full test suite**

```bash
flutter test
# Expected: all tests PASS, zero compilation errors
```

- [ ] **Step 5 — Run analyzer**

```bash
flutter analyze
# Expected: No issues found!
```

- [ ] **Step 6 — Final commit**

```bash
git add -A
git commit -m "chore: delete app_colors.dart and gradient_button.dart — fully replaced by design tokens"
```

---

## Final Verification

- [ ] `grep -r "AppColors" lib/` → empty
- [ ] `flutter analyze` → No issues found!
- [ ] `flutter test` → all pass
- [ ] Launch on simulator, navigate to `/debug/theme-preview` — 24 palette combinations render correctly
- [ ] Switch palette to Forest in Settings — all screens update
- [ ] Switch density to Compact in Settings — padding shrinks on all screens
- [ ] Tap Care / Forum / Collection feature cards on Home — navigate to stub screens
- [ ] GrainOverlay visible on Splash and Home (Loam palette); absent on Camera, Results, Profile, Settings
