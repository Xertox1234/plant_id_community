import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../models/forum_rich_text_markup.dart';

/// Wraps [value]'s selection in [marker] on both sides (e.g. `**bold**`,
/// `_italic_`, `` `code` ``). A non-collapsed selection is wrapped in place
/// and stays selected, so a re-tap or typing over it replaces it. A
/// collapsed selection gets an empty marker pair inserted with the cursor
/// — or, if [placeholder] is given, the placeholder text — selected between
/// them, so typing immediately overwrites it.
TextEditingValue wrapInlineMarker(
  TextEditingValue value,
  String marker, {
  String placeholder = '',
}) {
  final selection = value.selection;
  if (!selection.isValid) return value;
  final text = value.text;

  if (selection.isCollapsed) {
    final insertion = '$marker$placeholder$marker';
    final newText = text.replaceRange(
      selection.start,
      selection.start,
      insertion,
    );
    final placeholderStart = selection.start + marker.length;
    return value.copyWith(
      text: newText,
      selection: TextSelection(
        baseOffset: placeholderStart,
        extentOffset: placeholderStart + placeholder.length,
      ),
      // A pre-mutation composing range (e.g. Gboard's IME composing region)
      // can point past the end of the restructured text, tripping
      // TextEditingController's isComposingRangeValid assert and
      // misdirecting the next IME commit — todo 314 final review.
      composing: TextRange.empty,
    );
  }

  final selected = text.substring(selection.start, selection.end);
  final newText = text.replaceRange(
    selection.start,
    selection.end,
    '$marker$selected$marker',
  );
  final newStart = selection.start + marker.length;
  return value.copyWith(
    text: newText,
    selection: TextSelection(
      baseOffset: newStart,
      extentOffset: newStart + selected.length,
    ),
    composing: TextRange.empty,
  );
}

/// Inserts a `[text](url)` link at [value]'s selection. [url] must already
/// be validated by the caller via [isAllowedForumLinkHref] (the toolbar's
/// link dialog does this before calling); an invalid [url] is still a
/// defensive no-op here rather than inserting a broken link. Link text is
/// the current non-empty selection, else [linkTextOverride], else [url]
/// itself.
TextEditingValue insertLink(
  TextEditingValue value, {
  required String url,
  String? linkTextOverride,
}) {
  if (!isAllowedForumLinkHref(url)) return value;
  final selection = value.selection;
  if (!selection.isValid) return value;
  final text = value.text;

  final selected = selection.isCollapsed
      ? ''
      : text.substring(selection.start, selection.end);
  final override = linkTextOverride;
  final linkText = selected.isNotEmpty
      ? selected
      : (override != null && override.isNotEmpty ? override : url);

  // Percent-encode a literal ')' in the href so it can't be mistaken for the
  // closing paren of the `[text](url)` marker syntax — e.g. a Wikipedia
  // disambiguation link like `.../Ficus_(Moraceae)` would otherwise
  // truncate the generator's non-greedy link regex at the embedded `)`,
  // corrupting the href (todo 314 final review). An unencoded '(' is not
  // ambiguous for that regex (it only searches for the next ')'), so it is
  // left as-is.
  final encodedUrl = url.replaceAll(')', '%29');
  final markup = '[$linkText]($encodedUrl)';
  final newText = text.replaceRange(selection.start, selection.end, markup);
  final newOffset = selection.start + markup.length;
  return value.copyWith(
    text: newText,
    selection: TextSelection.collapsed(offset: newOffset),
    composing: TextRange.empty,
  );
}

/// Toggles a `- ` bullet prefix on every line the current selection touches
/// (found via `lastIndexOf`/`indexOf('\n', ...)` from the selection bounds,
/// matching [toggleListPrefix]'s own contract). Toggles OFF only when
/// *every* touched line already has the prefix; otherwise toggles ON for
/// every touched line that lacks it (an already-prefixed touched line is
/// left as-is). The toggled range is left selected.
TextEditingValue toggleListPrefix(TextEditingValue value) {
  final selection = value.selection;
  if (!selection.isValid) return value;
  final text = value.text;

  final selStart = selection.start;
  final selEnd = selection.end;
  final lineStart = selStart == 0
      ? 0
      : text.lastIndexOf('\n', selStart - 1) + 1;
  final foundLineEnd = text.indexOf('\n', selEnd);
  final lineEnd = foundLineEnd == -1 ? text.length : foundLineEnd;

  final touched = text.substring(lineStart, lineEnd);
  final lines = touched.split('\n');
  final allPrefixed = lines.every((l) => l.startsWith('- '));

  final newLines = allPrefixed
      ? lines.map((l) => l.substring(2)).toList()
      : lines.map((l) => l.startsWith('- ') ? l : '- $l').toList();

  final newTouched = newLines.join('\n');
  final newText = text.replaceRange(lineStart, lineEnd, newTouched);

  if (!selection.isCollapsed) {
    // A real selection stays selected, spanning the toggled region — lets
    // the user see exactly what changed.
    return value.copyWith(
      text: newText,
      selection: TextSelection(
        baseOffset: lineStart,
        extentOffset: lineStart + newTouched.length,
      ),
      composing: TextRange.empty,
    );
  }

  // A collapsed caret must stay collapsed — selecting the whole line here
  // would mean the user's very next keystroke replaces it. Shift the caret
  // by the delta of only the single line it's actually on, not the whole
  // touched span (a multi-line touch only ever has one line to be
  // collapsed within).
  var oldLineStart = lineStart;
  var newLineStart = lineStart;
  var newOffset = lineStart;
  for (var i = 0; i < lines.length; i++) {
    final oldLine = lines[i];
    final newLine = newLines[i];
    final oldLineEnd = oldLineStart + oldLine.length;
    final isLast = i == lines.length - 1;
    if (selStart <= oldLineEnd || isLast) {
      final within = (selStart - oldLineStart).clamp(0, oldLine.length);
      final delta = newLine.length - oldLine.length;
      final adjusted = delta > 0
          ? within + delta
          : (within + delta).clamp(0, newLine.length);
      newOffset = newLineStart + adjusted;
      break;
    }
    oldLineStart = oldLineEnd + 1;
    newLineStart += newLine.length + 1;
  }

  return value.copyWith(
    text: newText,
    selection: TextSelection.collapsed(offset: newOffset),
    composing: TextRange.empty,
  );
}

