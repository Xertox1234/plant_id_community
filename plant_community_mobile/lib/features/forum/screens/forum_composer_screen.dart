import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants/app_spacing.dart';
import '../../../services/api_service.dart';
import '../../../services/auth_service.dart';
import '../models/forum_rich_text_markup.dart';
import '../models/models.dart';
import '../services/forum_api.dart';
import '../services/forum_composer_controller.dart';
import '../services/forum_image_picker.dart';
import '../widgets/forum_mention_suggestions.dart';
import '../widgets/forum_notice_banner.dart';
import '../widgets/forum_rich_text_toolbar.dart';

/// Which kind of content the composer creates.
enum ForumComposeMode { topic, reply, edit }

/// Navigation arguments for [ForumComposerScreen], passed as go_router `extra`.
class ForumComposeArgs {
  const ForumComposeArgs.topic({required this.boardSlug, this.boardTitle})
    : mode = ForumComposeMode.topic,
      topicId = null,
      postId = null,
      initialBodyText = '',
      hasNonTextContent = false,
      quoteText = null;

  /// Reply to [topicId]. [quoteText] (the "Quote" action, todo 341 wave 3)
  /// pre-fills a read-only `quote` block above the body field — it is sent
  /// as a real `quote` block, never folded into the paragraph.
  const ForumComposeArgs.reply({required this.topicId, this.quoteText})
    : mode = ForumComposeMode.reply,
      boardSlug = null,
      boardTitle = null,
      postId = null,
      initialBodyText = '',
      hasNonTextContent = false;

  /// Edit an existing post (todo 292). [parseForumRichHtmlToMarkup] is tried
  /// first (todo 314): when the body is a single paragraph block whose HTML
  /// is within the five-mark grammar it emits, [initialBodyText] is the
  /// reconstructed marker text and the post opens fully rich-editable — a
  /// deliberate side effect is that a web-authored post using only those
  /// five marks becomes editable here too (nothing new is trusted: the
  /// server re-sanitizes on every save regardless of origin). Anything
  /// outside that grammar falls back to the existing plain-text logic,
  /// unchanged: a body that isn't exactly one plain-text paragraph block
  /// cannot be pre-filled without losing content, so [initialBodyText] is
  /// left empty and [hasNonTextContent] is true, so the screen can warn
  /// rather than silently discard it on submit.
  factory ForumComposeArgs.edit({required ForumPost post}) {
    final body = post.body;
    if (body.length == 1 && body.first is ParagraphBlock) {
      final markup = parseForumRichHtmlToMarkup(
        (body.first as ParagraphBlock).html,
      );
      if (markup != null) {
        return ForumComposeArgs._edit(
          postId: post.id,
          initialBodyText: markup,
          hasNonTextContent: false,
        );
      }
    }
    final singleParagraph = isSingleEditableParagraph(body);
    return ForumComposeArgs._edit(
      postId: post.id,
      initialBodyText: singleParagraph
          ? plainTextFromParagraphHtml((body.first as ParagraphBlock).html)
          : '',
      hasNonTextContent: !singleParagraph,
    );
  }

  const ForumComposeArgs._edit({
    required this.postId,
    required this.initialBodyText,
    required this.hasNonTextContent,
  }) : mode = ForumComposeMode.edit,
       boardSlug = null,
       boardTitle = null,
       topicId = null,
       quoteText = null;

  final ForumComposeMode mode;
  final String? boardSlug;
  final String? boardTitle;
  final int? topicId;
  final int? postId;
  final String initialBodyText;
  final bool hasNonTextContent;
  final String? quoteText;
}

/// Compose a new topic or a reply. Holds one [ForumComposerController] for the
/// screen's lifetime, so every retry of a failed submit reuses the same
/// `Idempotency-Key` and the backend replays rather than duplicating. Pops
/// `true` when content is published (caller refreshes); handles the
/// pending-moderation ("notify-and-return") outcome inline.
class ForumComposerScreen extends ConsumerStatefulWidget {
  const ForumComposerScreen({
    super.key,
    required this.args,
    this.imagePicker = const DeviceForumImagePicker(),
  });

