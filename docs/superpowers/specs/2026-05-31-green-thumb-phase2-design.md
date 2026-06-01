# Green Thumb Phase 2 — Screen Application Design

## Goal

Apply the Green Thumb design system (built in Phase 1) to every screen and widget in the Flutter mobile app. Replace all `AppColors` references with `GreenThumbExtension`/`ColorScheme` tokens, adopt density-responsive padding, apply `GrainOverlay` selectively, and add three new stub screens (Care, Forum, Collection). Delete `app_colors.dart` when all references are gone.

## Scope

**Modify (existing):**

- `lib/shared/widgets/gradient_button.dart` → replaced by `clay_button.dart`
- `lib/shared/widgets/feature_card.dart`
- `lib/shared/widgets/loading_indicator.dart`
- `lib/features/splash/splash_screen.dart`
- `lib/features/home/home_page.dart`
- `lib/features/camera/camera_screen.dart`
- `lib/features/results/results_screen.dart`
- `lib/features/profile/profile_screen.dart`
- `lib/core/routing/app_router.dart`

**Create (new):**

- `lib/shared/widgets/clay_button.dart`
- `lib/features/settings/settings_screen.dart` (extracted from `app_router.dart`)
- `lib/features/care/care_screen.dart`
- `lib/features/forum/forum_screen.dart`
- `lib/features/collection/collection_screen.dart`

**Delete:**

- `lib/core/theme/app_colors.dart`
- `lib/shared/widgets/gradient_button.dart`

**Out of scope:** `lib/features/garden/` models, auth screens (login/register), backend, web frontend.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary CTA | `ext.clay` fill, `ext.onClay` text, `rPill` | Warm terracotta — distinct from primary, matches Loam palette character |
| Secondary action | `colorScheme.primary` fill, `colorScheme.onPrimary` text, `rPill` | Moss — consistent with M3 primary role |
| Gradient text (ShaderMask) | Removed | Bricolage Grotesque italic carries sufficient personality |
| GrainOverlay placement | Splash + Home `Scaffold.body` only | Camera/Results need clean image surfaces; Profile/Settings are functional |
| Gradient background (Splash) | Replaced with solid `colorScheme.surface` | Loam's parchment surface is the identity; gradient was generic |
| Feature card accent colours | camera→primary, care→sky, community→berry, collection→tertiary | Semantic — sky=water, berry=social, tertiary(honey)=collection |
| New stub screens | Care, Forum, Collection — real layouts, sample data, "coming soon" footnote | User-requested; wire-up deferred to a later phase |
| Settings screen | Extracted to own file + palette/density controls added | Completes Phase 1 PaletteNotifier integration |
| New routes | `/care`, `/forum`, `/collection` added to `AppRoutes` | Home feature cards navigate to them in Task 11 |

---

## Token Mapping

| Old (`AppColors.*`) | New token | Context |
|---------------------|-----------|---------|
| `green600` (primary CTA) | `ext.clay` | ClayButton primary, Identify button |
| `green500`–`green700` (brand green) | `colorScheme.primary` | Logo circle, progress bar fill, Take Photo button |
| `green100` / `green900.withValues(alpha:0.3)` | `colorScheme.surfaceContainerLow` | Outer hero ring, care item icon bg |
| `green400` / `green700` (text) | `ext.leaf` | "Identified" badge bg, confidence indicator |
| `green400` / `green700` (care icons) | `ext.statusOk` | Care instruction icon colour |
| `blue600` | `ext.sky` | Care/water icon, care card header |
| `purple500` / `purple600` | `ext.berry` | Community feature card accent |
| `amber500` / `amber600` | `colorScheme.tertiary` | Collection feature card accent |
| `lightDestructive` | `colorScheme.error` | Error snackbar, logout button |
| `lightCard` / `darkCard` | `colorScheme.surface` | Card/placeholder backgrounds |
| `green950`, `emerald950`, `green50`, `emerald100` (gradients) | `colorScheme.surface` | Splash background (solid, no gradient) |
| gradient text colours | `colorScheme.onSurface` | Titles (Bricolage italic replaces ShaderMask) |
| `green500.withValues(alpha:0.3)` (shadow glow) | `ext.shadow2` | Logo circle shadow |
| `green700`/`green800` (splash/highlight) | `colorScheme.primary` | Consistent with primary role |

