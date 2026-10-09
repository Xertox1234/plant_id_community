---
status: pending
priority: p4
issue_id: "533"
tags: [backend, core, email, dead-code]
dependencies: ["409"]
---

# Remove the legacy newsletter email path

## Problem

Todo 409 built the real newsletter sender (`apps/blog/newsletter_digest.py`,
`manage.py send_blog_newsletter`). An older, never-wired path is still in the tree:

- `NotificationService.send_newsletter` in
  `backend/apps/core/services/notification_service.py`. Nothing calls it
  (grep, 2026-10-09). It mails any list it is given, with no consent check
  and no List-Unsubscribe header.
- `backend/templates/emails/newsletter.html`, its template. It links to
  `preferences_url` and `forum_url`, which nothing supplies.
- `EmailType.NEWSLETTER` and the `"newsletter"` entries in
  `apps/core/management/commands/test_email.py` and
  `apps/core/tests/test_email_service_silent_failures.py`, if nothing else
  uses them.

A future caller could pick up `send_newsletter` and mail people who never
confirmed.

## Acceptance Criteria

- [ ] `send_newsletter` and `emails/newsletter.html` are deleted, or a
  reason to keep each is recorded here.
- [ ] `EmailType.NEWSLETTER` and its test/command references are removed or
  kept with a reason. `pytest apps/core` passes.

## Work Log

### 2026-10-09 - Filed from todo 409 slice B

Left out of 409 to keep that PR to the sender.
