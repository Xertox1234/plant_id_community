---
status: pending
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

- [ ] Package exposes (or is confirmed to already expose) unread state for
      conversations; if added, covered by package tests
- [ ] Web: a user can start a DM from a profile, see conversation list +
      thread, send/receive messages, report a message; blocked 403 handled
      with a readable message
- [ ] Flutter: conversation list + thread screens reachable from forum
      profile, send works
- [ ] No new package->host coupling: `wagtail_forum` remains installable
      without host code (package tests green standalone)

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (fresh catalog of
  `wagtail_forum` + `apps/forum_host` + web + Flutter vs. competition).
  Ranked gap #1: "DMs have no UI."