All hardcoded padding values (`16`, `24`, etc. used as screen/card padding) → `ext.padScreen` / `ext.padCard` / `ext.gapY`. Structural spacing constants (`AppSpacing.sm`, `AppSpacing.xl`, etc.) remain for non-density-sensitive gaps.

---

## Shared Widgets

### ClayButton (`lib/shared/widgets/clay_button.dart`)

Replaces `GradientButton` entirely. `GradientButton` file is deleted.

```dart
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
}
```

**Sizing:**
| Size | Vertical padding | Horizontal padding | Font size |
|------|-----------------|-------------------|-----------|
| small | `AppSpacing.sm` | `AppSpacing.md` | 14px |
| medium | `AppSpacing.md` | `AppSpacing.lg` | 16px |
| large | `AppSpacing.lg` | `AppSpacing.xl` | 16px |

**Variant colours (from `GreenThumbExtension`):**

- `primary`: bg=`ext.clay`, fg=`ext.onClay`, shadow=`ext.shadow1`
- `secondary`: bg=`colorScheme.primary`, fg=`colorScheme.onPrimary`, shadow=`ext.shadow1`
- `outline`: bg=transparent, border=`colorScheme.primary`, fg=`colorScheme.primary`

**Shape:** `BorderRadius.circular(AppSpacing.rPill)` on all variants.

**Disabled state:** `colorScheme.surfaceContainerHighest` bg, `colorScheme.onSurface.withValues(alpha: 0.38)` fg, no shadow.

**Loading state:** replace icon/label with `SizedBox(20×20, CircularProgressIndicator(strokeWidth:2, color: fg))`.

**Tests** (`test/shared/widgets/clay_button_test.dart`):

- renders label
- primary variant uses clay background (check `Container` decoration color)
- secondary variant uses colorScheme.primary
- outline variant has transparent background + border
- disabled state: onPressed is null, bg is grey
- fullWidth SizedBox wraps when true
- icon renders when provided

### FeatureCard (`lib/shared/widgets/feature_card.dart`)

Remove `AppColors` import. Update `FeatureCardColors.getIconColor`:

```dart
static Color getIconColor(BuildContext context, FeatureType type) {
  final cs = Theme.of(context).colorScheme;
  final ext = Theme.of(context).extension<GreenThumbExtension>()!;
  return switch (type) {
    FeatureType.camera    => cs.primary,
    FeatureType.care      => ext.sky,
    FeatureType.community => ext.berry,
    FeatureType.collection => cs.tertiary,
  };
}
```

Card elevation: replace `AppSpacing.elevationSM` with `BoxDecoration(boxShadow: ext.shadow1)` — use `Material(elevation:0)` + `Container(decoration: BoxDecoration(color: cs.surface, borderRadius: ..., boxShadow: ext.shadow1))`.

Padding: `EdgeInsets.all(ext.padCard)`.

**Tests:** update existing tests — confirm no `AppColors` reference, confirm sky/berry/tertiary colours.

### LoadingIndicator (`lib/shared/widgets/loading_indicator.dart`)

Single change: `AppColors.green600` → `Theme.of(context).colorScheme.primary`.

---

## Screen Specs

### SplashScreen (`lib/features/splash/splash_screen.dart`)

**Remove:** `AppColors` import, `ShaderMask` gradient text, `LinearGradient` background, all `AppColors.*` colour literals.

**Background:** Solid `colorScheme.surface` — no gradient.

**GrainOverlay:** Wrap `Scaffold.body` content column in `GrainOverlay(child: ...)`.

**Logo circle:**

- Outer ring removed (was `green100`/`green900` gradient) — logo sits directly on surface
- Circle: `colorScheme.primary` fill, `BoxDecoration(shape: BoxShape.circle, color: cs.primary, boxShadow: ext.shadow2)`
- Icon: `Icons.eco`, size 48, `Colors.white`