/// Normalizes an invalid selection (e.g. [TextEditingValue.empty]'s
/// `TextSelection.collapsed(offset: -1)`, which a fresh, never-focused
/// [TextEditingController] starts with) to a collapsed caret at the end of
/// the text, so the toolbar's transform functions above always receive a
/// valid selection to act on instead of defensively no-op'ing (todo 314
/// final review — otherwise the first tap on any toolbar button before the
/// body field has been focused silently does nothing).
TextEditingValue _withValidSelection(TextEditingValue value) {
  return value.selection.isValid
      ? value
      : value.copyWith(
          selection: TextSelection.collapsed(offset: value.text.length),
          composing: TextRange.empty,
        );
}

/// The composer's rich-text toolbar (todo 314): five buttons — bold,
/// italic, inline code, link, bulleted list — each wired to a pure
/// transform function above, mutating [controller]'s value directly.
///
/// Deliberately does not use a Material [TextField] for its own link-entry
/// dialog (a [CupertinoTextField] instead) — a `TextField` nested here would
/// make `find.byType(TextField)` ambiguous in composer-screen widget tests
/// whenever the dialog happens to be open.
class ForumRichTextToolbar extends StatelessWidget {
  const ForumRichTextToolbar({super.key, required this.controller});

  final TextEditingController controller;

  void _wrap(String marker, {String placeholder = ''}) {
    controller.value = wrapInlineMarker(
      _withValidSelection(controller.value),
      marker,
      placeholder: placeholder,
    );
  }

  Future<void> _showLinkDialog(BuildContext context) async {
    final urlController = TextEditingController();
    try {
      final url = await showDialog<String>(
        context: context,
        builder: (dialogContext) {
          String? error;
          return StatefulBuilder(
            builder: (context, setState) {
              return AlertDialog(
                title: const Text('Insert link'),
                // The error lives in `content`, not `actions`: an
                // `AlertDialog`'s actions lay out in a single row alongside
                // Cancel/Insert, and this message is long enough to overflow
                // there on a narrow phone.
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CupertinoTextField(
                      controller: urlController,
                      placeholder: 'https://example.com',
                      autofocus: true,
                      keyboardType: TextInputType.url,
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(dialogContext).pop(),
                    child: const Text('Cancel'),
                  ),
                  TextButton(
                    onPressed: () {
                      final candidate = urlController.text.trim();
                      if (!isAllowedForumLinkHref(candidate)) {
                        setState(() {
                          error =
                              'Enter a valid http(s), mailto:, or /relative link.';
                        });
                        return;
                      }
                      Navigator.of(dialogContext).pop(candidate);
                    },
                    child: const Text('Insert'),
                  ),
                ],
              );
            },
          );
        },
      );
      if (url == null) return;
      controller.value = insertLink(
        _withValidSelection(controller.value),
        url: url,
      );
    } finally {
      urlController.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          icon: const Icon(Icons.format_bold),
          tooltip: 'Bold',
          onPressed: () => _wrap('**'),
        ),
        IconButton(
          icon: const Icon(Icons.format_italic),
          tooltip: 'Italic',
          onPressed: () => _wrap('_'),
        ),
        IconButton(
          icon: const Icon(Icons.code),
          tooltip: 'Inline code',
          onPressed: () => _wrap('`'),
        ),
        IconButton(
          icon: const Icon(Icons.link),
          tooltip: 'Insert link',
          onPressed: () => _showLinkDialog(context),
        ),
        IconButton(
          icon: const Icon(Icons.format_list_bulleted),
          tooltip: 'Bulleted list',
          onPressed: () {
            controller.value = toggleListPrefix(
              _withValidSelection(controller.value),
            );
          },
        ),
      ],
    );
  }
}
