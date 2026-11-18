import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/routing/main_shell.dart';
import '../../../core/theme/green_thumb_extension.dart';
import '../../../services/api_service.dart';
import '../../../shared/widgets/canopy_notice.dart';
import '../../../shared/widgets/clay_button.dart';
import '../models/models.dart';
import '../providers/forum_providers.dart';
import '../services/forum_api.dart';
import '../services/forum_unlock_store.dart';

/// Unlocks a password forum (spec §7.4): the forum's name, one password
/// field and an Unlock button. A success keeps the server's unlock token for
/// the member who sent the password and opens the forum.
///
/// The password lives only in the field's controller and the one request:
/// it is never logged, never put in provider state, and cleared after a
/// successful unlock. Each tap sends it once (a busy flag disables the
/// button, and the request is never marked safe to retry).
class ForumUnlockScreen extends ConsumerStatefulWidget {
  const ForumUnlockScreen({
    super.key,
    required this.boardSlug,
    this.boardTitle,
  });

  final String boardSlug;
  final String? boardTitle;

  @override
  ConsumerState<ForumUnlockScreen> createState() => _ForumUnlockScreenState();
}

class _ForumUnlockScreenState extends ConsumerState<ForumUnlockScreen> {
  final _password = TextEditingController();
  bool _busy = false;

  /// Under the field: a wrong password, or too many tries.
  String? _fieldError;

  /// Anything else (offline, a server error): a retry message.
  bool _failed = false;

  static const _retryMessage = 'Could not unlock this forum. Try again.';

  @override
  void initState() {
    super.initState();
    // Rebuild for the button's enabled state only; never read the text here.
    _password.addListener(_onTyped);
  }

  @override
  void dispose() {
    _password
      ..removeListener(_onTyped)
      ..dispose();
    super.dispose();
  }

  bool _hadText = false;

  void _onTyped() {
    final hasText = _password.text.isNotEmpty;
    if (hasText == _hadText) return;
    setState(() => _hadText = hasText);
  }

  Future<void> _unlock() async {
    final password = _password.text;
    // The member the password is for, captured before anything is sent.
    final viewer = ref.read(forumViewerProvider);
    if (_busy || password.isEmpty || viewer == null) return;
    setState(() {
      _busy = true;
      _fieldError = null;
      _failed = false;
    });

    String? error;
    var failed = false;
    try {
      // The forum id keys the token. It comes from the feed, which lists
      // locked forums too. Resolved before the password goes out: a token
      // that cannot be kept would waste a rate-limited try.
      final forumId = await _forumId(viewer);
      if (!mounted || !_sameViewer(viewer)) return;
      if (forumId == null) {
        failed = true;
      } else {
        final token = await ref
            .read(forumApiProvider)
            .unlockBoard(widget.boardSlug, password);
        if (!mounted || !_sameViewer(viewer)) return;
        // Null: nothing to unlock (already open, or staff). No stored token
        // changes; the forum opens all the same.
        if (token != null) {
          await ref
              .read(forumUnlocksProvider.notifier)
              .add(forumId, token, forUid: viewer);
          if (!mounted || !_sameViewer(viewer)) return;
        }
        _password.clear();
        // The feed reads the unlocks without watching them.
        ref
          ..invalidate(categoriesProvider)
          ..invalidate(boardTopicsProvider(widget.boardSlug, viewer));
        context.pushReplacementNamed(
          'forumBoard',
          pathParameters: {'slug': widget.boardSlug},
          extra: widget.boardTitle,
        );
        return;
      }
    } on ApiException catch (e) {
      switch (e.statusCode) {
        case 400:
          error = 'Wrong password.';
        case 429:
          error = _tooManyTries(e.retryAfterSeconds);
        default:
          failed = true;
      }
    } catch (_) {
      // Never shown or logged: only the retry message.
      failed = true;
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      _fieldError = error;
      _failed = failed;
    });
  }

  /// False when the member who sent the password is no longer the one
  /// signed in. Then nothing is kept and the forum is not opened, and the
  /// typed password is dropped rather than left for the next member.
  bool _sameViewer(String viewer) {
    if (ref.read(forumViewerProvider) == viewer) return true;
    _password.clear();
    setState(() => _busy = false);
    return false;
  }

  /// The forum's id from the feed, or null when the feed does not list it.
  /// A feed that failed, or that does not list the forum (it may be
  /// stale), is fetched again first, so a retry tap never meets the same
  /// old answer.
  Future<int?> _forumId(String viewer) async {
    final feed = categoriesProvider(viewer);
    int? find(List<ForumCategory> categories) {
      for (final category in categories) {
        for (final forum in category.forums) {
          if (forum.slug == widget.boardSlug) return forum.id;
        }
      }
      return null;
    }

    if (!ref.read(feed).hasError) {
      final id = find(await ref.read(feed.future));
      if (id != null || !mounted) return id;
    }
    ref.invalidate(feed);
    return find(await ref.read(feed.future));
  }

  static String _tooManyTries(int? retryAfterSeconds) {
    if (retryAfterSeconds == null || retryAfterSeconds < 0) {
      return 'Too many tries. Try again later.';
    }
    final rounded = (retryAfterSeconds / 60).ceil();
    final minutes = rounded < 1 ? 1 : rounded;
    return 'Too many tries. Try again in $minutes '
        '${minutes == 1 ? 'minute' : 'minutes'}.';
  }

  @override
  Widget build(BuildContext context) {
    final viewer = ref.watch(forumViewerProvider);
    // Held while the screen is open: the forum id is read from it, and it
    // names the forum when the route came without a title.
    final feed = viewer == null
        ? null
        : ref.watch(viewerCategoriesProvider).value;
    final listed = feed
        ?.expand((c) => c.forums)
        .where((f) => f.slug == widget.boardSlug)
        .firstOrNull;
    final title = widget.boardTitle ?? listed?.title ?? 'Forum';
    final ext = context.canopy;
    final canUnlock = !_busy && _password.text.isNotEmpty;

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SafeArea(
        child: ListView(
          padding:
              EdgeInsets.all(ext.padScreen) + MainShell.fabClearanceOf(context),
          children: viewer == null
              ? [
                  // A guest (a deep link): the password could not be kept.
                  const CanopyNotice(
                    message: 'Sign in to open this forum.',
                    liveRegion: false,
                  ),
                  SizedBox(height: ext.gapY * 2),
                  ClayButton(
                    label: 'Sign in',
                    fullWidth: true,
                    onPressed: () => context.pushNamed('login'),
                  ),
                ]
              : [
                  TextField(
                    controller: _password,
                    obscureText: true,
                    // Null, not empty: no autofill (Android, web), and the
                    // field is offered to no autofill service.
                    autofillHints: null,
                    autocorrect: false,
                    enableSuggestions: false,
                    enableIMEPersonalizedLearning: false,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) {
                      if (canUnlock) _unlock();
                    },
                    decoration: InputDecoration(
                      labelText: 'Password',
                      errorText: _fieldError,
                      errorMaxLines: 3,
                    ),
                  ),
                  if (_failed) ...[
                    SizedBox(height: ext.gapY),
                    const CanopyNotice(
                      message: _retryMessage,
                      tone: CanopyNoticeTone.error,
                    ),
                  ],
                  SizedBox(height: ext.gapY * 2),
                  ClayButton(
                    label: 'Unlock',
                    loadingLabel: 'Unlocking…',
                    loading: _busy,
                    fullWidth: true,
                    onPressed: canUnlock ? _unlock : null,
                  ),
                ],
        ),
      ),
    );
  }
}
