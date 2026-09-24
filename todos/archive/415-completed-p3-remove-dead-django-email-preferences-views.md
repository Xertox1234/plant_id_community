---
status: completed
priority: p3
issue_id: "415"
tags: [backend, email, users, dead-code]
dependencies: []
source_review: "todos/archive/408-completed-p2-email-unsubscribe-signed-token-and-pages.md"
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

- [x] No view renders a template that does not exist (`grep` for `render(` in
      `apps/users/` resolves every template name).
- [x] The full backend pytest is green.

## Work Log

### 2026-09-23 - Filed from todo 408

The two views were left out of todo 408's PR on purpose, to keep it to the
signed unsubscribe link.

### 2026-09-24 - Completed (goal run, todo-next → completing-todos), with 417

- Deleted `email_preferences`, `ajax_update_preference`,
  `update_forum_subscriptions` and `get_forum_subscription_preferences`, their
  two URL patterns, and the six imports only they used. The module docstring
  now describes what is left: the signed-link unsubscribe endpoints.
- `rg -n "render\(|render_to_string\(|template_name\s*=" apps/users --glob
  '!**/tests/**'` → **no matches**: no view in `apps/users/` renders a
  template at all now.
- `forum_digest.html:188` now links `{{ app_url }}/settings` (the web
  Settings page, the same path as `WAGTAILFORUM_DIGEST_SETTINGS_PATH`)
  instead of `{% url 'users:email_preferences' %}`. The template's other
  `{% url 'forum:…' %}` tags are machina-era and were already broken. Nothing
  renders it (the live digest uses the package's own templates), so they are
  left as they were, and it stays pinned as broken in
  `test_email_service_silent_failures.py`.
- **`ForumNotificationSubscription` was NOT removed.** Step 2 needs a
  production row count first. The auto-mode classifier refused the read-only
  `railway ssh` count ("Production Reads"), and dropping a table on an
  assumption is irreversible. Re-pointed to **todo 430** (p4, operator count,
  then a `DeleteModel` migration). The model now has no reader or writer.
- New test `test_removed_session_preference_views_have_no_route`
  (`NoReverseMatch` for both names).
- `pytest apps/users apps/core/tests` → `1573 passed, 24 warnings in 62.95s`.
  The full suite is CI's `Run backend test suite` required check on the PR.
