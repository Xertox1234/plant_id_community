import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/auth/password_reset_link.dart';

void main() {
  test('the reset page sits on the API origin, not under /api/v1', () {
    expect(
      passwordResetUri('https://api.houseplant-md.com/api/v1').toString(),
      'https://api.houseplant-md.com/accounts/password/reset/',
    );
  });

  test('a development base keeps its scheme and port', () {
    expect(
      passwordResetUri('http://localhost:8000/api/v1').toString(),
      'http://localhost:8000/accounts/password/reset/',
    );
  });
}
