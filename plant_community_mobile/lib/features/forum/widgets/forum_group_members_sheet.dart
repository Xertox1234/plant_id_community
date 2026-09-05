import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../forum_errors.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import 'author_identity.dart';

/// Open the group members sheet (todo 350) for conversation
/// [conversationId]. Resolves `true` when the viewer LEFT the group — the
/// caller pops the thread and tells the user; `null`/`false` otherwise.
///
/// Gating mirrors the contract: "Remove" only when `can_manage` and never
/// for yourself (the creator, who is the only manager, cannot leave while
/// others remain); "Add member" only when `can_manage`, disabled at the cap;
/// "Leave group" only for non-creators.
Future<bool?> showForumGroupMembersSheet(
  BuildContext context, {
  required int conversationId,
  required String? myUsername,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => ForumGroupMembersSheet(
      conversationId: conversationId,
      myUsername: myUsername,
    ),
  );
}

/// The members list itself; public so tests can pump it directly.
class ForumGroupMembersSheet extends ConsumerStatefulWidget {
  const ForumGroupMembersSheet({
    super.key,
    required this.conversationId,
    required this.myUsername,
  });

  final int conversationId;

  /// The signed-in username, or `null` while the account profile is still
  /// loading — in which case no self-targeting action is offered.
  final String? myUsername;

  @override
  ConsumerState<ForumGroupMembersSheet> createState() =>
      _ForumGroupMembersSheetState();
}

class _ForumGroupMembersSheetState
    extends ConsumerState<ForumGroupMembersSheet> {
  /// Re-entrancy guard shared by add / remove / leave.
  bool _busy = false;

  GroupConversationThread get _notifier =>
      ref.read(groupConversationThreadProvider(widget.conversationId).notifier);

  void _notice(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _run(
    Future<void> Function() action, {
    required String fallback,
    required String forbidden,
  }) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await action();
    } catch (e) {
      _notice(forumErrorMessage(e, fallback: fallback, forbidden: forbidden));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addMember() async {
    final username = await showDialog<String>(
      context: context,
      builder: (_) => const _AddMemberDialog(),
    );
    if (username == null || username.isEmpty || !mounted) return;
    await _run(
      () => _notifier.addMember(username),
      fallback: 'Could not add that member.',
      forbidden: 'Only the group creator can add members.',
    );
  }

  Future<void> _removeMember(ForumAuthor member) => _run(
    () => _notifier.removeMember(member.username),
    fallback: 'Could not remove ${member.name}.',
    forbidden: 'Only the group creator can remove members.',
  );

  /// Leave after an explicit confirmation — the same `showDialog<bool>`
  /// shape Block uses on the profile screen, for the same reason: it is
  /// hard to reverse (only a member can add you back), so a mis-tap in a
  /// sheet full of other buttons must not act.
  Future<void> _leave(String me) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Leave this group?'),
        content: const Text(
          "You'll stop receiving its messages and it leaves your inbox. "
          'Someone still in the group has to add you back to rejoin.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Leave'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    var left = false;
    await _run(
      () async {
        await _notifier.leave(me);
        left = true;
      },
      fallback: 'Could not leave the group.',
      forbidden: "You can't leave this group.",
    );
    if (left && mounted) Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final row = ref
        .watch(groupConversationThreadProvider(widget.conversationId))
        .asData
        ?.value
        .conversation;
    final me = widget.myUsername;
    final participants = row?.participants ?? const <ForumAuthor>[];
    final creator = row?.createdBy?.username;
    final canManage = row?.canManage ?? false;
    final atCapacity = row?.isAtCapacity ?? true;
    final count = row?.participantCount ?? participants.length;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Members',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '$count of $forumGroupMaxParticipants',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              for (final member in participants)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: AuthorAvatar(author: member, radius: 18),
                  title: Text(
                    member.username == me
                        ? '${member.name} (you)'
                        : member.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: member.username == creator
                      ? const Text('Creator')
                      : null,
                  // Never yourself, never the creator (the creator is the
                  // only manager, so both guards hold even while `me` is
                  // still unknown).
                  trailing:
                      canManage &&
                          member.username != me &&
                          member.username != creator
                      ? TextButton(
                          onPressed: _busy ? null : () => _removeMember(member),
                          child: const Text('Remove'),
                        )
                      : null,
                ),
              if (canManage) ...[
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  height: 48,
                  child: FilledButton.tonalIcon(
                    onPressed: _busy || atCapacity ? null : _addMember,
                    icon: const Icon(Icons.person_add_alt_1),
                    label: const Text('Add member'),
                  ),
                ),
                if (atCapacity)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.xs),
                    child: Text(
                      'This group is full.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
              ] else if (row != null && me != null) ...[
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  height: 48,
                  child: TextButton.icon(
                    style: TextButton.styleFrom(
                      foregroundColor: theme.colorScheme.error,
                    ),
                    onPressed: _busy ? null : () => _leave(me),
                    icon: const Icon(Icons.logout),
                    label: const Text('Leave group'),
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

class _AddMemberDialog extends StatefulWidget {
  const _AddMemberDialog();

  @override
  State<_AddMemberDialog> createState() => _AddMemberDialogState();
}

class _AddMemberDialogState extends State<_AddMemberDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final username = _controller.text.trim().replaceFirst(RegExp(r'^@'), '');
    if (username.isEmpty) return;
    Navigator.of(context).pop(username);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add member'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        autocorrect: false,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _submit(),
        decoration: const InputDecoration(
          labelText: 'Username',
          prefixText: '@',
          border: OutlineInputBorder(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Add')),
      ],
    );
  }
}
