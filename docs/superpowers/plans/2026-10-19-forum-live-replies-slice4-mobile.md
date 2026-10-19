# Live Forum Replies, Slice 4 (Mobile) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in reader with a topic open in the Flutter app sees new replies, edits, deletes and topic changes live over the slice 2 socket. A per-device "Live updates" switch turns it off. The thread screen gains pull-to-refresh, and two toasts ship with it: the first-time "Turn off" toast and the signed-out "missing out" toast.

**Architecture:**

- A framework-free socket client (`live/forum_live_client.dart`) owns connect, backoff, heartbeat and the close-code rules. It talks to an abstract `ForumLiveChannel`, so tests fake the socket the way `ForumApi` is faked.
- An autoDispose family notifier (`TopicLive`, one per topic) owns the client's lifetime and makes every decision about an event: insert, pill, splice, remove, refetch the topic, or "gone". The screen only reports whether the reader is at the bottom and renders the notifier's state.
- `TopicPosts` and `TopicDetail` gain small local-splice methods. Nothing invalidates a paged list.
- The setting and the toast flags live in `FlutterSecureStorage`, following `config/theme_provider.dart`.

**Tech Stack:** Flutter, Riverpod 3 (`@riverpod` codegen), `dart:io` `WebSocket`, `flutter_test`. There are **no new dependencies**: `web_socket_channel` is not in `pubspec.yaml`, and `dart:io` can set headers.

