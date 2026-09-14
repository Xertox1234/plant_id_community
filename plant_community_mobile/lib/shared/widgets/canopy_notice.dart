import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/green_thumb_extension.dart';

/// The tone of a [CanopyNotice] — which semantic colour tints it.
enum CanopyNoticeTone { info, success, warning, error }

/// An inline status banner: error, warning, success or info.
///
/// This is the Flutter counterpart of the web's one notice recipe, which is
/// identical wherever it appears (`ForumErrorState`, `SaveDiagnosisModal`,
/// `ProfilePage`, `GoogleSignInButton`):
///
/// ```
/// bg-<tone>/10 border border-<tone>/30 text-ink px-4 py-3 rounded-md
/// ```
///
/// A 10% tint of the semantic colour, a 30% border of the same, and **ink**
/// text — never an "on-container" foreground. This exists because Material 3
/// derives `errorContainer` / `tertiaryContainer` and their `on*` pairs
/// algorithmically from the seed, and those derived colours are not Canopy
/// colours: the auth error banner was rendering in a mauve-pink Material
/// default that appears nowhere in the design system.
class CanopyNotice extends StatelessWidget {
  const CanopyNotice({
    super.key,
    required this.message,
    this.tone = CanopyNoticeTone.info,
    this.icon,
    this.liveRegion = true,
  });

  final String message;
  final CanopyNoticeTone tone;

  /// Defaults to the tone's glyph. The web pairs the same icon with each tone.
  final IconData? icon;

  /// Announce the message politely when it appears. On for the transient
  /// notices this replaced; turn it off for a banner that is part of the
  /// static page furniture and would otherwise be announced on every build.
  final bool liveRegion;

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final cs = Theme.of(context).colorScheme;
    final (Color accent, IconData glyph) = switch (tone) {
      CanopyNoticeTone.info => (ext.sky, LucideIcons.info),
      CanopyNoticeTone.success => (ext.statusOk, LucideIcons.circleCheck),
      CanopyNoticeTone.warning => (ext.statusWarn, LucideIcons.hourglass),
      CanopyNoticeTone.error => (cs.error, LucideIcons.circleAlert),
    };

    return Semantics(
      liveRegion: liveRegion,
      container: true,
      child: Container(
        width: double.infinity,
        // px-4 py-3 — the web's notice padding, not the density's card padding:
        // a notice keeps the same weight however dense the surrounding layout.
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: accent.withValues(alpha: 0.10),
          border: Border.all(color: accent.withValues(alpha: 0.30)),
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon ?? glyph, size: AppSpacing.iconMD, color: accent),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              // `text-ink`: the message reads as body copy, tinted only by the
              // surface behind it. Colouring the text itself in the accent is
              // what made these banners hard to read at small sizes.
              child: Text(
                message,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(color: cs.onSurface),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