**App name:** `Theme.of(context).textTheme.displayLarge?.copyWith(fontSize: 48)` — Bricolage Grotesque italic, size boosted to 48px on the splash (the home title uses the default 32px). Colour: `colorScheme.onSurface`. No `ShaderMask`.

**Tagline ("Discover Nature's Secrets"):**

```dart
Text(
  'DISCOVER NATURE\'S SECRETS',
  style: Theme.of(context).textTheme.labelSmall?.copyWith(
    letterSpacing: 0.06 * 11,
    color: ext.ink3,
  ),
)
```

(maps to `AppTypography.eyebrow` — all-caps Geist, `ext.ink3`)

**Progress bar:**

- `backgroundColor`: `colorScheme.surfaceContainerLow`
- `valueColor`: `colorScheme.primary`
- Wrapped in `ClipRRect(borderRadius: BorderRadius.circular(AppSpacing.rPill))`

**Vertical spacing:** replace `AppSpacing.xl` / `AppSpacing.xl2` gaps with `SizedBox(height: ext.gapY * 2)` and `SizedBox(height: ext.gapY)` where appropriate.

**Tests:** existing animation/navigation tests unchanged. Add: confirms no `AppColors` import, `GrainOverlay` present in widget tree.

### HomePage (`lib/features/home/home_page.dart`)

**Remove:** `AppColors` import, `ShaderMask` on title.

**GrainOverlay:** Wrap `SingleChildScrollView` content in `GrainOverlay(child: ...)`.

**Screen padding:** `EdgeInsets.symmetric(horizontal: ext.padScreen, vertical: ext.padScreen * 2)`.

**Hero section:**

- Eyebrow label above title:

  ```dart
  Text(
    'PLANT IDENTIFICATION',
    style: Theme.of(context).textTheme.labelSmall?.copyWith(
      letterSpacing: 0.06 * 11,
      color: ext.ink3,
    ),
  )
  ```

- Outer circle: `colorScheme.surfaceContainerLow` bg, 128px diameter
- Inner circle: `colorScheme.primary` bg, 96px, `BoxDecoration(boxShadow: ext.shadow2)`
- Title: `Theme.of(context).textTheme.displayLarge` (Bricolage italic), `colorScheme.onSurface` — no `ShaderMask`
- Description: `Theme.of(context).textTheme.bodyMedium?.copyWith(color: ext.ink2, height: 1.5)`

**Feature cards section:** gap between cards = `SizedBox(height: ext.gapY)`.

**CTA:** Replace `GradientButton` with `ClayButton(label:'Get Started', icon:Icons.arrow_forward, fullWidth:true, onPressed:...)`.

**FAB (Settings):** no colour changes needed — uses `colorScheme.primaryContainer` from M3 theme.

**Tests:** existing tests unchanged. Add: `ClayButton` present, `GrainOverlay` present, no `AppColors` import.

### CameraScreen (`lib/features/camera/camera_screen.dart`)

**Remove:** `AppColors` import, `AppColors.*` colour literals.

**No GrainOverlay.**

**Screen padding:** `EdgeInsets.all(ext.padScreen)`.

**Image card:**

- `BorderRadius.circular(AppSpacing.rLg)` (was `Clip.antiAlias` on default Card)
- Explicit `BoxDecoration(boxShadow: ext.shadow2)` on card container

**Placeholder container:**

- `color: colorScheme.surfaceContainerLow` (replaces `AppColors.lightCard`/`darkCard`)
- Icon colour: `colorScheme.onSurface.withValues(alpha: 0.4)`

**Buttons:**

- Take Photo: `ElevatedButton.icon` — uses `colorScheme.primary` via M3 theme (no explicit color override needed)
- Upload from Gallery: `OutlinedButton.icon` — uses `colorScheme.primary` via M3 theme
- Identify Plant: `ClayButton(variant: ClayButtonVariant.primary, label: 'Identify Plant', icon: Icons.search, fullWidth: true)`

