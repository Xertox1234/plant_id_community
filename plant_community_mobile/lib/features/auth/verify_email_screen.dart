import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/theme/green_thumb_extension.dart';
import '../../services/auth_service.dart';
import '../../shared/widgets/canopy_notice.dart';
import 'login_screen.dart' show dismissAfterAuth;

/// Confirmation shown after Resend succeeds.
const verificationEmailSentMessage =
    'Verification email sent. Check your inbox and spam folder.';

/// The "Check your email" state of the sign-in and register screens (todo
/// 660).
///
/// The backend refuses a Firebase token whose email is unverified (403, todos
/// 447/449), so an email/password account cannot finish signing in until its
/// holder opens the mailed link. This panel replaces the form on both screens
/// at that point, instead of the old silent return to a signed-out Profile:
///
/// * **I've verified** reloads the Firebase user and re-runs the token
///   exchange with a forced token refresh ([AuthService.confirmEmailVerified]).
/// * **Resend email** sends the verification mail again.
/// * **Use a different account** signs out of Firebase and returns to the
///   form ([onCancel]).
///
/// Rendered inline rather than as its own route: a pushed sign-in screen
/// keeps the location at `/profile`, so a route-based redirect could not see
/// it (see [dismissAfterAuth]). Once the exchange succeeds, from here or from
/// any other path, the panel leaves via [dismissAfterAuth] like the forms do.
class VerifyEmailPanel extends ConsumerStatefulWidget {
  const VerifyEmailPanel({super.key, required this.onCancel});

  /// Called after "Use a different account" has signed out.
  final VoidCallback onCancel;

  @override
  ConsumerState<VerifyEmailPanel> createState() => _VerifyEmailPanelState();
}

class _VerifyEmailPanelState extends ConsumerState<VerifyEmailPanel> {
  bool _checking = false;
  bool _resending = false;
  bool _dismissed = false;
  String? _error;
  String? _info;

  bool get _busy => _checking || _resending;

  void _dismiss() {
    if (_dismissed || !mounted) return;
    _dismissed = true;
    dismissAfterAuth(context);
  }

  Future<void> _confirm() async {
    if (_busy) return;
    setState(() {
      _checking = true;
      _error = null;
      _info = null;
    });
    try {
      final signedIn = await ref
          .read(authServiceProvider.notifier)
          .confirmEmailVerified();
      if (!mounted) return;
      if (signedIn) {
        _dismiss();
        return;
      }
      setState(
        () => _error =
            ref.read(authServiceProvider).error ?? emailStillUnverifiedMessage,
      );
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  Future<void> _resend() async {
    if (_busy) return;
    setState(() {
      _resending = true;
      _error = null;
      _info = null;
    });
    try {
      await ref.read(authServiceProvider.notifier).resendVerificationEmail();
      if (!mounted) return;
      setState(() => _info = verificationEmailSentMessage);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _resending = false);
    }
  }

  Future<void> _useDifferentAccount() async {
    if (_busy) return;
    try {
      await ref.read(authServiceProvider.notifier).signOut();
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
      return;
    }
    if (mounted) widget.onCancel();
  }

  @override
  Widget build(BuildContext context) {
    // Signed in by any path (this panel, or the auth-state listener's own
    // exchange): leave, as the forms do.
    ref.listen<AuthState>(authServiceProvider, (previous, next) {
      if (next.isAuthenticated && previous?.isAuthenticated != true) {
        WidgetsBinding.instance.addPostFrameCallback((_) => _dismiss());
      }
    });

    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final theme = Theme.of(context);
    final email = ref.watch(
      authServiceProvider.select((s) => s.firebaseUser?.email),
    );

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Icon(LucideIcons.mailCheck, size: 48, color: theme.colorScheme.primary),
        SizedBox(height: ext.gapY),
        Text(
          'Check your email',
          style: theme.textTheme.headlineSmall,
          textAlign: TextAlign.center,
        ),
        SizedBox(height: ext.gapY),
        Text(
          email == null
              ? 'We sent you a verification link. Open it, then come back '
                    "and tap \"I've verified\"."
              : 'We sent a verification link to $email. Open it, then come '
                    "back and tap \"I've verified\".",
          style: theme.textTheme.bodyMedium,
          textAlign: TextAlign.center,
        ),
        if (_error != null) ...[
          SizedBox(height: ext.gapY),
          CanopyNotice(message: _error!, tone: CanopyNoticeTone.error),
        ],
        if (_info != null) ...[
          SizedBox(height: ext.gapY),
          CanopyNotice(message: _info!, tone: CanopyNoticeTone.success),
        ],
        SizedBox(height: ext.gapY * 2),
        FilledButton(
          onPressed: _busy ? null : _confirm,
          child: _checking
              ? const SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text("I've verified"),
        ),
        SizedBox(height: ext.gapY),
        OutlinedButton(
          onPressed: _busy ? null : _resend,
          child: Text(_resending ? 'Sending...' : 'Resend email'),
        ),
        SizedBox(height: ext.gapY),
        TextButton(
          onPressed: _busy ? null : _useDifferentAccount,
          child: const Text('Use a different account'),
        ),
      ],
    );
  }
}
