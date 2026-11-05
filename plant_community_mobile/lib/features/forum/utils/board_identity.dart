import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/theme/green_thumb_extension.dart';

/// Accent tone of a board. Mirrors the web's `TileTone`; each maps to a Canopy
/// accent token, so light mode gets the darkened accents automatically.
enum CanopyTone {
  sage,
  pollen,
  bloom,
  orchid;

  Color colorOf(GreenThumbExtension c) => switch (this) {
    CanopyTone.sage => c.leaf,
    CanopyTone.pollen => c.clay,
    CanopyTone.bloom => c.berry,
    CanopyTone.orchid => c.sky,
  };
}

/// Tone, icon and short chip label of a board.
class BoardIdentity {
  const BoardIdentity({
    required this.tone,
    required this.icon,
    required this.chipLabel,
  });

  final CanopyTone tone;
  final IconData icon;
  final String chipLabel;
}

/// Port of `web/src/utils/hashString.ts`: 31x rolling hash over UTF-16 code
/// units, kept to 32-bit unsigned (`>>> 0`) so a slug lands in the same bucket
/// on both platforms.
int webHashString(String value) {
  var hash = 0;
  for (final unit in value.codeUnits) {
    hash = (hash * 31 + unit) & 0xFFFFFFFF;
  }
  return hash;
}

/// Deliberate identities for the five Canopy boards (spec §6.1); mirrors
/// `web/src/utils/forumTones.ts`.
const _boardIdentities = <String, BoardIdentity>{
  'plant-identification': BoardIdentity(
    tone: CanopyTone.sage,
    icon: LucideIcons.leaf,
    chipLabel: 'Identification',
  ),
  'care-problems': BoardIdentity(
    tone: CanopyTone.pollen,
    icon: LucideIcons.droplet,
    chipLabel: 'Care',
  ),
  'pests-diseases': BoardIdentity(
    tone: CanopyTone.bloom,
    icon: LucideIcons.bug,
    chipLabel: 'Pests',
  ),
  'garden-design': BoardIdentity(
    tone: CanopyTone.orchid,
    icon: LucideIcons.layoutDashboard,
    chipLabel: 'Design',
  ),
  'show-tell': BoardIdentity(
    tone: CanopyTone.sage,
    icon: LucideIcons.camera,
    chipLabel: 'Show & tell',
  ),
};

/// Identity for [slug]; unknown slugs get the hash tone, a leaf icon and
/// [fallbackLabel] (or the slug) so third-party boards still render.
BoardIdentity boardIdentity(String slug, {String fallbackLabel = ''}) =>
    _boardIdentities[slug] ??
    BoardIdentity(
      tone: CanopyTone.values[webHashString(slug) % CanopyTone.values.length],
      icon: LucideIcons.leaf,
      chipLabel: fallbackLabel.isEmpty ? slug : fallbackLabel,
    );
