---
status: completed
priority: p2
issue_id: "339"
tags: [forum, dm, web, flutter]
dependencies: ["319"]
---

# Ship DMs UI — backend complete, no web or Flutter surface

## Problem

Private messaging shipped end-to-end at the API layer (todo 319 / audit M10,
PR #580) — canonicalized 1:1 conversations, block-aware sends, spam-checked
messages, reporting, rate limits — but **neither frontend exposes it**. Users
cannot discover, start, or read a conversation. A shipped-but-invisible
feature is carrying testing and migration weight for zero product value.

## Findings

- Backend routes are live (2026-09-04 frontend catalog, read-only):
  `conversation-list` (`GET /conversations/`), `conversation-messages`
  (`GET/POST /conversations/<id>/messages/`), `user-message-send`
  (`POST /users/<username>/messages/`), `message-report`
  (`POST /messages/<id>/report/`) — `apps/forum_host/api_urls.py:75-196`,
  mirroring `wagtail_forum/api/urls.py:43-143`.
- `wagtail_forum/models/messages.py:1-92` — `Conversation` + `Message`,
  plain text, 4000-char cap, persist indefinitely, blocked by `UserBlock`
  (403), reuse `Report.file_for_message`.
- No web screens: no matches for `Conversation`/`messages` routes under
  `web/src/pages/forum/` or `web/src/components/forum/` (catalog absent).
- No Flutter screens: `plant_community_mobile/lib/features/forum/` has no
  conversation list/thread UI.
- **Package-sufficiency check needed before UI work:** the DM API exposes
  list + messages, but it is unverified whether there is an *unread
  conversation count* or per-conversation unread state — required for a
  usable inbox badge. If absent, that is a `wagtail_forum` package gap, not
  a UI gap, and lands in this todo's scope.

## Recommended Action

1. Verify the package surface first: read
   `wagtail_forum/api/direct_messages.py:1-356` for unread-count/read-state
   fields. If missing, add them at **package level** (model field or
   annotation + serializer exposure) — the package must remain UI-complete
   for any host, per the reusable-package constraint.
2. Web: add `/messages` route — conversation list (last-message preview,
   unread bold) + conversation thread (cursor "Load more", plain-text
   composer, report action per message). Entry points: `UserProfilePage`
   ("Message" button next to block/mute controls,
   `web/src/components/forum/UserProfilePage.tsx:168-205`) and a bell-adjacent
   inbox icon in `AppShell`.
3. Handle the 403 blocked-case explicitly ("You can't message this member")
   — `UserBlock` returns 403 on send.
4. Flutter: conversations list + thread screens in the forum feature module,
   launched from `forum_user_profile_screen.dart`.
5. No push notification scope here — DM push is a separate item (see Notes).

## Technical Details

- Backend: `wagtail_forum/api/direct_messages.py`, `wagtail_forum/models/messages.py`
- Rate limits already applied: `DEFAULT_FORUM_RATELIMITS` in
  `apps/forum_host/constants.py:15-91` via `apps/forum_host/api.py`.
- Web conventions: `web/CLAUDE.md` (react-router-dom imports, CSRF header,
  DOMPurify for any rich render — DMs are plain text, so plain rendering).
- Flutter conventions: `plant_community_mobile/docs/patterns/riverpod.md`.

## Acceptance Criteria

- [x] Package exposes (or is confirmed to already expose) unread state for
      conversations; if added, covered by package tests
- [x] Web: a user can start a DM from a profile, see conversation list +
      thread, send/receive messages, report a message; blocked 403 handled
      with a readable message
- [x] Flutter: conversation list + thread screens reachable from forum
      profile, send works
- [x] No new package->host coupling: `wagtail_forum` remains installable
      without host code (package tests green standalone)

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (fresh catalog of
  `wagtail_forum` + `apps/forum_host` + web + Flutter vs. competition).
  Ranked gap #1: "DMs have no UI."

### 2026-09-05 - Started by completing-todos skill (run 2026-09-05-1142) (run 2026-09-05-0408)

- Picked up by automated workflow.

### 2026-09-05 - Package contract first (run 2026-09-05-1142)

Package-sufficiency check (Recommended Action 1) found the DM API had no
unread state, no activity ordering and no preview — an inbox could not be
built on it. Added at PACKAGE level (`wagtail_forum`), migration 0032:

- `Conversation.last_message_at` (bumped on every send, backfilled from the
  newest message) — the inbox orders by it; `participant_a/b_read_at` read
  markers. **Only reading marks read** (`GET conversations/<id>/messages/`
  advances the caller's marker); sending only bumps activity, so a reply
  fired from a profile never silently "reads" the other side's messages.
- `GET conversations/` rows carry `unread_count` (other side's messages newer
  than my marker; own messages never count) and `last_message`
  `{body ≤140, is_mine, created_at}` — one annotated query per page
  (`_inbox_queryset`), the flat-query pin still holds at 4.
- `GET conversations/unread-count/` → `{count}` of conversations with unread
  messages (badge), host-throttled `dm_unread_count` 120/m like the bell.
- `GET conversations/with/<username>/` → the thread or 404 (none yet /
  unknown / blocked pair / self) — lets a profile's "Message" open the
  existing thread without listing the inbox.
- **Contract change, deliberate:** `conversations/<id>/messages/` is now
  **newest first** — a chat thread opens on its latest page and pages
  older; there was no consumer to break (that is this todo's premise).

Evidence:

```text
$ pytest test_direct_messages_api.py test_ratelimits.py test_api_mounted.py test_docs.py → 49 + host suites green (61 passed on the first run incl. mounted/docs)
$ manage.py makemigrations --check --dry-run wagtail_forum → No changes detected
$ manage.py spectacular → rc=0; schema lists conversations/unread-count/ and conversations/with/{username}/
```

Full backend suite with the package contract (alone, `--create-db`):

```text
2147 passed, 8 skipped, 5 warnings in 257.20s (0:04:17)
```

### 2026-09-05 - Review round 1 (backend): cross-cutting reviewer

- **[high] badge poll reused the heavy inbox query** (avatar joins, preview
  subqueries, GROUP BY) — repaired: `_unread_conversation_count` is one
  COUNT over an EXISTS per row (`Coalesce(my_read_at, epoch)` folds the
  never-read case), pinned at 4 queries with `avatar` absent from the SQL.
- **[high] the `created_at > my_read_at` arm was untested** — repaired:
  `test_a_message_after_a_read_is_unread_again` (read → 0, new message →
  1, on both the list and the badge).
- **[high] flat query pin had no avatars**, so the select_related's last
  leg was never traversed — repaired: every other side gets an avatar and a
  message; pin still 4 with the annotations riding the page query.
- **[high] migration backfill untested** — repaired:
  `test_migration_0032_backfills_last_message_at_from_the_newest_message`
  (newest message; `created_at` fallback for a messageless conversation),
  importing the migration module as `test_subscriptions.py` does for 0014.
- **[medium] no pin on the badge endpoint** — covered by the pin above;
  **[low] dead `Coalesce` import in the migration** — removed.

```text
$ pytest test_direct_messages_api.py → 35 passed
```

### 2026-09-05 - Web half (implemented by a general-purpose agent against the contract, reviewed below)

- `services/messageService.ts` (own module — forumService is 825 lines;
  throws `ForumApiError` so callers branch on status), `pages/forum/MessagesPage.tsx`
  (`/messages`), `pages/forum/ConversationPage.tsx` (`/messages/:username`),
  `components/layout/MessagesLink.tsx` (envelope + badge beside the bell),
  `components/forum/reportReasons.ts` (`REPORT_REASONS` extracted from
  PostCard, imported by both), routes under `ProtectedLayout`, "Message"
  button on `UserProfilePage` (shown when `isAuthenticated && can_block &&
  !is_blocked` — `can_block` is the backend's "authenticated and not
  yourself"), `UnreadNotificationsContext` polls both counts in one tick
  (`Promise.allSettled`: a DM failure never blanks the bell).
- 404 on `with/<username>/` renders the empty thread with a live composer;
  the first send re-resolves. 403 → persistent `aria-live` notice, draft
  kept; 400 → server message.

```text
$ vitest run (full web) → Test Files 94 passed (94) / Tests 1155 passed (1155)
$ npm run type-check → rc=0; eslint on the 20 touched files → clean; prettier applied
mutation probe: removing the newest→oldest reverse failed 2 ConversationPage tests; restored from a copy; MUTANT residue 0
```

### 2026-09-05 - Review round 1 (backend): django-drf reviewer

Verified against a disposable Postgres scratch DB (migrated to 0031, seeded
pre-migration rows, re-applied 0032; never the dev/test DBs): the
`Count(filter=…)` over the `my_read_at` CASE compiles correctly with no
join multiplication from the two preview subqueries; the list holds at 4
queries end-to-end; the lean badge query is one `COUNT(*) … WHERE EXISTS`;
the backfill overrides the AddField default for every row and is
reversible. Findings: **[low] `mark_read` stamps `now()` after the page's
SELECT** — accepted and documented (topic-read precedent); if tightened
later use `Greatest(F(marker), newest_shown.created_at)` so an older
cursor page cannot move the marker backwards. **[info]** `with/<self>` 404
vs send-to-self 400 is a deliberate GET-vs-POST divergence, no leak.

### 2026-09-05 - Flutter half (implemented by a general-purpose agent against the contract, reviewed below)

- Models `ForumConversation`/`ForumLastMessage`/`ForumDirectMessage`;
  `ForumApi` + 6 methods (`fetchConversationWith` maps 404 → null;
  `Idempotency-Key` on send/report — the backend consumes it and
  `docs/rules/flutter.md` requires one per action, reused for a same-body
  retry and rotated on a new body); providers `ConversationsFeed`,
  `unreadConversationCount`, `ConversationThread(username)` with
  `loadOlder()` (prepends a reversed page) and `send()` (appends the echo,
  resolves the conversation on first send, invalidates badge + inbox);
  screens `forum_conversations_screen.dart` and
  `forum_conversation_screen.dart` (`reverse: true` list, long-press report
  sheet with the real `Report.REASON_CHOICES` — `spam/abuse/off_topic/other`);
  routes `/forum/messages` and `/forum/messages/:username` (auth-guarded via
  `protectedPrefixes`); "Message" `IconButton` on the profile (hidden for
  anonymous/self/deleted/loading); inbox button + badge on the forum home.
- Current-username source is `userProfileServiceProvider` (`AuthState` has
  no username) — one autoDispose fetch when opening a profile signed in.

```text
$ flutter analyze → No issues found!
$ flutter test → 00:48 +474 ~3: All tests passed!
$ dart run build_runner build --delete-conflicting-outputs → generated files unchanged (md5 stable)
```

### 2026-09-05 - Review round 1 (web): react-typescript reviewer — all repaired

- **[high] stuck `sending`/`loadingOlder` after navigating mid-request** —
  the epoch bump skipped their guarded `finally`, pinning the next
  thread's composer disabled. Repaired: the `:username` reset block clears
  both (test: navigate away mid-send → next thread's composer enabled).
- **[high] no id-dedupe on page merges** — repaired: `mergeMessages` dedupes
  by id for "Load older" prepends and the send echo (test: an overlapping
  older page renders one row).
- **[medium] report callbacks unguarded** — repaired: the form captures the
  page epoch via an accessor at submit and re-checks after the await
  (`react-hooks/refs` forbids reading a ref during render, so it is an
  accessor, not a prop value).
- **[medium] ownership by negation of the other member** — repaired:
  `sender.username === user.username`, falling back to the two-party rule
  only when the auth user carries no username (todo 350 will break the
  shortcut).
- **[medium] no identity-swap race test** — repaired: two manually-settled
  promises, the previous member's late response never renders.
- **[medium] inbox `loadingMore` stuck across an identity swap** —
  repaired: reset in `load()`.
- **[low] live-region test after-the-fact** → present-and-empty asserted
  before the failure; **[low] focus dropped after send** → refocus via an
  effect after React re-enables the textarea (focusing a disabled control is
  a no-op — the first attempt failed exactly so); **[low] 36px tap target** →
  `min-h-11 min-w-11`. **[info]** shared-epoch tradeoff documented.

```text
$ vitest run (touched files) → 36 passed; full web suite → Test Files 94 passed / Tests 1159 passed
$ npm run type-check → rc=0; eslint clean (after the refs fix); prettier applied
```

### 2026-09-05 - Review round 1 (Flutter): flutter-dart reviewer — all repaired

- **[medium] `ref.invalidate(conversationsFeedProvider)` from the thread
  collapsed a paged inbox to page 1** (the anti-pattern `TopicPosts` avoids).
  Repaired: `ConversationsFeed.markRead(id)` / `applyActivity(row)` splice
  the loaded pages in place, called only `if (ref.exists(...))`; the badge
  provider is still invalidated (cheap). Tests: pages preserved, row moved
  to the top with the "You: …" preview, new row inserted, no refetch.
- **[info] ownership inference fails toward "mine" on a malformed sender**
  — repaired: a `[deleted]` sentinel sender is never mine, so Report stays
  available. **[low] hide-on-error of the Message action** — made explicit
  in the code comment (deliberate: without knowing who "you" are, the
  action could offer to message yourself).
- Verified clean by the reviewer: idempotency-key rotation, reversal and
  prepend math, the route guard's prefix match, controller disposal, no
  force-unwraps, fixtures never mount `CachedNetworkImage`, generated files
  consistent.

```text
$ flutter analyze → No issues found!
$ flutter test (DM providers + 3 screens) → +34 all passed
```

### 2026-09-05 - Acceptance criteria evidence

- AC1 (package unread state): `Conversation.participant_a/b_read_at` +
  `unread_count`/`last_message`/`last_message_at` on every row,
  `conversations/unread-count/`, `conversations/with/<username>/` — 12 new
  package tests in `test_direct_messages_api.py` (35 total in the file).
- AC2 (web): `MessagesPage`, `ConversationPage`, profile "Message" button,
  inbox badge; send/receive/report/403/400 covered — `vitest run` full web:
  **Test Files 94 passed / Tests 1159 passed**.
- AC3 (Flutter): inbox + thread screens, profile action, inbox button —
  `flutter test`: **+476 All tests passed!**; `flutter analyze`: no issues.
- AC4 (no package→host coupling): `grep "from apps\." packages/wagtail_forum/wagtail_forum`
  (non-test) → **0**; throttle lives in `apps/forum_host` only; the package
  suite runs inside the full backend run (see below).

Post-repair full backend suite (alone, `--create-db`):

```text
2150 passed, 8 skipped, 5 warnings in 278.73s (0:04:38)
```

### 2026-09-05 - Completed by completing-todos skill (run 2026-09-05-0408)

- Verification: all 4 acceptance criteria evidenced (backend 2150 passed / web 1159 passed / flutter 476 passed; package imports nothing from the host).
- Review: cross-cutting + django-drf (backend), react-typescript (web), flutter-dart (mobile) — 1 round each; every finding repaired.
