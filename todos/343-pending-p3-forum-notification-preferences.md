---
status: pending
priority: p3
issue_id: "343"
tags: [forum, notifications, backend, package, web]
dependencies: []
---

# Per-channel notification preferences (in-app / push / email per verb)

## Problem

Forum notifications fire on four verbs (REPLY, MENTION, SOLUTION,
MODERATION) across in-app, FCM push, and (partially) email — but the only
user control is a single `forum_notifications` flag. There is no preference
UI; `SettingsPage.tsx:1-13` even lists "Email notifications preferences" as
planned. Users can't opt out of push for replies while keeping mention
pushes, which is how notification fatigue starts.

## Findings

- `apps/forum_host/tasks.py:1-465` — push fires for `reply_added`/`mention`
  (tray) and `moderation_decided`/`answer_accepted` (data-only); the only
  gate besides `ForumProfile.fcm_token` is the global flag (2026-09-04
  backend catalog §6.2).
- `AppShell.tsx:284` + `NotificationBell.tsx` — in-app bell is mature; no
  settings route exists for channels.
- `web/src/pages/.../SettingsPage.tsx:1-13` — placeholder text already
  promises this feature.

## Recommended Action

1. **Package (`wagtail_forum`):** add a per-user preference model — either
   a JSONField on `ForumProfile` or (cleaner for auditability) a
   `ForumNotificationPreference` row keyed by `(profile, verb, channel)`.
   Defaults via `get_setting("NOTIFICATION_DEFAULTS", ...)` in `conf.py`;
   hosts can change defaults without a migration. Modest matrix: verbs
   {reply, mention, solution, moderation} x channels {in_app?, push, email}
   — decide whether in-app is toggleable at all (Discourse: in-app always
   on; recommend same).
2. Package gates its own fan-out (`wagtail_forum/notifications.py`) and
   exposes prefs read/write on `me/profile/` (fits existing
   `MeProfileView`, `api/views.py:1572-1761`).
3. **Host:** `apps/forum_host/notifications.py` push/email enqueue steps
   check the preference before `transaction.on_commit` enqueue.
4. **Web:** settings section replacing the placeholder; save via
   `PATCH /me/profile/`.
5. Relationship to todo 340 (digest): digest frequency is intentionally a
   separate profile field — don't conflate "which events notify me" with
   "which cadence batches them".

## Technical Details

- Existing gates: `wagtail_forum/api/notifications.py:1-142` (visibility
  filtering), `ForumProfile.fcm_token`, `is_firebase_available()`.
- Package/host split: package owns model + serializer + in-app gating; host
  owns push/email wiring only.
- Email send path being gated: `NotificationService.send_forum_reply_notification`
  via `apps/forum_host/tasks.py:279-362`.

## Acceptance Criteria

- [ ] Preference model + API in `wagtail_forum` with package tests
      (defaults applied when no row exists; unknown verb/channel rejected)
- [ ] Push/email fan-out respects preferences (host tests)
- [ ] Web settings UI replaces the "planned" placeholder; changes persist
- [ ] No change to default behavior for existing users beyond current state

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses
  item: notification preference UI listed as planned in `SettingsPage`).
