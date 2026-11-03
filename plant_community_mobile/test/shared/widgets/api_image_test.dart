import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/services/api_service.dart';
import 'package:plant_community_mobile/shared/widgets/api_image.dart';

const _origin = 'https://api.test';

Future<Map<String, String>?> _headersFor(
  WidgetTester tester,
  String url, {
  String? token = 'tok-123',
}) async {
  final api = ApiService(baseUrl: '$_origin/api/v1', authToken: token);
  await tester.pumpWidget(
    ProviderScope(
      overrides: [apiServiceProvider.overrideWithValue(api)],
      child: MaterialApp(home: ApiImage(url: url)),
    ),
  );
  return tester
      .widget<CachedNetworkImage>(find.byType(CachedNetworkImage))
      .httpHeaders;
}

void main() {
  testWidgets('ApiImage adds auth header only for API URLs', (tester) async {
    final api = await _headersFor(
      tester,
      '$_origin/api/v1/plant-identification/scans/j/photos/whole/',
    );
    expect(api?['Authorization'], 'Bearer tok-123');
    expect(api?['Accept'], 'image/*');

    final firebase = await _headersFor(
      tester,
      'https://firebasestorage.googleapis.com/v0/b/x/o/p.jpg',
    );
    expect(firebase, isNull);
  });

  testWidgets('ApiImage never sends the token to a look-alike host', (
    tester,
  ) async {
    for (final url in [
      'https://api.test.evil.com/a.jpg',
      'https://evil.com/?u=https://api.test/api/v1/a.jpg',
      'http://api.test/api/v1/a.jpg',
      'https://api.test:8443/a.jpg',
    ]) {
      expect(await _headersFor(tester, url), isNull, reason: url);
    }
  });

  testWidgets('ApiImage loads an API URL without a header when no token', (
    tester,
  ) async {
    final headers = await _headersFor(
      tester,
      '$_origin/api/v1/x/',
      token: null,
    );
    expect(headers, isNull);
  });
}
