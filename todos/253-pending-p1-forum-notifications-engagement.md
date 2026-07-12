---
status: pending
priority: p1
issue_id: "253"
tags: [forum, notifications, product-ux, celery]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "C2, H1, H2, H3, H4, H10"
---

# Forum epic: notifications & engagement loop

## Problem

The forum has no working notification or engagement loop at all: no in-app
notifications, an FCM push pipeline that always no-ops (no client ever registers
a token), fully orphaned email senders, no subscriptions/watching, no @mentions,
and no unread indicators. The ask→answered loop — the core retention mechanic of
any forum — does not exist. This is the C2-anchored p1 epic from the 2026-07-11
forum-modernization audit.

## Findings

Path shorthand: `W` = `backend/packages/wagtail_forum/wagtail_forum`, `H` = `backend/apps/forum_host`.
Full detail lives in the source manifest rows.

- **C2** — No in-app notifications and no working delivery channel: no
  Notification model/endpoints/bell UI; FCM is server-side only — `fcm_token` is
  never populated by web or mobile, so `send_forum_push` always no-ops
  (`H/tasks.py:52-57`, `W/models/profiles.py:34`).
- **H1** — Email notifications fully orphaned: `send_forum_reply/mention/digest`
  and `EmailType.FORUM_*` and the user-visible `forum_notifications` preference
  all exist with zero callers (`apps/core/services/notification_service.py:287,407,472`).
- **H2** — Push event coverage minimal: `reply_added` notifies the topic author
  only (not participants), `topic_created` is log-only, nothing for
  mentions/reactions (`H/notifications.py:26-72`).
- **H3** — No topic/board subscription or watching model.
- **H4** — No @mentions: no write-side parsing, no composer autocomplete, no
  linkification (`W/api/sanitize.py`, web TipTapEditor).
- **H10** — No unread/new-content indicators, no read-state model, no
  polling/live updates (`websocket_urlpatterns = []`).

## Recommended Action

Sequenced so each step ships value alone:

1. **Notification model + API + bell** (C2 core): host-side model (recipient,
   actor, verb, target ids, `read_at`), cursor-paginated list + mark-read
   endpoints, bell with unread count in the web layout.
2. **Wire the orphaned email senders** (H1): connect
   `send_forum_reply/mention/digest` into the signal path so the existing
   `forum_notifications` preference finally gates something.
3. **Subscriptions** (H3): explicit follow/unfollow + auto-subscribe on
   create/reply; fan-out in `H/notifications.py` replaces the author-only rule (H2).
4. **@mentions** (H4): server-side parse on publish, mention notification type,
   TipTap autocomplete + linkification.
5. **Unread indicators** (H10): per-user topic last-read timestamp (or a cheap
   localStorage first pass) driving new/unread badges in lists.
6. **FCM token registration** on at least one real client so push works
   end-to-end (C2 residue; mobile side coordinates with todo 260).

## Technical Details

- Keep reusable primitives (models, signals) in the package `W`; delivery
  concerns (FCM, the email service) stay host-side in `forum_host` — the split
  already exists (`H/notifications.py`, `H/tasks.py`, `W/signals.py` with 3
  public signals).
- Reuse the `send_forum_push` Celery pattern (now with permanent-error handling
  and backoff after audit fix M33).
- Fan-out writes should be bulk (`bulk_create`) and tested with exact query pins
  per `docs/rules/testing.md`.

## Acceptance Criteria

- [ ] A reply to a subscribed topic produces an in-app notification visible via
      bell UI; mark-read works
- [ ] The `forum_notifications` preference actually gates deliveries (email and push)
- [ ] Reply/mention events fan out to subscribers/participants, not only the topic author
- [ ] An @mention notifies the mentioned user and renders as a profile link
- [ ] Topic lists show an unread/new indicator
- [ ] At least one real client (web or mobile) registers an FCM token and
      receives a push end-to-end

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 6 open findings per the manifest's Phase 4 grouping table
  (user-approved: one todo per epic; social/engagement selected as a p1 theme).

## Notes

p1 by user triage decision. C2 (one of only two Critical findings) anchors this
epic. Related: todo 260 (mobile client) owns the Flutter FCM registration half.
