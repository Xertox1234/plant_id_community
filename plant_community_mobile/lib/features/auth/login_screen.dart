import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/routing/app_router.dart';
import '../../shared/widgets/canopy_notice.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../services/auth_service.dart';
import 'verify_email_screen.dart';

/// Email/password sign-in.
///
/// Replaces the `PlaceholderScreen(title: 'Login')` that stood here since the
/// route was first declared — `AppRoutes` still carried the comment
/// "Auth routes (screens not yet implemented)". The auth *logic* was always
/// finished; only this was missing, which is why the app shipped to TestFlight
/// with no way to sign in at all (todo 384).
///
/// **On success this screen dismisses itself** via [dismissAfterAuth]. It used
/// to rely on `appRouter`'s redirect instead, on the reasoning that
/// `refreshListenable: authChanged` would bounce an authenticated user off
/// `authOnlyRoutes`. That is only true for a route reached with `go`: the
/// redirect matches on `state.uri.path`, which stays `/profile` when this
/// screen is PUSHED from the Profile tab, so it never fired and a signed-in
/// user was left looking at the sign-in form.
///
/// Note `AuthState.isAuthenticated` means *the Django JWT has been exchanged*,
/// not merely that Firebase accepted the password — the exchange happens on the
/// auth-state listener afterwards. So the button stays busy until the exchange
/// lands and the redirect fires, rather than appearing to succeed and sitting
/// still.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;
  bool _submitting = false;
  bool _awaitingVerification = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final needsVerification = await ref
          .read(authServiceProvider.notifier)
          .signInWithEmailPassword(
            _emailController.text.trim(),
            _passwordController.text,
          );
      if (!mounted) return;
      if (needsVerification) {
        // The backend refuses an unverified email (403): say so and offer
        // the way through, instead of a silent signed-out Profile (todo 660).
        setState(() => _awaitingVerification = true);
      } else {
        dismissAfterAuth(context);
      }
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _openForgotPassword() => showDialog<void>(
    context: context,
    builder: (_) =>
        ForgotPasswordDialog(initialEmail: _emailController.text.trim()),
  );

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    return Scaffold(
      appBar: AppBar(title: const Text('Sign in')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: EdgeInsets.all(ext.padScreen),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: _awaitingVerification
                  ? VerifyEmailPanel(
                      onCancel: () =>
                          setState(() => _awaitingVerification = false),
                    )
                  : Form(
                      key: _formKey,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Welcome back',
                            style: Theme.of(context).textTheme.headlineSmall,
                            textAlign: TextAlign.center,
                          ),
                          SizedBox(height: ext.gapY * 2),
                          TextFormField(
                            controller: _emailController,
                            decoration: const InputDecoration(
                              labelText: 'Email',
                              prefixIcon: Icon(LucideIcons.mail),
                            ),
                            keyboardType: TextInputType.emailAddress,
                            textInputAction: TextInputAction.next,
                            autofillHints: const [AutofillHints.email],
                            autocorrect: false,
                            enabled: !_submitting,
                            validator: validateEmail,
                          ),
                          SizedBox(height: ext.gapY),
                          TextFormField(
                            controller: _passwordController,
                            decoration: InputDecoration(
                              labelText: 'Password',
                              prefixIcon: const Icon(LucideIcons.lock),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? LucideIcons.eye
                                      : LucideIcons.eyeOff,
                                ),
                                tooltip: _obscurePassword
                                    ? 'Show password'
                                    : 'Hide password',
                                onPressed: () => setState(
                                  () => _obscurePassword = !_obscurePassword,
                                ),
                              ),
                            ),
                            obscureText: _obscurePassword,
                            textInputAction: TextInputAction.done,
                            autofillHints: const [AutofillHints.password],
                            enabled: !_submitting,
                            validator: (v) => (v == null || v.isEmpty)
                                ? 'Enter your password'
                                : null,
                            onFieldSubmitted: (_) => _submit(),
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton(
                              onPressed: _submitting
                                  ? null
                                  : _openForgotPassword,
                              child: const Text('Forgot password?'),
                            ),
                          ),
                          if (_error != null) ...[
                            SizedBox(height: ext.gapY),
                            _AuthErrorBanner(message: _error!),
                          ],
                          SizedBox(height: ext.gapY * 2),
                          FilledButton(
                            onPressed: _submitting ? null : _submit,
                            child: _submitting
                                ? const SizedBox(
                                    height: 20,
                                    width: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
                                  )
                                : const Text('Sign in'),
                          ),
                          SizedBox(height: ext.gapY),
                          AppleSignInButton(enabled: !_submitting),
                          GoogleSignInButton(enabled: !_submitting),
                          SizedBox(height: ext.gapY),
                          TextButton(
                            // pushReplacement, not push: bouncing between sign-in and
                            // register would otherwise stack a page per tap.
                            onPressed: _submitting
                                ? null
                                : () => context.pushReplacement(
                                    AppRoutes.register,
                                  ),
                            child: const Text(
                              "Don't have an account? Create one",
                            ),
                          ),
                        ],
                      ),
                    ),
            ),
          ),
        ),
      ),
    );
  }
}

