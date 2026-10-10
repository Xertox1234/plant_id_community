---
status: pending
priority: p4
issue_id: "536"
tags: [backend, users, migrations, ops]
dependencies: ["532"]
---

# Confirm the DemoData drop (users 0018) applied in production

## Problem

Todo 532 removes the unused `users.DemoData` model with a single `DeleteModel` migration,
`users.0018_delete_demodata`, which drops `users_demodata`. Only the owner can confirm the production
deploy applied it.

`DemoData.created_by` was a ForeignKey to `User`. During the rolling deploy, the old container's
`User.delete()` still touches the dropped table, so an account deletion between `migrate` and cutover
fails and rolls back. The owner accepted that window on 2026-10-10, since only owner and test accounts
exist.

## Acceptance Criteria

- [ ] The owner confirms the production deploy of todo 532's PR applied `users.0018_delete_demodata`.
      Record the date and the quoted `showmigrations users` line, or the deploy log line.
- [ ] The owner records the `users_demodata` row count from before the drop, if one can still be had (a backup
      or a pre-deploy snapshot); otherwise a dated note that it cannot. (From todo 537, finding #979-2, promoted
      2026-10-10.)

## Work Log
