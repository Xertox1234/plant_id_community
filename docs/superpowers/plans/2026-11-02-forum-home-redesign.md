# Forum Home Redesign (mobile) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Flutter Forum tab home as the approved design: branded app bar, Your season card, grouped boards with per-board accent identity, expandable Recent activity cards, a members-only Who's online panel and a footer, in dark and light mode.

**Architecture:** Two PRs. PR 1 (backend, `wagtail_forum` package) extends `GET forum/topics/recent/` and adds two read endpoints: latest replies for a topic, and community stats. PR 2 (Flutter) adds models, API methods and providers for those, three small shared Canopy widgets, and rebuilds `forum_screen.dart` from focused section widgets. PR 2 depends on PR 1 being deployed for the on-device check only. Its tests use `FakeForumApi`.

**Tech Stack:** Django 6 + DRF + Wagtail (pytest, PostgreSQL 16, Redis); Flutter + Riverpod 3 (`@riverpod` codegen) + go_router + Material 3; Canopy tokens via `context.canopy`.

**Spec:** `docs/superpowers/specs/2026-11-02-forum-home-redesign-design.md`. Mockup (dark + light): `docs/superpowers/specs/2026-11-02-forum-home-redesign-mockup.html`. Read both before Task 1.

## Global Constraints

- Colours only from `Theme.of(context).colorScheme` or `context.canopy`. No hex, no `Colors.*`, no `withOpacity` (use `.withValues(alpha:)`). Accents only on small elements (tiles, chips, dots, the streak number).
- Accent tones map to the extension's semantic fields, so light mode gets the darkened set automatically: sage → `leaf`, pollen → `clay`, bloom → `berry`, orchid → `sky`.
- Type from theme roles / `AppTypography`: display face for section headings and card titles, Geist Mono for counts and times. No ad hoc `fontSize`.
- `BrandMark` keeps its deep-pine tile in both modes; never a red cross on a light ground.
- Max 3 items in an expanded card (solution counts toward the 3). Max 10 activity cards. Max 5 avatars in the online sample. One card open at a time.
- Footer: `BrandMark`, "Houseplant MD", eyebrow "THE PLANT CLINIC", "© {current year} Houseplant MD". No links.
- Who's online: members only, no guests. Totals site-wide over fully public boards only.
- Blocked and muted members are hidden (`_exclude_blocked_authors`, which already applies both) from latest replies, participants, online sample and newest member.
- Peek reads never mark a topic read and never write on a `public`-cached response path (`docs/rules/caching.md`).
- Every scrollable on the home keeps `MainShell.fabClearanceOf(context)` padding.
- Motion: all durations through `MediaQuery.disableAnimationsOf(context)`; values from `Durations`/`Easing` (spec §8.3).
- Riverpod 3 `@riverpod` only; regenerate with `dart run build_runner build --delete-conflicting-outputs` and commit `*.g.dart`.
- Backend tests: `cd backend && PYTHONPATH=packages/wagtail_forum pytest <path> -q` for a file; before PR 1 is opened, run the full suite (`pytest -q`). An app-scoped run is a false green.
- Mobile tests: `cd plant_community_mobile && flutter test <path>`; `flutter analyze` clean.

## Review Focus

1. **A topic whose only replies are from members the viewer blocked**: the expanded card shows "No replies yet" with `more_count == 0`, not an empty box or a negative count. Test in Task 2.
2. **Very long titles and display names at 320pt and 2.0× text scale** (activity card, expanded reply row, online names line): wrap or ellipsis, never overflow. Test in Task 11.
3. **Tapping a second card while the first is mid-expand, or tapping the same card twice quickly**: exactly one card ends open and no request is fired twice for the same topic. Test in Task 9.
4. **Signed-out viewer**: no Your season section, recent feed and Who's online still render, and `is_unread` is false everywhere. Tests in Task 1 (backend) and Task 11 (screen).
5. **Recent feed or stats request fails while the other succeeds**: only the failed section shows its error or hides; the rest of the home renders. Test in Task 11.

---

## PR 1 — Backend