/// "Forgot password?" (todo 704, audit H7): mails a Firebase password reset
/// link ([AuthService.sendPasswordResetEmail]), the credential the sign-in
/// form checks.
///
/// After a send it says the same thing whether or not the address has an
/// account, so the dialog cannot be used to find out which addresses do.
class ForgotPasswordDialog extends ConsumerStatefulWidget {
  const ForgotPasswordDialog({super.key, this.initialEmail = ''});

  /// What the sign-in form's email field held, to save retyping it.
  final String initialEmail;

  @override
  ConsumerState<ForgotPasswordDialog> createState() =>
      _ForgotPasswordDialogState();
}

class _ForgotPasswordDialogState extends ConsumerState<ForgotPasswordDialog> {
  final _formKey = GlobalKey<FormState>();
  late final _emailController = TextEditingController(
    text: widget.initialEmail,
  );
  bool _sending = false;
  String? _sentTo;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_sending) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final email = _emailController.text.trim();
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await ref
          .read(authServiceProvider.notifier)
          .sendPasswordResetEmail(email);
      if (!mounted) return;
      setState(() => _sentTo = email);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final sentTo = _sentTo;

    if (sentTo != null) {
      return AlertDialog(
        title: const Text('Check your email'),
        content: Text(
          'If an account exists for $sentTo, we have sent it a link to reset '
          'the password.',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Done'),
          ),
        ],
      );
    }

    return AlertDialog(
      title: const Text('Reset your password'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter the email you sign in with, and we will send you a link '
              'to choose a new password.',
            ),
            SizedBox(height: ext.gapY),
            TextFormField(
              controller: _emailController,
              decoration: const InputDecoration(
                labelText: 'Email',
                prefixIcon: Icon(LucideIcons.mail),
              ),
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.send,
              autofillHints: const [AutofillHints.email],
              autocorrect: false,
              enabled: !_sending,
              validator: validateEmail,
              onFieldSubmitted: (_) => _send(),
            ),
            if (_error != null) ...[
              SizedBox(height: ext.gapY),
              _AuthErrorBanner(message: _error!),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _sending ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _sending ? null : _send,
          child: _sending
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Send link'),
        ),
      ],
    );
  }
}

/// "Continue with Google" -- shared by the sign-in and register screens.
///
/// Prominent rather than tucked below the form: it is the one path that
/// signs in at once, with no verification mail to open first. See
/// [AuthService.signInWithGoogle].
class GoogleSignInButton extends ConsumerStatefulWidget {
  const GoogleSignInButton({
    super.key,
    this.enabled = true,
    this.acceptedTerms = false,
  });

  final bool enabled;

  /// Whether the user ticked the consent box on this screen (sign-up only).
  final bool acceptedTerms;

  @override
  ConsumerState<GoogleSignInButton> createState() => _GoogleSignInButtonState();
}

class _GoogleSignInButtonState extends ConsumerState<GoogleSignInButton> {
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(authServiceProvider.notifier)
          .signInWithGoogle(acceptedTerms: widget.acceptedTerms);
      if (!mounted) return;
      dismissAfterAuth(context);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_error != null) ...[
          _AuthErrorBanner(message: _error!),
          SizedBox(height: ext.gapY),
        ],
        OutlinedButton.icon(
          onPressed: (!widget.enabled || _busy) ? null : _submit,
          icon: _busy
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(LucideIcons.circleUser),
          label: Text(_busy ? 'Signing in...' : 'Continue with Google'),
        ),
      ],
    );
  }
}

/// "Continue with Apple" -- shared by the sign-in and register screens, on
/// iOS only ([appleSignInSupported]; hidden on Android, owner decision
/// 2026-11-19). App Store Guideline 4.8 (todo 717): an app offering Google
/// sign-in must offer an equivalent that shares only the name and email and
/// lets the user hide the email.
///
/// Apple's button style (Human Interface Guidelines, Sign in with Apple):
/// the Apple logo and "Continue with Apple", black on a light screen and
/// white on a dark one, full width and placed above Google, so it is at
/// least as prominent. Renders nothing where Apple sign-in is not offered,
/// its gap included. See [AuthService.signInWithApple].
class AppleSignInButton extends ConsumerStatefulWidget {
  const AppleSignInButton({
    super.key,
    this.enabled = true,
    this.acceptedTerms = false,
  });

  final bool enabled;

  /// Whether the user ticked the consent box on this screen (sign-up only).
  final bool acceptedTerms;

  static const label = 'Continue with Apple';

  @override
  ConsumerState<AppleSignInButton> createState() => _AppleSignInButtonState();
}

