import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../models/models.dart';
import '../services/forum_api.dart';
import '../services/forum_composer_controller.dart';
import '../widgets/forum_notice_banner.dart';

/// Which kind of content the composer creates.
enum ForumComposeMode { topic, reply }

/// Navigation arguments for [ForumComposerScreen], passed as go_router `extra`.
class ForumComposeArgs {
  const ForumComposeArgs.topic({required this.boardSlug, this.boardTitle})
    : mode = ForumComposeMode.topic,
      topicId = null;

  const ForumComposeArgs.reply({required this.topicId})
    : mode = ForumComposeMode.reply,
      boardSlug = null,
      boardTitle = null;

  final ForumComposeMode mode;
  final String? boardSlug;
  final String? boardTitle;
  final int? topicId;
}

/// Compose a new topic or a reply. Holds one [ForumComposerController] for the
/// screen's lifetime, so every retry of a failed submit reuses the same
/// `Idempotency-Key` and the backend replays rather than duplicating. Pops
/// `true` when content is published (caller refreshes); handles the
/// pending-moderation ("notify-and-return") outcome inline.
class ForumComposerScreen extends ConsumerStatefulWidget {
  const ForumComposerScreen({super.key, required this.args});

  final ForumComposeArgs args;

  @override
  ConsumerState<ForumComposerScreen> createState() =>
      _ForumComposerScreenState();
}

class _ForumComposerScreenState extends ConsumerState<ForumComposerScreen> {
  late final ForumComposerController _controller;
  final _titleController = TextEditingController();
  final _bodyController = TextEditingController();

  bool _submitting = false;
  bool _pending = false;
  String? _error;

  bool get _isTopic => widget.args.mode == ForumComposeMode.topic;

  @override
  void initState() {
    super.initState();
    _controller = ForumComposerController(api: ref.read(forumApiProvider));
  }

  @override
  void dispose() {
    _titleController.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  bool get _canSubmit {
    if (_bodyController.text.trim().isEmpty) return false;
    if (_isTopic && _titleController.text.trim().isEmpty) return false;
    return true;
  }

  Future<void> _submit() async {
    if (!_canSubmit || _submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final ForumModerationStatus status;
      if (_isTopic) {
        final result = await _controller.submitTopic(
          boardSlug: widget.args.boardSlug!,
          title: _titleController.text,
          bodyText: _bodyController.text,
        );
        status = result.status;
      } else {
        final result = await _controller.submitReply(
          topicId: widget.args.topicId!,
          bodyText: _bodyController.text,
        );
        status = result.status;
      }
      if (!mounted) return;
      if (status.isPending) {
        setState(() {
          _submitting = false;
          _pending = true;
        });
      } else {
        Navigator.of(context).pop(true);
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = e.statusCode == 409
            ? 'Still processing your last attempt — tap Post again to retry.'
            : e.message;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _error = 'Something went wrong. Tap Post to retry.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    final title = _isTopic ? 'New topic' : 'Reply';

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: !isAuthenticated
              ? _LoginPrompt(action: _isTopic ? 'start a topic' : 'reply')
              : _pending
              ? _PendingView(isTopic: _isTopic)
              : _form(context),
        ),
      ),
    );
  }

  Widget _form(BuildContext context) {
    return ListView(
      children: [
        if (widget.args.boardTitle != null)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Text(
              'in ${widget.args.boardTitle}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: ForumNoticeBanner(
              message: _error!,
              icon: Icons.error_outline,
            ),
          ),
        if (_isTopic) ...[
          TextField(
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: 'Title',
              border: OutlineInputBorder(),
            ),
            textInputAction: TextInputAction.next,
            maxLength: 255,
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        TextField(
          controller: _bodyController,
          decoration: InputDecoration(
            labelText: _isTopic ? 'Body' : 'Your reply',
            alignLabelWithHint: true,
            border: const OutlineInputBorder(),
          ),
          minLines: 5,
          maxLines: 12,
          onChanged: (_) => setState(() {}),
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton(
          onPressed: _canSubmit && !_submitting ? _submit : null,
          child: _submitting
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Post'),
        ),
      ],
    );
  }
}

class _PendingView extends StatelessWidget {
  const _PendingView({required this.isTopic});
  final bool isTopic;

  @override
  Widget build(BuildContext context) {
    final what = isTopic ? 'topic' : 'reply';
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        ForumNoticeBanner(
          message:
              'Your $what was submitted and is awaiting moderation. It will '
              'appear once approved.',
        ),
        const SizedBox(height: AppSpacing.md),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Done'),
        ),
      ],
    );
  }
}

class _LoginPrompt extends StatelessWidget {
  const _LoginPrompt({required this.action});
  final String action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        'Log in to $action.',
        style: Theme.of(context).textTheme.bodyLarge,
        textAlign: TextAlign.center,
      ),
    );
  }
}
