import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/user_profile_service.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import '../widgets/author_identity.dart';
import '../widgets/forum_group_members_sheet.dart';
import '../widgets/forum_report_sheet.dart';

/// Backend `MESSAGE_BODY_MAX_CHARS` (`wagtail_forum/models/messages.py`).
/// Enforced client-side too so the composer can't submit a body the server
/// would reject with a 400.
const int forumMessageMaxChars = 4000;

/// A DM thread: messages oldest → newest, own messages right-aligned,
/// "Load older" at the top, a plain-text composer at the bottom.
/// Long-pressing another member's message opens the report sheet.
///
/// Two modes, exactly one of which is set:
/// * [username] — a 1:1 thread with that member (todo 339), sent through
///   the username endpoint (it creates the conversation on first send);
/// * [conversationId] — a group thread (todo 350): the group's title in the
///   app bar, a members sheet, every message attributed to its sender, and
///   sends through the by-id endpoint.
class ForumConversationScreen extends ConsumerStatefulWidget {
  const ForumConversationScreen({super.key, this.username, this.conversationId})
    : assert(
        (username == null) != (conversationId == null),
        'Pass exactly one of username (direct) or conversationId (group)',
      );

  final String? username;
  final int? conversationId;

  bool get isGroup => conversationId != null;

  @override
  ConsumerState<ForumConversationScreen> createState() =>
      _ForumConversationScreenState();
}

