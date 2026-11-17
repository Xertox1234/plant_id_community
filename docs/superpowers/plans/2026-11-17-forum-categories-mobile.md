# Forum Categories on Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Flutter forum tab opens on a traditional index of categories and forums, with
link forums, password forums and collapsible categories, as the web has.

**Architecture:** The app stops calling `/forum/boards/` and reads `GET /forum/categories/`.
The flat forum list the search filter and topic header need is derived from that one
response. The only backend change is a signed unlock token so a password unlock survives
the app's cookie-less requests.

**Tech Stack:** Flutter, Riverpod 3 (codegen), go_router, dio (`ApiService`),
flutter_secure_storage, url_launcher; Django, DRF, `django.core.signing`.

**Spec:** `docs/superpowers/specs/2026-11-17-forum-categories-mobile-design.md`. Read it
first; section numbers below (§) point into it.

Paths: `mob/` = `plant_community_mobile/`, `forum/` = `mob/lib/features/forum/`,
`wf/` = `backend/packages/wagtail_forum/wagtail_forum/`.

## Global Constraints

- `/forum/boards/` response keys and behaviour do not change (no links, no locked forums).
- Four slices, one feature branch and one PR each, in order. The app works after each.
- Riverpod per `mob/docs/patterns/riverpod.md`. After any `@riverpod` change run
  `flutter pub run build_runner build --delete-conflicting-outputs` and commit the output.
- UI per `mob/docs/patterns/flutter-ui-design.md`: Canopy tokens only, light and dark,
  tap targets at least 48pt, reduced motion respected.
- The forum home keeps its single `Column` inside the `ListView` (`forum/forum_screen.dart`,
  comment at the `ListView`).
- Task 6 is permission code: no cheap-worker tools (`ask-kimi`, `kimi-write`,
  `kimi-challenge`) on it.
- Backend tests: `cd backend && pytest packages/wagtail_forum -q`, then the full
  `pytest -q` before the PR (an app-scoped run alone is a false green in this repo).
- App checks before every PR: `cd plant_community_mobile && flutter analyze && flutter test`.
- No destructive git commands; never push to `main`.

## Review Focus

Conditions the spec implies that are most likely to bite a real user. Each has a test in
the task named.

1. The feed returns a category whose `icon` or `colour` is a value the app does not know
   (a new accent name, a multi-codepoint emoji). Expected: the row falls back per §7.2 and
   never throws. → Task 2.
2. The categories request fails while a device copy of nothing exists (first launch,
   offline). Expected: the Forums section shows "Could not load forums." with Retry, and
   the rest of the tab still loads. → Task 3.
3. A stored unlock token has expired or the forum password changed. Expected: the forum
   shows as locked again and tapping it opens the unlock screen; the dead token is dropped.
   → Task 7.
4. A link row's `link_url` is not http or https (a row saved around validation).
   Expected: nothing opens and a message says the link cannot be opened. → Task 5.
5. A category id in the saved collapsed list no longer exists, or the member collapses
   every category. Expected: unknown ids are ignored, and the tab shows only headers
   without error. → Task 9.

---

## Slice 1: category index (branch `feat/mobile-forum-categories`)

### Task 0: Branch and docs

- [ ] Create the branch from current `main`, add this plan and the spec
  (`docs/superpowers/specs/2026-11-17-forum-categories-mobile-design.md`), and commit:
  `docs: mobile forum categories design and plan`. They are not in `main` yet.

### Task 1: Models and API call

**Files:**

- Modify: `forum/models/forum_board.dart`
- Create: `forum/models/forum_category.dart` (export it from `forum/models/models.dart`)
- Modify: `forum/services/forum_api.dart`
- Modify: `mob/test/features/forum/support/forum_test_support.dart`
- Test: `mob/test/features/forum/models/forum_category_test.dart`

**Interfaces — Produces:**

- `ForumBoard` gains, all optional with these defaults: `String icon = ''`,
  `String colour = ''`, `bool hasUnread = false`, `bool isLocked = false`,
  `bool isClosed = false`, `bool canPost = false`, `DateTime? lastPostAt`. JSON keys:
  `icon, colour, has_unread, is_locked, is_closed, can_post, last_post_at`.
- `class ForumLink { int id; String title; String slug; String description;
  String linkUrl; bool trackClicks; int? clickCount; factory ForumLink.fromJson }`.
