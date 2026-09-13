import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_router.dart';
import '../../core/theme/green_thumb_extension.dart';
import '../../services/auth_service.dart';

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
      await ref
          .read(authServiceProvider.notifier)
          .signInWithEmailPassword(
            _emailController.text.trim(),
            _passwordController.text,
          );
      if (!mounted) return;
      dismissAfterAuth(context);
    } on AuthException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

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
              child: Form(
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
                        prefixIcon: Icon(Icons.mail_outline),
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
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_outlined
                                : Icons.visibility_off_outlined,
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
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Sign in'),
                    ),
                    SizedBox(height: ext.gapY),
                    GoogleSignInButton(enabled: !_submitting),
                    SizedBox(height: ext.gapY),
                    TextButton(
                      // pushReplacement, not push: bouncing between sign-in and
                      // register would otherwise stack a page per tap.
                      onPressed: _submitting
                          ? null
                          : () => context.pushReplacement(AppRoutes.register),
                      child: const Text("Don't have an account? Create one"),
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

/// "Continue with Google" -- shared by the sign-in and register screens.
///
/// Prominent rather than tucked below the form, because it is currently the
/// ONLY path that reaches a signed-in state: the backend 403s an unverified
/// email/password token and this app sends no verification mail. See
/// [AuthService.signInWithGoogle].
class GoogleSignInButton extends ConsumerStatefulWidget {
  const GoogleSignInButton({super.key, this.enabled = true});

  final bool enabled;

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
      await ref.read(authServiceProvider.notifier).signInWithGoogle();
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
              : const Icon(Icons.account_circle_outlined),
          label: Text(_busy ? 'Signing in...' : 'Continue with Google'),
        ),
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
/// IS an auth route, so there is nothing to go back to and home is correct.
///
/// Before this, signing in left a fully authenticated user staring at the
/// sign-in form; the owner only discovered it had worked by tapping the back
/// arrow. Regression test: `test/routing/auth_dismiss_test.dart`.
void dismissAfterAuth(BuildContext context) {
  final router = GoRouter.of(context);
  final uri = router.routerDelegate.currentConfiguration.uri;
  final cameFromAnAuthRoute =
      uri.path == AppRoutes.login || uri.path == AppRoutes.register;
  router.go(cameFromAnAuthRoute ? AppRoutes.home : uri.toString());
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

/// Firebase's own minimum. Rejecting locally saves a round trip and gives the
/// user the rule before they submit.
String? validatePassword(String? value) {
  final password = value ?? '';
  if (password.isEmpty) return 'Enter a password';
  if (password.length < 6) return 'Use at least 6 characters';
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
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cs.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, size: 20, color: cs.onErrorContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: cs.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
