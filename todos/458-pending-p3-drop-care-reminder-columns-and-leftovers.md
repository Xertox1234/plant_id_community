---
status: pending
priority: p3
issue_id: "458"
tags: [backend, users, migrations, cleanup]
dependencies: ["410"]
---

# Drop the care-reminder columns once #854 is deployed, and clear the leftovers

## Problem

PR #854 (todo 410 slice B) removed `User.care_reminder_email` and
`OnboardingProgress.first_care_reminder_created` from Django **state only**.
The columns stay in the database with a DB default of `false`. This is expand
and contract: during a rolling deploy the old container keeps serving while the
new one migrates, and the old code selects those columns on every User fetch.
Dropping them in the same deploy would 500 auth until cutover.

The PR #854 review also turned up leftovers that predate that PR.

## Recommended Action

1. **Contract.** Once #854 is live in production, add a migration that drops
   both columns: `auth_user.care_reminder_email` and
   `users_onboardingprogress.first_care_reminder_created`. Use
   `SeparateDatabaseAndState` with `database_operations` only (a `RunSQL`
   `ALTER TABLE … DROP COLUMN` with a literal table name, never an f-string),
   since the fields are already gone from state. Update
   `apps/users/tests/test_care_reminders_removed.py::ExpandContractColumnsTest`
   to assert that the columns are gone.
2. **The seasonal-care email cannot render.** `templates/emails/seasonal_care.html`
   uses `{% url 'forum:category' 'seasonal-care' %}`, and no `forum` URL
   namespace exists, so it raises `NoReverseMatch`. Nothing sends it today
   (`EmailType.SEASONAL_CARE` has no sender). Fix the link, or delete the
   template and the email type.
3. **`scripts/add_log_prefixes.py --check` fails on main.** Its
   `plant_identification/views.py` table has 11 keys that match no logger
   message. Remove or reword them. PR #854 removed only the keys it had made
   stale, plus the users demo-data keys that todo 412 had made stale.
4. **`DemoData.DEMO_TYPES` still lists `care_reminder`.** `DemoData` has no
   reader or writer since todo 412. Delete the model, or at least the choice.

## Acceptance Criteria

- [ ] Both columns are dropped by a migration that ships AFTER #854 is deployed.
- [ ] Items 2–4 are fixed, or each is closed with a recorded reason.

## Work Log

### 2026-09-27 - Filed from the PR #854 round-1 review