### Task 1: Extend the recent-topics feed

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (`RECENT_TOPICS_SCHEMA` ~2476, `RecentTopicsView.get` ~2531)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_recent_topics.py`

**Interfaces:**

- Produces: each `results[]` row gains `is_solved: bool`, `is_unread: bool`, `image_url: str | null`. Existing keys unchanged (`id, slug, title, board{id,name,slug}, reply_count, last_post_at, is_pinned, thumbnail_url`).

- [ ] **Step 1: Write the failing tests** in `test_recent_topics.py`:
  - `test_recent_topics_is_solved_reflects_solved_post`: one topic with `solved_post` set, one without → `[True, False]` by id.
  - `test_recent_topics_is_unread_false_for_anonymous`: anonymous GET → every row `is_unread is False`.
  - `test_recent_topics_is_unread_for_member`: member who read topic A before its last post and never opened topic B → A `True`; after the member reads A (use the same read-marking path `test_topics_list.py` uses for `is_unread`) → `False`.
  - `test_recent_topics_image_url_wide_rendition`: topic whose opening post has an image block → `image_url` ends with a rendition filename containing `fill-720x400`, and `thumbnail_url` still contains `fill-80x80`; topic without image → `image_url is None`.
  - `test_recent_topics_query_count_unchanged_by_new_fields`: 5 topics, 3 with images, authenticated member → assert the exact query count with `CaptureQueriesContext` (measure once, pin the number; it must not grow with topic count — repeat with 10 topics and assert equal).
- [ ] **Step 2: Run** `cd backend && PYTHONPATH=packages/wagtail_forum pytest packages/wagtail_forum/wagtail_forum/tests/api/test_recent_topics.py -q` → the five new tests FAIL with `KeyError`.
- [ ] **Step 3: Implement.** Apply `_annotate_topic_unread(recent, request.user)` before the slice (it already returns `False` for anonymous). `is_solved = t.solved_post_id is not None`. Prefetch both `fill-80x80` and `fill-720x400` in the existing `prefetch_renditions(...)` call; add `wide(topic)` beside `thumb(topic)` with the same failure handling. Add the three keys to `RECENT_TOPICS_SCHEMA` (`image_url` nullable string) and update the docstring line on what the view returns.
- [ ] **Step 4: Run** the file again → all PASS. Also run `tests/api/test_read_cache_headers.py` and `tests/api/test_schema.py` → PASS (authenticated response stays `private, no-store`).
- [ ] **Step 5: Commit** `feat(forum): recent topics carry is_solved, is_unread and a wide image`.

### Task 2: Latest-replies peek endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (new `TopicLatestRepliesView` + `TOPIC_LATEST_REPLIES_SCHEMA`, placed after `RecentTopicsView`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py` (route next to `topics/recent/`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/conf.py` (`"LATEST_REPLIES_LIMIT": 3`, `"LATEST_REPLIES_EXCERPT_CHARS": 160`, `"LATEST_REPLIES_PARTICIPANTS": 5`)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_topic_latest_replies.py`

**Interfaces:**

- Produces: `GET forum/topics/<int:topic_id>/latest-replies/` (url name `topic-latest-replies`) →
  `{"replies": [Reply], "solution": Reply | null, "more_count": int, "participant_count": int, "participants": [Author], "started_by": Author | null}` where `Reply = {"id": int, "author": serialize_forum_author(...), "created_at": iso8601, "excerpt": str}` and `Author = serialize_forum_author(...)`.
- `replies` is newest first and excludes the opening post and the solution. `len(replies) + (1 if solution else 0) <= 3`. `more_count = visible_reply_count - len(replies) - (1 if solution else 0)`, never negative.

- [ ] **Step 1: Write the failing tests:**
  - `test_latest_replies_returns_three_newest_newest_first`: 5 replies → ids of the 3 newest, descending; `more_count == 2`.
  - `test_latest_replies_solution_counts_toward_three`: 5 replies, the 2nd oldest is the solution → `solution.id` is it; `len(replies) == 2` (two newest non-solution); `more_count == 2`.
  - `test_latest_replies_hides_blocked_and_muted_authors`: 4 replies, one by a member the viewer blocked, one by a member the viewer muted → neither in `replies` or `participants`; `more_count` counts only visible replies.
  - `test_latest_replies_hidden_solution_author_omits_solution`: solution by a blocked member → `solution is None`, newest visible replies fill up to 3.
  - `test_latest_replies_only_blocked_replies`: every reply by blocked members → `replies == []`, `more_count == 0`.
  - `test_latest_replies_no_replies`: opening post only → `replies == []`, `solution is None`, `participant_count == 1`, `started_by.username` is the starter.
  - `test_latest_replies_excerpt_plain_and_capped`: reply body with HTML and >400 chars → excerpt has no `<`, length ≤ 160 (+ ellipsis as `plain_text_excerpt` produces).
  - `test_latest_replies_404_when_topic_not_visible`: topic in a hidden forum (`hide_forum`) → 404; non-live topic → 404.
  - `test_latest_replies_does_not_mark_read`: member GETs it → the topic still reports `is_unread True` on `topics/recent/`.
  - `test_latest_replies_query_count`: pin the exact count, equal for a topic with 3 and 30 replies.
  - `test_latest_replies_cache_headers`: anonymous → the same `public` headers other `PublicForumReadCacheMixin` reads send; member → `private, no-store`.
- [ ] **Step 2: Run** `... pytest .../tests/api/test_topic_latest_replies.py -q` → FAIL (404 for the unknown route).
- [ ] **Step 3: Implement `TopicLatestRepliesView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView)`** with `permission_classes = [AllowAny]`. Resolve the topic with the same visibility check `TopicDetailView` uses (`board__in=_visible_boards(request=request)`, `live=True`), else 404. Base posts query: live, non-opening posts of the topic, passed through `_exclude_blocked_authors(qs, request.user)`, `select_related("author")` plus whatever `serialize_forum_author` needs (copy `PostListView`'s `select_related`/`prefetch`). Solution: the topic's `solved_post` only if it is in that filtered set. Newest = `order_by("-created_at", "-id")` excluding the solution id, sliced to `LIMIT - (1 if solution else 0)`. `visible_reply_count` = `.count()` of the filtered set. Participants: distinct authors of the topic's live posts after the same filter, most recent post first, first `LATEST_REPLIES_PARTICIPANTS`; `participant_count` = distinct count. Excerpt: `plain_text_excerpt(post.body, get_setting("LATEST_REPLIES_EXCERPT_CHARS"))`. `started_by`: the opening post's author unless blocked or muted, then `None`. Add `@extend_schema` with `TOPIC_LATEST_REPLIES_SCHEMA`. Route it in `api/urls.py` beside `topics/recent/` with an `<int:topic_id>` converter (literal-path ordering comment applies).
- [ ] **Step 4: Run** the new file + `tests/api/test_schema.py` → PASS.
- [ ] **Step 5: Commit** `feat(forum): latest-replies peek for the home activity cards`.

### Task 3: Community stats endpoint

**Files:**

- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/views.py` (new `CommunityStatsView` + `COMMUNITY_STATS_SCHEMA`, after `ExpertsView`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/api/urls.py` (`community/stats/`)
- Modify: `backend/packages/wagtail_forum/wagtail_forum/conf.py` (`"COMMUNITY_STATS_CACHE_SECONDS": 60`, `"COMMUNITY_ONLINE_SAMPLE": 5`)
- Test: `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_community_stats.py`

**Interfaces:**

- Produces: `GET forum/community/stats/` (url name `community-stats`) → `{"members_online": int, "online_sample": [Author], "registered_members": int, "topic_count": int, "post_count": int, "newest_member": Author | null}`.
- Definitions (document in the schema description): online = active user whose `ForumProfile.last_seen` is within `effective_online_window_seconds()`; registered = active users with a `ForumProfile`; topic/post counts = live topics / live posts in boards with no permission grant and no password (the fully public set; reuse the predicate `_visible_boards` applies for an anonymous viewer with no unlocked forums, not a request-dependent call).

- [ ] **Step 1: Write the failing tests:**
  - `test_community_stats_counts`: 3 active profiles seen 1 min ago, 1 seen 1 h ago, 1 inactive user seen 1 min ago → `members_online == 3`, `registered_members == 4`.
  - `test_community_stats_counts_only_public_boards`: topics/posts in a public forum, a password forum and a permission-restricted forum → counts include only the public forum's, for anonymous AND for a member who has unlocked the password forum.
  - `test_community_stats_online_sample_limit_and_order`: 7 online → 5 in the sample, most recently seen first.
  - `test_community_stats_hides_blocked_and_muted`: viewer blocked one online member and muted another → neither in `online_sample`; `members_online` unchanged (site-wide count).
  - `test_community_stats_newest_member_skips_blocked`: newest member blocked by the viewer → the next newest.
  - `test_community_stats_counts_cached_shared`: two requests inside 60 s with a new topic created between them → same `topic_count` (use `override_settings` + clear the cache in setup); after `cache.clear()` → updated.
  - `test_community_stats_per_viewer_filter_not_cached_shared`: viewer A blocks X, then anonymous request → X present for anonymous.
  - `test_community_stats_query_count`: pin the exact count for a member viewer with a warm counts cache.
- [ ] **Step 2: Run** the new file → FAIL (404).
- [ ] **Step 3: Implement `CommunityStatsView(UnversionedForumAPIMixin, PublicForumReadCacheMixin, APIView)`**, `AllowAny`. Counts dict cached under key `wagtail_forum:community_stats:v1` for `COMMUNITY_STATS_CACHE_SECONDS` via `cache.get_or_set`. Sample and newest member built per request: `ForumProfile` rows of active users, through `_exclude_blocked_authors(qs, request.user, author_field="user_id")`, ordered `-last_seen` / `-user__date_joined`, serialized with `serialize_forum_author`. Apply the throttle class other public forum reads use (copy from `ExpertsView`/`RecentTopicsView` if present; if none, add none). Route it, `@extend_schema` it.
- [ ] **Step 4: Run** the new file, `tests/api/test_schema.py`, `tests/api/test_read_cache_headers.py` → PASS. Then the full backend suite: `cd backend && pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat(forum): community stats endpoint for Who's online`, then open PR 1.

---

## PR 2 — Flutter

### Task 4: Models and API methods

**Files:**

- Create: `plant_community_mobile/lib/features/forum/models/forum_home.dart` (export it from `models/models.dart`)
- Modify: `plant_community_mobile/lib/features/forum/services/forum_api.dart` (abstract `ForumApi` + `HttpForumApi`)
- Modify: `plant_community_mobile/test/features/forum/support/forum_test_support.dart` (`FakeForumApi`)
- Test: `plant_community_mobile/test/features/forum/models/forum_home_test.dart`

**Interfaces:**

- Produces (all `@immutable`, `fromJson` tolerant of missing keys like the existing models):
  - `ForumRecentTopic { int id; String slug; String title; ForumTopicBoardRef board; int replyCount; DateTime? lastPostAt; bool isPinned; bool isSolved; bool isUnread; String? thumbnailUrl; String? imageUrl; bool get hasPicture => imageUrl != null; }`. `board` parses the feed's `{id, name, slug}` (`name` → the ref's title).
  - `ForumLatestReply { int id; ForumAuthor author; DateTime? createdAt; String excerpt; }`
  - `ForumLatestReplies { List<ForumLatestReply> replies; ForumLatestReply? solution; int moreCount; int participantCount; List<ForumAuthor> participants; ForumAuthor? startedBy; bool get isEmpty => replies.isEmpty && solution == null; }`
  - `ForumCommunityStats { int membersOnline; List<ForumAuthor> onlineSample; int registeredMembers; int topicCount; int postCount; ForumAuthor? newestMember; }`
  - `ForumApi.fetchRecentTopics({int limit = 10}) → Future<List<ForumRecentTopic>>` (`GET /forum/topics/recent/?limit=`), `fetchLatestReplies(int topicId) → Future<ForumLatestReplies>` (`GET /forum/topics/$topicId/latest-replies/`), `fetchCommunityStats() → Future<ForumCommunityStats>` (`GET /forum/community/stats/`).
  - `FakeForumApi` gains settable `recentTopics`, `latestRepliesByTopic`, `communityStats`, an `Object? latestRepliesError` / `communityStatsError` / `recentTopicsError` to throw, and `int latestRepliesCalls(int topicId)`.

- [ ] **Step 1: Write the failing tests:** `fromJson` round-trips a full payload for each model; missing `image_url`/`is_unread`/`is_solved` default to `null`/`false`/`false` (an older server); `solution: null` → `null`; `ForumLatestReplies.isEmpty` true only when both are empty.
- [ ] **Step 2: Run** `flutter test test/features/forum/models/forum_home_test.dart` → FAIL (undefined).
- [ ] **Step 3: Implement** the models and the three `HttpForumApi` methods (shape like `fetchExperts`), and the `FakeForumApi` members.
- [ ] **Step 4: Run** the test + `flutter analyze` → PASS.
- [ ] **Step 5: Commit** `feat(mobile): forum home models and API calls`.

### Task 5: Home providers

**Files:**

- Modify: `plant_community_mobile/lib/features/forum/providers/forum_providers.dart` (+ regenerated `.g.dart`)
- Test: `plant_community_mobile/test/features/forum/providers/forum_home_providers_test.dart`

**Interfaces:**

- Consumes: Task 4's API methods.
- Produces:
  - `@riverpod Future<List<ForumRecentTopic>> homeRecentTopics(Ref ref)` → `fetchRecentTopics(limit: 10)`. The existing `RecentTopics` notifier (offline mirror) stays untouched.
  - `@riverpod Future<ForumLatestReplies> latestReplies(Ref ref, int topicId)` with `ref.keepAlive()` (kept while the screen lives; invalidated on pull-to-refresh).
  - `@riverpod Future<ForumCommunityStats> communityStats(Ref ref)`.
  - `@riverpod class ExpandedActivityTopic extends _$ExpandedActivityTopic { int? build() => null; void toggle(int topicId); void collapse(); }`. `toggle` sets the id, or `null` when the id is already open.

- [ ] **Step 1: Write the failing tests:** `toggle(1)` → 1; `toggle(2)` → 2 (one open at a time); `toggle(2)` → null; `latestReplies(5)` read twice → `FakeForumApi.latestRepliesCalls(5) == 1`; `homeRecentTopics` passes `limit: 10`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement**, then `dart run build_runner build --delete-conflicting-outputs`.
- [ ] **Step 4: Run** the test + `flutter analyze` → PASS.
- [ ] **Step 5: Commit** `feat(mobile): forum home providers` (include `forum_providers.g.dart`).

### Task 6: Board identity

**Files:**

- Create: `plant_community_mobile/lib/features/forum/utils/board_identity.dart`
- Test: `plant_community_mobile/test/features/forum/utils/board_identity_test.dart`

**Interfaces:**

- Produces: `enum CanopyTone { sage, pollen, bloom, orchid }` with `Color colorOf(GreenThumbExtension c)` → `leaf` / `clay` / `berry` / `sky`; `class BoardIdentity { CanopyTone tone; IconData icon; String chipLabel; }`; `BoardIdentity boardIdentity(String slug, {String fallbackLabel = ''})`; `int webHashString(String value)` (31-multiplier over UTF-16 code units, masked to 32-bit unsigned, identical to `web/src/utils/hashString.ts`).
- Map (spec §6.1): `plant-identification` sage `LucideIcons.leaf` "Identification"; `care-problems` pollen `LucideIcons.droplet` "Care"; `pests-diseases` bloom `LucideIcons.bug` "Pests"; `garden-design` orchid `LucideIcons.layoutDashboard` "Design"; `show-tell` sage `LucideIcons.camera` "Show & tell". Fallback: `CanopyTone.values[webHashString(slug) % 4]`, leaf icon, `fallbackLabel` or the slug.

- [ ] **Step 1: Write the failing tests:** each of the five slugs → its exact tone/icon/label; `webHashString('general') == 4214819048`, `('off-topic') == 343965521`, `('houseplants') == 2051170952`; fallback tones `general` → sage, `off-topic` → pollen; fallback label uses `fallbackLabel`; `CanopyTone.pollen.colorOf(GreenThumbExtension light) == light.clay` (and dark).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(mobile): board identity shared with the web`.

### Task 7: Shared Canopy pieces

**Files:**

- Create: `plant_community_mobile/lib/shared/widgets/canopy_accents.dart`
- Test: `plant_community_mobile/test/shared/widgets/canopy_accents_test.dart`; goldens added to `test/core/theme/canopy_visual_golden_test.dart` (dark + light).

**Interfaces:**

- Produces:
  - `CanopyAccentTile({required IconData icon, required Color tone, double size = 40})`: rounded 12, fill `tone` at 15% alpha over the card, 1px border at 30%, icon in `tone`.
  - `CanopyChip({required String label, required Color tone, IconData? icon})`: pill, label 10.5-size role from `AppTypography` (use the nearest label role), text in `tone`, fill 15%.
  - `CanopyGroupedCard({required List<Widget> rows})`: one `CanopyCard`, rows separated by 1px `line` dividers, no outer padding (rows own theirs).
  - `CanopyPressable({required Widget child, required VoidCallback? onTap, CanopyPressStyle style = CanopyPressStyle.highlight, String? semanticLabel, bool? expanded})`: `highlight` paints `surface3` under a row while pressed; `scale` goes to 0.98 with `SpringDescription(mass: 1, stiffness: 420, damping: 30)` and no overshoot; under `disableAnimations` both become an opacity dim to 0.7. Exposes `Semantics(button: true, expanded: expanded)`.

- [ ] **Step 1: Write the failing tests:** chip and tile pick their colours from the passed tone; grouped card with 3 rows renders exactly 2 dividers; `CanopyPressable` scale style reports scale < 1 while a gesture is held and 1 after release; with `MediaQuery(disableAnimations: true)` no `Transform` scale is applied; semantics `expanded` flag passes through; goldens at 375 wide, dark and light.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** the tests + `flutter test --update-goldens test/core/theme/canopy_visual_golden_test.dart`, then re-run without the flag → PASS.
- [ ] **Step 5: Commit** `feat(mobile): Canopy accent tile, chip, grouped card, pressable`.

### Task 8: Header, Your season, Experts, Boards sections

**Files:**

- Create: `plant_community_mobile/lib/features/forum/widgets/home/forum_season_card.dart`, `.../home/forum_boards_section.dart`
- Modify: `plant_community_mobile/lib/features/forum/widgets/forum_experts_strip.dart` (avatar size 48, online dot border on ground)
- Test: `plant_community_mobile/test/features/forum/widgets/home/forum_season_card_test.dart`, `.../home/forum_boards_section_test.dart`

**Interfaces:**

- Consumes: `ForumMyStats` (`meStatsProvider` data, same fields `ForumStatsGrid` reads), `ForumBoard`, Task 6, Task 7.
- Produces: `ForumSeasonCard({required ForumMyStats stats})`: `CanopyCard`, leaf watermark at 6% (`ExcludeSemantics`), eyebrow "YOUR SEASON", four equal-flex stats (IDs, Posts, Solutions, Day streak; streak value in `clay`), labelled progress row using the same next-badge fields `ForumStatsGrid` uses, badge chips (`ForumBadgeChips`) below when present. `ForumBoardsSection({required List<ForumBoard> boards, required void Function(ForumBoard) onTap})`: `CanopyGroupedCard` of rows: `CanopyAccentTile` + title + one-line description (`maxLines: 1`) + "N topics · N posts" (mono, singular "1 topic"/"1 post") + chevron, each row a `CanopyPressable(style: highlight)`, ≥48pt tall.

- [ ] **Step 1: Write the failing tests:** season card shows the four values from a fixture and "0 / 20 IDs"-style progress text from the fixture's next-badge fields; boards section renders one tile per board with the identity icon, "1 topic · 1 post" singulars, tapping a row calls `onTap` with that board; both at 320×640 with text scale 2.0 → no overflow (`tester.takeException() == null`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(mobile): forum home season card and grouped boards`.

### Task 9: Recent activity cards (picture + expandable text)

**Files:**

- Create: `plant_community_mobile/lib/features/forum/widgets/home/forum_activity_card.dart`, `.../home/forum_latest_replies_view.dart`
- Test: `plant_community_mobile/test/features/forum/widgets/home/forum_activity_card_test.dart`

**Interfaces:**

- Consumes: `ForumRecentTopic`, `latestRepliesProvider(topicId)`, `expandedActivityTopicProvider`, Tasks 6–7, `ClayButton`, `forumRelativeTime(DateTime?, {DateTime? now})` from `forum_format.dart`.
- Produces: `ForumActivityCard({required ForumRecentTopic topic, required VoidCallback onOpen})` (a `ConsumerWidget`). Picture variant (`topic.hasPicture`): chip, title (display role), `CachedNetworkImage`/the app's existing network image widget at 16:9-ish fixed aspect, sized with `memCacheWidth`, reply count + time + chevron; whole card → `onOpen`. Text variant: chip, unread dot (`clay`) or "Solved" (`leaf`, `LucideIcons.circleCheck`), title, reply count, time, "New replies" when unread, rotating chevron; tap → `toggle(topic.id)`; expanded body = `ForumLatestRepliesView`. `ForumLatestRepliesView({required int topicId, required VoidCallback onOpen})`: loading → two skeleton lines; data → solution first (with "Solution" `CanopyChip`), then replies (avatar, name, relative time, excerpt `maxLines: 2`), "+N more replies" when `moreCount > 0`, participants cluster (`AuthorAvatarCluster` (`forum_avatar_cluster.dart`, `max:` 5)) + "N people in this thread · started by name" (omit "· started by" when `startedBy == null`), `ClayButton(label: 'Open topic', fullWidth: true, onPressed: onOpen)`; empty → "No replies yet" + button; error → "Couldn't load replies" + Retry (`ref.invalidate`) + button.
- Motion (spec §8.3): `AnimatedSize` `Easing.emphasizedDecelerate` ~250 ms open / `emphasizedAccelerate` ~200 ms close; content `FadeTransition` delayed 80 ms; chevron `AnimatedRotation` 0.5 turns; `AnimatedSwitcher` `Durations.short4` from skeleton to content; `HapticFeedback.selectionClick()` on toggle; all zero under `disableAnimationsOf`, keeping the fade.

- [ ] **Step 1: Write the failing tests:**
  - picture card: tap → `onOpen` called, never fetches latest replies.
  - text card: tap → expanded, `FakeForumApi.latestRepliesCalls(id) == 1`, shows 3 items max from a fixture with solution + 4 replies (solution + 2 newest), "+2 more replies".
  - two cards: open A then tap B → A collapsed, B expanded; tap B twice within 50 ms → ends collapsed and the fetch count for B is 1.
  - empty fixture → "No replies yet"; error → "Couldn't load replies", Retry refetches (calls == 2).
  - `startedBy: null` → no "started by" text.
  - semantics: text card reports `expanded: false` then `true`.
  - reduced motion (`MediaQuery(disableAnimations: true)`): expand completes in one `pump()`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(mobile): expandable recent activity cards`.

### Task 10: Who's online panel and footer

**Files:**

- Create: `plant_community_mobile/lib/features/forum/widgets/home/forum_whos_online.dart`, `.../home/forum_home_footer.dart`
- Test: `plant_community_mobile/test/features/forum/widgets/home/forum_whos_online_test.dart`, `.../home/forum_home_footer_test.dart`

**Interfaces:**

- Consumes: `communityStatsProvider`, `AuthorAvatarCluster` (`forum_avatar_cluster.dart`, `max:` 5), `BrandMark`.
- Produces: `ForumWhosOnline()` (`ConsumerWidget`): hides entirely (`SizedBox.shrink`) while loading or on error, like `_ExpertsSection`; data → heading "Who's online", `CanopyCard` with members online (live dot in `leaf`), "registered" total, avatar cluster of `onlineSample` + names line ("Sam, Will and simtest"; first names via `displayName` split, max 3 then "and N others"), footer row "N topics · N posts" and "Newest: name" (omitted when `newestMember == null`). `membersOnline == 0` → "No members online right now" in place of the cluster. `ForumHomeFooter({DateTime? now})`: `BrandMark(size: 30)`, "Houseplant MD", eyebrow "THE PLANT CLINIC", "© ${(now ?? DateTime.now()).year} Houseplant MD".

- [ ] **Step 1: Write the failing tests:** loading and error → no "Who's online" text; data → counts, three names line, newest member; `membersOnline 0` copy; names line with 5 → "Sam, Will, Iris and 2 others"; footer with `now: DateTime(2027)` → "© 2027 Houseplant MD"; footer in light theme still finds `BrandMark`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(mobile): who's online panel and forum footer`.

### Task 11: Assemble the forum home

**Files:**

- Modify: `plant_community_mobile/lib/features/forum/forum_screen.dart`
- Test: `plant_community_mobile/test/features/forum/forum_screen_test.dart` (update existing expectations that assert on the old `_RecentTile`/spinners; do not delete coverage), `plant_community_mobile/test/features/forum/forum_home_layout_test.dart` (new)

**Interfaces:**

- Consumes: Tasks 5, 8, 9, 10.
- Produces: `ForumScreen` order: app bar (`BrandMark(size: 28)` + "Community" left-aligned, `centerTitle: false`, existing actions unchanged) → `ForumSeasonCard` (signed in) → Experts → Boards (`boardsProvider`) → Recent activity heading + "View all" (only if `forumSearch` supports sorting by latest activity; otherwise omit) + up to 10 `ForumActivityCard`s (`homeRecentTopicsProvider`) → `ForumWhosOnline` → `ForumHomeFooter`. Section gap 30pt (`AppSpacing` nearest token). Loading for boards and activity: skeleton rows shaped like each section instead of `_SectionLoader`. Errors: existing `_SectionError` per section. Pull-to-refresh also invalidates `homeRecentTopicsProvider`, `communityStatsProvider`, every `latestRepliesProvider` (`ref.invalidate(latestRepliesProvider)`) and collapses the open card. First-visit staggered fade (40 ms, 8pt rise) only on first build, not on refresh, fade-only under reduced motion. Padding keeps `MainShell.fabClearanceOf(context)`.

- [ ] **Step 1: Write the failing tests** in `forum_home_layout_test.dart`, looping over {320×640, 375×812} × {1.0, 2.0} × {dark, light}: pump the full screen with fixtures (long titles and display names included) → no exceptions; scroll to the end → the footer's bottom edge is above the camera FAB's top edge; `meetsGuideline` for `androidTapTargetGuideline`, `iOSTapTargetGuideline`, `labeledTapTargetGuideline`, `textContrastGuideline`. Plus: signed out → no "YOUR SEASON", activity and Who's online present; recent feed error + stats OK → activity error line shown, Who's online shown; stats error → Who's online absent, rest present; pull-to-refresh collapses an open card.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**, removing `_BoardTile`, `_RecentTile` and `_SectionLoader` from this screen once unused. **Step 4: Run** `flutter test test/features/forum` + `flutter analyze` → PASS.
- [ ] **Step 5: Commit** `feat(mobile): redesigned forum home`.

### Task 12: On-device check and PR 2

- [ ] **Step 1:** With PR 1 deployed, build for the simulator (`flutter build ios --simulator --debug --dart-define-from-file=<main checkout>/plant_community_mobile/.env.production`) and launch on the iPhone 17 Pro simulator.
- [ ] **Step 2:** Screenshots in dark AND light (switch with the simulator's appearance setting): the whole home top to bottom, an expanded text card, a picture card, Who's online, the footer clear of the FAB. Compare with the mockup; fix differences in the owning task's files.
- [ ] **Step 3:** Record the live board slugs shown in Boards. If any board falls back to the hash colour, list it in the PR description for the owner (spec §6.1). Do not change the map in this PR.
- [ ] **Step 4:** `flutter test` (whole app) + `flutter analyze` → PASS. Commit any fixes, open PR 2 with the before/after screenshots.

---

## Self-review notes

- Spec coverage: §5 layout → Tasks 8–11; §5.1 light → Global Constraints tone mapping, Task 7 goldens, Task 11 loop, Task 12 screenshots; §6.1 → Task 6; §6.2 → Task 1 + 4/5; §6.3 → Task 3 + 10; §6.4 → Task 2 + 9; §7 → Task 9; §8 motion/states → Tasks 7, 9, 11; §10 verification → Tasks 3 (full backend suite), 11, 12.
- "View all" is conditional by design (spec §11 calls it a builder check).
