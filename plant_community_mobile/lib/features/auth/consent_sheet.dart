import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/auth_service.dart';
import 'consent_checkbox.dart';

/// The Navigator a consent sheet is open on, so a second 428 does not stack
/// another. Keyed to the Navigator rather than a bare flag: a Navigator that
/// is gone (a test torn down mid-sheet) cannot leave it stuck.
NavigatorState? _openOn;

/// Show [ConsentSheet] and act on the answer: Continue calls
/// [AuthService.acceptTermsAndRetry]; Cancel, Back, a tap outside or a drag
/// down call [AuthService.declineTerms]. Does nothing while a sheet is
/// already open.
///
/// Only the user's own dismissal declines. A drag down completes the sheet
/// with `null`, and so does removing the page beneath it (`router.go` after
/// a sign-in, a deep link): Flutter pops a pageless route with its page. The
/// two differ in whether that page survives, so a `null` declines only while
/// it is still in the navigator's pages. Declining deletes the new Firebase
/// user, so a navigation must never pass for it.
///
/// A removal asks again instead: the sheet re-opens over the new page on the
/// next frame while `consentRequired` still holds, or the user would be left
/// signed in to Firebase only, with no sheet (the root opens it only when the
/// flag turns true). Each re-open needs another removal to close it, and an
/// unmounted Navigator stops it, so it cannot loop.
Future<void> showConsentSheet(BuildContext context) async {
  final navigator = Navigator.of(context);
  final open = _openOn;
  if (open != null && open.mounted) return;
  _openOn = navigator;
  final container = ProviderScope.containerOf(context, listen: false);
  final auth = container.read(authServiceProvider.notifier);
  final pages = navigator.widget.pages;
  final pageKeyBelow = pages.isEmpty ? null : pages.last.key;
  var reopen = false;
  try {
    final accepted = await showModalBottomSheet<bool>(
      context: navigator.context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => ConsentSheet(
        policyUpdate: container.read(authServiceProvider).policyUpdate,
      ),
    );
    if (accepted == true) {
      await auth.acceptTermsAndRetry();
    } else if (accepted == false ||
        _pageSurvived(navigator, pages.isEmpty, pageKeyBelow)) {
      await auth.declineTerms();
    } else {
      reopen = navigator.mounted;
    }
  } finally {
    if (identical(_openOn, navigator)) _openOn = null;
  }
  if (reopen) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!navigator.mounted) return;
      if (!container.read(authServiceProvider).consentRequired) return;
      showConsentSheet(navigator.context);
    });
  }
}

/// Whether the page the sheet opened over is still there, i.e. a `null`
/// result was the user's drag, not the page's removal. A Navigator with no
/// pages (pageless routes only) has no page to lose.
bool _pageSurvived(NavigatorState navigator, bool pageless, LocalKey? key) {
  if (!navigator.mounted) return false;
  if (pageless) return true;
  return navigator.widget.pages.any((p) => p.key == key);
}

/// Asks a new account for the sign-up consent the server requires (428
/// `consent_required` from the token exchange): a Google sign-in from the
/// sign-in screen, or an email account verified on a device that never saw
/// its box ticked. Pops `true` for Continue, `false` for Cancel.
class ConsentSheet extends StatefulWidget {
  const ConsentSheet({super.key, this.policyUpdate = false});

  /// An existing account accepting a changed policy (428
  /// `policy_update_required`), not a new one: only the wording differs.
  final bool policyUpdate;

  @override
  State<ConsentSheet> createState() => _ConsentSheetState();
}

class _ConsentSheetState extends State<ConsentSheet> {
  bool _accepted = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Back and a tap outside arrive as a blocked pop: answer them with an
    // explicit `false`, the same as Cancel. A pop that did happen (a drag,
    // or the page beneath removed) is sorted out by showConsentSheet.
    return PopScope<bool>(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.of(context).pop(false);
      },
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Semantics(
                header: true,
                child: Text(
                  widget.policyUpdate
                      ? 'Our policies have changed'
                      : 'One more step',
                  style: theme.textTheme.titleLarge,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                widget.policyUpdate
                    ? 'To keep using your account, accept the updated Privacy '
                          'Policy and Terms of Service. Cancel signs you out.'
                    : 'To finish creating your account, accept the Privacy '
                          'Policy and Terms of Service.',
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 8),
              ConsentCheckbox(
                value: _accepted,
                onChanged: (v) => setState(() => _accepted = v),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _accepted
                    ? () => Navigator.of(context).pop(true)
                    : null,
                child: const Text('Continue'),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
