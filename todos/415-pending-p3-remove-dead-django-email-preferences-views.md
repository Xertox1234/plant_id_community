---
status: pending
priority: p3
issue_id: "415"
tags: [backend, email, users, dead-code]
dependencies: []
source_review: "todos/408-pending-p2-email-unsubscribe-signed-token-and-pages.md"
source_finding: "follow-up filed 2026-09-23"
---

# Remove the dead Django email-preferences views

## Problem

`apps/users/email_preferences_views.py` still holds two views from before the
web Settings page existed. Both are unreachable in practice, and one renders a
template that does not exist, so it would 500 if anything called it.

## Findings

Filed while doing todo 408, which replaced this file's `unsubscribe` view with
the signed-link endpoints and left these two alone to keep the PR scoped.

- `email_preferences` renders `users/email_preferences.html`, which does not
  exist. It is `@login_required` (a session login), but the web app and mobile
  both authenticate with JWT, so no client has a session to reach it with.
- `ajax_update_preference` is also `@login_required`, and no client calls it.
  `grep -rn "email-preferences\|ajax-update" web/src plant_community_mobile/lib`
  returns nothing.
- Their helpers `update_forum_subscriptions` and
  `get_forum_subscription_preferences` are the only readers and writers of
  `apps.core.models.ForumNotificationSubscription` outside migrations. It is a
  relic from before the forum rebuild; the live per-event preferences are the
  `ForumProfile.notification_preferences` matrix (todo 343).
- `templates/emails/forum_digest.html:188` names `{% url 'users:email_preferences' %}`.
  That template already fails to render for other reasons (it is pinned as
  broken in `apps/core/tests/test_email_service_silent_failures.py`), and the
  live digest is the package's own template. Still, todo 405 slice 4 (removing
  the legacy `/api/` mount) should not be the thing that surfaces it.

## Recommended Action

1. Delete both views, their two URL patterns (`email_preferences`,
   `ajax_update_preference`) and the two helpers.
2. Decide about `ForumNotificationSubscription`: count its production rows
   read-only first. If they are all zero, remove the model with a migration.
3. Fix or delete `forum_digest.html`'s `{% url %}` references.

## Technical Details

- `backend/apps/users/email_preferences_views.py`
- `backend/apps/users/urls.py`
- `backend/apps/core/models.py` (`ForumNotificationSubscription`)
- `backend/templates/emails/forum_digest.html:188`

## Acceptance Criteria

- [ ] No view renders a template that does not exist (`grep` for `render(` in
      `apps/users/` resolves every template name).
- [ ] The full backend pytest is green.

## Work Log

### 2026-09-23 - Filed from todo 408

The two views were left out of todo 408's PR on purpose, to keep it to the
signed unsubscribe link.