**Error snackbar:** `backgroundColor: colorScheme.error` (replaces `AppColors.lightDestructive`).

**Tests:** existing tests unchanged. Add: `ClayButton` present when image selected, no `AppColors` import.

### ResultsScreen (`lib/features/results/results_screen.dart`)

**Remove:** `AppColors` import, all `AppColors.*` colour literals.

**No GrainOverlay.**

**Screen padding:** `EdgeInsets.all(ext.padScreen)`.

**Plant image card:**

- `BorderRadius.circular(AppSpacing.rLg)`, `BoxDecoration(boxShadow: ext.shadow2)`

**"Identified" badge:**

- `color: ext.leaf` (replaces `AppColors.green600`)
- Text colour: `colorScheme.onSurface` (dark ink — sufficient contrast on lime-green leaf)
- `BorderRadius.circular(AppSpacing.rXs)`

**Plant info card:** `EdgeInsets.all(ext.padCard)`.

- Common name: `Theme.of(context).textTheme.headlineMedium` (Bricolage italic, maps to h2)
- Scientific name:

  ```dart
  Text(
    plant.scientificName,
    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
      fontFamily: 'GeistMono',
      fontStyle: FontStyle.italic,
      color: ext.ink2,
    ),
  )
  ```

- Description: `bodyMedium` with `color: ext.ink2, height: 1.5`

**Care instructions card:** `EdgeInsets.all(ext.padCard)`.

- Header icon (`Icons.water_drop`): `color: ext.sky` (replaces `AppColors.blue600`)
- Care item icon circle: bg=`ext.statusOk.withValues(alpha: 0.12)`, icon=`ext.statusOk`

**Timestamp:** `Theme.of(context).textTheme.bodySmall?.copyWith(color: ext.ink3)`

**Image placeholder:** `color: colorScheme.surfaceContainerLow` (replaces `AppColors.lightCard`)

**Image loading placeholder** (`CachedNetworkImage`): `color: colorScheme.surfaceContainerLow` (replaces `AppColors.green100`)

**Tests:** existing tests unchanged. Add: `ext.leaf` on badge, `ext.sky` on care header, no `AppColors` import.

### ProfileScreen (`lib/features/profile/profile_screen.dart`)

No `AppColors` import currently — token-level changes only.

**Screen/card padding:** replace all hardcoded `16` and `24` pixel values with `ext.padScreen` and `ext.padCard`.

**Section gap:** `SizedBox(height: ext.gapY * 2)` between major sections.

**Profile header card:**

- Display name: `Theme.of(context).textTheme.headlineMedium` (Bricolage italic h2)
- Username: eyebrow style — `textTheme.labelSmall?.copyWith(letterSpacing: 0.06*11, color: ext.ink3)`
- Email: `textTheme.bodySmall?.copyWith(color: ext.ink2)`

**Stat values:** `Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)`

**Stat labels:** `textTheme.bodySmall?.copyWith(color: ext.ink3)`

**Section headings ("Profile Details", "Settings"):** eyebrow style matching above.

**Inline error state icon** (the `profileAsync.when(error:...)` branch inside `ProfileScreen`): `color: colorScheme.error` (replaces hardcoded `Colors.red`). This is not `ErrorScreen` — it is the error widget rendered within the profile body when the profile load fails.

**Stat card spacing:** `const SizedBox(width: 12)` → `SizedBox(width: ext.gapY)`.

**Tests:** no functional changes — add: correct padding values via ext tokens.

### SettingsScreen — extract + expand

**Extract** `SettingsScreen`, `_PlaceholderScreen`, and `ErrorScreen` from `app_router.dart` into:

- `lib/features/settings/settings_screen.dart` — `SettingsScreen`
- `lib/core/routing/error_screen.dart` — `ErrorScreen`
- `lib/core/routing/placeholder_screen.dart` — `_PlaceholderScreen` (rename to `PlaceholderScreen`, drop private prefix since it moves to its own file)

**SettingsScreen additions:**