**Spec:** `docs/superpowers/specs/2026-10-18-forum-live-replies-design.md`, sections "How it behaves", "The setting", §4 "Client fetch after an event", §6 "Mobile client" and "Testing → Mobile". The web client (slice 3, `docs/superpowers/plans/2026-10-19-forum-live-replies-slice3-web.md`, live since #1161) is the reference for every rule this plan mirrors.

**Server contract (live in prod since #1159; the client must match it exactly):**

- **URL:** `wss://api.houseplant-md.com/ws/forum/topics/<topic_id>/`. Note there is **no `/api/v1`**. `ApiService.baseUrl` is `https://host/api/v1`, so the socket URL keeps the scheme and host and replaces the path.
- **Auth:** the header `Authorization: Bearer <access>`. `dart:io` sends no `Origin`, which the server allows.
- **Server → client:** `{"v":1,"type":T,"topic_id":int,"post_id":int}`, where `T` is `post.created`, `post.updated`, `post.removed`, `topic.updated` or `topic.removed`. `topic.*` carries no `post_id`. `{"v":1,"type":"pong"}` answers a ping.
- **Client → server:** only `{"type":"ping"}`.
- **Close codes** (accept, then close, so the code reaches `WebSocket.closeCode`): 4503 flag off (**every** prod connection until slice 5), 4401 no valid user, 4404 topic not visible or removed (sent after `topic.removed`), 4429 socket cap.
- **A refused handshake** makes `WebSocket.connect` throw a `WebSocketException`. There is no close code.
- **Refetch:** `GET /api/v1/forum/posts/<id>/` returns the post exactly as the post list does (`ForumPost.fromJson` reads it), or 404 when the viewer can't see it. `GET /forum/topics/<id>/?peek=1` reads the topic without counting a view or marking it read.

## Global Constraints

- Signed-out readers never open a socket (O10).
- Nothing auto-scrolls unless the reader is already at the bottom with every page loaded (anti-goal "page jumping").
- Retry is silent. There is no error banner unless the topic itself fails to load.
- The socket closes when the screen goes away, when the app is hidden (background), and when the setting turns off.
- Setting: named **"Live updates"**, on by default, stored in `FlutterSecureStorage` under the key `forum_live_updates` (`'on'`/`'off'`), with try/catch and default on if unreadable. It has no backend field.
- Toast copy, verbatim:
  - *"Replies now appear live."* with the action **Turn off**;
  - *"Live updates off"* with the action **Undo**;
  - signed out: *"New replies are coming in. Sign in or sign up to follow along live."* with **Sign in** and **Sign up**.
- Pull-to-refresh is on the thread screen whatever the setting and the sign-in state.
- Every `StreamSubscription` and `Timer` a provider opens is cancelled in `ref.onDispose` (mobile `CLAUDE.md` gotcha).
- Riverpod 3 `@riverpod` `Notifier` classes only, never `StateNotifier`. Each task that adds or changes an annotated provider runs `dart run build_runner build --delete-conflicting-outputs` and commits the `.g.dart` (the `flutter-codegen` pre-commit hook checks it).
- The access token is never logged, never put in a URL, and never put in an exception message.
- The OS reduce-motion setting (`MediaQuery.disableAnimationsOf`) turns off the slide and the animated scroll. The highlight still shows.

## Decisions this plan makes (the spec leaves them to the builder)

| # | Decision | Why |
|---|---|---|
| D1 | **Transport: `dart:io` `WebSocket.connect(uri, headers: …)`**, behind `ForumLiveChannel` and `forumLiveConnectorProvider`. | There are no new dependencies, and the spec allows it. The seam is the fake. |
| D2 | **4401:** run the catch-up peek read (`fetchTopicDetail(id, peek: true)`) once, then reconnect once with `ApiService.authToken`. A second 4401 is terminal. | On mobile the REST bearer **is** the socket bearer, so an expired token 401s the peek too, and `ApiService`'s own interceptor refreshes it (or signs the user out on a refused refresh, which closes the socket through the auth watch). That adds no new auth code path. |
| D3 | **The token comes from a new `String? get authToken` on `ApiService`.** | `AuthState.jwtToken` is set at sign-in. `ApiService` holds the token every request uses, including after a silent refresh. |
| D4 | **4503 and 4429 are terminal** for that foreground session of the screen. A resume from background makes one new attempt. | Slice 4 ships while the flag is off. One connect per resume is cheap. Retrying would be a reconnect storm against prod. |
| D5 | **4404, before or after `topic.removed`:** the screen replaces its body with "This topic is no longer available." and hides the Reply button. | Mobile has no "topic unavailable" state today, so this adds it. The spec says to show it. |
| D6 | **Any other close, or a thrown connect:** backoff `delay = 1000 + random · min(29 000, 4000 · 2^attempt)` ms, so the first retry is spread over 1–5 s. `attempt` resets on every successful open. Retries continue forever at the cap. | The same formula as slice 3 after its final review, so a deploy doesn't bring every phone back in the same second. |
| D7 | **Heartbeat:** send an app-level `{"type":"ping"}` every 25 s. If no frame arrives within 10 s of a ping, close and reconnect. It does not use `dart:io`'s `pingInterval`. | It mirrors slice 3 and the server contract, and it keeps the fake trivial. |
| D8 | **Lifecycle:** `AppLifecycleListener` `onHide` suspends (closes the client), and `onShow` resumes (a new client, which catches up on open). `inactive` alone (the Control Centre, a call banner) keeps the socket. | The spec says to close on background. `hidden` is the first state that means the app is not on screen on both iOS and Android. |
| D9 | **Catch-up:** on every socket open, one peek read of the topic. It applies the fresh topic to `TopicDetail`. With every page loaded, it sets the pill to `max(0, fresh.replyCount − loadedReplies)`, where `loadedReplies` counts the loaded posts that are not the opening post. With pages still unloaded, it leaves the pill as it is (Load more reaches them). | This is slice 3's `checkForNewReplies` rule: the server's count is the truth. |
| D10 | **The decisions live in the `TopicLive` notifier,** not in widget state. The screen calls `setReaderAtBottom(bool)` from a scroll listener. | Each rule is then a `ProviderContainer` test with no widget tree. |
| D11 | **Own reply:** `_openReply` calls `beginOwnReply()` before it pushes the composer, and `endOwnReply()` after `refreshAfterReply()` settles, whether it succeeded or not. `post.created` events are held in between. On release, a held id already in the list is dropped. | The composer returns only `bool`, so the new post id isn't known. After the refresh walk, every reply up to that moment is already in the list, so nothing shows twice, adds to the pill, or uses up the intro toast. |
| D12 | **The pill tap** walks every page (`refreshAfterReply`), takes the last `pendingCount` posts as the new ones, highlights them, and scrolls to the first of them with the bounded viewport chase that `_jumpToAnswer` already uses, generalised to a target id. | The spec warns that the `highlightPostId` one-shot fails off-screen. The chase already works. |
| D13 | **Highlight:** a 2.5 s fade of `colorScheme.secondaryContainer` behind the card (the web's `canopy-flash` length). A new reply that is inserted live also slides in (a `SizeTransition` from 0, 250 ms) unless reduce motion is on. | The spec's O3 and the reduce-motion rule. |
| D14 | **Toasts are `SnackBar`s on the screen's `ScaffoldMessenger`, 10 s long, with `showCloseIcon: true`.** The missing-out toast puts **Sign in** and **Sign up** as two `TextButton`s in its content, because a `SnackBar` takes one action. | A `SnackBar` is the platform toast the spec names, and TalkBack/VoiceOver announce it. |
| D15 | **Sign in** pushes `login` and **Sign up** pushes `register`. Both return to the topic, because `dismissAfterAuth` re-navigates to the underlying location. | Unlike web (slice 3 D11), the mobile auth screens already return to the screen that pushed them. |
| D16 | **Settings:** the "Live updates" `SwitchListTile` sits under a new `FORUM` label, after `NOTIFICATIONS`, and is **hidden** while signed out. | The spec leaves hide or disable to the builder. A disabled switch with a hint would be a second sign-in prompt on a screen that already has one. |
| D17 | **The signed-out check (`TopicMissingOut`):** a peek read every 30 s while the app is shown. The first read sets the baseline `replyCount`. The toast is due when a later read's count is higher and `mayShowMissingOut(now)` allows it. "Per app launch" is an in-memory flag on a keepAlive provider. The 24 h timestamp is stored under `forum_live_missing_out_at`. | Spec "Signed-out readers", mobile trigger. |
| D18 | **The intro flag** is stored under `forum_live_intro_shown` (`'1'`). It is read and recorded before the toast shows, so a crash can't show it twice. `takeIntro()` sets an in-memory flag **synchronously** before it awaits the read and write, so two events in a row can't both get true. The intro fires only on an **event-driven** insert or pill (a handled `post.created`), never on a pill the catch-up set. A catch-up result that arrives after the client has stopped (4503, 4429) is dropped. | O12: once per device. In prod the flag is off, and the catch-up peek from the brief open before 4503 finishes after the close. Without these two rules, a busy topic would show a pill and "Replies now appear live." while nothing is live. |
| D19 | **Event fetches:** `post.created` and `post.updated` fetch the post once per id, with in-flight ids deduped. `topic.updated` and "the removed post was the accepted answer" schedule one peek refetch of the topic, debounced 500 ms. A 404 is ignored. An event whose `topic_id` isn't this topic is dropped. | Spec §4 and slice 3 D7. |
| D20 | **Locked while typing:** the reply composer is its own route, pushed over the thread. In reply mode it watches `topicDetailProvider(topicId)`, which the thread beneath keeps alive and `TopicLive` updates. When the topic is locked or closed, Post is disabled, the typed text stays, and a notice reads "This thread is locked — new replies are disabled." (the web's copy). A reply that still gets the server's 409 for a locked topic shows that notice, not "Still processing your last attempt". | The spec's "keep their text, disable sending, show the locked notice". Today a reply 409 always reads as an in-flight twin (`forum_composer_screen.dart:450`), which is wrong for a lock. |

## Review Focus

1. **Prod flag-off.** Every connect gets 4503. The client must make exactly one attempt per foreground session of the screen and leave no timer running. Pinned in Task 3 (`does not reconnect after 4503`) and Task 6 (`flag off: one connect, no retry, no toast`).
2. **Background and resume.** Hiding closes the socket. Showing opens one new socket and runs one catch-up, and replies that landed in between show up as the pill. It must not open two sockets or retry in a loop. Pinned in Task 6 (`hide closes, show reconnects once and offers missed replies`).
3. **Own-reply race.** The event for the reader's own reply arrives while the composer is open or while the refresh walk runs. It must never show twice, add to the pill, or use up the intro toast. Pinned in Task 4 (`held post.created events already in the list are dropped`) and Task 6 (`own reply never counts`).
4. **An expired token on resume** (the app sat in the background past 15 min): 4401, then one peek read (which refreshes through `ApiService`), one reconnect, and never a loop. Pinned in Task 3 (`4401 refreshes once and reconnects once; a second 4401 stops`).
5. **A stray frame fetches nothing:** another topic's event, `v != 1`, an unknown type, bad JSON, a binary frame, or a post event with no integer `post_id`. Pinned in Task 2 (`parseLiveEvent`) and Task 4 (`ignores an event for another topic`).

---

### Task 1: API additions (`authToken`, `fetchPost`, `peek`)

**Files:**

- Modify: `plant_community_mobile/lib/services/api_service.dart`. Add `String? get authToken => _authToken;` next to `hasAuthToken` (line ~499), with a doc comment saying it is for the forum socket's `Authorization` header and must never be logged.
- Modify: `plant_community_mobile/lib/features/forum/services/forum_api.dart`
  - In the abstract `ForumApi`: `Future<ForumTopicDetail> fetchTopicDetail(int topicId, {bool peek = false});` and `Future<ForumPost?> fetchPost(int postId);`
  - In `HttpForumApi`: `peek` sends `queryParameters: {'peek': '1'}`. `fetchPost` GETs `/forum/posts/$postId/`, maps the body with `ForumPost.fromJson`, and returns `null` for an `ApiException` whose `statusCode == 404`. Any other error rethrows.
- Modify: `plant_community_mobile/test/features/forum/support/forum_test_support.dart` (`FakeForumApi`)
  - `fetchTopicDetail` takes `{bool peek = false}` and counts `peekCalls`. A `List<ForumTopicDetail> peekDetails` returns successive fixtures for peek reads (the last one repeats), falling back to `topicDetail` when empty.
  - `fetchPost` returns from `Map<int, ForumPost> postsById` (null when the id is missing) and records `fetchPostCalls`.
- Test: `plant_community_mobile/test/features/forum/forum_api_live_test.dart`, using the `_FakeApiService` harness from `forum_api_link_preview_test.dart`.

**Interfaces:**

- Produces: `ApiService.authToken`, `ForumApi.fetchPost(int) → Future<ForumPost?>`, `ForumApi.fetchTopicDetail(int, {bool peek})`, `FakeForumApi.peekCalls`, `peekDetails`, `postsById` and `fetchPostCalls`.

- [ ] **Step 1: Write the failing tests:**
  - `fetchTopicDetail(peek: true) sends peek=1`, and the plain call sends no query;
  - `fetchPost maps the post`;
  - `fetchPost returns null on 404`;
  - `fetchPost rethrows a 500`;
  - in `test/api_service_test.dart`: `authToken reflects setAuthToken and replaceAuthToken`.
- [ ] **Step 2: Run** `cd plant_community_mobile && flutter test test/features/forum/forum_api_live_test.dart test/api_service_test.dart`. Expected: FAIL to compile, because the methods don't exist.
- [ ] **Step 3: Implement** the four additions above, plus the `FakeForumApi` changes.
- [ ] **Step 4: Run it again,** then run `flutter analyze`. Expected: PASS and no issues.
- [ ] **Step 5: Commit:** `feat(mobile): single-post fetch, peek topic read and the socket's token getter (forum live, slice 4)`.

### Task 2: The setting, the toast flags, the event parser and the channel seam

**Files:**

- Create: `plant_community_mobile/lib/features/forum/live/live_updates_settings.dart`
- Create: `plant_community_mobile/lib/features/forum/live/forum_live_event.dart`
- Create: `plant_community_mobile/lib/features/forum/live/forum_live_channel.dart`
- Create: `plant_community_mobile/lib/features/settings/live_updates_tile.dart`
- Modify: `plant_community_mobile/lib/features/settings/settings_screen.dart`. Add `const CanopyLabel('FORUM')`, a gap and `const LiveUpdatesTile()` after the `NOTIFICATIONS` block.
- Test: `test/features/forum/live/live_updates_settings_test.dart`, `test/features/forum/live/forum_live_event_test.dart`, `test/features/forum/live/forum_live_channel_test.dart`, `test/features/settings/live_updates_tile_test.dart`
- Modify: `test/features/settings/settings_screen_test.dart`. Its `_wrap` gains an `authServiceProvider` override (`FakeAuthService(loggedIn: false)`); without it the screen's new auth watch builds the real `AuthService`.

**Interfaces:**

- Produces, in `live_updates_settings.dart`:
  - `@Riverpod(keepAlive: true) class LiveUpdatesSetting` with `bool build()` (true until the stored value loads) and `void setEnabled(bool on)`. It follows `ThemeModeNotifier`: a `static const _storage = FlutterSecureStorage()`, a load in `build`, and try/catch with a `[FORUM_LIVE]` `debugPrint` on failure.
  - `class LiveToastFlags` with `Future<bool> takeIntro()`, `Future<bool> mayShowMissingOut(DateTime now)` and `Future<void> markMissingOutShown(DateTime now)`; provided by `final liveToastFlagsProvider = Provider<LiveToastFlags>((ref) => LiveToastFlags(const FlutterSecureStorage()))`, which is keepAlive so its per-launch flag lives as long as the app.
  - The constants `liveUpdatesKey = 'forum_live_updates'`, `liveIntroKey = 'forum_live_intro_shown'`, `missingOutKey = 'forum_live_missing_out_at'` and `missingOutQuiet = Duration(hours: 24)`.
- Produces, in `forum_live_event.dart`:
  - `enum LiveStatus { off, connecting, live, stopped, gone }`
  - `sealed class LiveFrame`, with `final class LivePong extends LiveFrame` and `final class LiveEvent extends LiveFrame { final LiveEventType type; final int topicId; final int? postId; }`
  - `enum LiveEventType { postCreated, postUpdated, postRemoved, topicUpdated, topicRemoved }`
  - `LiveFrame? parseLiveFrame(Object? data)`
- Produces, in `forum_live_channel.dart`:
  - `abstract interface class ForumLiveChannel { Stream<Object?> get frames; void send(String text); Future<void> close(); int? get closeCode; }`
  - `typedef ForumLiveConnector = Future<ForumLiveChannel> Function(Uri uri, Map<String, String> headers);`
  - `final forumLiveConnectorProvider = Provider<ForumLiveConnector>((ref) => ioForumLiveConnector);` The `dart:io` implementation `ioForumLiveConnector` calls `WebSocket.connect(uri.toString(), headers: headers)` and wraps the socket.
  - `Uri topicLiveUri(String apiBaseUrl, int topicId)`
- Produces, in `test/features/forum/support/forum_test_support.dart`:
  - `class FakeLiveChannel implements ForumLiveChannel`, with `sent`, `closedByClient`, `serverFrame(Object)` and `serverClose(int? code)` (which sets `closeCode` and closes `frames`).
  - `class FakeLiveConnector`, with `List<({Uri uri, Map<String,String> headers})> connects`, `List<FakeLiveChannel> channels`, `Object? throwOnConnect` and `ForumLiveConnector get fn`.
  - `List<Override> liveTestOverrides(FakeLiveConnector c)`, which overrides `forumLiveConnectorProvider` with `c.fn`.

- [ ] **Step 1: Write the failing tests.** Call `FlutterSecureStorage.setMockInitialValues({})` in `setUp`.
  - Setting: `defaults to on`; `stored off is read back after load`; `setEnabled(false) writes 'off'`; `a storage read that throws leaves it on`.
  - Flags: `takeIntro is true once, then false, across a new LiveToastFlags on the same storage`; `mayShowMissingOut is false after markMissingOutShown in the same launch`; `false within 24 h of the stored time in a new launch` (a new `LiveToastFlags`, with the stored time at `now - missingOutQuiet + 1 s`); `true again after 24 h`.
  - Parser: `parses each of the five types`; `maps a pong`; `null for v != 1`; `null for an unknown type`; `null for bad JSON`; `null for a List<int> (binary) frame`; `null for a post event with no integer post_id`; `null for a non-integer topic_id`; `ignores extra fields`.
  - URI: `topicLiveUri('http://localhost:8000/api/v1', 12)` is `ws://localhost:8000/ws/forum/topics/12/`, and `topicLiveUri('https://api.houseplant-md.com/api/v1', 12)` is `wss://api.houseplant-md.com/ws/forum/topics/12/`.
  - Tile: `hidden when signed out`; `a "Live updates" switch, on by default, when signed in`; `toggling it calls setEnabled(false)` (override the setting with a no-storage fake, the `_FakeDensityNotifier` pattern); `the subtitle names this device`.
- [ ] **Step 2: Run** `flutter test test/features/forum/live test/features/settings`. Expected: FAIL, missing files.
- [ ] **Step 3: Implement.**
  - The tile is a `ConsumerWidget`. It returns `SizedBox.shrink()` unless `authServiceProvider.select((s) => s.isAuthenticated)` is true. Subtitle copy: "Show new replies, edits and deletes in an open topic as they happen, on this device. Off, pull down on a topic to check for new replies."
  - The flags class keeps `_shownThisLaunch` in memory. `markMissingOutShown` sets it and writes `now.millisecondsSinceEpoch.toString()`. Every read and write is in try/catch: a failed read counts as "never shown", and a failed write is ignored.
  - Run build_runner.
- [ ] **Step 4: Run it again.** Expected: PASS. Then run `flutter analyze`.
- [ ] **Step 5: Commit:** `feat(mobile): Live updates setting, toast flags, live event parser and socket seam`.

### Task 3: `ForumLiveClient` (connect, close codes, backoff, heartbeat)

**Files:**

- Create: `plant_community_mobile/lib/features/forum/live/forum_live_client.dart`
- Test: `test/features/forum/live/forum_live_client_test.dart`

**Interfaces:**

- Consumes: `ForumLiveConnector`, `ForumLiveChannel`, `parseLiveFrame`, `LiveStatus` and `LiveEvent` (Task 2).
- Produces:
  - `class ForumLiveClient`
    - constructor `ForumLiveClient({required ForumLiveConnector connect, required Uri uri, required String? Function() token, required Future<void> Function() refreshAuth, required void Function(LiveEvent) onEvent, required void Function() onOpen, required void Function(LiveStatus) onStatus, double Function()? random})`
    - methods `void start()` and `Future<void> close()`
  - the constants `liveCloseDisabled = 4503`, `liveCloseUnauthenticated = 4401`, `liveCloseNotFound = 4404`, `liveCloseLimited = 4429`, `livePingInterval = Duration(seconds: 25)` and `livePongTimeout = Duration(seconds: 10)`
  - `Duration liveBackoff(int attempt, double random)`
- Rules: `start()` with a null `token()` reports `stopped` and connects nothing. The headers are `{'Authorization': 'Bearer <token>'}`. Status transitions are as in slice 3: `connecting` on each connect, `live` on the first frame-ready (after `connect` resolves), `stopped` after 4503, 4429 or a second 4401, `gone` after 4404, and `off` after `close()`. After `close()`, a connect still in flight closes its channel on arrival.

- [ ] **Step 1: Write the failing tests.** Use `testWidgets` with `tester.pump(duration)` to drive timers, and `random: () => 0.5`.
  - `liveBackoff: at random 0.5, attempt 0 is 3000 ms and attempt 3 is 15500 ms (the cap already applies); at random 1.0, attempt 10 is 30000 ms`.
  - `sends the bearer header and reports connecting then live, calling onOpen`.
  - `no token: no connect, status stopped`.
  - `delivers events and drops null frames and pongs`.
  - `does not reconnect after 4503`: `serverClose(4503)`, pump 2 min, then exactly one connect and status `stopped`. A `close()` afterwards changes nothing, and the test ends with no pending timer (`testWidgets` fails on one).
  - `does not reconnect after 4429`.
  - `4404 reports gone and does not reconnect`.
  - `4401 refreshes once and reconnects once; a second 4401 stops`: `refreshAuth` is called once, there are 2 connects, the second carries the token `token()` returns after the refresh, and the status ends `stopped`.
  - `a thrown connect retries with backoff`: `throwOnConnect = WebSocketException('refused')`, then no second connect at 2999 ms and one at 3000 ms.
  - `the backoff resets after a successful open`.
  - `pings every 25 s, and reconnects when no frame arrives within 10 s`.
  - `any frame clears the pong timer`.
  - `close() stops everything`: no reconnect, the status is `off`, and the channel is `closedByClient`.
  - `close() during an in-flight connect closes that channel when it arrives`.
- [ ] **Step 2: Run** `flutter test test/features/forum/live/forum_live_client_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement it.** It is a plain class with `_channel`, `_sub`, `_attempt`, `_retriedAuth`, `_closed` and three `Timer?` fields (retry, ping, pong). After the frame stream's `onDone`, read `closeCode` and apply the rules. The backoff formula is D6.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(mobile): topic live socket client with close-code rules, backoff and heartbeat`.

### Task 4: Local splices and the `TopicLive` notifier

**Files:**

- Modify: `plant_community_mobile/lib/features/forum/providers/forum_providers.dart`
  - `TopicPosts.applyLivePost(ForumPost post)`: append when the id is absent, splice when present.
  - `TopicPosts.removeLocal(int postId)`: the local half of `deletePost`, with no API call.
  - `TopicDetail.applyPeek(ForumTopicDetail fresh)`: `state = AsyncData(fresh)`.
- Create: `plant_community_mobile/lib/features/forum/live/topic_live.dart`
- Test: `test/features/forum/live/topic_live_test.dart` (a `ProviderContainer` with `forumApiProvider`, `authServiceProvider`, `liveUpdatesSettingProvider` and `liveTestOverrides`), plus the splice tests in `test/features/forum/providers/forum_providers_test.dart`.

**Interfaces:**

- Consumes: `ForumLiveClient` (Task 3), `topicLiveUri`, `forumLiveConnectorProvider`, `liveUpdatesSettingProvider`, `liveToastFlagsProvider` (Task 2), `ApiService.authToken`, `fetchPost` and `fetchTopicDetail(peek:)` (Task 1).
- Produces:
  - `class TopicLiveState { final LiveStatus status; final int pendingCount; final Set<int> flashIds; final int introSeq; }`. `introSeq` goes up by one when the intro toast is due. `gone` is `status == LiveStatus.gone`.
  - `@riverpod class TopicLive extends _$TopicLive`, which is autoDispose, with `TopicLiveState build(int topicId)`.
  - `void setReaderAtBottom(bool atBottom)`
  - `void suspend()` and `void resume()`
  - `void beginOwnReply()` and `void endOwnReply()`
  - `Future<int?> takePending()`: walks every page, then returns the id of the first new post (null if none), moves the new ids into `flashIds`, and sets `pendingCount` to 0.
  - `void clearFlash(int postId)`
- Rules:
  - `build` watches `authServiceProvider.select(isAuthenticated)` and `liveUpdatesSettingProvider`. With both true and not suspended, it starts a client; otherwise the status is `off`. `ref.onDispose` closes the client and cancels the debounce timer.
  - `refreshAuth` is `fetchTopicDetail(topicId, peek: true)` with errors swallowed (D2).
  - `onOpen` runs the catch-up (D9).
  - `post.created` (not held, not in the list, fetched non-null): insert when at the bottom, `!hasMore` and `pendingCount == 0` (`applyLivePost`, then add to `flashIds`); otherwise `pendingCount + 1`. The first insert or pill of the session calls `takeIntro()` and bumps `introSeq` when it returns true.
  - `post.updated`: fetch, then `applyEditedPost` when the post is loaded.
  - `post.removed`: `removeLocal`. If it was `solvedPostId`, schedule the topic refetch.
  - `topic.updated`: schedule the debounced refetch (500 ms), which ends in `applyPeek`.
  - `topic.removed`, or a client status of `gone`: the status is `gone`, and the client is closed.

- [ ] **Step 1: Write the failing tests.**
  - Splices: `applyLivePost appends a new id and splices an existing one`; `removeLocal removes without calling the API`.
  - Notifier:
    - `connects when signed in with the setting on`;
    - `no socket when signed out`;
    - `no socket when the setting is off`;
    - `turning the setting off closes the socket`;
    - `catch-up on open sets the pill from the peek count when every page is loaded`;
    - `catch-up leaves the pill alone with pages unloaded`;
    - `post.created at the bottom inserts and flashes`;
    - `post.created when scrolled up counts in the pill`;
    - `post.created with pages unloaded counts in the pill`;
    - `post.created while the pill is showing counts, never inserts`;
    - `a post.created that 404s does nothing`;
    - `a post.created already in the list does nothing`;
    - `held post.created events already in the list are dropped` (`beginOwnReply`, an event, the fake list gains the post, `endOwnReply`: there is no insert, the pill is 0 and `introSeq` is 0);
    - `a held event for someone else's reply that isn't in the list is applied on release`;
    - `post.updated splices the fetched post`;
    - `post.removed removes it, and removing the accepted answer refetches the topic`;
    - `topic.updated: three events in 500 ms make one peek read`;
    - `topic.removed sets gone`;
    - `ignores an event for another topic`;
    - `the intro is due once, on the first insert`;
    - `a catch-up pill does not trigger the intro`;
    - `a catch-up that returns after 4503 sets no pill` (the peek completes after `serverClose(4503)`, with `peekDetails` one reply higher);
    - `4401: two peek reads (refresh, then the reconnect's catch-up) and one reconnect` (`peekCalls == 2`);
    - `suspend closes, resume reconnects and catches up`;
    - `takePending walks every page and returns the first new id`.
- [ ] **Step 2: Run** `flutter test test/features/forum/live/topic_live_test.dart test/features/forum/providers/forum_providers_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement** the splices and the notifier, then run build_runner.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(mobile): TopicLive notifier applies live events to the open topic`.

### Task 5: `TopicMissingOut`, the signed-out check

**Files:**

- Create: `plant_community_mobile/lib/features/forum/live/topic_missing_out.dart`
- Test: `test/features/forum/live/topic_missing_out_test.dart` (a `testWidgets` with an empty `SizedBox` host, so `tester.pump(duration)` drives the 30 s timer)

**Interfaces:**

- Consumes: `fetchTopicDetail(peek: true)` (Task 1) and `liveToastFlagsProvider` (Task 2).
- Produces:
  - `@riverpod class TopicMissingOut extends _$TopicMissingOut`, which is autoDispose, with `int build(int topicId)`. The state is a sequence number that goes up by one each time the toast is due.
  - `void suspend()` and `void resume()`
  - `const missingOutPollInterval = Duration(seconds: 30)`
- Rules: it runs only while signed out (it watches `isAuthenticated`) and not suspended. The first read sets the baseline. A later read with a higher `replyCount` and `mayShowMissingOut(DateTime.now())` true bumps the state, calls `markMissingOutShown`, and stops the timer for this screen. A failed read is silent.

- [ ] **Step 1: Write the failing tests:**
  - `no polling while signed in`;
  - `the first read sets the baseline without a toast`;
  - `a higher count makes the toast due once, then stops polling`;
  - `not due when mayShowMissingOut is false`;
  - `suspend stops polling, and resume restarts it`;
  - `a failed read is silent and the next tick retries`.
- [ ] **Step 2: Run** `flutter test test/features/forum/live/topic_missing_out_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement it,** then run build_runner.
- [ ] **Step 4: Run it again.** Expected: PASS.
- [ ] **Step 5: Commit:** `feat(mobile): signed-out missing-out check on the topic screen`.

### Task 6: The thread screen

**Files:**

- Modify: `plant_community_mobile/lib/features/forum/screens/forum_thread_screen.dart`
- Create: `plant_community_mobile/lib/features/forum/widgets/live_flash.dart` (the 2.5 s highlight plus the optional slide-in)
- Modify: `plant_community_mobile/lib/features/forum/screens/forum_composer_screen.dart` (D20, reply mode only)
- Test: `test/features/forum/screens/forum_thread_live_test.dart`, plus `test/features/forum/screens/forum_composer_screen_test.dart` for D20
- Modify: every existing test that pumps `ForumThreadScreen`, which today is `forum_read_path_test.dart`, `forum_thread_engagement_test.dart`, `forum_thread_links_test.dart`, `forum_thread_parity_test.dart`, `test/routing/app_router_test.dart` and `test/services/push_message_router_service_test.dart` (re-check with `grep -rl ForumThreadScreen test`). Add `...liveTestOverrides(FakeLiveConnector())` to their overrides, so no test opens a real `dart:io` socket. Change no assertion.

**Interfaces:**

- Consumes: `topicLiveProvider` (Task 4), `topicMissingOutProvider` (Task 5), `liveUpdatesSettingProvider` and `LiveToastFlags` (Task 2).
- Changes:
  - `ForumThreadScreen` becomes a `ConsumerStatefulWidget`. It owns an `AppLifecycleListener` (`onHide` and `onShow` call `suspend`/`resume` on both notifiers). It `ref.listen`s `introSeq` and the missing-out state to show the D14 toasts.
    - **Turn off** calls `setEnabled(false)` and shows "Live updates off" with **Undo** (`setEnabled(true)`).
    - **Sign in** and **Sign up** call `context.pushNamed('login')` / `pushNamed('register')`.
  - When `status == gone`, the body is a centred "This topic is no longer available." and there is no Reply button.
  - `_openReply` wraps the push and refresh in `beginOwnReply()` and a `finally` `endOwnReply()` (D11).
  - `_ThreadBody`:
    - takes `pendingCount`, `flashIds`, `onTakePending` (returns the `Future<int?>` target id), `onAtBottom` and `onRefresh`;
    - wraps the `ListView` (not the `Column` with `_SolvedBanner`) in a `RefreshIndicator`, with `AlwaysScrollableScrollPhysics`. The "No posts yet." branch becomes a scrollable list, so it can be pulled. `onRefresh` is `refreshAfterReply()` plus `invalidate(topicDetailProvider)`;
    - a `_scrollController` listener reports at-bottom as `pixels >= maxScrollExtent - 48`;
    - renders a bottom-centre pill, `"$n new repl${n == 1 ? 'y' : 'ies'}"`, when `pendingCount > 0`. Tapping it awaits `onTakePending` and then chases to the returned id. `_jumpToAnswer` generalises to `_chaseTo(int postId, GlobalKey key)`, with a third single key `_firstNewKey` that `_keyFor` gives to that id after `highlightPostId` and `solvedPostId`;
    - wraps each card whose id is in `flashIds` in `LiveFlash`, which calls `onFlashDone(id)` → `clearFlash` when the fade ends;
    - after a live insert while at the bottom, scrolls to `maxScrollExtent` post-frame: `jumpTo` with reduce motion, otherwise `animateTo` over 250 ms.

- [ ] **Step 1: Write the failing widget tests.** Use `FakeForumApi`, a `FakeLiveConnector`, `FakeAuthService` and `FlutterSecureStorage.setMockInitialValues({})`.
  - `flag off: one connect, no retry, no pill, no toast`: `peekDetails` returns `replyCount + 1`, so a catch-up that wrongly counted *would* set a pill. Then `serverClose(4503)`, pump 2 min, and expect one connect, no pill and no `SnackBar`.
  - `a reply at the bottom slides in with the intro toast`. The intro toast's **Turn off** closes the socket (`closedByClient`) and shows "Live updates off". **Undo** reconnects (a second connect).
  - `the intro toast shows once per device`: a second insert in a new pump of the screen shows no toast.
  - `scrolled up: the pill counts, and tapping it loads, highlights and reveals the first new reply`. Use a 40-post thread over two pages, so the target starts off-screen. Expect `find.text(firstNewBody)` hit-testable after the tap.
  - `own reply never counts`: open the composer through the Reply button, emit `post.created` for the new id while the composer is open, publish, and expect no pill, no toast and exactly one card with that body.
  - `edit splices in place and keeps the scroll offset`.
  - `delete removes the card`.
  - `topic.updated relocks the topic: the Reply button goes away after the debounce`.
  - `topic.removed shows "This topic is no longer available." and no Reply button`.
  - `hide closes, show reconnects once and offers missed replies`: drive it with `tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden)`, then `.resumed`. In between, `peekDetails` gains two replies, so the pill reads "2 new replies".
  - `pull-to-refresh loads a new reply with the setting off`: drag the list down with `tester.fling`.
  - `signed out: no socket, and the missing-out toast after the count grows, with Sign in and Sign up`. **Sign in** routes to `login`, using a `GoRouter` host like `forum_thread_engagement_test.dart`'s second wrap.
  - `reduce motion: an inserted reply is highlighted but not animated` (`MediaQuery(data: MediaQueryData(disableAnimations: true))`).
  - In the composer test: `a topic locked while typing keeps the text, disables Post and shows the locked notice` (pump with `UncontrolledProviderScope(container)`, type a body, then call `container.read(topicDetailProvider(10).notifier).applyPeek(lockedDetail)`, which is the same path `TopicLive` uses); and `a reply 409 on a locked topic shows the locked notice`.
- [ ] **Step 2: Run** `flutter test test/features/forum/screens/forum_thread_live_test.dart`. Expected: FAIL.
- [ ] **Step 3: Implement** the screen changes and `LiveFlash`, then add the overrides to the existing tests.
- [ ] **Step 4: Run** the new file, then `flutter test test/features/forum test/routing test/services`. Expected: PASS, with every existing thread test unchanged apart from its overrides.
- [ ] **Step 5: Commit:** `feat(mobile): live replies, the new-replies pill, pull-to-refresh and toasts on the thread screen`.

### Task 7: Docs, the full gate and the real-socket smoke

**Files:**

- Modify: `backend/docs/patterns/domain/forum.md`. Add a "Mobile client (slice 4)" section next to the web one: the close-code table, D2 (refresh via the peek read), D8 (hide/show), D11 (own reply) and the fake seam.
- Modify: `plant_community_mobile/docs/patterns/riverpod.md`. Add a short pattern, "A socket notifier per screen (autoDispose family, client closed in onDispose, lifecycle from the screen)".
- Modify: `docs/LEARNINGS.md`. Add a 2026-10-19 entry, but only for lessons this slice actually hit. Write none if there were none.

- [ ] **Step 1: Full gate.** Run `cd plant_community_mobile && flutter analyze && flutter test > $WS/flutter-test.log 2>&1; tail -5 $WS/flutter-test.log`. Expected: `No issues found!` and `All tests passed!`. Also run `python3 scripts/check_flutter_codegen.py` from the repo root. Expected: clean.
- [ ] **Step 2: Real `dart:io` smoke** against a local uvicorn with `FORUM_LIVE_UPDATES_ENABLED=True` on a throwaway DB (slice 3's recipe: mint a JWT for a test user; don't use the 5/15 min login endpoint). Write the smoke script in the plan's workspace, not the repo. It is a plain `dart run` script with **no package imports**: `forum_live_channel.dart` pulls in Riverpod and Flutter, which `dart run` can't load. It calls `WebSocket.connect('ws://localhost:8000/ws/forum/topics/<id>/', headers: {'Authorization': 'Bearer …'})` directly, with the same headers and URL shape as `ioForumLiveConnector` and `topicLiveUri`.
  - Check that it opens.
  - Check that a reply posted over REST arrives as `post.created` with the right ids.
  - Check that a ping gets a pong.
  - Check that a bad token closes with 4401.
  - Restart with the flag off: the close is 4503.
  - Drop the DB afterwards. Record the results in the ledger and the PR body.
- [ ] **Step 3: Simulator check (best effort).** Run the app on the iOS simulator against the local server and open a topic. A local Google sign-in is known to fail without `GOOGLE_APPLICATION_CREDENTIALS` (memory), so if it can't be signed in, record that and leave the signed-in device check to slice 5's owner check. Signed out, confirm pull-to-refresh and that no socket opens (the server log shows no `[FORUM_LIVE]` line).
- [ ] **Step 4: Commit:** `docs: mobile live replies client (slice 4)`.

## Out of scope (slice 5 or later)

- Turning the flag on, and the owner's TestFlight device check (two accounts, phone plus web).
- The slice 5 server gates: re-checking visibility for open sockets, a per-IP connect-rate gate, confirming production `CORS_ALLOWED_ORIGINS`, and declaring `FORUM_LIVE_UPDATES_ENABLED` in `.railway/railway.ts`.
- Editing a post that someone else deletes while the composer is open. The composer's existing 409/404 handling keeps the text and shows the server's sentence.
- Reactions, presence, and a live topic list.
