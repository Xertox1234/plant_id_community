// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'forum_unlock_store.dart';

// **************************************************************************
// RiverpodGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// ignore_for_file: type=lint, type=warning
/// The signed-in member's unlocks, kept in step with the store and with the
/// `X-Forum-Unlock` header [ApiService] sends.
///
/// Keyed on the signed-in member's Firebase uid (the same "signed in" as the
/// forum home's viewer: a Firebase user still waiting on its JWT is not):
/// - signed out (also at launch, before the session restores): no header,
///   and the store is left alone;
/// - signed in as the member the store holds: their tokens;
/// - signed in as anyone else: the store is cleared.
///
/// Every end of a session (`signOut()`, a session expiry, a sign-out
/// Firebase reports, a declined consent) and an account switch clear the
/// store and the header and end the unlock session (`AuthService`'s
/// `_forgetForumData`, through [ApiService], since this provider depends on
/// the auth one and not the other way round; audit F130);
/// `_resetForViewer` on the forum home must not, since it also runs at launch
/// and on an author block.

@ProviderFor(ForumUnlocksController)
final forumUnlocksProvider = ForumUnlocksControllerProvider._();

/// The signed-in member's unlocks, kept in step with the store and with the
/// `X-Forum-Unlock` header [ApiService] sends.
///
/// Keyed on the signed-in member's Firebase uid (the same "signed in" as the
/// forum home's viewer: a Firebase user still waiting on its JWT is not):
/// - signed out (also at launch, before the session restores): no header,
///   and the store is left alone;
/// - signed in as the member the store holds: their tokens;
/// - signed in as anyone else: the store is cleared.
///
/// Every end of a session (`signOut()`, a session expiry, a sign-out
/// Firebase reports, a declined consent) and an account switch clear the
/// store and the header and end the unlock session (`AuthService`'s
/// `_forgetForumData`, through [ApiService], since this provider depends on
/// the auth one and not the other way round; audit F130);
/// `_resetForViewer` on the forum home must not, since it also runs at launch
/// and on an author block.
final class ForumUnlocksControllerProvider
    extends $AsyncNotifierProvider<ForumUnlocksController, Map<int, String>> {
  /// The signed-in member's unlocks, kept in step with the store and with the
  /// `X-Forum-Unlock` header [ApiService] sends.
  ///
  /// Keyed on the signed-in member's Firebase uid (the same "signed in" as the
  /// forum home's viewer: a Firebase user still waiting on its JWT is not):
  /// - signed out (also at launch, before the session restores): no header,
  ///   and the store is left alone;
  /// - signed in as the member the store holds: their tokens;
  /// - signed in as anyone else: the store is cleared.
  ///
  /// Every end of a session (`signOut()`, a session expiry, a sign-out
  /// Firebase reports, a declined consent) and an account switch clear the
  /// store and the header and end the unlock session (`AuthService`'s
  /// `_forgetForumData`, through [ApiService], since this provider depends on
  /// the auth one and not the other way round; audit F130);
  /// `_resetForViewer` on the forum home must not, since it also runs at launch
  /// and on an author block.
  ForumUnlocksControllerProvider._()
    : super(
        from: null,
        argument: null,
        retry: null,
        name: r'forumUnlocksProvider',
        isAutoDispose: false,
        dependencies: null,
        $allTransitiveDependencies: null,
      );

  @override
  String debugGetCreateSourceHash() => _$forumUnlocksControllerHash();

  @$internal
  @override
  ForumUnlocksController create() => ForumUnlocksController();
}

String _$forumUnlocksControllerHash() =>
    r'6832a6b671f242b5e58e74413535b030a368a051';

/// The signed-in member's unlocks, kept in step with the store and with the
/// `X-Forum-Unlock` header [ApiService] sends.
///
/// Keyed on the signed-in member's Firebase uid (the same "signed in" as the
/// forum home's viewer: a Firebase user still waiting on its JWT is not):
/// - signed out (also at launch, before the session restores): no header,
///   and the store is left alone;
/// - signed in as the member the store holds: their tokens;
/// - signed in as anyone else: the store is cleared.
///
/// Every end of a session (`signOut()`, a session expiry, a sign-out
/// Firebase reports, a declined consent) and an account switch clear the
/// store and the header and end the unlock session (`AuthService`'s
/// `_forgetForumData`, through [ApiService], since this provider depends on
/// the auth one and not the other way round; audit F130);
/// `_resetForViewer` on the forum home must not, since it also runs at launch
/// and on an author block.

abstract class _$ForumUnlocksController
    extends $AsyncNotifier<Map<int, String>> {
  FutureOr<Map<int, String>> build();
  @$mustCallSuper
  @override
  WhenComplete runBuild() {
    final ref =
        this.ref as $Ref<AsyncValue<Map<int, String>>, Map<int, String>>;
    final element =
        ref.element
            as $ClassProviderElement<
              AnyNotifier<AsyncValue<Map<int, String>>, Map<int, String>>,
              AsyncValue<Map<int, String>>,
              Object?,
              Object?
            >;
    return element.handleCreate(ref, build);
  }
}
