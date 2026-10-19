// The "Live updates" switch in Settings (live forum replies, slice 4): shown
// only to signed-in readers, since signed-out readers never get a socket.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/forum/live/live_updates_settings.dart';
import 'package:plant_community_mobile/features/settings/live_updates_tile.dart';
import 'package:plant_community_mobile/services/auth_service.dart';

import '../forum/support/forum_test_support.dart';

/// Updates state without touching FlutterSecureStorage, recording each call.
class _FakeLiveUpdatesSetting extends LiveUpdatesSetting {
  final List<bool> calls = [];

  @override
  bool build() => true;

  @override
  void setEnabled(bool on) {
    calls.add(on);
    state = on;
  }
}

void main() {
  late _FakeLiveUpdatesSetting setting;

  Widget wrap({required bool loggedIn}) {
    setting = _FakeLiveUpdatesSetting();
    return ProviderScope(
      overrides: [
        authServiceProvider.overrideWith(
          () => FakeAuthService(loggedIn: loggedIn),
        ),
        liveUpdatesSettingProvider.overrideWith(() => setting),
      ],
      child: const MaterialApp(home: Scaffold(body: LiveUpdatesTile())),
    );
  }

  testWidgets('hidden when signed out', (tester) async {
    await tester.pumpWidget(wrap(loggedIn: false));
    expect(find.text('Live updates'), findsNothing);
    expect(find.byType(Switch), findsNothing);
  });

  testWidgets('a "Live updates" switch, on by default, when signed in', (
    tester,
  ) async {
    await tester.pumpWidget(wrap(loggedIn: true));
    expect(find.text('Live updates'), findsOneWidget);
    expect(
      tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
      isTrue,
    );
  });

  testWidgets('toggling it calls setEnabled(false)', (tester) async {
    await tester.pumpWidget(wrap(loggedIn: true));
    await tester.tap(find.byType(SwitchListTile));
    await tester.pump();

    expect(setting.calls, [false]);
    expect(
      tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
      isFalse,
    );
  });

  testWidgets('the subtitle names this device', (tester) async {
    await tester.pumpWidget(wrap(loggedIn: true));
    expect(find.textContaining('on this device'), findsOneWidget);
  });
}
