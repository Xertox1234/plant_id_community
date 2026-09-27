---
status: pending
priority: p4
issue_id: "454"
tags: [django, email, testing]
dependencies: []
source_review: "todos/364-pending-p3-mailers-migration-and-warning-gate.md"
---

# Mail call sites' `except Exception` swallows the RemovedInDjango70Warning gate

## Problem

From the todo 364 review (PR #850, bundled `/code-review`, not blocking).
`pytest.ini` turns a `RemovedInDjango70Warning` into an exception. The three
mail call sites catch every `Exception`, log it, and return, so a first-party
deprecation added there would not fail the run:

- `wagtail_forum/digest.py` `send_digest`;
- `apps/core/security.py` `_send_lockout_notification`;
- `apps/users/services.py` `CareReminderService.send_care_reminder_email`,
  which todo 410 deletes.

A future `message.send(fail_silently=False)`, `connection=` or `auth_user=`
would log "[EMAIL] … failed" and stay green unless a test checks the outbox
or the return value.

## Recommended Action

Either re-raise `Warning` subclasses from those `except` blocks
(`except Warning: raise` ahead of `except Exception`), or give each call
site a test that sends through locmem and asserts `mail.outbox` has the
message. The outbox tests prove delivery as well as the gate.

## Acceptance Criteria

- [ ] Planting a deprecated argument at each remaining mail call site fails a test

## Work Log

### 2026-09-26 - Filed from the todo 364 review (PR #850)
