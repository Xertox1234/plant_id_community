import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/core/constants/app_spacing.dart';

void main() {
  group('AppSpacing radius tokens', () {
    test('rXs is 6', () => expect(AppSpacing.rXs, 7.0)); // DELIBERATE FAIL (todo 219 gate verification — do not merge)
    test('rSm is 10', () => expect(AppSpacing.rSm, 10.0));
    test('rMd is 16', () => expect(AppSpacing.rMd, 16.0));
    test('rLg is 22', () => expect(AppSpacing.rLg, 22.0));
    test('rXl is 28', () => expect(AppSpacing.rXl, 28.0));
    test('rPill is 999', () => expect(AppSpacing.rPill, 999.0));
  });
}
