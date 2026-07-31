---
status: completed
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
  (called from `apps/forum_host/tasks.py:364`). Its siblings
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
- The homes also differ in **coverage**, not just wording: the push tray
  deliberately renders only `reply_added` and `mention` (everything else returns
  `None` to stay tray-silent — see its docstring). A copy table must not flatten
  that away — an event with no push copy has to stay `None`, not fall through to
  generic wording, or the tray starts popping "your post was published" at users
  on every routine autopublish. Note the *live* overlap between the two backend
  homes is therefore exactly one event: `reply_added`.
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
   `_notification_content` and the live `send_forum_reply_notification` read
   from it.
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

- [x] One backend copy table is the single source for forum notification
      wording; neither `_notification_content` nor the live
      `send_forum_reply_notification` contains an inline subject/title/body
      string
- [x] An explicit decision recorded for the three uncalled `send_forum_*`
      siblings — port their copy into the table, or delete them — rather than
      silently carrying dead copy forward
- [x] The push tray's event whitelist still holds — an event with no push copy
      produces `None` (no generic fallback), pinned by the existing tests
- [x] `pytest apps/forum_host apps/core packages/wagtail_forum` passes
- [x] The cross-reference comments in all three homes are updated to describe
      the new arrangement (or removed where they no longer apply)

## Work Log

### 2026-07-31 - Implemented (run 2026-07-31-0411)

New module `apps/forum_host/notification_copy.py`: a `ForumEventCopy` dataclass
plus `FORUM_NOTIFICATION_COPY`, keyed by the wire event name (Celery
JSON-serialises `NotificationVerb.MENTION` to `"mention"`), with two render
helpers, `push_content()` and `email_content()`. Both backend surfaces now read
it; **no user-facing string changed** — the existing wording assertions in
`test_tasks.py` were left untouched precisely so they'd catch it if one had.

**Direction of the dependency.** `notification_service` is not forum-specific
(plant-care reminders, identification results, newsletters), so the forum owns
its copy and the core service reads it — via a *function-level* import, which
also rules out a cycle with `forum_host.tasks`.

**Decision on the three uncalled siblings (AC 2): DELETED**, not ported. Re-verified
zero call sites repo-wide first (definition + docstring mentions only; no tests, no
dynamic dispatch). Porting their emoji-bearing copy would have enshrined wording no
user has ever seen and implied a contract that does not exist — the exact trap in
`docs/LEARNINGS.md` 2026-07-29 / todo 270, where a roadmap doc credited
`send_forum_mention_notification` as the shipped mention mechanism. That roadmap
correction note now records the deletion, since its line reference no longer resolves.

**Whitelist preserved and re-pinned.** `push_content` returns `None` for an event
absent from the table *and* for an event present with no push copy — never a
generic fallback. A new test adds an email-only `moderation_decided` entry and
asserts the tray stays silent, which is the case that actually matters:
`workflow.py` fires that event on every routine autopublish.

**Tests** (`apps/forum_host/tests/test_notification_copy.py`, 7):
- The consolidation claim asserted by *moving the source of truth* —
  `monkeypatch.setitem` the table entry, then assert BOTH the email subject and
  the tray title change. A string-equality test would pass equally well against
  two hard-coded copies that happen to agree.
- A source scan for the old inline literals in both homes (AC 1 verbatim). The
  failure it guards is someone re-adding a literal *alongside* the lookup, which
  no behavioural test notices until the two drift.

Mutation-checked: re-adding an inline `reply_added` branch to
`_notification_content` turns 2 of the 7 red.

**Web bell left as the second home, deliberately** — the frontend cannot import
a Python table, so converging it means serving the label from the API. Its
comment now says that instead of describing a three-way split.

Verification:

```
$ pytest apps/forum_host apps/core packages/wagtail_forum --create-db -q
728 passed, 2 warnings in 40.59s

$ npx vitest run NotificationBell
Test Files  1 passed (1)      Tests  12 passed (12)

$ flake8 apps/core/services/notification_service.py apps/forum_host/notification_copy.py apps/forum_host/tasks.py
(clean)
```

### 2026-07-31 - Review and repair

