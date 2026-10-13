# Notification policy

Who gets which email and push, and which switch decides. Written for todo 620
(2026-10-12). The owner decisions it rests on are recorded in that todo's
`owner_decision`; they are quoted under [Decisions](#decisions) below.

## The switches, in precedence order

A message is sent only if every switch above it allows it. A lower switch can
never turn back on what a higher one turned off.

| # | Switch | Where it is stored | Where a member changes it |
|---|--------|--------------------|---------------------------|
| 0 | Security mail | none: always sent | nowhere (exempt) |
| 1 | `email_notifications`: the email master switch | `User` | web Settings "Account-wide switches"; mobile Profile "Email notifications" |
| 2 | `forum_notifications`: the forum master switch | `User` | web Settings "Account-wide switches"; mobile Profile "Forum notifications" |
| 3 | Per-event matrix: push / email per forum event | `ForumProfile.notification_preferences` (sparse overrides) | web Settings "Notifications" grid; mobile Profile "Forum notifications by event" |
| 4 | Digest cadence (`off` / `weekly`) | `ForumProfile.digest_frequency` | web Settings "Email digest"; mobile Profile "Weekly forum digest" |
| - | Blog newsletter | `BlogNewsletter` (by address, double opt-in) | the newsletter sign-up and its own unsubscribe link |
| - | Care reminders | `User.care_reminder_notifications` | mobile care settings |

In-app notifications (the forum inbox) are always on and are not a preference.
OS notification permission and device registration sit below all of this: a
push the policy allows still needs a registered device that the OS lets us
reach (diagnostics: todo 621).

## Effective opt-in for every live event

"On" means the member gets it. Every row also needs an active account; email
needs an address on file.

| Event | Channel | Sent when | Code |
|-------|---------|-----------|------|
| Email verification, password reset, security alert, account lockout | email | always (security mail) | `EmailService._should_send_email` system set; `apps/core/security.py` |
| Reply on a followed topic | email | `email_notifications` AND `forum_notifications` AND matrix `reply.email` | `send_forum_email_batch` then `EmailService` |
| Reply on a followed topic | push (mobile FCM and web push) | `forum_notifications` AND matrix `reply.push` | `send_forum_push_batch`, `send_forum_web_push_batch` |
| Mention | push | `forum_notifications` AND matrix `mention.push` | same push tasks |
| Quote of your post | push | `forum_notifications` AND matrix `quote.push` | same push tasks |
| Your answer accepted | push | `forum_notifications` AND matrix `solution.push` | `send_forum_push` |
| Moderation decision | push (tray-silent client sync) | `forum_notifications` | `send_forum_push`; not a matrix cell, it has no in-app row |
| Weekly forum digest | email | `email_notifications` AND `forum_notifications` AND `digest_frequency = weekly` | `send_forum_digest` with `WAGTAILFORUM_DIGEST_RECIPIENT_FILTER` (`apps/users/notification_policy.py`) |
| Blog newsletter | email | a confirmed, active `BlogNewsletter` row for the address | `send_blog_newsletter`; independent of every switch above |
| Plant care reminder | push | `care_reminder_notifications` | `apps/garden_calendar/tasks.py` (todo 410) |

There is no email for mentions, quotes or accepted answers today. Whether to
add one, and quiet hours or coalescing, are todo 624.

### What each master switch means

- **`email_notifications` off**: no optional email at all, the weekly forum
  digest included. Security mail still sends. The blog newsletter is not
  affected; it is its own consent with its own unsubscribe link. Push is not
  affected.
- **`forum_notifications` off**: no forum push (mobile or browser) and no
  forum email, the digest included. In-app notifications stay.
- Either switch off leaves the member's per-event matrix and digest cadence
  exactly as stored. Turning the switch back on restores them; nothing is
  reset and nobody is silently subscribed.

### Signed unsubscribe links

A link in an email turns off one list and nothing else (todo 408):

| List | Turns off | Turned back on by |
|------|-----------|-------------------|
| `forum_reply` | matrix `reply.email` | the Settings grid (web or mobile) |
| `forum_digest` | `digest_frequency` (to `off`) | the digest selector (web or mobile) |

A link never touches a master switch. With `email_notifications` off no list's
email is sent, whatever the list itself says.

### Legacy flags and migration

`email_notifications` and `forum_notifications` are kept as the master
switches. There is no data migration: every stored value keeps its meaning,
so an earlier opt-out stays an opt-out. The one behaviour change is that the
digest now honours both master switches; it used to ignore them.

`plant_id_notifications` is inert. Nothing in production sends an
identification-result or disease-alert email or push:
`NotificationService.send_identification_result_notification` has no caller
outside tests and the `test_email` command. The switch is kept and labelled
"Plant identification updates (coming soon)" on mobile so it promises nothing.
Web does not show it.

## Decisions

- 2026-10-12, owner: policy matrix and web/mobile parity ship in todo 620;
  important-event email and quiet hours/coalescing are re-pointed to todo 624.
- 2026-10-12, owner: keep `User.email_notifications` / `forum_notifications`
  as master switches shown on web and mobile; off means no optional email
  (digest included) / no forum push; security mail exempt; the per-event
  matrix applies beneath; no data migration.
- 2026-10-12, owner: relabel the inert Plant ID switch, do not remove it or
  build a trigger. The label must not use "Plant ID" branding (the app is
  Houseplant MD); it describes plant identification updates, coming soon.
- Implementation reading (todo 620): `forum_notifications` off also stops
  forum email, the digest included. That was already true of reply email
  (`EmailService` maps `FORUM_REPLY` and `FORUM_DIGEST` to it); the digest
  now matches.