```text
Appearance section:
  - Dark/Light/System toggle (existing SegmentedButton, keep as-is)

Palette section (new):
  - Section heading: eyebrow style
  - `Wrap(spacing: AppSpacing.sm)` of 4 tappable colour swatches (Loam / Garden / Forest / Heritage)
  - Each swatch: `InkWell` → `Container(padding: EdgeInsets.symmetric(horizontal:12, vertical:8), decoration: BoxDecoration(color: paletteColor, borderRadius: rSm, border: isSelected ? Border.all(color: colorScheme.primary, width:2) : null))`
  - Selected swatch: 2px primary border + `fontWeight: FontWeight.bold`
  - Tapping calls: `ref.read(paletteProvider.notifier).setPalette(choice)`

Density section (new):
  - Section heading: eyebrow style
  - SegmentedButton<AppDensity> with 3 segments (Comfortable / Cozy / Compact)
  - onChange calls: ref.read(paletteProvider.notifier).setDensity(density)

Debug section (kDebugMode only, existing):
  - ThemePreview link (already exists, keep)
```

**Screen padding:** `ext.padScreen`.

**Section title style:** eyebrow — `textTheme.labelSmall?.copyWith(letterSpacing: 0.06*11, color: ext.ink3)`.

**Tests:**

- Palette swatches render (4 items)
- Tapping Loam swatch calls `setPalette(AppPaletteChoice.loam)`
- Density SegmentedButton renders
- Changing density calls `setDensity`
- ThemePreview link hidden in non-debug mode (assert `kDebugMode` guard)

---

## New Stub Screens

### CareScreen (`lib/features/care/care_screen.dart`)

**Route:** `AppRoutes.care = '/care'`

**Layout:**

```text
Scaffold
  AppBar: title 'Plant Care'
  SafeArea > SingleChildScrollView(padding: ext.padScreen)
    Column
      eyebrow label: 'CARE GUIDES'
      SizedBox(height: ext.gapY)
      Text('Keep your plants happy', style: textTheme.headlineMedium)  // h2, Bricolage italic
      SizedBox(height: ext.gapY)
      Text(description, style: bodyMedium, color: ext.ink2)
      SizedBox(height: ext.gapY * 2)
      _CareCategory × 4  (Watering, Sunlight, Soil & Fertilising, Temperature)
      SizedBox(height: ext.gapY * 2)
      Text('Full care guides coming soon', style: bodySmall, color: ext.ink3, textAlign: center)
```

**`_CareCategory` card:**

```dart
Card(  // rMd from theme, shadow1
  child: ListTile(
    contentPadding: EdgeInsets.all(ext.padCard),
    leading: Container(
      padding: EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.rSm),
      ),
      child: Icon(icon, color: accentColor, size: 24),
    ),
    title: Text(title, style: textTheme.titleMedium),
    subtitle: Text(subtitle, style: textTheme.bodySmall?.copyWith(color: ext.ink2)),
    trailing: Icon(Icons.chevron_right, color: ext.ink3),
  ),
)
```

**Accent colours per category:**
| Category | Icon | Accent |
|----------|------|--------|
| Watering | `Icons.water_drop` | `ext.sky` |
| Sunlight | `Icons.wb_sunny` | `colorScheme.tertiary` |
| Soil & Fertilising | `Icons.grass` | `colorScheme.primary` |
| Temperature | `Icons.thermostat` | `ext.clay` |

**Tests:** 4 category cards render, eyebrow text present, "coming soon" text present.

### ForumScreen (`lib/features/forum/forum_screen.dart`)

**Route:** `AppRoutes.forum = '/forum'`

**Layout:**

```text
Scaffold
  AppBar: title 'Community'
  SafeArea > Padding(horizontal: ext.padScreen)
    Column
      Expanded > ListView(
          padding: EdgeInsets.only(top: ext.padScreen, bottom: ext.gapY))
        _ForumPost × 3 (sample data, hardcoded)
      SizedBox(height: ext.gapY)
      ClayButton('+ New Post', fullWidth: true, variant: primary)
      SizedBox(height: AppSpacing.xs)
      Text('Live posting coming soon', style: bodySmall, color: ext.ink3, textAlign: center)
      SizedBox(height: ext.padScreen)
```

