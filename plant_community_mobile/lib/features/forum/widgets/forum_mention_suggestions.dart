import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';

/// The `@word` fragment under the caret of [value]: its span in the text and
/// the prefix typed so far (the part between `@` and the caret).
///
/// Mirrors the server's `MENTION_RE = (?<!\w)@(\w+)` (`mentions.py`): the
/// `@` must not follow a word character (so `me@gmail` is an email, not a
/// mention) and the word is `\w+`. The span runs to the END of the word even
/// when the caret sits inside it, so inserting a suggestion replaces the
/// whole fragment rather than leaving a tail glued to the username.
/// `null` for a non-collapsed selection or when no such fragment exists.
({int start, int end, String prefix})? mentionFragmentAt(
  TextEditingValue value,
) {
  final selection = value.selection;
  if (!selection.isValid || !selection.isCollapsed) return null;
  final text = value.text;
  final caret = selection.baseOffset;
  if (caret < 1 || caret > text.length) return null;

  var start = caret;
  while (start > 0 && _isWordChar(text[start - 1])) {
    start--;
  }
  if (start == 0 || text[start - 1] != '@') return null;
  final at = start - 1;
  if (at > 0 && _isWordChar(text[at - 1])) return null;
  final prefix = text.substring(start, caret);
  if (prefix.isEmpty) return null;

  var end = caret;
  while (end < text.length && _isWordChar(text[end])) {
    end++;
  }
  return (start: at, end: end, prefix: prefix);
}

bool _isWordChar(String ch) => RegExp(r'\w').hasMatch(ch);

/// Replace the fragment [start, end) with `@username ` and park the caret
/// after the trailing space. The mention is PLAIN TEXT — that is what the
/// web posts too (forumMentionNode.ts: the sanitizer keeps only the literal
/// `@username`, the server resolves it). `composing` is cleared like every
/// other hand-rolled controller transform (docs/rules/flutter.md).
TextEditingValue insertMention(
  TextEditingValue value, {
  required int start,
  required int end,
  required String username,
}) {
  final insertion = '@$username ';
  final text = value.text.replaceRange(start, end, insertion);
  return value.copyWith(
    text: text,
    selection: TextSelection.collapsed(offset: start + insertion.length),
    composing: TextRange.empty,
  );
}

/// @mention autocomplete strip for the composer's body field (todo 341 wave
/// 4). Watches [controller]: whenever the caret sits inside an `@word`
/// it asks [MentionSearch] for that prefix (debounced 300 ms, superseded
/// lookups cancelled) and renders up to eight matches; a tap inserts
/// `@username ` in place. Rendered ABOVE the field so it stays visible while
/// the keyboard is up — a popup anchored below a multi-line field would sit
/// under the keyboard.
class ForumMentionSuggestions extends ConsumerStatefulWidget {
  const ForumMentionSuggestions({super.key, required this.controller});

  final TextEditingController controller;

  @override
  ConsumerState<ForumMentionSuggestions> createState() =>
      _ForumMentionSuggestionsState();
}

class _ForumMentionSuggestionsState
    extends ConsumerState<ForumMentionSuggestions> {
  ({int start, int end, String prefix})? _fragment;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    super.dispose();
  }

  void _onChanged() {
    final fragment = mentionFragmentAt(widget.controller.value);
    final previous = _fragment;
    _fragment = fragment;
    final notifier = ref.read(mentionSearchProvider.notifier);
    if (fragment == null) {
      if (previous != null) notifier.clear();
      return;
    }
    if (previous?.prefix != fragment.prefix) notifier.lookup(fragment.prefix);
  }

  void _insert(ForumMentionUser user) {
    final fragment = _fragment;
    if (fragment == null) return;
    widget.controller.value = insertMention(
      widget.controller.value,
      start: fragment.start,
      end: fragment.end,
      username: user.username,
    );
    ref.read(mentionSearchProvider.notifier).clear();
  }

  @override
  Widget build(BuildContext context) {
    final suggestions = ref.watch(mentionSearchProvider);
    if (!suggestions.isActive || suggestions.results.isEmpty) {
      return const SizedBox.shrink();
    }
    final theme = Theme.of(context);
    return Semantics(
      container: true,
      label: 'Mention suggestions',
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
        child: Material(
          color: theme.colorScheme.surfaceContainerHigh,
          borderRadius: BorderRadius.circular(AppSpacing.rSm),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final user in suggestions.results)
                ListTile(
                  dense: true,
                  minTileHeight: 48,
                  leading: const Icon(Icons.alternate_email, size: 18),
                  title: Text('@${user.username}'),
                  subtitle: user.displayName != user.username
                      ? Text(user.displayName)
                      : null,
                  onTap: () => _insert(user),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
