import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../forum_format.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import '../widgets/forum_report_sheet.dart';

/// Backend `MESSAGE_BODY_MAX_CHARS` (`wagtail_forum/models/messages.py`).
/// Enforced client-side too so the composer can't submit a body the server
/// would reject with a 400.
const int forumMessageMaxChars = 4000;

/// A 1:1 DM thread with [username] (todo 339): messages oldest → newest,
/// own messages right-aligned, "Load older" at the top, a plain-text
/// composer at the bottom. Long-pressing the other member's message opens
/// the report sheet.
class ForumConversationScreen extends ConsumerStatefulWidget {
  const ForumConversationScreen({super.key, required this.username});

  final String username;

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

  @override
  Widget build(BuildContext context) {
    final threadAsync = ref.watch(conversationThreadProvider(widget.username));
    final thread = threadAsync.asData?.value;
    final other = thread?.conversation?.otherParticipant;
    final title = other?.name ?? widget.username;
    final isSending = thread?.isSending ?? false;
    final canSend = _hasText && !isSending && thread != null;

    return Scaffold(
      appBar: AppBar(
        title: Tooltip(
          message: 'View profile',
          child: InkWell(
            borderRadius: BorderRadius.circular(AppSpacing.rXs),
            onTap: () => context.pushNamed(
              'forumUserProfile',
              pathParameters: {'username': widget.username},
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.xs,
                vertical: AppSpacing.xs,
              ),
              child: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: threadAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => _ErrorRetry(
                  message: 'Could not load this conversation.',
                  onRetry: () => ref.invalidate(
                    conversationThreadProvider(widget.username),
                  ),
                ),
                data: (thread) => _MessageList(
                  thread: thread,
                  otherUsername:
                      thread.conversation?.otherParticipant.username ??
                      widget.username,
                  otherName: title,
                  onLoadOlder: () => ref
                      .read(
                        conversationThreadProvider(widget.username).notifier,
                      )
                      .loadOlder(),
                  onReport: _openReport,
                ),
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
    try {
      await ref
          .read(conversationThreadProvider(widget.username).notifier)
          .send(body);
      if (mounted) _controller.clear();
    } on ApiException catch (e) {
      if (!mounted) return;
      // 403 = blocked pair; 400 = empty / spam-screened, whose message is
      // the backend's own reason (surfaced verbatim, like the composer's
      // 409 handling); 404 = the member no longer exists.
      final text = switch (e.statusCode) {
        403 => "You can't message this member.",
        400 => e.message,
        404 => 'This member could not be found.',
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
    required this.otherUsername,
    required this.otherName,
    required this.onLoadOlder,
    required this.onReport,
  });

  final ConversationThreadState thread;
  final String otherUsername;
  final String otherName;
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
            'No messages yet. Say hello to $otherName.',
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
        // Anything not from the other participant is mine: a 1:1 thread
        // has exactly two senders, and the route/conversation names one.
        // Two-party inference (the serializer carries no is_mine on a
        // message). Fail toward "theirs": a `[deleted]` sentinel sender is
        // never mine, so the report affordance survives a malformed payload.
        final isMine =
            !message.sender.isDeleted &&
            message.sender.username != otherUsername;
        return _MessageBubble(
          message: message,
          isMine: isMine,
          onReport: isMine ? null : () => onReport(message),
        );
      },
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.isMine,
    this.onReport,
  });

  final ForumDirectMessage message;
  final bool isMine;

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

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Align(
        alignment: isMine ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.78,
          ),
          child: Column(
            crossAxisAlignment: isMine
                ? CrossAxisAlignment.end
                : CrossAxisAlignment.start,
            children: [
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
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: textColor,
                      ),
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
          ),
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