**`_ForumPost` item:**

```dart
Card(  // rMd, shadow1
  child: Padding(
    padding: EdgeInsets.all(ext.padCard),
    child: Column(
      children: [
        Row(
          children: [
            CircleAvatar(  // initial letter, radius 16, bg: colorScheme.primaryContainer
            ),
            SizedBox(width: AppSpacing.sm),
            Text(username, style: bodySmall, color: ext.ink2),
            Spacer(),
            _TagPill(tag, color: tagColor),  // rXs, tinted bg
          ],
        ),
        SizedBox(height: AppSpacing.xs),
        Text(title, style: titleMedium),
        SizedBox(height: AppSpacing.xs),
        Row(
          children: [
            Icon(Icons.arrow_upward, size:14, color: ext.ink3),
            Text(upvotes, style: bodySmall, color: ext.ink3),
            SizedBox(width: AppSpacing.sm),
            Icon(Icons.chat_bubble_outline, size:14, color: ext.ink3),
            Text(replies, style: bodySmall, color: ext.ink3),
          ],
        ),
      ],
    ),
  ),
)
```

**Sample posts (hardcoded):**
| Author | Tag | Title | Upvotes | Replies |
|--------|-----|-------|---------|---------|
| Sarah G. | Help | "Why are my Monstera leaves turning yellow?" | 12 | 4 |
| Mark B. | Share | "My succulent collection after 2 years 🌵" | 48 | 11 |
| Leaf Lover | ID | "Can anyone identify this fern I found?" | 7 | 2 |

**Tag colour mapping:**

- Help → `ext.berry.withValues(alpha:0.12)` bg, `ext.berry` text
- Share → `colorScheme.primary.withValues(alpha:0.12)` bg, `colorScheme.primary` text
- ID → `ext.sky.withValues(alpha:0.12)` bg, `ext.sky` text

**Tests:** 3 post items render, ClayButton present, "coming soon" text present.

### CollectionScreen (`lib/features/collection/collection_screen.dart`)

**Route:** `AppRoutes.collection = '/collection'`

**Layout:**

```text
Scaffold
  AppBar: title 'My Collection'
  SafeArea > CustomScrollView
    SliverPadding(padding: ext.padScreen)
      SliverToBoxAdapter
        eyebrow: '3 PLANTS IDENTIFIED'
        SizedBox(height: ext.gapY)
      SliverGrid(
          gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: ext.gapY,
            crossAxisSpacing: ext.gapY,
            childAspectRatio: 0.8,
          ),
          delegate: SliverChildListDelegate([
            _PlantCard × 3 (sample data),
            _AddCard (outlined border, + icon, 'Identify a plant'),
          ]))
    SliverToBoxAdapter
      Text('Sync & history coming soon', style: bodySmall, color: ext.ink3, textAlign: center)
      SizedBox(height: ext.gapY)
```

**`_PlantCard`:**

```dart
Card(  // rMd, shadow1, clipBehavior: antiAlias
  child: Column(
    children: [
      Container(  // image placeholder
        height: 100,
        color: colorScheme.surfaceContainerLow,
        child: Center(child: Icon(Icons.eco, size:32, color: colorScheme.primary.withValues(alpha:0.4))),
      ),
      Padding(
        padding: EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(commonName, style: textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w600)),
            Text(scientificName, style: textTheme.bodySmall?.copyWith(fontFamily:'GeistMono', color: ext.ink2)),
            SizedBox(height: AppSpacing.xs),
            _IdentifiedBadge(),  // ext.leaf bg, colorScheme.surface text, rXs
          ],
        ),
      ),
    ],
  ),
)
```

**`_AddCard`:**

```dart
Container(
  decoration: BoxDecoration(
    borderRadius: BorderRadius.circular(AppSpacing.rMd),
    border: Border.all(color: colorScheme.outlineVariant, width: 2),
    color: colorScheme.surfaceContainerLow,
  ),
  child: Center(
    child: Column(children: [
      Icon(Icons.add, color: ext.ink3),
      Text('Identify a plant', style: textTheme.bodySmall?.copyWith(color: ext.ink3)),
    ]),
  ),
)
```

