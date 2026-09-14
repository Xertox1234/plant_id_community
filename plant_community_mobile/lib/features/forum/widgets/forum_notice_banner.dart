import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../shared/widgets/canopy_notice.dart';

/// An inline info banner used for the "awaiting moderation" (notify-and-return)
/// notice and similar transient messages. Announced to screen readers via a
/// polite live region.
class ForumNoticeBanner extends StatelessWidget {
  const ForumNoticeBanner({
    super.key,
    required this.message,
    this.icon = LucideIcons.hourglass,
  });

  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) => CanopyNotice(
    message: message,
    tone: CanopyNoticeTone.warning,
    icon: icon,
  );
}