- `class ForumCategory { int id; String title; String slug; String description;
  String icon; String colour; bool hasUnread; List<ForumBoard> forums;
  List<ForumLink> links; factory ForumCategory.fromJson }`.
- `ForumApi.fetchCategories() -> Future<List<ForumCategory>>`:
  `GET /forum/categories/`, reads `results`.
- `ForumApi.fetchBoards()` is removed, along with the `/forum/boards/` call.
- Test fake: `categories` list, `categoriesError`, `fetchCategoriesCalls`, replacing the
  `boards` trio. Keep a `boards` getter that flattens `categories` so existing tests that
  read it still compile.

- [ ] **Step 1: Write failing model tests**

```dart
test('parses a category with forums and links', () {
  final c = ForumCategory.fromJson({
    'id': 17, 'title': 'Community', 'slug': 'community', 'description': '',
    'icon': '🌱', 'colour': 'bloom', 'has_unread': true,
    'forums': [{'id': 15, 'title': 'Show & tell', 'slug': 'show-tell',
      'description': 'd', 'topic_count': 3, 'post_count': 9,
      'last_post_at': '2026-11-17T10:00:00Z', 'has_unread': true,
      'is_locked': false, 'is_closed': true, 'can_post': false,
      'icon': '📷', 'colour': 'sage'}],
    'links': [{'id': 20, 'title': 'Seed swap', 'slug': 'seed-swap',
      'description': '', 'link_url': 'https://example.org', 'track_clicks': true,
      'click_count': 4}],
  });
  expect(c.forums.single.lastPostAt, DateTime.utc(2026, 11, 17, 10));
  expect(c.forums.single.isClosed, isTrue);
  expect(c.links.single.clickCount, 4);
});
test('missing and null fields take defaults', () {
  final c = ForumCategory.fromJson({'id': 1});
  expect(c.title, ''); expect(c.forums, isEmpty); expect(c.links, isEmpty);
  final b = ForumBoard.fromJson({'id': 2, 'last_post_at': null, 'icon': null});
  expect(b.icon, ''); expect(b.lastPostAt, isNull); expect(b.isLocked, isFalse);
});
test('rows that are not JSON objects are skipped', () {
  final c = ForumCategory.fromJson({'id': 1, 'forums': [1, 'x', null]});
  expect(c.forums, isEmpty);
});
```

- [ ] **Step 2:** Run `flutter test test/features/forum/models/forum_category_test.dart`. Expected: FAIL, `ForumCategory` undefined.
- [ ] **Step 3:** Implement the models, `fetchCategories()`, remove `fetchBoards()`, update the fake.
- [ ] **Step 4:** Run the test file. Expected: PASS. (`flutter analyze` still fails until Task 3; that is expected.)
- [ ] **Step 5:** Commit: `feat(mobile): forum category models and feed call`.

### Task 2: Icon and colour from the server

**Files:**

- Modify: `forum/utils/board_identity.dart`
- Modify: `mob/lib/shared/widgets/canopy_accents.dart` (`CanopyAccentTile`)
- Test: `mob/test/features/forum/utils/board_identity_test.dart` (extend if present)

**Interfaces — Produces:**