`django-drf-reviewer`. Two mediums (one chain), three lows, two infos.

**Repaired (the medium chain — the one that mattered).** The reviewer traced a
consequence I had dismissed. `subject, message = email_content(...)` unpacks a
value whose signature says it can be `None` — unreachable today, so I'd left it
as "don't write speculative branches". But `send_forum_email_batch`'s docstring
justifies its `autoretry_for=(OperationalError,)` config with an explicit
invariant: *the send loop can never raise*, because email has no collapse-key
dedup and a retry after a partial send would double-email everyone. A
`TypeError` from that unpack is not in `autoretry_for`, so it would abort the
batch mid-loop and silently skip every remaining recipient. My change had
falsified a load-bearing safety argument in a file I never opened. The guard now
logs and returns `False`, and
`test_a_missing_email_arm_returns_false_instead_of_raising` pins it.

**Repaired (low): a placeholder-typo test.** Moving from f-strings to
`str.format` templates introduced a failure class f-strings cannot have — a
typo'd or unbalanced placeholder raises at *send* time. Every field in the table
is now rendered by a test.

**Repaired (low): two weak assertions of my own.**
`test_the_table_is_the_only_place_that_names_a_surface` checked
`push_title or email_subject`, but the renderers require `push_title` AND
`push_body`; a half-filled entry passed a test named for "renders somewhere"
while rendering nowhere. It now asserts exactly what the renderers check. And a
`push_title` with no `push_title_without_topic` would have pushed a BLANK tray
title (the `or ""` fallback) rather than failing — the pair is now required.

**Repaired (info): deleted the orphaned `templates/emails/new_forum_topic.html`.**
Its only reference was `template_name="new_forum_topic"` inside the deleted
`send_new_topic_notification`, so my deletion orphaned it; leaving it would be
residue from this change. Updated the one comment in
`test_email_service_silent_failures.py` that cited it.

**Not changed (info), recorded so a later cleanup does not over-delete:**
`forum_mention.html` / `forum_digest.html` and the `EmailType.FORUM_MENTION` /
`FORUM_DIGEST` members are NOT orphaned despite their first-party callers being
gone — they stay wired in `_get_email_template_for_type`, drive
`forum_notifications` preference gating in `email_service.py`, and are reachable
via a direct `send_notification(notification_type=...)` call and
`management/commands/test_email.py`.

**Acknowledged, not changed (low):** the source-scan test strips docstring/
comment lines by prefix heuristic rather than `ast`. It is exact for both
modules today; if it ever false-positives on prose, switch it to `ast`.

Mutation-checked, 4/4 caught: a typo'd placeholder, a dropped
`push_title_without_topic`, a half-filled entry, and reverting the `None` guard
to a bare unpack.

Re-verified: `pytest apps/forum_host apps/core packages/wagtail_forum --create-db -q`
→ `731 passed, 2 warnings in 40.98s`.

### 2026-07-29 - Spun out of todo 272 (item 5)

- Promoted rather than re-deferred: todo 272's Recommended Action conditioned
  items 4/5/6 on "if the area is touched again (todo 260's mobile forum client
  is the likely trigger)". That trigger **has fired** — todo 260 shipped and
  merged (PR #498) — so re-deferring was not available, and per `CLAUDE.md` →
  Review Doc Tracking, promote-all is the only terminal state for a parking todo.
- Re-verified the three homes and their actual current strings by grep before
  promoting, rather than trusting todo 272's description. Two facts 272 did not
  record, both of which change this todo's shape: that three of the four
  `send_forum_*` methods are **dead code** (so the email side is one method, not
  four, and the emoji-bearing copy is unshipped), and that the homes differ in
  event *coverage* as well as wording.
- Stopgap shipped in the meantime: a mutual cross-reference comment in each of
  the three homes, so a copy edit in one surfaces the other two.

## Notes

p3: cosmetic inconsistency with no correctness impact and no user complaint.
Worth doing before any i18n pass, which would otherwise triple the translation
surface. Related: todo 272 (origin), todo 267 (EmailService systemic work —
likely wants to land first or together, since it touches the same
`apps/core/services/notification_service.py`), todo 268 (fan-out batching).
