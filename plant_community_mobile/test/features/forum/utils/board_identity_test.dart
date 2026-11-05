import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:plant_community_mobile/core/theme/app_theme.dart';
import 'package:plant_community_mobile/core/theme/green_thumb_extension.dart';
import 'package:plant_community_mobile/features/forum/utils/board_identity.dart';

void main() {
  group('boardIdentity map', () {
    for (final (slug, tone, icon, label) in [
      (
        'plant-identification',
        CanopyTone.sage,
        LucideIcons.leaf,
        'Identification',
      ),
      ('care-problems', CanopyTone.pollen, LucideIcons.droplet, 'Care'),
      ('pests-diseases', CanopyTone.bloom, LucideIcons.bug, 'Pests'),
      (
        'garden-design',
        CanopyTone.orchid,
        LucideIcons.layoutDashboard,
        'Design',
      ),
      ('show-tell', CanopyTone.sage, LucideIcons.camera, 'Show & tell'),
    ]) {
      test(slug, () {
        final id = boardIdentity(slug, fallbackLabel: 'ignored');
        expect(id.tone, tone);
        expect(id.icon, icon);
        expect(id.chipLabel, label);
      });
    }
  });

  group('webHashString parity with web/src/utils/hashString.ts', () {
    test('known values', () {
      expect(webHashString('general'), 4214819048);
      expect(webHashString('off-topic'), 343965521);
      expect(webHashString('houseplants'), 2051170952);
      expect(webHashString(''), 0);
    });
  });

  group('fallback', () {
    test('hash tone, leaf icon', () {
      expect(boardIdentity('general').tone, CanopyTone.sage);
      expect(boardIdentity('off-topic').tone, CanopyTone.pollen);
      expect(boardIdentity('general').icon, LucideIcons.leaf);
    });
    test('label uses fallbackLabel, else slug', () {
      expect(
        boardIdentity('general', fallbackLabel: 'General').chipLabel,
        'General',
      );
      expect(boardIdentity('general').chipLabel, 'general');
    });
  });

  group('CanopyTone.colorOf', () {
    for (final b in Brightness.values) {
      test('maps to the accent tokens (${b.name})', () {
        final c = AppTheme.build(
          b,
          AppDensity.cozy,
        ).extension<GreenThumbExtension>()!;
        expect(CanopyTone.sage.colorOf(c), c.leaf);
        expect(CanopyTone.pollen.colorOf(c), c.clay);
        expect(CanopyTone.bloom.colorOf(c), c.berry);
        expect(CanopyTone.orchid.colorOf(c), c.sky);
      });
    }
  });
}
