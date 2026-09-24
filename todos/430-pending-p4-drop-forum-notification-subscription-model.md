---
status: pending
priority: p4
issue_id: "430"
tags: [backend, core, dead-code, migration, operator]
dependencies: []
source_review: "todos/archive/415-completed-p3-remove-dead-django-email-preferences-views.md"
source_finding: "recommended action 2"
---

# Drop the orphaned `ForumNotificationSubscription` model once production confirms it is empty

## Problem

Todo 415 removed the two session-authenticated email-preference views and
their helpers, `update_forum_subscriptions` and
`get_forum_subscription_preferences`. Those helpers were the only code that
read or wrote `apps.core.models.ForumNotificationSubscription` outside
migrations. The model now has no reader and no writer. It dates from before
the forum rebuild; per-event preferences now live in the
`ForumProfile.notification_preferences` matrix (todo 343).

Todo 415's recommended step 2 was to "count its production rows read-only
first. If they are all zero, remove the model with a migration." The
automated run could not do the count: the auto-mode classifier refuses
production reads, correctly. Dropping a table is irreversible, so it must not
be done on an assumption.

## Recommended Action

1. **Operator:** count the rows, read-only:
   `railway ssh --service plant_id_community -- python manage.py shell -c "from apps.core.models import ForumNotificationSubscription as F; print(F.objects.count())"`.
   Record the count and date here.
2. If it is 0, delete the model (and its `related_name="forum_subscriptions"`
   reverse accessor) with a `DeleteModel` migration. The package comments in
   `wagtail_forum/models/subscriptions.py`, `activity.py` and `bookmarks.py`
   mention the legacy `forum_subscriptions` name as a clash to avoid. Update
   them once the name is free.
3. If it is not 0, decide whether the rows mean anything now. Nothing has read
   them since the forum rebuild.

## Acceptance Criteria

- [ ] The production row count is recorded here, with its date.
- [ ] The model is removed by a migration, or kept with a written reason.

## Work Log

### 2026-09-24 - Filed from todo 415

The views and helpers were removed in todo 415's PR. The model was left in
place because the production count could not be taken.
