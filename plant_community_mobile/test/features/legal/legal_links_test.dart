import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:plant_community_mobile/features/legal/legal_links.dart';

void main() {
  test('legalLangFor maps language codes to the three published locales', () {
    expect(legalLangFor(const Locale('fr', 'CA')), 'fr');
    expect(legalLangFor(const Locale('es', 'MX')), 'es');
    expect(legalLangFor(const Locale('pt', 'BR')), 'en');
    expect(legalLangFor(const Locale('en', 'US')), 'en');
  });

  test('legalUri builds the document URL', () {
    expect(
      legalUri(LegalDoc.privacy, const Locale('fr', 'CA')).toString(),
      'https://houseplant-md.com/privacy?lang=fr',
    );
    expect(
      legalUri(LegalDoc.terms, const Locale('es')).toString(),
      'https://houseplant-md.com/terms?lang=es',
    );
    expect(
      legalUri(LegalDoc.terms, const Locale('de')).toString(),
      'https://houseplant-md.com/terms?lang=en',
    );
  });
}
