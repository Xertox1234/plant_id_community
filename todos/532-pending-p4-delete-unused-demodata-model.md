---
status: pending
priority: p4
issue_id: "532"
tags: [backend, users, migrations]
dependencies: []
---

# Delete the unused `users.DemoData` model

## Problem

Nothing creates or reads `DemoData`: outside its migrations, `apps/users/models.py`
is its only reference (checked 2026-10-09). Rows with
`demo_type="care_reminder"` or `target_onboarding_step="care_reminder_set"`
keep the retired values (todo 531 item 3; todo 458 item 4). Deleting the
model settles both instead of remapping data nobody reads.

Owner decision (2026-10-09): record it in 531 and do the deletion as its own
todo, not inside a p4 cleanup.

## Approach

Expand/contract, per `docs/rules/database.md`: first remove the model from
Django state only (`SeparateDatabaseAndState`, `DeleteModel` in state), so the
old container never selects a missing table during the rolling deploy; drop
the table in a later deploy. Check the admin, serializers, fixtures and the
web/mobile clients for any reference first.

## Acceptance Criteria

- [ ] No code references `DemoData` (grep across backend, web, mobile).
- [ ] State-only removal shipped and deployed.
- [ ] Table dropped in a later PR.

## Work Log

### 2026-10-09 - Filed from todo 531 item 3
