import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

/// The two published legal documents.
enum LegalDoc { privacy, terms }

/// The document locale for [locale]: `fr*` -> `fr`, `es*` -> `es`, else `en`.
/// Only the three languages the documents are published in exist.
String legalLangFor(Locale locale) {
  switch (locale.languageCode) {
    case 'fr':
      return 'fr';
    case 'es':
      return 'es';
    default:
      return 'en';
  }
}

/// `https://houseplant-md.com/<privacy|terms>?lang=<en|fr|es>`.
Uri legalUri(LegalDoc doc, Locale locale) => Uri.https(
  'houseplant-md.com',
  doc == LegalDoc.privacy ? '/privacy' : '/terms',
  {'lang': legalLangFor(locale)},
);

/// Opens [doc] in the in-app browser, in the device's language when published.
Future<void> openLegalDoc(BuildContext context, LegalDoc doc) async {
  final messenger = ScaffoldMessenger.of(context);
  final uri = legalUri(doc, Localizations.localeOf(context));
  var opened = false;
  try {
    opened = await launchUrl(uri, mode: LaunchMode.inAppBrowserView);
  } catch (_) {
    opened = false;
  }
  if (!opened) {
    messenger.showSnackBar(
      const SnackBar(content: Text("Couldn't open the page")),
    );
  }
}
