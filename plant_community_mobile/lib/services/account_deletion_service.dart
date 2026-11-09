import 'package:dio/dio.dart' show Options;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_service.dart';

/// The 403 `reauth_required`: the fresh token was refused (too old, or a
/// different Firebase user than the signed-in account).
const reauthAgainMessage = "Please confirm it's you again.";

/// The device could not reach the server: a connection error or a timeout
/// ([ApiException.connectivity]).
const offlineMessage = "You're offline. Connect and try again.";

/// The 503 `verifier_unavailable`, and every other failure without a message
/// of ours to show.
const tryAgainLaterMessage =
    'Something went wrong. Try again in a few minutes.';

/// A 409 whose body is not our JSON envelope, so it carries no message we
/// can trust to show.
const contactSupportFallbackMessage =
    "Your account can't be deleted here. Contact support and we'll help.";

/// What one deletion request came to.
sealed class AccountDeletionResult {
  const AccountDeletionResult();
}

/// 202: the server scheduled the deletion. The caller signs out.
final class AccountDeletionScheduled extends AccountDeletionResult {
  const AccountDeletionScheduled();
}

/// 401: the JWT was refused. After a deletion was scheduled (on another
/// device, ruling R15) the account is inactive, so this is "signed out", and
/// the caller routes to the login screen rather than showing an error.
final class AccountDeletionSignedOut extends AccountDeletionResult {
  const AccountDeletionSignedOut();
}

/// Nothing was scheduled; [message] is fit to show the user.
final class AccountDeletionFailed extends AccountDeletionResult {
  const AccountDeletionFailed(this.message);

  final String message;
}

/// Self-service account deletion (Plan B): `POST /auth/account/delete/` with
/// a Firebase ID token minted right after re-authentication.
///
/// Goes through [ApiService], so the JWT interceptor attaches the bearer and
/// an expired access token is refreshed once before a 401 reaches here. Not
/// retried on a 5xx: a POST is not in the client's safe-retry set.
///
/// Sent with [ApiService.skipSessionExpiryKey]: when the refresh is refused
/// (the account is already inactive, ruling R15), the 401 comes back here
/// instead of ApiService signing out with "Your session expired", and the
/// delete screen signs out itself.
class AccountDeletionService {
  AccountDeletionService(this._api);

  final ApiService _api;

  static const path = '/auth/account/delete/';

  Future<AccountDeletionResult> deleteAccount(String firebaseToken) async {
    try {
      await _api.post(
        path,
        data: {'firebase_token': firebaseToken},
        options: Options(extra: {ApiService.skipSessionExpiryKey: true}),
      );
      return const AccountDeletionScheduled();
    } on ApiException catch (e) {
      return _failure(e);
    }
  }

  static AccountDeletionResult _failure(ApiException e) {
    final status = e.statusCode;
    if (status == null) {
      return AccountDeletionFailed(
        e.connectivity ? offlineMessage : tryAgainLaterMessage,
      );
    }
    if (status == 401) return const AccountDeletionSignedOut();
    if (status == 403 && e.code == 'reauth_required') {
      return const AccountDeletionFailed(reauthAgainMessage);
    }
    if (status == 409) {
      // Only a message one of our views wrote is shown (docs/rules/flutter.md).
      final ours = !e.unstructured && e.message.trim().isNotEmpty;
      return AccountDeletionFailed(
        ours ? e.message : contactSupportFallbackMessage,
      );
    }
    return const AccountDeletionFailed(tryAgainLaterMessage);
  }
}

final accountDeletionServiceProvider = Provider<AccountDeletionService>(
  (ref) => AccountDeletionService(ref.watch(apiServiceProvider)),
);