class _AppleSignInButtonState extends ConsumerState<AppleSignInButton> {
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final signedIn = await ref
          .read(authServiceProvider.notifier)
          .signInWithApple(acceptedTerms: widget.acceptedTerms);
      // A closed sheet is a cancel: stay on this screen.
      if (!mounted || !signedIn) return;
      dismissAfterAuth(context);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!appleSignInSupported()) return const SizedBox.shrink();
    final ext =
        Theme.of(context).extension<GreenThumbExtension>() ??
        GreenThumbExtension.fallback;
    final dark = Theme.of(context).brightness == Brightness.dark;
    final background = dark ? Colors.white : Colors.black;
    final foreground = dark ? Colors.black : Colors.white;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (_error != null) ...[
          _AuthErrorBanner(message: _error!),
          SizedBox(height: ext.gapY),
        ],
        FilledButton.icon(
          onPressed: (!widget.enabled || _busy) ? null : _submit,
          style: FilledButton.styleFrom(
            backgroundColor: background,
            foregroundColor: foreground,
            disabledBackgroundColor: background.withValues(alpha: 0.4),
            disabledForegroundColor: foreground.withValues(alpha: 0.7),
            minimumSize: const Size.fromHeight(48),
            textStyle: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w600,
            ),
          ),
          icon: _busy
              ? SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: foreground,
                  ),
                )
              : const Icon(Icons.apple, size: 22),
          label: Text(_busy ? 'Signing in...' : AppleSignInButton.label),
        ),
        SizedBox(height: ext.gapY),
      ],
    );
  }
}

/// Leave an auth screen once sign-in has actually succeeded.
///
/// **The router's redirect cannot do this, and `context.pop()` does not work
/// either.** Both were tried against the production router and observed:
///
/// `appRouter` matches `authOnlyRoutes.contains(state.uri.path)`, but when this
/// screen is PUSHED from the Profile tab the location stays `/profile` — on the
/// auth-change refresh the redirect is handed `uri.path`, `matchedLocation` AND
/// `fullPath` all equal to `/profile`, with nothing anywhere exposing the
/// pushed `/login`. No redirect rule can see it.
///
/// `context.pop()` reports `canPop() == true` and then changes nothing: the
/// refresh triggered by the auth flip re-parses the route information first,
/// and the pop that follows leaves the match list at length 2 with `/login`
/// still on top. Measured, not assumed.
///
/// Re-navigating to the UNDERLYING location collapses the imperative push
/// deterministically (match list 2 -> 1), and returns the user to whichever
/// screen sent them here — normally the Profile tab, now rendering signed-in.
///
/// When they arrived by REDIRECT from a protected route the underlying location
/// IS an auth route, so there is nothing to return to. That case lands on the
/// PROFILE tab, not home: someone who just signed in is there to be signed in,
/// and the profile tab is what reflects that. Observed on build 8 — the owner
/// landed on Home and said "the profile tab would be the preferred
/// destination".
///
/// Before this, signing in left a fully authenticated user staring at the
/// sign-in form; the owner only discovered it had worked by tapping the back
/// arrow. Regression test: `test/routing/auth_dismiss_test.dart`.
void dismissAfterAuth(BuildContext context) {
  final router = GoRouter.of(context);
  final uri = router.routerDelegate.currentConfiguration.uri;
  final cameFromAnAuthRoute =
      uri.path == AppRoutes.login || uri.path == AppRoutes.register;
  router.go(cameFromAnAuthRoute ? AppRoutes.profile : uri.toString());
}

/// Inline validation shared by the sign-in and register forms.
///
/// Deliberately permissive: the authority on whether an address exists is
/// Firebase, and a clever local regex only ever produces false rejections.
String? validateEmail(String? value) {
  final email = value?.trim() ?? '';
  if (email.isEmpty) return 'Enter your email';
  if (!email.contains('@') || email.startsWith('@') || email.endsWith('@')) {
    return 'Enter a valid email address';
  }
  return null;
}

/// The minimum length of a new password: the Firebase Auth password policy
/// (set to 14 in the console on 2026-11-19, todo 715) and the web sign-up's
/// own minimum. Firebase enforces it; checking locally saves a round trip.
const int minPasswordLength = 14;

/// For a NEW password (sign-up) only. The sign-in form must not use it: the
/// policy does not force an upgrade on sign-in, so an older account with a
/// shorter password still signs in.
String? validatePassword(String? value) {
  final password = value ?? '';
  if (password.isEmpty) return 'Enter a password';
  if (password.length < minPasswordLength) {
    return 'Use at least $minPasswordLength characters';
  }
  return null;
}

/// Inline error for a failed auth attempt.
///
/// `main.dart` also surfaces `AuthState.error` in a root SnackBar, so a failure
/// shows in both places. That listener is app-wide (it also carries
/// session-expiry messages), so it is left alone; a form still needs its error
/// anchored to the form rather than floating over the bottom of the screen.
class _AuthErrorBanner extends StatelessWidget {
  const _AuthErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) =>
      CanopyNotice(message: message, tone: CanopyNoticeTone.error);
}
