---
status: pending
priority: p3
issue_id: "287"
tags: [forum, notifications, backend, i18n]
dependencies: []
source_review: "todo 272 item 5 (spun out 2026-07-29)"
---

# Forum notification copy lives in three independent homes

## Problem

The same forum event is phrased three separate times — once for email, once for
the FCM tray, once for the web bell. They already disagree with each other, so
any copy change (or a future i18n pass) has to find all three by hand, and
missing one ships inconsistent wording rather than an error.

## Findings

Verified by grep on 2026-07-29 during todo 272's closure. For a single
`reply_added` event:

| Surface | Home | Current wording |
| --- | --- | --- |
| Email | `backend/apps/core/services/notification_service.py:326` (`send_forum_reply_notification`, defined `:287`) | subject `New reply in: {topic_title}`, body `{author} replied to a topic you're following` |
| Push tray | `backend/apps/forum_host/tasks.py` (`_notification_content`) | title `New reply in "{topic_title}"`, body `{actor} replied` |
| Web bell | `web/src/components/layout/NotificationBell.tsx` (`notificationLabel`) | `{actor} replied to "{topic}"` |

- **Scope is smaller than it looks — three of the four `send_forum_*` methods
  are dead code.** `send_forum_reply_notification` is the ONLY live email path
  (called from `apps/forum_host/tasks.py:363`). Its siblings
  `send_forum_mention_notification` (`💬 {user} mentioned you in: {title}`),
  `send_new_topic_notification` (`🌱 New topic in {category}: {title}`) and
  `send_forum_digest_email` (`🌿 Your {period} … digest`) have **zero call
  sites repo-wide** — verified 2026-07-29 by grepping for callers, not
  definitions, and confirmed there is no `getattr`-style dynamic dispatch.
  Mention delivery runs entirely through the package's own notification path.
  So the emoji-bearing copy, and the "mention" email arm, are not shipped
  behavior at all; a consolidation must decide whether to port that dead copy
  into the table or delete it, and should not treat it as an existing contract.
  (This is the exact trap in `docs/LEARNINGS.md` 2026-07-29 / todo 270 —
  `PLANNING/20_FORUM_MOBILE_ROADMAP.md:421` still credits
  `send_forum_mention_notification` as the shipped mention mechanism.)
- The three homes also differ in **coverage**, not just wording: the push tray
  deliberately renders only `reply_added` and `mention` (everything else returns
  `None` to stay tray-silent — see its docstring), while email has a topic and a
  digest path with no tray equivalent. A copy table must not flatten that away.
- All three now carry a mutual cross-reference comment pointing at each other
  and at this todo (added during 272's closure) — that is the stopgap, not the
  fix.
- Discovery source: todo 253 slice 6 review (2026-07-16), deferred as item 5 of
  todo 272.

## Recommended Action

1. Consolidate the **two backend homes first** — that is the natural first step
   and the only part that is a pure refactor. Add a copy table (a module of
   event → `{subject, body, push_title, push_body}` templates), most plausibly
   in `apps/forum_host/` next to the existing constants, and have both
   `_notification_content` and the `send_forum_*` methods read from it.
2. Preserve the tray-silence whitelist explicitly: an event absent from the push
   columns must stay `None`, not fall back to generic wording. The existing
   `_notification_content` tests pin this — keep them green rather than
   rewriting them to match the new shape.
3. Note the seam this crosses: `apps/core/services/notification_service.py` is
   **not** forum-specific (it also serves plant care reminders, identification
   results, newsletters), so the copy table should live on the forum side and be
   consumed by the core service's forum methods — not the other way round.
4. Leave the web bell as a third home unless/until an i18n pass gives it a
   shared source; the frontend cannot import a Python table. If web copy must
   converge, the realistic route is serving the label from the API rather than
   duplicating a table in TypeScript.

## Technical Details

- `backend/apps/core/services/notification_service.py` —
  `send_forum_reply_notification` (**the only live one**; the
  `send_forum_mention_notification` / `send_new_topic_notification` /
  `send_forum_digest_email` siblings are uncalled). Note the live method also
  drives template context keys that must match `emails/forum_reply.{html,txt}`
  — Django renders an undefined var as `''`, so a rename here can silently
  blank an email (already commented in the code).
- `backend/apps/forum_host/tasks.py` — `_notification_content`, plus its
  callers at the two send sites; `PUSH_TITLE_TOPIC_MAX_CHARS` truncation lives
  in `apps/forum_host/constants.py`.
- `backend/apps/forum_host/tests/test_tasks.py` — the existing
  `_notification_content` tests (`test_notification_content_reply_uses_topic_title_and_actor`,
  `test_notification_content_mention`, and the tray-silence cases).
- `web/src/components/layout/NotificationBell.tsx` — `notificationLabel`.
- Backend convention: no magic strings/numbers outside `constants.py`
  (`backend/CLAUDE.md`).

## Acceptance Criteria

- [ ] One backend copy table is the single source for forum notification
      wording; neither `_notification_content` nor the live
      `send_forum_reply_notification` contains an inline subject/title/body
      string
- [ ] An explicit decision recorded for the three uncalled `send_forum_*`
      siblings — port their copy into the table, or delete them — rather than
      silently carrying dead copy forward
- [ ] The push tray's event whitelist still holds — an event with no push copy
      produces `None` (no generic fallback), pinned by the existing tests
- [ ] `pytest apps/forum_host apps/core packages/wagtail_forum` passes
- [ ] The cross-reference comments in all three homes are updated to describe
      the new arrangement (or removed where they no longer apply)

## Work Log

### 2026-07-29 - Spun out of todo 272 (item 5)

- Promoted rather than re-deferred: todo 272's Recommended Action conditioned
  items 4/5/6 on "if the area is touched again (todo 260's mobile forum client
  is the likely trigger)". That trigger **has fired** — todo 260 shipped and
  merged (PR #498) — so re-deferring was not available, and per `CLAUDE.md` →
  Review Doc Tracking, promote-all is the only terminal state for a parking todo.
- Re-verified the three homes and their actual current strings by grep before
  promoting, rather than trusting todo 272's description. Two facts 272 did not
  record: the emoji-only-in-email divergence, and that the homes differ in event
  *coverage* as well as wording.
- Stopgap shipped in the meantime: a mutual cross-reference comment in each of
  the three homes, so a copy edit in one surfaces the other two.

## Notes

p3: cosmetic inconsistency with no correctness impact and no user complaint.
Worth doing before any i18n pass, which would otherwise triple the translation
surface. Related: todo 272 (origin), todo 267 (EmailService systemic work —
likely wants to land first or together, since it touches the same
`apps/core/services/notification_service.py`), todo 268 (fan-out batching).
