import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/constants/app_spacing.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/shared/widgets/brand_mark.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_label.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_notice.dart';
import 'package:plant_community_mobile/shared/widgets/canopy_surfaces.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/shared/widgets/feature_card.dart';

/// Renders the Canopy primitives to real pixels, for eyeballing against the
/// web's `/debug/theme` page.
///
/// Widget tests that assert with `find.text` search the WIDGET TREE, not the
/// screen — which is how an opaque full-screen overlay once shipped with a
/// green suite (the grain PNG incident). A golden renders what a user sees.
///
/// OFF by default. Goldens are font- and platform-sensitive (they differ
/// between macOS and CI Linux), so this is a local review tool rather than a
/// gate — a skipped-by-default test cannot turn CI red on a font update.
/// Run it deliberately:
///
///     CANOPY_GOLDENS=1 flutter test test/core/theme/canopy_visual_golden_test.dart \
///       --update-goldens
/// Set `CANOPY_GOLDENS=1` to run. See the note above.
final bool _goldensEnabled = Platform.environment['CANOPY_GOLDENS'] == '1';

void main() {
  setUpAll(() async {
    // Without this every glyph renders as a box: the test environment ships
    // only the placeholder font, so a golden would prove nothing about type.
    TestWidgetsFlutterBinding.ensureInitialized();
    for (final (family, paths) in [
      ('BricolageGrotesque', ['assets/fonts/BricolageGrotesque-SemiBold.ttf']),
      (
        'Geist',
        [
          'assets/fonts/Geist-Regular.ttf',
          'assets/fonts/Geist-Medium.ttf',
          'assets/fonts/Geist-SemiBold.ttf',
        ],
      ),
      ('GeistMono', ['assets/fonts/GeistMono-Regular.ttf']),
      // The icon font ships inside the package; without it every Lucide glyph
      // renders as a box and the golden says nothing about the icon migration.
      // A font declared by a PACKAGE resolves as `packages/<pkg>/<family>`,
      // not the bare family name — registering 'Lucide' renders every glyph as
      // a box (which is exactly what the first golden showed).
      (
        'packages/lucide_icons_flutter/Lucide',
        [
          '${Platform.environment['HOME']}/.pub-cache/hosted/pub.dev/'
              'lucide_icons_flutter-3.1.19/assets/lucide.ttf',
        ],
      ),
    ]) {
      final loader = FontLoader(family);
      var loaded = false;
      for (final path in paths) {
        final file = File(path);
        if (!file.existsSync()) continue;
        loader.addFont(file.readAsBytes().then((b) => ByteData.view(b.buffer)));
        loaded = true;
      }
      if (loaded) await loader.load();
    }
  });

  Widget swatchPage(Brightness brightness, AppDensity density) {
    final theme = AppTheme.build(brightness, density);
    return MaterialApp(
      theme: theme,
      debugShowCheckedModeBanner: false,
      home: Builder(
        builder: (context) {
          final ext = context.canopy;
          return Scaffold(
            body: CanopyGround(
              child: SingleChildScrollView(
                padding: EdgeInsets.all(ext.padScreen),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const BrandLockup(markSize: 40, showTagline: true),
                    SizedBox(height: ext.gapY),
                    CanopyLabel('${brightness.name} · ${density.name}'),
                    SizedBox(height: ext.gapY),
                    Text(
                      'Discover the world of plants',
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    SizedBox(height: ext.gapY),
                    const FeatureCard(
                      icon: LucideIcons.camera,
                      title: 'Instant identification',
                      description: 'Snap a photo and name any plant',
                    ),
                    SizedBox(height: ext.gapY),
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: [
                        ClayButton(
                          label: 'Primary',
                          size: ClayButtonSize.small,
                          onPressed: () {},
                        ),
                        ClayButton(
                          label: 'Secondary',
                          size: ClayButtonSize.small,
                          variant: ClayButtonVariant.secondary,
                          onPressed: () {},
                        ),
                        ClayButton(
                          label: 'Outline',
                          size: ClayButtonSize.small,
                          variant: ClayButtonVariant.outline,
                          onPressed: () {},
                        ),
                        ClayButton(
                          label: 'Ghost',
                          size: ClayButtonSize.small,
                          variant: ClayButtonVariant.ghost,
                          onPressed: () {},
                        ),
                        const ClayButton(
                          label: 'Disabled',
                          size: ClayButtonSize.small,
                        ),
                      ],
                    ),
                    SizedBox(height: ext.gapY),
                    const TextField(
                      decoration: InputDecoration(
                        labelText: 'Plant name',
                        hintText: 'e.g. Monstera',
                      ),
                    ),
                    SizedBox(height: ext.gapY),
                    Wrap(
                      spacing: AppSpacing.sm,
                      children: const [
                        Chip(label: Text('Tropical')),
                        Chip(label: Text('Low light')),
                        Chip(label: Text('Healthy')),
                      ],
                    ),
                    SizedBox(height: ext.gapY),
                    // The four *Container roles reach the screen through these:
                    // a Material-derived colour shows up immediately as a hue
                    // that belongs to no Canopy ramp.
                    const CanopyNotice(
                      message: 'That email is already registered.',
                      tone: CanopyNoticeTone.error,
                    ),
                    SizedBox(height: ext.gapY),
                    const CanopyNotice(
                      message: 'Your reply is awaiting moderation.',
                      tone: CanopyNoticeTone.warning,
                    ),
                    SizedBox(height: ext.gapY),
                    CanopyCard(
                      accentBorder: Theme.of(context).colorScheme.secondary,
                      child: Text(
                        'Accepted answer — the accent border a solution gets.',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  for (final (brightness, density) in [
    (Brightness.dark, AppDensity.cozy),
    (Brightness.light, AppDensity.cozy),
    (Brightness.dark, AppDensity.compact),
    (Brightness.light, AppDensity.comfortable),
  ]) {
    testWidgets('canopy ${brightness.name}/${density.name}', (tester) async {
      tester.view.physicalSize = const Size(420 * 2, 900 * 2);
      tester.view.devicePixelRatio = 2.0;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(swatchPage(brightness, density));
      await tester.pumpAndSettle();

      await expectLater(
        find.byType(MaterialApp),
        matchesGoldenFile(
          'goldens/canopy_${brightness.name}_${density.name}.png',
        ),
      );
    }, skip: !_goldensEnabled);
  }
}
