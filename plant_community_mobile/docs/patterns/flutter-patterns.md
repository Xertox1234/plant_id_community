# Flutter/Dart Patterns

**Stack**: Flutter 3.x, Dart 3.x, Riverpod 3.x (code generation), go_router 17.0.0, Material Design 3

---

## Memory Leak Prevention — StreamSubscription Disposal

Every `StreamSubscription` declared in a Riverpod provider MUST be cancelled in `ref.onDispose()`.

```dart
@riverpod
class PlantDataNotifier extends _$PlantDataNotifier {
  StreamSubscription<QuerySnapshot>? _firestoreSubscription;

  @override
  PlantDataState build() {
    _firestoreSubscription = _firestore
        .collection('plants')
        .snapshots()
        .listen(_onSnapshot);

    // REQUIRED — missing this causes memory leaks across hot restarts
    ref.onDispose(() {
      _firestoreSubscription?.cancel();
    });

    return const PlantDataState.initial();
  }
}
```

---

## Riverpod 3.x — Notifier Pattern

Use `Notifier` class with `@riverpod` annotation. Do NOT use deprecated `StateNotifier`.

```dart
// ✅ Riverpod 3.x — code-generated
@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  AuthState build() => const AuthState.initial();

  Future<void> signIn(String email, String password) async { ... }
}

// ❌ Deprecated
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState.initial());
}
```

After adding/modifying `@riverpod` providers, regenerate with:

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

---

## go_router 17.0.0

Router debug logging must use `kDebugMode`, not hardcoded `true`:

```dart
GoRouter(
  debugLogDiagnostics: kDebugMode,
  ...
)
```

---

## Material Design 3 — Correct APIs

```dart
// ✅ Material 3
CardTheme(data: CardThemeData(...))
color.withValues(alpha: 0.5)

// ❌ Deprecated
CardTheme(...)
color.withOpacity(0.5)
```

Dark mode check:

```dart
if (Theme.of(context).brightness == Brightness.dark) { ... }
```

---

## Null Safety

Prefer `?.` and `??` over `!` null-force-unwrap on values that could legitimately be null:

```dart
// ✅
final name = user?.displayName ?? 'Anonymous';

// ❌ Crash risk
final name = user!.displayName;
```

---

## Image Handling

Use `CachedNetworkImage` for network images — never `Image.network`:

```dart
CachedNetworkImage(
  imageUrl: plant.imageUrl,
  placeholder: (context, url) => const CircularProgressIndicator(),
  errorWidget: (context, url, error) => const Icon(Icons.error),
)
```

---

## Minimum Tap Target

Minimum interactive element size: 48×48 dp (Material 3 specification).

```dart
SizedBox(
  width: 48,
  height: 48,
  child: IconButton(onPressed: ..., icon: ...),
)
```

## Epoch-Guarded Async Lifecycle Services

**Context** (todo 253 slice 6, races confirmed empirically in review): a
service whose async work must stop at sign-out (`PushRegistrationService`)
cannot rely on cancelling subscriptions alone — a continuation already parked
on an `await` (permission dialog, `getToken()`, an in-flight PATCH) resumes
AFTER the cleanup ran and re-registers state for a signed-out session.

**The pattern** (mirrors `AuthService._authGeneration`):

```dart
int _epoch = 0;

Future<void> syncAfterLogin() async {
  final epoch = _epoch;                      // capture at entry
  final settings = await messaging.requestPermission();
  if (epoch != _epoch) return;               // re-check after EVERY await…
  await _refreshSubscription?.cancel();
  if (epoch != _epoch) return;               // …including cancel() itself
  // attach listeners / register …
}

void detach() {
  _epoch++;                                  // invalidates all parked work
  _refreshSubscription?.cancel();
  _refreshSubscription = null;
  _lastSyncedToken = null;                   // full local reset — the next
}                                            // account must not be deduped
                                             // against the previous one
```

Rules that fell out of the confirmed bugs:

- **Re-check after EVERY await** — the one that was missed in review was
  `subscription.cancel()`, which is an async gap like any other.
- **`detach()` is a FULL local reset** (epoch, subscriptions, markers). A
  session-expiry sign-out runs only `detach()`, and the next user on the same
  device must not inherit dedupe markers.
- **Attach healing listeners BEFORE the fallible first attempt** — the
  `onTokenRefresh` listener goes up before `getToken()`/first PATCH, so a
  null token (iOS APNS warm-up) or transient failure self-heals on the next
  event instead of silencing the whole session. Always pass `onError:` — a
  platform error event on the stream is otherwise an unhandled zone error.
- **Interceptor side effects are suppressed per-REQUEST, not per-flag.** A
  boolean flag around `await patch(...).timeout(3s)` fails: the timeout
  abandons the Future but Dio keeps the request alive (~receiveTimeout), and
  its late 401 fires the session-expired handler after the flag reset. Put
  the opt-out on the request (`Options(extra: {ApiService.skipSessionExpiryKey:
  true})`) and check `requestOptions.extra` in the interceptor.

Reference: `lib/services/push_registration_service.dart` (+ its unit tests:
epoch-parked-sync, listener-survives-failed-PATCH, detach-clears-marker).

## Shared-Widget Consolidation: Fixed Chrome vs. Flex-Constrained Cells

