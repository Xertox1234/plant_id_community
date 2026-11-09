import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/constants/app_spacing.dart';
import '../../core/routing/app_router.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../services/account_deletion_service.dart';
import '../../services/auth_service.dart';
import '../../services/firestore_service.dart';
import '../../services/user_profile_service.dart';
import '../../shared/widgets/canopy_notice.dart';
import '../../shared/widgets/canopy_surfaces.dart';

/// Opens [uri] outside the app and reports whether it opened. A seam so a
/// widget test can assert the URL without a platform channel.
///
/// External, not the in-app browser `forumLinkLauncherProvider` uses: the
/// store subscription pages only hand off to the App Store / Play Store app
/// when the OS opens them.
final externalLinkLauncherProvider = Provider<Future<bool> Function(Uri)>(
  (ref) =>
      (uri) => launchUrl(uri, mode: LaunchMode.externalApplication),
);

/// The platform's own subscriptions page: Premium is billed by the store, so
/// only the store can cancel it.
Uri subscriptionsUri(TargetPlatform platform) => platform == TargetPlatform.iOS
    ? Uri.parse('https://apps.apple.com/account/subscriptions')
    : Uri.parse('https://play.google.com/store/account/subscriptions');

/// Self-service account deletion (Plan B task 10).
///
/// The button re-authenticates (a fresh Google pick, or the password), posts
/// the fresh Firebase ID token to `account/delete/`, then signs out and shows
/// the final dialog, whose OK goes to the login screen.
///
/// The route is deliberately NOT in the router's `protectedRoutes`: signing
/// out re-runs the redirect, and redirecting off this page would drop the
/// final dialog with it. The screen gates itself instead, and Settings shows
/// its entry only to a signed-in user.
class DeleteAccountScreen extends ConsumerStatefulWidget {
  const DeleteAccountScreen({super.key});

  static const routePath = '/settings/delete-account';

  @override
  ConsumerState<DeleteAccountScreen> createState() =>
      _DeleteAccountScreenState();
}

class _DeleteAccountScreenState extends ConsumerState<DeleteAccountScreen> {
  bool _busy = false;

  /// Set once the account is gone from this device, so the sign-out that
  /// follows does not swap the page for the signed-out notice under the
  /// final dialog.
  bool _finished = false;

  Future<void> _delete() async {
    // Everything the flow needs, read before the first await: once the
    // request is in flight the screen may be gone (something else navigated),
    // and `ref` is unusable after dispose. The 202 must still sign out.
    final auth = ref.read(authServiceProvider.notifier);
    final deletion = ref.read(accountDeletionServiceProvider);
    final profile = ref.exists(userProfileServiceProvider)
        ? ref.read(userProfileServiceProvider.notifier)
        : null;
    final clearOfflineCache = ref.read(firestoreOfflineCacheClearerProvider);
    final method = auth.reauthMethod;
    if (method == null) {
      await _showError(reauthUnsupportedMessage);
      return;
    }

    String? password;
    if (method == ReauthMethod.password) {
      password = await showDialog<String>(
        context: context,
        builder: (_) => const _PasswordDialog(),
      );
      if (password == null || password.isEmpty || !mounted) return;
    }

    // Busy only while the requests run: a spinner left spinning under a
    // dialog would never settle. Back is blocked while busy (PopScope).
    setState(() => _busy = true);
    AccountDeletionResult? result;
    String? reauthError;
    try {
      final token = await auth.freshIdTokenAfterReauth(password: password);
      result = await deletion.deleteAccount(token);
    } on ReauthCancelledException {
      // Backed out: nothing sent, nothing to say.
    } on AuthException catch (e) {
      reauthError = e.message;
    } finally {
      if (mounted) setState(() => _busy = false);
    }

    switch (result) {
      case AccountDeletionScheduled():
        // Mounted or not: the account is inactive now, so this device must
        // not stay signed in to it.
        await _endSession(auth, profile, clearOfflineCache);
        if (!mounted) return;
        await showDialog<void>(
          context: context,
          barrierDismissible: false,
          builder: (dialogContext) => AlertDialog(
            title: const Text('Account deletion started'),
            content: const Text(
              "Your account is being deleted. You'll get an email when "
              "it's done.",
            ),
            actions: [
              FilledButton(
                onPressed: () => Navigator.of(dialogContext).pop(),
                child: const Text('OK'),
              ),
            ],
          ),
        );
        if (mounted) context.go(AppRoutes.login);
      case AccountDeletionSignedOut():
        // Already scheduled from another device (ruling R15): the account is
        // inactive, so this session is over. No error to show.
        await _endSession(auth, profile, clearOfflineCache);
        if (mounted) context.go(AppRoutes.login);
      case AccountDeletionFailed(:final message):
        await _showError(message);
      case null:
        if (reauthError != null) await _showError(reauthError);
    }
  }