**Sample data (hardcoded):**
| Common name | Scientific name |
|-------------|----------------|
| Monstera | Monstera deliciosa |
| Golden Barrel | Echinocactus grusonii |
| Peace Lily | Spathiphyllum wallisii |

**Tests:** 3 plant cards render, `_AddCard` present, eyebrow count text present, "coming soon" text present.

---

## Router Changes (`lib/core/routing/app_router.dart`)

**Add to `AppRoutes`:**

```dart
static const care = '/care';
static const forum = '/forum';
static const collection = '/collection';
```

**Add GoRoutes:**

```dart
GoRoute(path: AppRoutes.care, name: 'care',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const CareScreen())),
GoRoute(path: AppRoutes.forum, name: 'forum',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const ForumScreen())),
GoRoute(path: AppRoutes.collection, name: 'collection',
  pageBuilder: (context, state) => _buildPageWithTransition(
    context: context, state: state, child: const CollectionScreen())),
```

**Replace** `SettingsScreen` inline class with import of `lib/features/settings/settings_screen.dart`.

**Replace** `ErrorScreen` inline class with import of `lib/core/routing/error_screen.dart`.

**Replace** `_PlaceholderScreen` inline class with import of `lib/core/routing/placeholder_screen.dart`.

> `PlaceholderScreen` is still used after Phase 2 by the `/login`, `/register`, and `/garden` routes, which remain unimplemented. Do not delete it.

---

## Task 11: Wire Home Feature Cards

Update `home_page.dart` — add `onTap` to each `FeatureCard`:

```dart
FeatureCard(
  icon: Icons.camera_alt,
  title: 'Instant Identification',
  description: '...',
  type: FeatureType.camera,
  onTap: () => context.go(AppRoutes.camera),
),
FeatureCard(
  icon: Icons.book,
  title: 'Care Instructions',
  description: '...',
  type: FeatureType.care,
  onTap: () => context.go(AppRoutes.care),
),
FeatureCard(
  icon: Icons.people,
  title: 'Community Forum',
  description: '...',
  type: FeatureType.community,
  onTap: () => context.go(AppRoutes.forum),
),
FeatureCard(
  icon: Icons.auto_awesome,
  title: 'Track Your Collection',
  description: '...',
  type: FeatureType.collection,
  onTap: () => context.go(AppRoutes.collection),
),
```

---

## Task 12: Delete `app_colors.dart`

After all 11 prior tasks pass `flutter analyze` with zero issues:

1. `grep -r "app_colors" lib/` — must return empty
2. `git rm lib/core/theme/app_colors.dart`
3. Remove `app_colors.dart` from any `test/` imports
4. `flutter test && flutter analyze`

---

## Testing Strategy

Each task commits with passing tests. No task leaves a red test suite.

- **ClayButton**: widget tests (7 cases listed above)
- **Shared widget updates**: update existing tests to remove `AppColors` mocks, confirm new token usage
- **Screen redesigns**: existing golden/widget tests updated; at minimum confirm `AppColors` import absent and key new widgets present
- **New stub screens**: 3–4 widget tests each (content renders, key widgets present, no crashes)
- **Router changes**: existing router tests updated for new routes
- **Delete task**: `flutter analyze` clean, `flutter test` green — this is the gate

---

## Success Criteria

1. `grep -r "AppColors" lib/` returns zero matches
2. `lib/core/theme/app_colors.dart` deleted
3. `flutter analyze` — zero issues
4. All tests pass (`flutter test`)
5. `ThemePreviewScreen` at `/debug/theme-preview` shows all 24 palette combinations correctly styled
6. Home page feature cards navigate to all three new stub screens
7. Settings screen shows palette switcher and density controls, both wired to `PaletteNotifier`
8. GrainOverlay visible on Splash and Home when Loam palette active; absent on Camera, Results, Profile, Settings
