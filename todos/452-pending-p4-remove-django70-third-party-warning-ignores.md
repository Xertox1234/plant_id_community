---
status: pending
priority: p4
issue_id: "452"
tags: [django, testing, dependencies]
dependencies: []
source_review: "todos/364-pending-p3-mailers-migration-and-warning-gate.md"
triage: blocked-external
triaged: 2026-09-28
blocked_on: "Upstream django-taggit and Wagtail releases that stop calling quote_name_unless_alias()/get_connection()."
owner_decision: "Owner: wait for upstream django-taggit and Wagtail releases (2026-09-28)"
---

# Remove the two third-party RemovedInDjango70Warning ignores from pytest.ini

## Problem

Todo 364 made `RemovedInDjango70Warning` fail the test run
(`backend/pytest.ini`, `error::`), with two narrow third-party exemptions
(message + module). Both must go before the Django 7.0 upgrade, which
removes the APIs they call:

1. **django-taggit**: `taggit/managers.py` `ExtraJoinRestriction.as_sql`
   calls `compiler.quote_name_unless_alias()`. Django deprecated it in
   ticket #36795, and 7.0 removes it. Seven `test_topic_tags.py` tests hit it
   through the forum tag filter.
2. **Wagtail**: `wagtail/admin/mail.py` `send_emails` calls
   `get_connection()` for workflow and moderation notifications
   (`test_topic_approval.py`). It works under `MAILERS` in 6.x, because
   `get_connection()` returns the default mailer, but 7.0 removes it.

No upstream issue for either could be found on 2026-09-26.

## Recommended Action

On each dependency bump of django-taggit or Wagtail, delete that `ignore:`
line and run the backend suite. If the suite is green, the upstream fix
shipped. If neither has shipped before a Django 7.0 bump is planned, file
an upstream issue or PR, or pin behind a patched fork.

## Acceptance Criteria

- [ ] Both `ignore:` lines are removed from `backend/pytest.ini`, and the full
      backend suite passes with the `error::` gate on

## Work Log

### 2026-09-26 - Filed from todo 364 (MAILERS migration + warning gate)
