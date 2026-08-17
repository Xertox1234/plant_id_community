import 'package:uuid/uuid.dart';

import '../models/models.dart';
import 'forum_api.dart';

/// Slugify a topic title for the create-topic request. The server still
/// auto-suffixes a taken slug, so the returned slug is a best-effort seed —
/// read the final slug from [CreateTopicResult.slug].
String slugifyForumTitle(String title) {
  final slug = title
      .toLowerCase()
      .replaceAll(RegExp(r'[^a-z0-9]+'), '-')
      .replaceAll(RegExp(r'^-+|-+$'), '');
  return slug.isEmpty ? 'topic' : slug;
}

/// Drives a single compose action (a new topic or a reply) with idempotent
/// retry semantics.
///
/// A [ForumComposerController] holds **one** `Idempotency-Key` for its whole
/// lifetime, so every retry of the same compose action reuses that key and the
/// backend replays the original response instead of creating a duplicate. A
/// new compose action = a new controller = a new key.
class ForumComposerController {
  ForumComposerController({required ForumApi api, String? idempotencyKey})
    : _api = api,
      _key = idempotencyKey ?? const Uuid().v4();

  final ForumApi _api;

  String _key;
  String? _lastFingerprint;

  /// The key attached to the next/most-recent submit. Stable across retries of
  /// the *same* content; rotated when the content changes (see
  /// [_refreshKeyForContent]).
  String get idempotencyKey => _key;

  /// Rotate the idempotency key when the submitted content differs from the
  /// previous attempt.
  ///
  /// Retrying the identical content reuses the key so the backend replays
  /// instead of duplicating. But if the user edits the draft after a failed
  /// submit, reusing the old key would wedge the request on a permanent
  /// `422 Idempotency-Key was already used with a different payload` — so a
  /// changed payload gets a fresh key (a genuinely new attempt).
  void _refreshKeyForContent(String fingerprint) {
    if (_lastFingerprint != null && _lastFingerprint != fingerprint) {
      _key = const Uuid().v4();
    }
    _lastFingerprint = fingerprint;
  }

  /// Create a topic. Empty [bodyText] with no [imageId] yields an empty body
  /// — the caller should validate non-empty input (text OR image) before
  /// calling. An attached [imageId] is appended as a write-shape `image`
  /// block after the paragraph (todo 294).
  Future<CreateTopicResult> submitTopic({
    required String boardSlug,
    required String title,
    required String bodyText,
    int? imageId,
  }) {
    _refreshKeyForContent(
      'topic|$boardSlug|${title.trim()}|${bodyText.trim()}|${imageId ?? ''}',
    );
    return _api.createTopic(
      boardSlug: boardSlug,
      title: title.trim(),
      slug: slugifyForumTitle(title),
      body: _buildBody(bodyText, imageId),
      idempotencyKey: _key,
    );
  }

  /// Post a reply to [topicId]. See [submitTopic] re: [imageId].
  Future<CreateReplyResult> submitReply({
    required int topicId,
    required String bodyText,
    int? imageId,
  }) {
    _refreshKeyForContent('reply|$topicId|${bodyText.trim()}|${imageId ?? ''}');
    return _api.createReply(
      topicId: topicId,
      body: _buildBody(bodyText, imageId),
      idempotencyKey: _key,
    );
  }

  List<Map<String, dynamic>> _buildBody(String bodyText, int? imageId) {
    return [
      ...buildParagraphBody(bodyText),
      if (imageId != null) buildImageBlockBody(imageId),
    ];
  }

  /// Upload an image for the composer to attach (todo 294). Reuses the same
  /// idempotency-key rotation as [submitTopic]/[submitReply]: retrying the
  /// SAME file path replays instead of storing a duplicate; a different file
  /// path (the user picked again) rotates to a fresh key.
  Future<ForumImageBlock> uploadImage({required String filePath, String? alt}) {
    _refreshKeyForContent('image|$filePath');
    return _api.uploadImage(filePath: filePath, alt: alt, idempotencyKey: _key);
  }

  /// Edit [postId] (todo 292). Same retry semantics as [submitReply]: the
  /// same edited text retried keeps the key so the backend replays; changed
  /// text rotates it to a fresh attempt.
  Future<EditPostResult> submitEdit({
    required int postId,
    required String bodyText,
  }) {
    _refreshKeyForContent('edit|$postId|${bodyText.trim()}');
    return _api.editPost(
      postId: postId,
      body: buildParagraphBody(bodyText),
      idempotencyKey: _key,
    );
  }
}
