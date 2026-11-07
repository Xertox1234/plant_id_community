import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/auth_service.dart';
import 'consent_checkbox.dart';

/// The Navigator a consent sheet is open on, so a second 428 does not stack
/// another. Keyed to the Navigator rather than a bare flag: a Navigator that
/// is gone (a test torn down mid-sheet) cannot leave it stuck.
NavigatorState? _openOn;

/// Show [ConsentSheet] and act on the answer: Continue calls
/// [AuthService.acceptTermsAndRetry]; Cancel, a drag down, a tap outside or
/// Back all call [AuthService.declineTerms]. Does nothing while a sheet is
/// already open.
Future<void> showConsentSheet(BuildContext context) async {
  final navigator = Navigator.of(context);
  final open = _openOn;
  if (open != null && open.mounted) return;
  _openOn = navigator;
  final auth = ProviderScope.containerOf(
    context,
    listen: false,
  ).read(authServiceProvider.notifier);
  try {
    final accepted = await showModalBottomSheet<bool>(
      context: navigator.context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => const ConsentSheet(),
    );
    if (accepted == true) {
      await auth.acceptTermsAndRetry();
    } else {
      await auth.declineTerms();
    }
  } finally {
    if (identical(_openOn, navigator)) _openOn = null;
  }
}

/// Asks a new account for the sign-up consent the server requires (428
/// `consent_required` from the token exchange): a Google sign-in from the
/// sign-in screen, or an email account verified on a device that never saw
/// its box ticked. Pops `true` for Continue, `false` for Cancel.
class ConsentSheet extends StatefulWidget {
  const ConsentSheet({super.key});

  @override
  State<ConsentSheet> createState() => _ConsentSheetState();
}

class _ConsentSheetState extends State<ConsentSheet> {
  bool _accepted = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              header: true,
              child: Text('One more step', style: theme.textTheme.titleLarge),
            ),
            const SizedBox(height: 8),
            Text(
              'To finish creating your account, accept the Privacy Policy and '
              'Terms of Service.',
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
    );
  }
}
