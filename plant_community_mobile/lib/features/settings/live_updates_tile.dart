import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/green_thumb_extension.dart';
import '../../services/auth_service.dart';
import '../../shared/widgets/canopy_label.dart';
import '../forum/live/live_updates_settings.dart';

/// The FORUM section of Settings: the per-device "Live updates" switch.
/// Signed-out readers never get a socket, so the whole section is hidden
/// for them, label included.
class LiveUpdatesTile extends ConsumerWidget {
  const LiveUpdatesTile({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signedIn = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    if (!signedIn) return const SizedBox.shrink();
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final on = ref.watch(liveUpdatesSettingProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const CanopyLabel('FORUM'),
        SizedBox(height: ext.gapY),
        SwitchListTile(
          title: const Text('Live updates'),
          subtitle: const Text(
            'Show new replies, edits and deletes in an open topic as they '
            'happen, on this device. Off, pull down on a topic to check for '
            'new replies.',
          ),
          value: on,
          onChanged: (value) =>
              ref.read(liveUpdatesSettingProvider.notifier).setEnabled(value),
        ),
        SizedBox(height: ext.gapY * 2),
      ],
    );
  }
}
