import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import '../../core/constants/app_spacing.dart';
import '../../core/theme/canopy_palette.dart';
import '../../core/theme/green_thumb_extension.dart';
import 'canopy_surfaces.dart';

/// A feature row: accent tile, title, description.
///
/// The web counterpart is a `Card` + `Tile` pair (see `HomePage.tsx`), which is
/// what this now builds on: [CanopyCard] for the lit gradient surface and
/// [CanopyTile] for the accent square. It previously painted a flat
/// `cs.surface` container with a 10%-alpha icon wash — a treatment the design
/// system does not have.
///
/// ```dart
/// FeatureCard(
///   icon: LucideIcons.camera,
///   title: 'Instant identification',
///   description: 'Snap a photo and name any plant',
///   type: FeatureType.camera,
/// )
/// ```
class FeatureCard extends StatelessWidget {
  const FeatureCard({
    super.key,
    required this.icon,
    required this.title,
    required this.description,
    this.type = FeatureType.camera,
    this.onTap,
  });

  final IconData icon;
  final String title;
  final String description;

  /// Chooses the accent tile's gradient.
  final FeatureType type;

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return CanopyCard(
      onTap: onTap,
      semanticLabel: title,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CanopyTile(icon: icon, tone: type.tone),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: text.titleMedium),
                const SizedBox(height: AppSpacing.xs),
                Text(description, style: text.bodySmall),
              ],
            ),
          ),
          if (onTap != null)
            Icon(
              LucideIcons.chevronRight,
              size: AppSpacing.iconMD,
              color: context.canopy.ink3,
            ),
        ],
      ),
    );
  }
}

/// Feature kinds and the accent each one carries. The accents are confined to
/// small elements by design (spec §1) — the tile is the only place they appear
/// on this card.
enum FeatureType {
  camera(CanopyTileTone.sage),
  care(CanopyTileTone.orchid),
  community(CanopyTileTone.bloom),
  collection(CanopyTileTone.pollen);

  const FeatureType(this.tone);

  final CanopyTileTone tone;
}