**Context** (todo 317, forum author identity): consolidating `PostCard`'s
and `TopicCard`'s duplicated inline author rendering into one shared
`AuthorIdentity` widget gave `TopicCard` a `TrustBadge` it had never shown
before — a natural side effect of reuse. `TopicCard`'s stat row placed the
author cell in a `Flexible` next to a `Spacer()`:

```dart
Row(children: [
  Flexible(child: AuthorIdentity(author: topic.author)),  // gets HALF the slack
  const SizedBox(width: AppSpacing.sm),
  _Stat(...), const SizedBox(width: AppSpacing.xs), _Stat(...),
  const Spacer(),                                          // claims the OTHER half
  Text(time),
]);
```

`Spacer()` is `Expanded(flex: 1)` — it unconditionally claims half the
row's free space regardless of what the `Flexible` sibling actually needs.
That was harmless when the cell held a bare ellipsizable `Text`. It stopped
being harmless the moment the shared widget added ~92px of FIXED,
non-shrinkable chrome (avatar + gaps + badge) into that half-share cell —
on a 375pt-wide screen (iPhone SE/mini) this computed to sit at the
`RenderFlex` overflow threshold, and became a hard overflow at larger text
scales.

**Why no test caught it:** the full suite stayed green throughout. Flutter's
default test viewport is 800×600 — nothing constrained width below that, so
this class of regression is invisible by construction no matter how much
coverage exists elsewhere. A task-scoped review noticed the badge as a
"visual surprise" but under-weighted it as cosmetic; only a broader review
that traced the actual pixel budget by hand caught its true severity.

**The rule:** moving fixed-width chrome into a flex-constrained slot is a
LAYOUT change, not a rendering change — budget it in pixels. When a shared
widget grows new always-on chrome, check every call site's actual layout
context (what else is in the row, is there a `Spacer()` claiming slack the
new chrome now needs), not just the widget's own isolated appearance. Add
at least one narrow-viewport (≤375pt) test for any row containing it:

```dart
addTearDown(tester.view.reset);
tester.view.physicalSize = const Size(375, 800);
tester.view.devicePixelRatio = 1.0;
// pump with a long name + real stats + a full-date timestamp — the
// combination that maximizes the fixed-chrome budget
expect(tester.takeException(), isNull);
```

If the new chrome isn't wanted at every call site, parameterize it
(`showTrustBadge: false`) rather than accepting the overflow — the shared
widget's default should match its most permissive existing call site, and
narrower call sites opt out explicitly.

Reference: `lib/features/forum/widgets/author_identity.dart`,
`lib/features/forum/widgets/topic_card.dart`,
`test/features/forum/widgets/topic_card_test.dart`.

## Forum parity waves 1+2 (todo 341): patterns worth reusing

- `forum_errors.dart::forumErrorMessage()` is the one place an `ApiException`
  becomes copy: 429 → "Too fast — try again in a minute", 403 → the
  action's own notice, 400/409/422 → the server's message. New write
  surfaces call it; they never show `e.toString()`.
- Optimistic toggles (bookmark, block) snapshot the prior value and restore
  it on failure; a non-optimistic write (mark solution) waits for the
  server because it can refuse. Both shapes are provider-tested with a
  fake API that fails on demand.
- `Idempotency-Key` goes only on writes whose backend view calls
  `idempotency_cache_key` (report, mark solution); naturally idempotent
  writes (block/unblock, bookmark/unbookmark, clear solution) send none —
  read the view before adding a key.
- A "jump to" that targets an item possibly outside the built children
  steps the viewport and pages the cursor with a hard bound, never an
  unbounded loop (`ensureVisible` only reaches built widgets).

## Forum parity waves 3+4 (todo 341): polls, mentions, quotes

- `poll_card.dart`: `ForumPoll.pendingOptionIds` is client-only state (never
  serialised) that disables the ballot the instant a vote is sent; the
  server's poll object replaces the model on success, so percentages are
  never computed locally. A 409 means "already voted" — show the server's
  sentence and `ref.invalidate` the SINGLE-VALUE topic detail to resync.
- `forum_mention_suggestions.dart`: `mentionFragmentAt(text, caret)` finds
  the `@word` under the caret (emails are not mentions), `insertMention`
  replaces exactly that fragment; the `MentionSearch` notifier debounces
  300 ms, cancels its timer on dispose and discards superseded responses
  by generation. The strip sits above the field, inline.
- Quote (todo 342): `forumBodyPlainText` (heading/paragraph/code; nested
  quotes and media dropped) + `forumQuoteDraft` (500-char cap, keyed to
  the post id; the author name rides along for the composer's draft card
  only) → a leading structured `post_quote` block `{post, text}` via
  `buildPostQuoteBlockBody`. No `"user wrote:"` line in the text — the
  server resolves the attribution on read (`PostQuoteBlock.available` /
  `author` / `topicId`; the renderer links "in topic" to the quoted post
  unless it lives in the topic being read — `ForumBodyRenderer.currentTopicId`,
  threaded from the thread screen and its edit-history sheet — and
  collapses a quote of a blocked/muted author (`isBlocked` / `isMuted`)
  behind the same "Show anyway" reveal `PostCard` uses, never hiding it;
  the "gone" notice appears only when `available` is `false`) and
  notifies the quoted author with the `quote` verb. A rejected quote
  is a 400 whose sentence `forumErrorMessage` shows verbatim.
