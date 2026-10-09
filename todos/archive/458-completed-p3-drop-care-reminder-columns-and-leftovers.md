---
status: completed
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
5. **`migration-remove-field-same-deploy` misses the shapes it exists for.**
   `content_absent: SeparateDatabaseAndState` silences it for the whole file,
   so a migration mixing a state-only removal with a bare `RemoveField` on a
   live column gets no warning (0015 is shaped that way, harmlessly), and it
   never matches `DeleteModel`, although `docs/rules/database.md` says dropped
   tables carry the same exposure. Make the check per operation, or say in the
   message that mixed files need a manual look.
6. **`NotificationService.get_/update_user_notification_preferences` are dead.**
   PR #854 added `care_reminder_notifications` to both, but no production code
   calls either; the real toggle is `UserProfileSerializer`. Delete them.
7. **`ExpandContractColumnsTest` reads `information_schema.columns` without
   `table_schema = current_schema()`**, so a same-named table in another
   schema could answer for the public one.
8. **Onboarding rows may still hold `care_reminder_set`.** 0016 only alters
   the choices. Check the prod count (owner ran it before merging #854) and
   remap any rows to the next step.

Items 5–8 come from the PR #854 final review (2026-10-09).

## Acceptance Criteria

- [x] Both columns are dropped by a migration that ships AFTER #854 is deployed.
  (2026-10-09: GitHub deployment status for #854 `08fee518` reported `success`
  at 14:01Z; `users/0017_drop_care_reminder_columns` drops both, and
  `DroppedColumnsTest` asserts they are gone.)
- [x] Items 2–8 are fixed, or each is closed with a recorded reason. (2026-10-09:
  one line per item in the Work Log below.)

## Work Log

### 2026-09-27 - Filed from the PR #854 round-1 review

### 2026-10-09 - Done

- **1.** `users/0017` drops both columns with `SeparateDatabaseAndState`
  `database_operations` (literal `RunSQL`, reverse re-adds them `NOT NULL
  DEFAULT false`). Nothing outside Django reads them (grep of the whole repo:
  only `PLANNING/DATABASE_SCHEMA.md`, docs and migrations).
- **2.** Deleted `templates/emails/seasonal_care.html` and
  `EmailType.SEASONAL_CARE` (and its two map entries) instead of fixing the
  link: nothing sends it.
- **3.** `scripts/add_log_prefixes.py --check` passes. Removed 16 stale keys:
  the 11 named here, 2 in `users/services.py` (push sender removed by #854) and
  3 in `users/signals.py` (welcome email moved by #842).
- **4.** Removed the `care_reminder` choice only (0017 `AlterField`). Kept the
  model: dropping it is a table drop with rows of unknown value and needs the
  same expand/contract care; nothing reads it, so it costs nothing to leave.
- **5.** The trigger now matches `RemoveField|DeleteModel` on the edit fragment
  and no longer has the file-wide `content_absent`; the message says an
  operation inside `state_operations` is fine and every other one needs a
  manual look. A regex cannot tell the two apart per operation.
- **6.** Deleted `NotificationService.get_/update_user_notification_preferences`
  (no callers outside one test, which no longer uses it).
- **7.** Superseded: `ExpandContractColumnsTest` is replaced by
  `DroppedColumnsTest`, which pins `table_schema = current_schema()`.
- **8.** 0017 moves `current_step = 'care_reminder_set'` to
  `onboarding_completed` (the step that followed it) and strips it from
  `completed_steps`, whatever the row count (`RetiredOnboardingStepTest`). The
  prod count was not taken: no code ever advanced `current_step` past
  `account_created`, so rows are unlikely, and the remap is correct either way.

### 2026-10-09 - Production check after the #963 deploy

#963 deployed at 15:55Z. Read-only checks against production (owner-authorized,
`manage.py shell` over `railway ssh`):

- Onboarding rows on `care_reminder_set` (`current_step` or
  `completed_steps`): **0**.
- `users.0017_drop_care_reminder_columns` applied at 15:55:00Z.
- `auth_user.care_reminder_email` and
  `users_onboardingprogress.first_care_reminder_created`: both gone.

The pre-remap count was not taken before the deploy, and 0017 does not log
one, so how many rows it moved is unknown.