- `BoardIdentity` gains `String? emoji` (null = use `icon`).
- `BoardIdentity boardIdentityOf(ForumBoard board)`: tone from `board.colour` when it is
  one of `sage, pollen, bloom, orchid`, else the slug's tone; `emoji` from `board.icon`
  when non-empty, else null (so the slug's Lucide icon shows). Icon and colour fall back
  independently (§7.2). `boardIdentity(slug)` stays for callers that have only a slug.
- `CanopyAccentTile` gains `String? emoji`; when set it renders the emoji as text in place
  of the `Icon`, same tile size and tone background.

- [ ] **Step 1: Write failing tests**

```dart
ForumBoard board({String slug = 'x', String icon = '', String colour = ''}) => ...;
test('server colour and icon win', () {
  final i = boardIdentityOf(board(slug: 'care-problems', icon: '🪴', colour: 'orchid'));
  expect(i.tone, CanopyTone.orchid); expect(i.emoji, '🪴');
});
test('each falls back on its own', () {
  final i = boardIdentityOf(board(slug: 'care-problems', colour: 'orchid'));
  expect(i.emoji, isNull); expect(i.icon, LucideIcons.droplet);
  expect(i.tone, CanopyTone.orchid);
});
test('unknown colour name falls back to the slug tone', () {
  final i = boardIdentityOf(board(slug: 'care-problems', colour: 'teal'));
  expect(i.tone, CanopyTone.pollen);
});
testWidgets('tile shows a multi-codepoint emoji without overflow', (t) async {
  // pump CanopyAccentTile(icon: LucideIcons.leaf, tone: ..., emoji: '👩‍🌾')
  expect(find.text('👩‍🌾'), findsOneWidget); expect(t.takeException(), isNull);
});
```

- [ ] **Step 2:** Run. Expected: FAIL, `boardIdentityOf` undefined.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(mobile): forum icon and colour from the server`.

### Task 3: Providers, the Forums section and the new home order

**Files:**

- Modify: `forum/providers/forum_providers.dart`
- Create: `forum/widgets/home/forum_categories_section.dart`
- Delete: `forum/widgets/home/forum_boards_section.dart` and its test
- Modify: `forum/forum_screen.dart`, `forum/screens/forum_topics_screen.dart`
- Test: `mob/test/features/forum/widgets/home/forum_categories_section_test.dart`,
  `mob/test/features/forum/forum_home_layout_test.dart`,
  `mob/test/features/forum/forum_home_reset_test.dart`

**Interfaces — Consumes:** Task 1 models and `fetchCategories()`; Task 2 `boardIdentityOf`.

**Interfaces — Produces:**

- `categoriesProvider`: `@riverpod class Categories` with `build()` →
  `fetchCategories()` and `refresh()`, same shape as today's `Boards`, same `forumRetry`.
- `boardsProvider` keeps its name and type (`Future<List<ForumBoard>>`) but is derived:
  every forum of every category with `isLocked == false`, in feed order. It makes no
  request of its own.
- `ForumCategoriesSection({required List<ForumCategory> categories,
  required void Function(ForumBoard) onForumTap,
  void Function(ForumBoard)? onLockedTap, void Function(ForumLink)? onLinkTap,
  Set<int> collapsed = const {}, void Function(ForumCategory)? onToggleCollapse})`.
  In this slice: locked forums and links are not drawn when their callback is null, and a
  category with nothing left to draw is skipped. No collapse chevron when
  `onToggleCollapse` is null.

**Behaviour to build (§7.1):**

- Per category: a header (emoji icon when set, name in the existing `_SectionHeader`
  style) then one `CanopyGroupedCard` of forum rows.
- Forum row = today's `_BoardRow` plus: an 8pt unread dot before the chevron when
  `hasUnread`; the counts line becomes `"12 topics · 80 posts · 2h"` using
  `forumRelativeTime(board.lastPostAt)` when `lastPostAt` is set. Row semantics label
  includes "unread" when the dot shows.
- `forum_screen.dart`: slot order becomes Forums, Your season (signed-in), Experts, Recent
  activity. `_BoardsSection` becomes `_ForumsSection` with no "Boards" header; copy:
  "Could not load forums." and "No forums yet.". `_refresh` invalidates
  `categoriesProvider` in place of `boardsProvider`. `_resetForViewer` now also
  invalidates `categoriesProvider`; rewrite its comment (the feed is per member).
- `forum_topics_screen.dart`: use `boardIdentityOf(board)` when `board` is known; both
  `ref.invalidate(boardsProvider)` calls become `categoriesProvider`.

- [ ] **Step 1: Write failing widget tests**

```dart
testWidgets('two categories render in feed order with their forums', ...
  // General[Plant identification], Community[Show & tell]
  // expect the y of 'General' < 'Plant identification' < 'Community' < 'Show & tell'
testWidgets('unread dot and last activity show', ...
  // forum hasUnread + lastPostAt 2h before `now` → find.bySemanticsLabel(RegExp('unread'))
  // and a counts line ending '· 2h'
testWidgets('a category with only links or locked forums is skipped in slice 1', ...
testWidgets('empty feed shows "No forums yet."', ...
testWidgets('feed error shows Retry and the other sections still build', ...
  // categoriesError = ApiException('x', connectivity: true)
  // expect 'Could not load forums.' and find 'Recent activity'
```

In `forum_home_layout_test.dart`: assert the Forums section's top is above "Experts".
In `forum_home_reset_test.dart`: after the fake auth switches user,
`expect(api.fetchCategoriesCalls, greaterThan(before))`; same after sign-out.

- [ ] **Step 2:** Run those three files. Expected: FAIL.
- [ ] **Step 3:** Implement; run build_runner.
- [ ] **Step 4:** `flutter analyze && flutter test`. Expected: no issues, all pass. Fix
  any remaining `fetchBoards`/`ForumBoardsSection` references in tests.
- [ ] **Step 5:** Commit: `feat(mobile): forum tab opens on the category index`.

### Task 4: Slice 1 checks and PR

- [ ] **Step 1:** Backend guard, in `wf/tests/test_forum_categories_api.py` add
  `test_boards_list_keys_are_the_flutter_contract`: `GET /forum/boards/` rows have exactly
  `{"id","title","slug","description","topic_count","post_count","last_post_at"}` and the
  body has exactly `{"results","intro"}`. Run it. Expected: PASS (no backend code changes).
- [ ] **Step 2:** Run the app on the iOS simulator against live data; screenshot the forum
  tab in light and dark. Expected: GENERAL over four forums, COMMUNITY over Show & tell,
  at the top of the tab.
- [ ] **Step 3:** Open the PR. Body lists the screenshots and says links, password forums
  and collapsing follow in later PRs.

---

## Slice 2: link forums (branch `feat/mobile-forum-links`)

### Task 5: Link rows

**Files:**

- Modify: `forum/services/forum_api.dart`, `forum/widgets/home/forum_categories_section.dart`,
  `forum/forum_screen.dart`, the test fake
- Test: `mob/test/features/forum/services/forum_api_links_test.dart`,
  `forum_categories_section_test.dart`

**Interfaces — Produces:**

- `ForumApi.resolveLink(ForumLink link) -> Future<Uri?>`:
  - `trackClicks == false` → `Uri.tryParse(link.linkUrl)`.
  - `trackClicks == true` → `GET /forum/links/{id}/go/` with
    `Options(followRedirects: false, validateStatus: (s) => s == 302)`; return the
    `location` header parsed. Any failure (exception, no header) → the `linkUrl` fallback.
  - In every case return null unless the scheme is `http` or `https`.
- `_ForumsSection` passes `onLinkTap`: `resolveLink`, then
  `launchUrl(uri, mode: LaunchMode.externalApplication)`; on null or a false launch show
  a SnackBar "This link can't be opened."

**Row (§7.3):** `LucideIcons.externalLink` in the accent tile, title, description, no
counts, no chevron. When `clickCount != null` show "N clicks" in the label style only if
the web row does (check `web/src/pages/forum/CategoryListPage.tsx`; mirror it).

- [ ] **Step 1: Write failing tests**

```dart
test('untracked link resolves to link_url without a request', ...
test('tracked link returns the Location of the 302', ...   // dio adapter stub
test('tracked link falls back to link_url when the go call fails', ...
test('javascript: and empty urls resolve to null', ...
testWidgets('links draw after the forums of their category', ...
testWidgets('tapping a link calls onLinkTap; a null resolve shows the message', ...
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `flutter analyze && flutter test`. Expected: clean.
- [ ] **Step 5:** Commit `feat(mobile): link forums on the forum index`; simulator check
  with a link forum created on a local backend; open the PR.

---

## Slice 3: password forums (branch `feat/mobile-forum-passwords`)

### Task 6: Backend unlock token

**Files:**

- Modify: `wf/services/forum_permissions.py`, `wf/api/forum_rows.py`, `wf/conf.py`,
  `backend/packages/wagtail_forum/README.md` (Passwords paragraph, settings table)
- Test: `wf/tests/test_forum_passwords.py`

**Interfaces — Produces:**

- Setting `FORUM_UNLOCK_TOKEN_MAX_AGE_SECONDS`, default `30 * 24 * 60 * 60`.
- `make_unlock_token(user, forum) -> str`:
  `signing.dumps({"u": user.pk, "f": forum.pk, "p": _unlock_fingerprint(forum.password_hash)}, salt="wagtail_forum.forum_unlock_token")`.
- Request header `X-Forum-Unlock`: comma-separated tokens; only the first 20 are read.
- `unlocked_forum_ids(request)` returns the union of the session unlocks (unchanged rule)
  and the forums of valid header tokens. A token is valid when `signing.loads(...,
  max_age=<setting>)` succeeds, `u == request.user.pk`, the forum still has a password,
  and `p` matches the forum's current fingerprint (`constant_time_compare`). A request
  with no session but a valid token still unlocks. Anonymous requests: always `[]`.
  Malformed tokens are ignored, never an error.
- `POST /forum/boards/{slug}/unlock/` 200 body becomes
  `{"unlocked": true, "unlock_token": <str or null>}`: a token after a correct password,
  null on the "nothing to unlock" path. Update `UNLOCKED_SCHEMA`.

- [ ] **Step 1: Write failing tests** (reuse the file's fixtures for a password forum,
  a member and a second member)

```python
def test_unlock_returns_a_token_that_opens_the_topic_list_without_a_session(...):
    token = client.post(unlock_url, {"password": "pw"}).json()["unlock_token"]
    fresh = APIClient(); fresh.force_authenticate(member)   # no session carried over
    assert fresh.get(topics_url).status_code == 403
    assert fresh.get(topics_url, HTTP_X_FORUM_UNLOCK=token).status_code == 200
def test_token_of_another_member_is_refused(...)        # 403 forum_locked
def test_token_for_another_forum_is_refused(...)        # 403
def test_token_dies_when_the_password_changes(...)      # 403
def test_expired_token_is_refused(...)                  # override the setting to 0, or freeze time
def test_anonymous_request_with_a_token_stays_locked_and_cacheable(...)
    # 403 on the topic list; the categories row still is_locked; Cache-Control public
def test_garbage_and_too_many_tokens_are_ignored(...)   # 403, not 500
def test_member_can_create_a_topic_and_reply_with_a_token(...)   # 201 and 201
def test_categories_row_is_unlocked_with_a_token(...)   # is_locked False, last_post_at set
def test_nothing_to_unlock_returns_null_token(...)
def test_session_unlock_still_works_without_a_token(...)
```

- [ ] **Step 2:** `cd backend && pytest packages/wagtail_forum/wagtail_forum/tests/test_forum_passwords.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3:** Implement. Keep `remember_unlocked` and the session path as they are.
- [ ] **Step 4:** Run the file, then `pytest -q` for the whole backend. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(forum): unlock token for cookie-less clients`.

### Task 7: App unlock store, header and locked rows

**Files:**

- Create: `forum/services/forum_unlock_store.dart`
- Modify: `mob/lib/services/api_service.dart`, `mob/lib/services/auth_service.dart`
  (`signOut`), `forum/services/forum_api.dart`, `forum/widgets/home/forum_categories_section.dart`,
  `forum/forum_screen.dart`, the test fake
- Test: `mob/test/features/forum/services/forum_unlock_store_test.dart`,
  `mob/test/services/api_service_forum_unlock_test.dart`, `forum_categories_section_test.dart`

**Interfaces — Produces:**

- `class ForumUnlocks { final String uid; final Map<int, String> tokens; }` and
  `abstract class ForumUnlockStore { Future<ForumUnlocks?> load();
  Future<void> save(ForumUnlocks unlocks); Future<void> clear(); }` with `SecureForumUnlockStore` (flutter_secure_storage, one key
  `forum_unlock_tokens`, JSON `{"uid": ..., "tokens": {forum id: token}}`) and `forumUnlockStoreProvider`.
- `ApiService.setForumUnlockTokens(Iterable<String> tokens)`. The request interceptor adds
  `X-Forum-Unlock: <tokens joined by ','>` when all hold: tokens are non-empty, an
  `Authorization` header is being sent, `options.uri.path` contains `/forum/`, and it does
  not contain `/forum/sync/`.
- `forumUnlocksProvider`: a keep-alive async notifier over `Map<int, String>`; `build()`
  loads the store and calls `setForumUnlockTokens`; `add(forumId, token)`, `drop(forumId)`,
  `clear()` update store, state and header together.
- `Categories.build()` awaits `forumUnlocksProvider.future` before it fetches when the
  viewer is signed in, so the first request after a cold start carries the header.
- `AuthService.signOut` clears the unlocks (store and header).
- Account switch: `forumUnlocksProvider.build()` watches the signed-in Firebase uid.
  Signed out (uid null, as at launch before the session restores): send no header and
  leave the store untouched. Signed in with the stored uid: use the tokens. Signed in with
  a different uid: clear the store. Do NOT clear from `_resetForViewer`: it also runs on app launch
  (signed-out to signed-in as the session restores) and on an author block, and would wipe
  a valid unlock.
- `ForumApi.unlockBoard(String slug, String password) -> Future<String?>` (the token).
- Dead-token rule: `Categories` notes which forum ids it held tokens for when it sent the
  request. After the response, it calls `drop(id)` only for those ids whose forum came
  back `isLocked == true`. A token added or loaded after the request went out is never
  dropped by that response.
- The phone forgetting a token is what ends an unlock at sign-out; the server would still
  accept that token until it expires or the password changes. Say so in the README.

**Row (§7.4):** `LucideIcons.lock` in the tile, title and description only: no counts, no
last activity, no unread dot, default tone (ignore `colour`).
`onLockedTap`: guest → SnackBar "Sign in to open this forum."; member →
`context.pushNamed('forumUnlock', pathParameters: {'slug': slug}, extra: title)` (Task 8).

- [ ] **Step 1: Write failing tests**

```dart
test('store round-trips, removes and clears', ...            // in-memory secure storage mock
test('header is sent on /forum/ calls with auth', ...
test('header is not sent on /forum/sync/', ...
test('header is not sent without an Authorization header', ...
test('header is not sent to non-forum paths', ...
test('cursor urls (absolute) under /forum/ carry the header', ...
testWidgets('a locked row shows no counts, time or unread dot', ...
testWidgets('guest tap on a locked row shows the sign-in message', ...
test('a forum still locked after load drops its stored token', ...
test('categories fetch waits for the unlock load on a cold start', ...
  // hold the store's load() on a Completer: fetchCategoriesCalls stays 0 until it completes
test('a token added while a fetch is in flight is not dropped by that response', ...
test('signed out at launch leaves the store untouched', ...
test('sign-out clears the tokens and the header', ...
test('tokens survive an app restart for the same member', ...
  // new container, same uid, auth goes signed-out -> signed-in: tokens still loaded
test('tokens stored for another uid are cleared, not sent', ...
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement; run build_runner.
- [ ] **Step 4:** `flutter analyze && flutter test`. Expected: clean.
- [ ] **Step 5:** Commit: `feat(mobile): locked forum rows and unlock token storage`.

### Task 8: Unlock screen, locked topic list, live socket

**Files:**

- Create: `forum/screens/forum_unlock_screen.dart`
- Modify: `mob/lib/core/routing/app_router.dart`, `forum/screens/forum_topics_screen.dart`,
  `forum/live/topic_live.dart`
- Test: `mob/test/features/forum/screens/forum_unlock_screen_test.dart`,
  `forum_topics_screen_test.dart`, `mob/test/features/forum/live/` (the topic live test file)

**Interfaces — Consumes:** `unlockBoard`, `forumUnlocksProvider`, `categoriesProvider`.

**Interfaces — Produces:**

- Route `/forum/boards/:slug/unlock`, name `forumUnlock`, `extra` = the forum title.
  Declare it before `/forum/boards/:slug` siblings as go_router requires.
- `ForumUnlockScreen({required String boardSlug, String? boardTitle})`: title, one
  obscured password field (autofill off), an "Unlock" button disabled while empty or busy.

**Behaviour (§7.4):**

- Success: the forum id comes from `boardsProvider`/`categoriesProvider` by slug;
  `add(id, token)`, invalidate `categoriesProvider` and `boardTopicsProvider(slug)`, then
  `context.pushReplacementNamed('forumBoard', ...)`. If the token is null (nothing to
  unlock), skip `add` and continue the same way.
- `ApiException` 400 → inline field error "Wrong password." 429 → "Too many tries. Try
  again in N minutes." where N = `ceil(retryAfterSeconds / 60)`, minimum 1; add
  `int? retryAfterSeconds` to `ApiException`, filled from the `retry-after` header where
  `api_service.dart` already reads it (line ~258). The unlock POST must go out exactly
  once: do not set `retryUnsafeRequestKey` on it, and confirm in `api_service.dart` that a
  429 on a POST is not re-sent by `_retry` (it would re-post the password). Other errors → the screen's generic
  retry message. The password is never logged or kept after the call.
- `forum_topics_screen.dart`: when the topics error is an `ApiException` with
  `code == 'forum_locked'`, show a locked state (lock icon, "This forum needs a
  password.", an "Unlock" button to `forumUnlock`) in place of `_ErrorRetry`, and hide the
  New topic action.
- `topic_live.dart`: do not open the socket when the topic's `board.id` is in
  `forumUnlocksProvider`; treat it as live-off (no "topic removed" state, no toast).

- [ ] **Step 1: Write failing tests**

```dart
testWidgets('correct password stores the token and opens the forum', ...
testWidgets('wrong password shows "Wrong password." and keeps the field', ...
testWidgets('429 with retry-after 840 shows "Try again in 14 minutes."', ...
testWidgets('Unlock is disabled while the field is empty', ...
test('a 429 on unlock makes exactly one request', ...        // dio adapter call count == 1
testWidgets('topic list 403 forum_locked shows the Unlock state, not Retry', ...
test('no live socket is opened for a topic in an unlocked password forum', ...
  // fake channel factory call count stays 0; state is not `gone`
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `flutter analyze && flutter test`. Expected: clean.
- [ ] **Step 5:** Commit `feat(mobile): unlock screen for password forums`. Local
  end-to-end check on the simulator against a local backend with a password forum: lock
  shows, wrong password, unlock, read a topic (no "removed" state), post a reply, kill and
  reopen the app (still unlocked), sign out (locked again). Open the PR; it needs the
  backend deployed before a TestFlight build is useful.

---

## Slice 4: collapsing (branch `feat/mobile-forum-collapse`)

### Task 9: Collapsible categories

**Files:**

- Modify: `forum/services/forum_api.dart`, `forum/providers/forum_providers.dart`,
  `forum/widgets/home/forum_categories_section.dart`, `forum/forum_screen.dart`, the fake
- Test: `mob/test/features/forum/providers/collapsed_categories_test.dart`,
  `forum_categories_section_test.dart`

**Interfaces — Produces:**

- `ForumApi.fetchCollapsedCategories() -> Future<List<int>>`: `GET /forum/me/profile/`,
  key `collapsed_categories` (missing or malformed → `[]`).
- `ForumApi.saveCollapsedCategories(List<int> ids) -> Future<void>`:
  `PUT /forum/me/collapsed-categories/` body `{"collapsed_categories": ids}`, no
  Idempotency-Key.
- `collapsedCategoriesProvider`: keep-alive notifier, state `Set<int>`.
  - `build()` returns the device copy at once (flutter_secure_storage key
    `forum_collapsed_categories`, following `LiveUpdatesSetting` in
    `forum/live/live_updates_settings.dart`), then, when signed in, fetches the server
    list, replaces the state and rewrites the device copy. A failed fetch keeps the device
    copy silently. The fetch never delays `categoriesProvider`.
  - `Future<bool> toggle(int categoryId)`: flips the id at once and writes the device
    copy; signed in, it saves the whole set; on a save failure it restores the previous
    set and device copy and returns false. Guests never call the server.
  - Rebuilds on viewer change (watch the same auth selector `forum_screen.dart` listens to).
- `_ForumsSection` passes `collapsed` and `onToggleCollapse`; on `false` it shows a
  SnackBar "Couldn't save. Try again."

**Header (§7.5):** the whole header row is the toggle (48pt high, button semantics
"Collapse General" / "Expand General"), with a chevron that rotates; `AnimatedSize` on
the card, no motion under reduced motion. Collapsed: the card is not built, and the header
shows the unread dot when `category.hasUnread`. Ids in the set that match no category are
ignored and left in the saved list.

- [ ] **Step 1: Write failing tests**

```dart
test('signed in: server list replaces the device copy', ...
test('toggle saves the whole set and keeps it on success', ...
test('toggle rolls back and returns false when the save fails', ...
test('guest toggle never calls the API and survives a rebuild', ...
test('profile fetch failure keeps the device copy', ...
test('categories load does not wait for the collapsed fetch', ...
  // hold fetchCollapsedCategories on a Completer; categoriesProvider still resolves
testWidgets('a collapsed category hides its rows and shows its unread dot', ...
testWidgets('all categories collapsed shows only headers, no error', ...
testWidgets('an unknown id in the set changes nothing', ...
```

- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement; run build_runner.
- [ ] **Step 4:** `flutter analyze && flutter test`. Expected: clean.
- [ ] **Step 5:** Commit `feat(mobile): collapsible forum categories`. Simulator check:
  collapse Community on the phone, reload the web forum signed in as the same member, it
  is collapsed there; and the reverse. Open the PR.

---

## After the last slice

- [ ] One TestFlight build for the owner's device check of all four slices (§10), unless
  the owner asks for a build per slice.
- [ ] Update `mob/docs/patterns/flutter-ui-design.md` where it says the forum boards are
  "five identical text rows", and the `/forum/boards/` note in
  `backend/packages/wagtail_forum/README.md` (the app no longer calls it; installed builds
  do).
