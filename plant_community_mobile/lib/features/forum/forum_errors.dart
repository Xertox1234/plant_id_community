import '../../services/api_service.dart';

/// Copy for a rate-limited write — the same line on every forum action so a
/// user learns it once.
const String forumRateLimitedMessage = 'Too fast — try again in a minute';
const String forumInProgressMessage =
    "That's already in progress — give it a moment.";

/// Map a failed forum write to user-facing copy (todo 341). Never leaks a
/// raw exception string:
///
/// * `429` → [forumRateLimitedMessage];
/// * `403` → [forbidden] (a per-action notice, e.g. "Only the topic's author
///   can accept an answer"), never the server's generic permission line;
/// * `400`/`409`/`422` → the server's own message (already specific and
///   human — "You cannot report your own post.");
/// * anything else (5xx, network, a non-[ApiException]) → [fallback].
String forumErrorMessage(
  Object error, {
  required String fallback,
  String forbidden = "You don't have permission to do that.",
}) {
  if (error is! ApiException) return fallback;
  switch (error.statusCode) {
    case 429:
      return forumRateLimitedMessage;
    case 403:
      return forbidden;
    case 409:
      // A same-key twin is still in flight (a double-tap on Report / Mark
      // as answer): the first request is succeeding — say so, never the
      // server's "Idempotency-Key is being processed" wording.
      return forumInProgressMessage;
    case 400:
    case 422:
      return error.message.isNotEmpty ? error.message : fallback;
    default:
      return fallback;
  }
}
