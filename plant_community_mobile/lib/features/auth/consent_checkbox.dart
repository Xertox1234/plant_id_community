import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import '../legal/legal_links.dart';

/// The sign-up consent checkbox. Unticked by default (the caller owns
/// [value]); the copy is fixed and must match everywhere it appears.
class ConsentCheckbox extends StatefulWidget {
  const ConsentCheckbox({
    super.key,
    required this.value,
    required this.onChanged,
    this.onOpenDoc,
  });

  final bool value;
  final ValueChanged<bool> onChanged;

  /// Test seam; defaults to [openLegalDoc].
  final Future<void> Function(LegalDoc doc)? onOpenDoc;

  static const copy =
      'I am 14 or older, and I have read and accept the Privacy Policy and '
      'Terms of Service.';

  @override
  State<ConsentCheckbox> createState() => _ConsentCheckboxState();
}

class _ConsentCheckboxState extends State<ConsentCheckbox> {
  late final TapGestureRecognizer _privacyTap = TapGestureRecognizer()
    ..onTap = () => _open(LegalDoc.privacy);
  late final TapGestureRecognizer _termsTap = TapGestureRecognizer()
    ..onTap = () => _open(LegalDoc.terms);

  void _open(LegalDoc doc) {
    final custom = widget.onOpenDoc;
    if (custom != null) {
      custom(doc);
    } else {
      openLegalDoc(context, doc);
    }
  }

  @override
  void dispose() {
    _privacyTap.dispose();
    _termsTap.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final base = theme.textTheme.bodyMedium;
    final link = base?.copyWith(
      color: theme.colorScheme.primary,
      decoration: TextDecoration.underline,
    );

    return Semantics(
      container: true,
      checked: widget.value,
      label: ConsentCheckbox.copy,
      onTap: () => widget.onChanged(!widget.value),
      // The links have no semantic nodes of their own (the row is one labelled
      // checkbox), so screen-reader users reach the documents from here.
      customSemanticsActions: {
        CustomSemanticsAction(label: 'Open Privacy Policy'): () =>
            _open(LegalDoc.privacy),
        CustomSemanticsAction(label: 'Open Terms of Service'): () =>
            _open(LegalDoc.terms),
      },
      child: ExcludeSemantics(
        child: InkWell(
          onTap: () => widget.onChanged(!widget.value),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 48),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Checkbox(
                  value: widget.value,
                  onChanged: (v) => widget.onChanged(v ?? false),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text.rich(
                      TextSpan(
                        style: base,
                        children: [
                          const TextSpan(
                            text:
                                'I am 14 or older, and I have read and accept '
                                'the ',
                          ),
                          TextSpan(
                            text: 'Privacy Policy',
                            style: link,
                            recognizer: _privacyTap,
                          ),
                          const TextSpan(text: ' and '),
                          TextSpan(
                            text: 'Terms of Service',
                            style: link,
                            recognizer: _termsTap,
                          ),
                          const TextSpan(text: '.'),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
