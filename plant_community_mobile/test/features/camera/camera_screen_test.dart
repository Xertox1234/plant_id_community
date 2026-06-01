import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/camera/camera_screen.dart';
import 'package:plant_community_mobile/shared/widgets/clay_button.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/app_palettes.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';

// CameraScreen is a ConsumerStatefulWidget, so it needs a ProviderScope
// ancestor. The placeholder state (no image selected) does not touch any
// provider at build time, so a plain MaterialApp under ProviderScope is enough.
Widget _wrap(Widget child) => ProviderScope(
  child: MaterialApp(
    theme: AppTheme.build(
      AppPaletteChoice.loam,
      Brightness.light,
      AppDensity.cozy,
    ),
    home: child,
  ),
);

void main() {
  testWidgets('no ClayButton in placeholder state (no image selected)', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(const CameraScreen()));
    // The Identify ClayButton only appears once an image is selected.
    expect(find.byType(ClayButton), findsNothing);
  });

  testWidgets('renders Take Photo and Upload from Gallery actions', (
    tester,
  ) async {
    await tester.pumpWidget(_wrap(const CameraScreen()));
    expect(find.text('Take Photo'), findsOneWidget);
    expect(find.text('Upload from Gallery'), findsOneWidget);
  });

  testWidgets('no crash on pump', (tester) async {
    await tester.pumpWidget(_wrap(const CameraScreen()));
    expect(tester.takeException(), isNull);
  });
}