class _ForumConversationScreenState
    extends ConsumerState<ForumConversationScreen> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onTextChanged() {
    final hasText = _controller.text.trim().isNotEmpty;
    if (hasText != _hasText) setState(() => _hasText = hasText);
  }

  String get _username => widget.username ?? '';

  AsyncValue<ConversationThreadState> _watchThread() {
    final id = widget.conversationId;
    return id != null
        ? ref.watch(groupConversationThreadProvider(id))
        : ref.watch(conversationThreadProvider(_username));
  }

  void _invalidateThread() {
    final id = widget.conversationId;
    if (id != null) {
      ref.invalidate(groupConversationThreadProvider(id));
    } else {
      ref.invalidate(conversationThreadProvider(_username));
    }
  }

  Future<void> _loadOlder() {
    final id = widget.conversationId;
    return id != null
        ? ref.read(groupConversationThreadProvider(id).notifier).loadOlder()
        : ref.read(conversationThreadProvider(_username).notifier).loadOlder();
  }

  /// Groups send by id; a direct thread keeps the username route (which is
  /// what creates the conversation on the first message).
  Future<void> _sendBody(String body) {
    final id = widget.conversationId;
    return id != null
        ? ref.read(groupConversationThreadProvider(id).notifier).send(body)
        : ref.read(conversationThreadProvider(_username).notifier).send(body);
  }

  @override
  Widget build(BuildContext context) {
    final isGroup = widget.isGroup;
    final threadAsync = _watchThread();
    final thread = threadAsync.asData?.value;
    final conversation = thread?.conversation;
    final other = conversation?.otherParticipant;
    final title = isGroup
        ? (conversation?.title ?? 'Group')
        : (other?.name ?? _username);
    // Who "I" am, for attributing group messages. Only a group needs the
    // account profile (a 1:1 thread infers "mine" from the two parties), so
    // the watch is scoped to that mode.
    final meAsync = isGroup ? ref.watch(userProfileServiceProvider) : null;
    // `asData` keeps the previously resolved value across a later re-fetch,
    // so this is null only before the FIRST resolve — no separate cache is
    // needed to stop a refresh flipping my messages to the other side.
    final me = meAsync?.asData?.value?.username;
    // Attribution is unknowable until that first resolve, and guessing would
    // paint my own messages on the wrong side for a frame. A FAILED profile
    // still renders (everything as theirs — the safe direction, since the
    // report affordance survives); only the loading window holds the list.
    final awaitingMe = isGroup && me == null && (meAsync?.isLoading ?? false);
    final isSending = thread?.isSending ?? false;
    final isUnavailable = thread?.isUnavailable ?? false;
    final canSend = _hasText && !isSending && thread != null && !isUnavailable;

    return Scaffold(
      appBar: AppBar(
        title: isGroup
            ? Text(title, maxLines: 1, overflow: TextOverflow.ellipsis)
            : Tooltip(
                message: 'View profile',
                child: InkWell(
                  borderRadius: BorderRadius.circular(AppSpacing.rXs),
                  onTap: () => context.pushNamed(
                    'forumUserProfile',
                    pathParameters: {'username': _username},
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.xs,
                      vertical: AppSpacing.xs,
                    ),
                    child: Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ),
        actions: [
          if (isGroup)
            IconButton(
              tooltip: 'Members',
              icon: const Icon(Icons.group_outlined),
              onPressed: conversation == null
                  ? null
                  : () => _openMembers(myUsername: me),
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: awaitingMe
                  ? const Center(child: CircularProgressIndicator())
                  : threadAsync.when(
                      loading: () =>
                          const Center(child: CircularProgressIndicator()),
                      error: (error, _) => _ErrorRetry(
                        message: 'Could not load this conversation.',
                        onRetry: _invalidateThread,
                      ),
                      data: (thread) {
                        if (thread.isUnavailable) {
                          // The by-id GET 404'd — I was removed, or the group is
                          // gone. Retry re-fetches: a member re-added since gets
                          // the thread back without leaving the screen.
                          return _ErrorRetry(
                            message: 'This group could not be found.',
                            onRetry: _invalidateThread,
                          );
                        }
                        final otherUsername =
                            thread.conversation?.otherParticipant?.username ??
                            _username;
                        return _MessageList(
                          thread: thread,
                          emptyText: isGroup
                              ? 'No messages yet. Say hello to the group.'
                              : 'No messages yet. Say hello to $title.',
                          showSender: isGroup,
                          isMine: isGroup
                              // Fail toward "theirs" until the profile resolves.
                              ? (m) => me != null && m.sender.username == me
                              // Anything not from the other participant is mine:
                              // a 1:1 thread has exactly two senders, and the
                              // route/conversation names one. A `[deleted]`
                              // sentinel sender is never mine, so the report
                              // affordance survives a malformed payload.
                              : (m) =>
                                    !m.sender.isDeleted &&
                                    m.sender.username != otherUsername,
                          onLoadOlder: _loadOlder,
                          onReport: _openReport,
                        );
                      },
                    ),
            ),
            _Composer(
              controller: _controller,
              canSend: canSend,
              isSending: isSending,
              onSend: _send,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _send() async {
    final body = _controller.text;
    final isGroup = widget.isGroup;
    try {
      await _sendBody(body);
      if (mounted) _controller.clear();
    } on ApiException catch (e) {
      if (!mounted) return;
      // 403 = blocked pair (direct) / not a member or a block-paired member
      // (group); 400 = empty / spam-screened, whose message is the
      // backend's own reason (surfaced verbatim, like the composer's 409
      // handling); 404 = the member / group no longer exists.
      final text = switch (e.statusCode) {
        403 =>
          isGroup
              ? "You can't message this group."
              : "You can't message this member.",
        400 => e.message,
        404 =>
          isGroup
              ? 'This group could not be found.'
              : 'This member could not be found.',
        _ => 'Could not send your message.',
      };
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not send your message.')),
      );
    }
  }

  Future<void> _openMembers({required String? myUsername}) async {
    final id = widget.conversationId;
    if (id == null) return;
    final left = await showForumGroupMembersSheet(
      context,
      conversationId: id,
      myUsername: myUsername,
    );
    if (left != true || !mounted) return;
    // The SnackBar outlives this route: the root ScaffoldMessenger carries
    // it onto the inbox underneath.
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('You left the group.')));
    Navigator.of(context).pop();
  }

  Future<void> _openReport(ForumDirectMessage message) async {
    final choice = await showForumReportSheet(
      context,
      title: 'Report message',
      prompt: 'Why are you reporting this message?',
    );
    if (choice == null || !mounted) return;
    try {
      await ref
          .read(forumApiProvider)
          .reportMessage(
            messageId: message.id,
            reason: choice.reason,
            detail: choice.detail,
            idempotencyKey: const Uuid().v4(),
          );
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Reported')));
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(e.message)));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not send your report.')),
      );
    }
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({
    required this.thread,
    required this.emptyText,
    required this.showSender,
    required this.isMine,
    required this.onLoadOlder,
    required this.onReport,
  });

  final ConversationThreadState thread;
  final String emptyText;

  /// Group threads attribute every other member's message with their
  /// avatar and name; a 1:1 thread's bubbles need no attribution.
  final bool showSender;
  final bool Function(ForumDirectMessage) isMine;
  final Future<void> Function() onLoadOlder;
  final void Function(ForumDirectMessage) onReport;

  @override
  Widget build(BuildContext context) {
    final messages = thread.messages;
    if (messages.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Text(
            emptyText,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }
    // `reverse: true` keeps the newest message pinned to the bottom (chat
    // convention) and opens scrolled there; index 0 is the LAST message, so
    // "Load older" — the final index — lands at the visual top.
    return ListView.builder(
      reverse: true,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      itemCount: messages.length + (thread.hasOlder ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= messages.length) {
          return _LoadOlderButton(
            isLoading: thread.isLoadingOlder,
            onLoadOlder: onLoadOlder,
          );
        }
        final message = messages[messages.length - 1 - index];
        final mine = isMine(message);
        return _MessageBubble(
          message: message,
          isMine: mine,
          showSender: showSender && !mine,
          onReport: mine ? null : () => onReport(message),
        );
      },
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.isMine,
    this.showSender = false,
    this.onReport,
  });

  final ForumDirectMessage message;
  final bool isMine;

  /// Lead with the sender's avatar and name (group threads, others' only).
  final bool showSender;

  /// Long-press handler; `null` for own messages (you can't report yourself).
  final VoidCallback? onReport;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final bubbleColor = isMine
        ? scheme.primaryContainer
        : scheme.surfaceContainerHighest;
    final textColor = isMine ? scheme.onPrimaryContainer : scheme.onSurface;
    final radius = BorderRadius.only(
      topLeft: const Radius.circular(AppSpacing.rMd),
      topRight: const Radius.circular(AppSpacing.rMd),
      bottomLeft: Radius.circular(isMine ? AppSpacing.rMd : AppSpacing.rXs),
      bottomRight: Radius.circular(isMine ? AppSpacing.rXs : AppSpacing.rMd),
    );
    final time = forumRelativeTime(message.createdAt);

    final bubble = Column(
      crossAxisAlignment: isMine
          ? CrossAxisAlignment.end
          : CrossAxisAlignment.start,
      children: [
        if (showSender)
          Padding(
            padding: const EdgeInsets.only(
              left: AppSpacing.xs,
              bottom: AppSpacing.xs,
            ),
            child: Text(
              message.sender.name,
              style: theme.textTheme.labelMedium?.copyWith(
                color: scheme.onSurfaceVariant,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        Material(
          color: bubbleColor,
          borderRadius: radius,
          child: InkWell(
            borderRadius: radius,
            onLongPress: onReport,
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm + AppSpacing.xs,
              ),
              child: Text(
                message.body,
                style: theme.textTheme.bodyMedium?.copyWith(color: textColor),
              ),
            ),
          ),
        ),
        if (time.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(
              top: AppSpacing.xs,
              left: AppSpacing.xs,
              right: AppSpacing.xs,
            ),
            child: Text(
              time,
              style: theme.textTheme.labelSmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ),
      ],
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Align(
        alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.78,
          ),
          child: showSender
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AuthorAvatar(author: message.sender, radius: 14),
                    const SizedBox(width: AppSpacing.sm),
                    Flexible(child: bubble),
                  ],
                )
              : bubble,
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.canSend,
    required this.isSending,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool canSend;
  final bool isSending;
  final Future<void> Function() onSend;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      color: theme.colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.sm,
          AppSpacing.sm,
          AppSpacing.sm,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                minLines: 1,
                maxLines: 5,
                maxLength: forumMessageMaxChars,
                textCapitalization: TextCapitalization.sentences,
                textInputAction: TextInputAction.newline,
                // A counter under a chat field is noise until the limit is
                // actually near; show it only for the last stretch.
                buildCounter:
                    (
                      context, {
                      required currentLength,
                      required isFocused,
                      maxLength,
                    }) {
                      if (maxLength == null ||
                          currentLength < maxLength - 500) {
                        return null;
                      }
                      return Text(
                        '$currentLength / $maxLength',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      );
                    },
                decoration: InputDecoration(
                  hintText: 'Message',
                  isDense: true,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(AppSpacing.rLg),
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm + AppSpacing.xs,
                  ),
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            if (isSending)
              const SizedBox(
                width: 48,
                height: 48,
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else
              IconButton.filled(
                tooltip: 'Send',
                onPressed: canSend ? onSend : null,
                icon: const Icon(Icons.send),
              ),
          ],
        ),
      ),
    );
  }
}

class _LoadOlderButton extends StatelessWidget {
  const _LoadOlderButton({required this.isLoading, required this.onLoadOlder});
  final bool isLoading;
  final Future<void> Function() onLoadOlder;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Center(
        child: isLoading
            ? const CircularProgressIndicator()
            : OutlinedButton(
                onPressed: () async {
                  try {
                    await onLoadOlder();
                  } catch (_) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Could not load older messages.'),
                        ),
                      );
                    }
                  }
                },
                child: const Text('Load older'),
              ),
      ),
    );
  }
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message),
          const SizedBox(height: AppSpacing.sm),
          OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
