---
status: pending
priority: p4
issue_id: "454"
tags: [django, email, testing]
dependencies: []
source_review: "todos/364-pending-p3-mailers-migration-and-warning-gate.md"
---

# Todo 364 review follow-ups: the gate can be swallowed; SMTP subclasses lose credentials

## Problem

From the todo 364 review (PR #850, bundled `/code-review`, not blocking).
`pytest.ini` turns a `RemovedInDjango70Warning` into an exception. The two remaining
mail call sites catch every `Exception`, log it, and return, so a first-party
deprecation added there would not fail the run:

- `wagtail_forum/digest.py` `send_digest`;
- `apps/core/security.py` `_send_lockout_notification`.

(A third, `CareReminderService.send_care_reminder_email`, was deleted with
todo 410 slice B, PR #854.)

A future `message.send(fail_silently=False)`, `connection=` or `auth_user=`
would log "[EMAIL] … failed" and stay green unless a test checks the outbox
or the return value.

## Recommended Action

Either re-raise `Warning` subclasses from those `except` blocks
(`except Warning: raise` ahead of `except Exception`), or give each call
site a test that sends through locmem and asserts `mail.outbox` has the
message. The outbox tests prove delivery as well as the gate.

## Second finding: SMTP subclasses lose credentials (django-drf review)

`apps/core/mail_config.build_default_mailer` routes only the exact
`django.core.mail.backends.smtp.EmailBackend` path through
`ConfiguredSMTPBackend`. Any other backend, including a custom SMTP
subclass set through `EMAIL_BACKEND`, gets plain `username`/`password`
OPTIONS. It would lose them to Wagtail's `get_connection(username=None,
password=None)`, the bug round 1 fixed for vanilla SMTP. Production uses
vanilla SMTP today. Either wrap any SMTP subclass (import it and
`issubclass`-check in `core.E364`), or refuse a non-vanilla SMTP-like
backend in the check.

## Acceptance Criteria

- [ ] Planting a deprecated argument at each remaining mail call site fails a test
- [ ] A non-vanilla SMTP backend either keeps its configured credentials under a
      `get_connection(username=None, password=None)` call or fails `core.E364`

## Work Log

### 2026-09-26 - Filed from the todo 364 review (PR #850)
