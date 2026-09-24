import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

/// Opens [uri] and reports whether it opened. A seam so widget tests can
/// assert the exact URL without a platform channel.
typedef ForumLinkLauncher = Future<bool> Function(Uri uri);

/// Opens forum links in the in-app browser: SFSafariViewController on iOS, a
/// Custom Tab on Android. The reader stays in the app and returns with one
/// gesture (todo 424).
final forumLinkLauncherProvider = Provider<ForumLinkLauncher>(
  (ref) =>
      (uri) => launchUrl(uri, mode: LaunchMode.inAppBrowserView),
);

/// The [Uri] a post's `href` may be opened as, or null when it must not be.
///
/// Only absolute `http`/`https` links with a host pass. `javascript:`,
/// `file:`, `intent:`, `tel:`, relative paths and the rest are refused here,
/// even though the server already sanitizes hrefs (nh3): the client enforces
/// its own allowlist rather than trusting the payload.
Uri? openableForumLink(String href) {
  final uri = Uri.tryParse(href.trim());
  if (uri == null || !uri.hasAuthority || uri.host.isEmpty) return null;
  final scheme = uri.scheme.toLowerCase();
  if (scheme != 'http' && scheme != 'https') return null;
  return uri;
}
