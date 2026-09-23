---
status: pending
priority: p2
issue_id: "408"
tags: [backend, email, security, users]
dependencies: []
source_review: "todos/405-pending-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Email unsubscribe and preferences links are broken and unsafe; build them properly

## Problem

Every forum reply email (the only live forum email path,
`apps/core/services/notification_service.py:308`) carries `{{ unsubscribe_url }}`.
That link is broken in three ways, and it is also unsafe:

- **It 500s.** The view renders `users/unsubscribe_confirm.html`,
  `unsubscribe_success.html`, `unsubscribe_error.html` and
  `users/email_preferences.html`, and none of them exist.
- **It is unsafe.** It accepts an unsigned `?user=<uuid>`, and a POST turns off
  all of that user's email. There is no token.
- **It may point at the wrong domain.** `SITE_URL` is not in
  `.railway/railway.ts`'s env list, so production likely uses the
  `https://plantcommunity.com` default (`settings.py:1082`). This is a
  hypothesis, not verified.
- **It resolves only through the legacy `/api/` mount.**
  `reverse("users:unsubscribe")` works only because that mount exists, and the
  mount is scheduled for removal in todo 405.

The owner decided (todo 405) to build this properly.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Add a signed, expiring token (`django.core.signing`, with its own salt),
   scoped to the user and the list. Stop accepting `?user=<uuid>`.
2. Add real templates: a confirmation page, success, and an error or expired
   page.
3. Confirm the production `SITE_URL`. If it is wrong, set it on Railway and add
   it to `.railway/railway.ts`.
4. Resolve the URL through the `v1:users:` namespace, so todo 405 can remove
   the legacy mount.
5. Decide whether `preferences_url` (a dead `#!/settings/email-preferences`
   PWA fragment) points at the web Settings page.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [ ] A link carrying a forged or expired token cannot unsubscribe anyone. Tests pin this.
- [ ] The unsubscribe page renders in all states, with no TemplateDoesNotExist.
- [ ] Production email links point at the real domain. Record the date and what was observed.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.