  final ForumComposeArgs args;

  /// Wrapped behind an interface so tests can inject a fake without touching
  /// platform channels — see `forum_image_picker.dart`.
  final ForumImagePicker imagePicker;

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

  // Image attachment (todo 294) — topic/reply only, not edit (todo 292's
  // text-first edit scope is unchanged here).
  ForumImageBlock? _attachedImage;
  bool _uploadingImage = false;
  String? _imageError;

  /// The pre-filled quote (reply mode, todo 341 wave 3), removable with one
  /// tap. Not counted as unsent input: the user never typed it and the
  /// Quote action recreates it in one tap.
  String? _quoteText;

  bool get _isTopic => widget.args.mode == ForumComposeMode.topic;
  bool get _isEdit => widget.args.mode == ForumComposeMode.edit;
  bool get _supportsImage => !_isEdit;

  @override
  void initState() {
    super.initState();
    _controller = ForumComposerController(api: ref.read(forumApiProvider));
    if (_isEdit) _bodyController.text = widget.args.initialBodyText;
    _quoteText = widget.args.quoteText;
    // A listener (not just the body TextField's `onChanged`) so `_canSubmit`
    // re-evaluates when the rich-text toolbar mutates `controller.value`
    // programmatically (todo 314) — `TextField.onChanged` only fires for
    // user-driven edits through the IME, never for a direct `.value =`
    // assignment, so a toolbar-only edit (e.g. tapping bold with nothing
    // else typed) would otherwise leave the Post button's enabled state
    // stale.
    _bodyController.addListener(_onBodyChanged);
    // The title feeds `_hasUnsentInput` (PopScope.canPop is read from the
    // last build), so it needs the same rebuild-on-change as the body.
    _titleController.addListener(_onBodyChanged);
  }

  void _onBodyChanged() => setState(() {});

