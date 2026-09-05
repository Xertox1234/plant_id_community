import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/user_profile_service.dart';
import '../forum_errors.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import 'forum_conversation_screen.dart' show forumMessageMaxChars;

/// Compose a new group DM (todo 350): a title, 2–7 members as username
/// chips (typed, or picked from the username-prefix search the @mention
/// autocomplete already uses), and the first message — the backend creates
/// the group and sends that message in one request. On success the screen
/// is REPLACED by the new thread so back returns to the inbox.
class ForumNewGroupScreen extends ConsumerStatefulWidget {
  const ForumNewGroupScreen({super.key});

  @override
  ConsumerState<ForumNewGroupScreen> createState() =>
      _ForumNewGroupScreenState();
}

class _ForumNewGroupScreenState extends ConsumerState<ForumNewGroupScreen> {
  final _titleController = TextEditingController();
  final _memberController = TextEditingController();
  final _bodyController = TextEditingController();
  final List<String> _members = [];

  /// Why the last "Add" did nothing, shown under the field as the input's
  /// error. Cleared on the next keystroke and on a successful add — a chip
  /// silently failing to appear reads as a broken button.
  String? _memberNotice;

  /// The signed-in username, refreshed from the account profile on every
  /// build (null while it loads — then the self-check simply doesn't fire,
  /// and the backend still ignores me server-side).
  String? _me;

  /// Re-entrancy guard: a second tap while the create is in flight is a no-op
  /// (the server would replay the same key anyway, but the UI shouldn't ask).
  bool _submitting = false;

  /// One `Idempotency-Key` per composed group, reused across retries of the
  /// SAME payload and rotated when it changes (docs/rules/flutter.md).
  String? _key;
  String? _fingerprint;

  @override
  void initState() {
    super.initState();
    _titleController.addListener(_refresh);
    _bodyController.addListener(_refresh);
    _memberController.addListener(_onMemberTextChanged);
  }

  @override
  void dispose() {
    _titleController.removeListener(_refresh);
    _bodyController.removeListener(_refresh);
    _memberController.removeListener(_onMemberTextChanged);
    _titleController.dispose();
    _memberController.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  void _refresh() => setState(() {});

  void _onMemberTextChanged() {
    if (_memberNotice != null) setState(() => _memberNotice = null);
    ref
        .read(mentionSearchProvider.notifier)
        .lookup(_normalize(_memberController.text));
  }

  static String _normalize(String raw) =>
      raw.trim().replaceFirst(RegExp(r'^@'), '');

  bool get _atCapacity => _members.length >= forumGroupMaxOthers;

  bool get _canSubmit =>
      !_submitting &&
      _titleController.text.trim().isNotEmpty &&
      _members.length >= forumGroupMinOthers &&
      _members.length <= forumGroupMaxOthers &&
      _bodyController.text.trim().isNotEmpty;

  void _addMember(String raw) {
    final username = _normalize(raw);
    if (username.isEmpty || _atCapacity) return;
    final me = _me;
    if (me != null && username.toLowerCase() == me.toLowerCase()) {
      // The backend drops me from `usernames` silently; say so instead of
      // letting the tap look broken.
      setState(() => _memberNotice = "That's you.");
      return;
    }
    if (_members.contains(username)) {
      setState(() => _memberNotice = 'Already added.');
      return;
    }
    setState(() {
      _members.add(username);
      _memberNotice = null;
    });
    _memberController.clear();
    ref.read(mentionSearchProvider.notifier).clear();
  }

  void _removeMember(String username) {
    setState(() => _members.remove(username));
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    final title = _titleController.text.trim();
    final usernames = List<String>.unmodifiable(_members);
    final body = _bodyController.text.trim();
    final fingerprint = '$title|${usernames.join(',')}|$body';
    if (_key == null || _fingerprint != fingerprint) {
      _key = const Uuid().v4();
      _fingerprint = fingerprint;
    }
    final key = _key;
    if (key == null) return;
    setState(() => _submitting = true);
    try {
      final row = await ref
          .read(forumApiProvider)
          .createGroupConversation(
            title: title,
            usernames: usernames,
            body: body,
            idempotencyKey: key,
          );
      _key = null;
      _fingerprint = null;
      // The inbox underneath (if mounted) gets the new row at the top —
      // spliced, never invalidated, so its loaded pages survive.
      if (ref.exists(conversationsFeedProvider)) {
        ref.read(conversationsFeedProvider.notifier).applyActivity(row);
      }
      if (!mounted) return;
      context.pushReplacementNamed(
        'forumGroupConversation',
        pathParameters: {'id': '${row.id}'},
      );
    } catch (e) {
      if (!mounted) return;
      // The form stays intact: 400 is the server's one generic sentence
      // ("One of the members cannot be added." — deliberately no oracle),
      // 429 the shared rate-limit line.
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            forumErrorMessage(e, fallback: 'Could not create the group.'),
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Watched (not read on demand): the provider has to be mounted and
    // resolved before `_addMember` can compare against it.
    _me = ref.watch(userProfileServiceProvider).asData?.value?.username;
    final suggestions = ref.watch(mentionSearchProvider);
    final visibleSuggestions = [
      for (final user in suggestions.results)
        if (!_members.contains(user.username)) user,
    ];
    final memberHint = _atCapacity
        ? 'Groups hold up to $forumGroupMaxParticipants people including you.'
        : 'Add $forumGroupMinOthers to $forumGroupMaxOthers members '
              '(${_members.length} added).';

    return Scaffold(
      appBar: AppBar(title: const Text('New group')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            TextField(
              controller: _titleController,
              maxLength: forumGroupTitleMaxChars,
              textCapitalization: TextCapitalization.sentences,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Group name',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              'Members',
              style: theme.textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w700,
              ),
            ),
            if (_members.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final username in _members)
                    InputChip(
                      label: Text('@$username'),
                      onDeleted: _submitting
                          ? null
                          : () => _removeMember(username),
                    ),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _memberController,
              enabled: !_atCapacity && !_submitting,
              autocorrect: false,
              textInputAction: TextInputAction.done,
              onSubmitted: _addMember,
              decoration: InputDecoration(
                labelText: 'Add member',
                prefixText: '@',
                errorText: _memberNotice,
                helperText: memberHint,
                helperMaxLines: 2,
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: 'Add',
                  onPressed: _atCapacity || _submitting
                      ? null
                      : () => _addMember(_memberController.text),
                  icon: const Icon(Icons.add),
                ),
              ),
            ),
            if (suggestions.isActive && visibleSuggestions.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.sm),
                child: Material(
                  color: theme.colorScheme.surfaceContainerHigh,
                  borderRadius: BorderRadius.circular(AppSpacing.rSm),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final user in visibleSuggestions)
                        ListTile(
                          dense: true,
                          minTileHeight: 48,
                          leading: const Icon(Icons.alternate_email, size: 18),
                          title: Text('@${user.username}'),
                          subtitle: user.displayName != user.username
                              ? Text(user.displayName)
                              : null,
                          onTap: () => _addMember(user.username),
                        ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.md),
            TextField(
              controller: _bodyController,
              enabled: !_submitting,
              minLines: 3,
              maxLines: 8,
              maxLength: forumMessageMaxChars,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'First message',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            SizedBox(
              height: 48,
              child: FilledButton.icon(
                onPressed: _canSubmit ? _submit : null,
                icon: _submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.group_add),
                label: const Text('Create group'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
