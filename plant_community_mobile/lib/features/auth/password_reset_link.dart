import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../services/api_service.dart';

/// Django's password reset page (allauth), on the API origin.
///
/// It resets the password of the Django account that holds an address. That
/// is NOT the credential this app's sign-in form checks: the form signs in to
/// Firebase. So the link is offered only where a Django account is the
/// obstacle, inside the account-conflict error after a sign-in (todo 447,
/// owner decision 2026-09-26), never on the form itself.
Uri passwordResetUri(String apiBaseUrl) =>
    Uri.parse(apiBaseUrl).replace(path: '/accounts/password/reset/');

final passwordResetUriProvider = Provider<Uri>(
  (ref) => passwordResetUri(ref.watch(apiServiceProvider).baseUrl),
);