  /// Signs out (JWT and Firebase session) through the notifier held since
  /// the tap, clears the on-device Firestore offline cache (the deleted
  /// account's `users/<uid>/identified_plants`), and forgets the account
  /// profile, as the Profile logout does. Never throws, and needs no `ref`:
  /// it runs even after this screen is gone. A failed sign-out or cache
  /// clear is not shown: the deletion is already scheduled and the account
  /// inactive.
  Future<void> _endSession(
    AuthService auth,
    UserProfileService? profile,
    Future<void> Function() clearOfflineCache,
  ) async {
    if (mounted) setState(() => _finished = true);
    try {
      await auth.signOut();
    } catch (e) {
      if (kDebugMode) debugPrint('[ACCOUNT DELETE] Sign-out failed: $e');
    }
    // After the sign-out, so the signed-in streams are torn down first.
    try {
      await clearOfflineCache();
    } catch (e) {
      if (kDebugMode) {
        debugPrint('[ACCOUNT DELETE] Offline cache clear failed: $e');
      }
    }
    try {
      profile?.clear();
    } catch (e) {
      // Disposed meanwhile: nothing holds a profile to clear.
      if (kDebugMode) debugPrint('[ACCOUNT DELETE] Profile clear skipped: $e');
    }
  }

  Future<void> _showError(String message) async {
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Couldn't delete your account"),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> _openSubscriptions() async {
    final messenger = ScaffoldMessenger.of(context);
    var opened = false;
    try {
      opened = await ref.read(externalLinkLauncherProvider)(
        subscriptionsUri(defaultTargetPlatform),
      );
    } catch (_) {
      opened = false;
    }
    if (!opened) {
      messenger.showSnackBar(
        const SnackBar(content: Text("Couldn't open the page")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final ext = context.canopy;
    final cs = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    final signedIn = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );

    return PopScope(
      // Leaving mid-request would leave nobody to show the outcome.
      canPop: !_busy,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Delete account'),
          automaticallyImplyLeading: !_busy,
        ),
        body: SafeArea(
          child: ListView(
            padding: EdgeInsets.all(ext.padScreen),
            children: [
              if (!signedIn && !_finished)
                const CanopyNotice(
                  message: 'Sign in to delete your account.',
                  liveRegion: false,
                )
              else ...[
                Text(
                  'This permanently deletes your account, saved plants, '
                  'garden, scans and forum posts. Other people keep their copy '
                  "of messages you sent them. It can't be undone.",
                  style: text.bodyLarge?.copyWith(color: cs.onSurface),
                ),
                SizedBox(height: ext.gapY * 2),
                Semantics(
                  link: true,
                  child: CanopyCard(
                    onTap: _openSubscriptions,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            "Deleting your account doesn't cancel a Premium "
                            'subscription. Manage subscriptions in the App '
                            'Store or Google Play.',
                            style: text.bodyMedium?.copyWith(
                              color: cs.onSurface,
                            ),
                          ),
                        ),
                        SizedBox(width: ext.gapY),
                        Icon(
                          LucideIcons.externalLink,
                          size: AppSpacing.iconSM,
                          color: ext.ink2,
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: ext.gapY * 3),
                FilledButton.icon(
                  onPressed: _busy ? null : _delete,
                  icon: _busy
                      ? SizedBox.square(
                          dimension: AppSpacing.iconSM,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: cs.onError,
                          ),
                        )
                      : const Icon(LucideIcons.trash2),
                  label: Text(_busy ? 'Deleting…' : 'Delete my account'),
                  style: FilledButton.styleFrom(
                    backgroundColor: cs.error,
                    foregroundColor: cs.onError,
                    minimumSize: const Size.fromHeight(48),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Asks a password user for their password. Pops it, or `null` on Cancel.
class _PasswordDialog extends StatefulWidget {
  const _PasswordDialog();

  @override
  State<_PasswordDialog> createState() => _PasswordDialogState();
}

class _PasswordDialogState extends State<_PasswordDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() => Navigator.of(context).pop(_controller.text);

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text("Confirm it's you"),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Enter your password to delete your account.'),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _controller,
            obscureText: true,
            autofocus: true,
            autofillHints: const [AutofillHints.password],
            decoration: const InputDecoration(labelText: 'Password'),
            onSubmitted: (_) => _submit(),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Continue')),
      ],
    );
  }
}
