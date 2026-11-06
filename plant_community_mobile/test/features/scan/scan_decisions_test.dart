import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/scan/scan_decisions.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

void main() {
  test('undecidedScansProvider is empty while signed out', () async {
    final container = ProviderContainer(
      overrides: [currentUserIdProvider.overrideWith((ref) => null)],
    );
    addTearDown(container.dispose);
    expect(await container.read(undecidedScansProvider.future), isEmpty);
  });
}