  @override
  void dispose() {
    _bodyController.removeListener(_onBodyChanged);
    _titleController.removeListener(_onBodyChanged);
    _titleController.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  /// Text (or an attachment) the user typed and has not sent — what a back
  /// gesture would silently throw away (audit 2026-09-04 L8). An edit counts
  /// only if it differs from the post as it was opened.
  bool get _hasUnsentInput {
    if (_isEdit) return _bodyController.text != widget.args.initialBodyText;
    return _titleController.text.trim().isNotEmpty ||
        _bodyController.text.trim().isNotEmpty ||
        _attachedImage != null;
  }

  Future<bool> _confirmDiscard() async {
    final discard = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Discard draft?'),
        content: const Text('Your unsent text will be lost.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Keep editing'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    return discard ?? false;
  }

  bool get _canSubmit {
    // Blocked while an upload is in flight (code review): otherwise a
    // "Post" tap that lands before the upload resolves submits with
    // `imageId: null` and silently drops the attachment — no error, no
    // retry prompt, and the upload's own success handler later no-ops
    // (post-navigation `!mounted`).
    // Blocked while an upload is in flight (code review): otherwise a
    // "Post" tap that lands before the upload resolves submits with
    // `imageId: null` and silently drops the attachment — no error, no
    // retry prompt, and the upload's own success handler later no-ops
    // (post-navigation `!mounted`).
    if (_uploadingImage) return false;
    final hasText = _bodyController.text.trim().isNotEmpty;
    final hasImage = _supportsImage && _attachedImage != null;
    if (!hasText && !hasImage) return false;
    if (_isTopic && _titleController.text.trim().isEmpty) return false;
    return true;
  }

  Future<void> _addPhoto() async {
    setState(() {
      _uploadingImage = true;
      _imageError = null;
    });
    try {
      // The picker call is INSIDE the try (code review): a platform-level
      // failure (e.g. a previously-denied photo-library permission) must
      // degrade the same way an upload rejection does, not propagate
      // unhandled out of this method.
      final path = await widget.imagePicker.pickImagePath();
      if (path == null) {
        if (!mounted) return;
        setState(() => _uploadingImage = false);
        return;
      }
      final image = await _controller.uploadImage(filePath: path);
      if (!mounted) return;
      setState(() {
        _attachedImage = image;
        _uploadingImage = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      // The drafted title/body text is untouched by this catch — a failed
      // upload must not cost the user what they already typed (AC2).
      setState(() {
        _uploadingImage = false;
        _imageError = e.message;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _uploadingImage = false;
        _imageError = 'Could not upload that photo.';
      });
    }
  }

  void _removePhoto() {
    setState(() => _attachedImage = null);
  }

  Future<void> _submit() async {
    if (!_canSubmit || _submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (_isEdit) {
        final result = await _controller.submitEdit(
          postId: widget.args.postId!,
          bodyText: _bodyController.text,
        );
        if (!mounted) return;
        if (result.status.isPending) {
          setState(() {
            _submitting = false;
            _pending = true;
          });
        } else {
          Navigator.of(context).pop(result.post);
        }
        return;
      }
      final ForumModerationStatus status;
      if (_isTopic) {
        final result = await _controller.submitTopic(
          boardSlug: widget.args.boardSlug!,
          title: _titleController.text,
          bodyText: _bodyController.text,
          imageId: _attachedImage?.id,
        );
        status = result.status;
      } else {
        final result = await _controller.submitReply(
          topicId: widget.args.topicId!,
          bodyText: _bodyController.text,
          imageId: _attachedImage?.id,
          quoteText: _quoteText,
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
        // Edit's 409 is a real, permanent state (frozen/locked topic or post
        // — Post.edit_block) as often as it is the create path's transient
        // in-flight-retry race, and the backend's message is already a
        // clear, specific, non-retry-implying sentence ("Post is locked.",
        // "Topic is closed or locked.") — so edit shows it verbatim rather
        // than the generic "tap again to retry" copy below, which would be
        // actively wrong for the frozen/locked case (todo 292 AC3).
        _error = (!_isEdit && e.statusCode == 409)
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

  String get _what => _isEdit ? 'edit' : (_isTopic ? 'topic' : 'reply');

  @override
  Widget build(BuildContext context) {
    final isAuthenticated = ref.watch(
      authServiceProvider.select((s) => s.isAuthenticated),
    );
    final title = _isEdit ? 'Edit post' : (_isTopic ? 'New topic' : 'Reply');

    // Back with unsent text asks first (audit 2026-09-04 L8). `canPop` only
    // governs maybePop (AppBar back, system back); the explicit
    // `Navigator.pop` after a published submit is unaffected. A pending
    // (moderation-queued) submit keeps the text in the controllers behind
    // the _PendingView, but it HAS been sent — never prompt for it.
    return PopScope(
      canPop: _pending || !_hasUnsentInput,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final discard = await _confirmDiscard();
        if (discard && context.mounted) Navigator.of(context).pop();
      },
      child: Scaffold(
        appBar: AppBar(title: Text(title)),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: !isAuthenticated
                ? _LoginPrompt(
                    action: _isTopic
                        ? 'start a topic'
                        : (_isEdit ? 'edit this post' : 'reply'),
                  )
                : _pending
                ? _PendingView(what: _what)
                : _form(context),
          ),
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
        if (_isEdit && widget.args.hasNonTextContent)
          const Padding(
            padding: EdgeInsets.only(bottom: AppSpacing.sm),
            child: ForumNoticeBanner(
              message:
                  "This post has formatting or an image the app can't show "
                  'here yet — saving will replace it with plain text.',
              icon: Icons.warning_amber_outlined,
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
        if (_imageError != null)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: ForumNoticeBanner(
              message: _imageError!,
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
            // No onChanged — the `_titleController` listener registered in
            // initState rebuilds on every change, like the body field below.
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        if (_quoteText != null)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: _QuoteDraft(
              text: _quoteText!,
              onRemove: () => setState(() => _quoteText = null),
            ),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: ForumRichTextToolbar(controller: _bodyController),
        ),
        // Above the field, not below it: a strip under a five-line field
        // would sit beneath the keyboard (todo 341 wave 4).
        ForumMentionSuggestions(controller: _bodyController),
        TextField(
          controller: _bodyController,
          decoration: InputDecoration(
            labelText: _isTopic
                ? 'Body'
                : (_isEdit ? 'Edit your post' : 'Your reply'),
            alignLabelWithHint: true,
            border: const OutlineInputBorder(),
          ),
          minLines: 5,
          maxLines: 12,
          // No onChanged here — the `_bodyController` listener registered in
          // initState covers both user-driven edits AND the rich-text
          // toolbar's programmatic `.value =` assignments (todo 314).
        ),
        if (_supportsImage) ...[
          const SizedBox(height: AppSpacing.sm),
          if (_attachedImage != null)
            _AttachedImagePreview(
              image: _attachedImage!,
              onRemove: _removePhoto,
            )
          else
            OutlinedButton.icon(
              onPressed: _uploadingImage ? null : _addPhoto,
              icon: _uploadingImage
                  ? const SizedBox(
                      height: 16,
                      width: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.add_photo_alternate_outlined),
              label: Text(_uploadingImage ? 'Uploading…' : 'Add photo'),
            ),
        ],
        const SizedBox(height: AppSpacing.md),
        FilledButton(
          onPressed: _canSubmit && !_submitting ? _submit : null,
          child: _submitting
              ? const SizedBox(
                  height: 18,
                  width: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(_isEdit ? 'Save' : 'Post'),
        ),
      ],
    );
  }
}

/// The pre-filled quote, read-only, in the same left-rule styling the body
/// renderer gives a `quote` block — so what the author sees is what the
/// thread will show. Removable (48dp target).
class _QuoteDraft extends StatelessWidget {
  const _QuoteDraft({required this.text, required this.onRemove});

  final String text;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      container: true,
      label: 'Quoted text',
      child: Container(
        padding: const EdgeInsets.only(left: AppSpacing.md),
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(color: theme.colorScheme.primary, width: 3),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                text,
                maxLines: 6,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontStyle: FontStyle.italic,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
            IconButton(
              tooltip: 'Remove quote',
              icon: const Icon(Icons.close, size: 20),
              onPressed: onRemove,
            ),
          ],
        ),
      ),
    );
  }
}

class _AttachedImagePreview extends StatelessWidget {
  const _AttachedImagePreview({required this.image, required this.onRemove});

  final ForumImageBlock image;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.topRight,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(AppSpacing.rMd),
          child: CachedNetworkImage(
            imageUrl: image.url,
            height: 160,
            width: double.infinity,
            fit: BoxFit.cover,
            placeholder: (context, _) => const SizedBox(
              height: 160,
              child: Center(child: CircularProgressIndicator()),
            ),
            errorWidget: (context, _, _) => const SizedBox(
              height: 160,
              child: Center(child: Icon(Icons.broken_image_outlined)),
            ),
          ),
        ),
        IconButton.filled(
          onPressed: onRemove,
          icon: const Icon(Icons.close),
          tooltip: 'Remove photo',
        ),
      ],
    );
  }
}

class _PendingView extends StatelessWidget {
  const _PendingView({required this.what});
  final String what;

  @override
  Widget build(BuildContext context) {
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
          // Pop with no value (null), not `false`: this view is shared by
          // every mode, and reply/topic push the composer as `<bool>` while
          // edit pushes it as `<ForumPost>` (code review) — `null` is a
          // valid `T?` for any T, where a literal `false` is only valid for
          // the bool-typed routes and throws a type error against the
          // ForumPost-typed one. Every caller already treats a non-success
          // result as "nothing to apply" (`result == true` / `result is
          // ForumPost`), so `null` behaves identically to the old `false`
          // for every existing caller.
          onPressed: () => Navigator.of(context).pop(),
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
