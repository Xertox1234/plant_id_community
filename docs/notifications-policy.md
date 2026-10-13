# Notification policy

Who gets which email and push, and which switch decides. Written for todo 620
(2026-10-12) and extended by todo 624 (important-event email, quiet hours,
coalescing, read-before-send). The owner decisions it rests on are recorded
in those todos' `owner_decision`; they are quoted under
[Decisions](#decisions) below.

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
| 5 | Quiet hours (opt-in window; holds, never drops) | `ForumProfile.quiet_hours_*`, `time_zone` | web Settings "Notifications"; mobile Profile "Quiet hours" |
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
| Mention | email (off by default) | `email_notifications` AND `forum_notifications` AND matrix `mention.email` | `send_forum_email_batch` (todo 624) |
| Quote of your post | push | `forum_notifications` AND matrix `quote.push` | same push tasks |
| Quote of your post | email (off by default) | `email_notifications` AND `forum_notifications` AND matrix `quote.email` | `send_forum_email_batch` (todo 624) |
| Your answer accepted | push | `forum_notifications` AND matrix `solution.push` | `send_forum_push` |
| Your answer accepted | email (off by default) | `email_notifications` AND `forum_notifications` AND matrix `solution.email` | `send_forum_email_batch` (todo 624) |
| Moderation decision | push (tray-silent client sync) | `forum_notifications` | `send_forum_push`; not a matrix cell, it has no in-app row |
| Weekly forum digest | email | `email_notifications` AND `forum_notifications` AND `digest_frequency = weekly` | `send_forum_digest` with `WAGTAILFORUM_DIGEST_RECIPIENT_FILTER` (`apps/users/notification_policy.py`) |
| Blog newsletter | email | a confirmed, active `BlogNewsletter` row for the address | `send_blog_newsletter`; independent of every switch above |
| Plant care reminder | push | `care_reminder_notifications` | `apps/garden_calendar/tasks.py` (todo 410) |

Every forum row except the digest, the moderation sync and care reminders
is also subject to quiet hours, coalescing (replies only) and read-before-send
below. None of them touches security mail or the in-app inbox.

### Important-event email (todo 624)

- Mention, quote and accepted-answer email are optional and **off by
  default**: no member is subscribed to new mail they did not ask for. Each
  is its own matrix cell, on web and mobile.
- **One merged email.** A mentioned (or quoted) member is never in the reply
  email batch for that post. They get the mention (or quote) email when that
  cell is on; otherwise, if they follow the topic and want reply email, the
  reply email; otherwise none. Never two.
- **Unsubscribe follows the gate.** Each email's signed link turns off the
  cell that let it through: `forum_mention`, `forum_quote`,
  `forum_solution`, or `forum_reply` for the merged reply email.
- Email does not depend on push: a member with no registered device still
  gets the email they turned on.

### Quiet hours (todo 624)

- Opt-in (`quiet_hours_enabled`, off by default). Default window 22:00-07:00.
- The window is wall-clock time in the IANA zone the client reports
  (`time_zone`). Web reports the browser's zone on every quiet-hours save.
  Mobile reports one only when the platform gives an IANA name; otherwise it
  sends none and the stored zone (or UTC) stays. Both clients show the zone in
  effect. Blank or unknown means UTC. The window follows daylight saving.
- A push or email that would arrive inside the window is **held** in the
  delivery outbox (`apps/core/delivery.py`, `mark_held`) and released when the
  window ends, by reconciliation (every 5 minutes). On release the task
  rechecks everything, so a preference changed overnight is honoured. Turning
  quiet hours off, or moving the window, reschedules what is held.
- Exempt: security mail (verification, password reset, security alerts,
  lockout), which never goes through the forum tasks, and the in-app inbox.
  The tray-silent moderation sync is not held.

### Coalescing (todo 624)

Owner decision: same-topic replies within 10 minutes reach a member as one
email and one push. Implementation reading (2026-10-12): the first reply goes
out at once. A reply arriving while the member's last message about that
topic on that channel is younger than 10 minutes is held until 10 minutes
after that message, then goes out as **one** message folding every reply
still waiting ("3 new replies in ...", showing the newest). A steady stream
is at most one message per 10 minutes per member, topic and channel; a quiet
topic gets no added latency. Mentions, quotes and accepted answers are never
folded.

### Read-before-send (todo 624)

Nothing goes out externally for a post the member already read in the app:
its bell row is read, or their read marker for the topic (or their
account-wide watermark) is at or past it. Checked on every attempt,
including when a held delivery is released.

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
| `forum_mention` | matrix `mention.email` | the Settings grid (web or mobile) |
| `forum_quote` | matrix `quote.email` | the Settings grid (web or mobile) |
| `forum_solution` | matrix `solution.email` | the Settings grid (web or mobile) |

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
- 2026-10-12, owner (todo 624): approve optional mention/quote/accepted-answer
  email, off by default (no silent opt-in); a mentioned subscriber gets one
  merged email.
- 2026-10-12, owner (todo 624): quiet hours are opt-in, default window
  22:00-07:00 in the client-reported IANA timezone (UTC if unknown); held
  pushes/emails release at window end; security mail exempt.
- 2026-10-12, owner (todo 624): coalesce same-topic replies within a 10-minute
  window into one email/push, and skip the external send if the user already
  read the post in-app. Implementation reading: leading message plus one
  folded message per window (see [Coalescing](#coalescing-todo-624)).
- Implementation reading (todo 620): `forum_notifications` off also stops
  forum email, the digest included. That was already true of reply email
  (`EmailService` maps `FORUM_REPLY` and `FORUM_DIGEST` to it); the digest
  now matches.
