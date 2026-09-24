---
status: completed
priority: p2
issue_id: "408"
tags: [backend, email, security, users]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
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

- [x] A link carrying a forged or expired token cannot unsubscribe anyone. Tests pin this.
      `apps/users/tests/test_email_unsubscribe.py`: `test_forged_token_changes_nothing`,
      `test_expired_token_changes_nothing` (both endpoints return 400, and
      `_assert_nothing_changed` holds), plus unit tests for tampered, UUID-swapped,
      unsalted or other-salt, unknown-list and inactive or deleted tokens. All 8
      mutation checks were killed, including "no max_age" (2 failed) and
      "signature skipped" (6 failed).
- [x] The unsubscribe page renders in all states, with no TemplateDoesNotExist.
      The page is now the web app's `/unsubscribe` route (it renders no Django
      template; the old view that 500'd is deleted). `UnsubscribePage.test.tsx`
      covers 8 states: confirm, done, already, missing token, invalid, expired,
      error with retry, and a failed save. 8 passed; full vitest 1376 passed.
- [x] Production email links point at the real domain. Record the date and what was observed.
      2026-09-23: Railway had NO `SITE_URL` on either service (checked by name), so
      links used the `https://plantcommunity.com` default. With owner approval I set
      `SITE_URL=https://houseplant-md.com` on `plant_id_community` and
      `forum-prune-cron`; a script confirmed both are present and equal that
      value. After the redeploy (SUCCESS), a read-only `railway ssh` at about
      23:46 UTC printed `SITE_URL_HOST houseplant-md.com`. Every emailed link is
      built on it (`unsubscribe_url()` = `SITE_URL/unsubscribe?token=…`, pinned by
      `test_forum_reply_email_carries_a_working_signed_link`).

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-23 - Implemented (branch fix/todo-408-unsubscribe-signed-token)

**Reproduced first.** On origin/main, `GET /api/v1/auth/unsubscribe/?user=<uuid>`
raised `TemplateDoesNotExist: users/unsubscribe_error.html`. `reverse("users:unsubscribe")`
gave `/api/auth/unsubscribe/`, which resolves only through the legacy mount.

**Two findings changed the design:**

- The live reply email carried `type=forum_reply`, but the old POST branched only
  on `all`, `plant_care` and `forum`. So even with templates in place,
  `forum_reply` fell through to a `user.save()` that changed nothing and still
  reported success.
- The flags the old view flipped were the wrong ones. `User.forum_notifications`
  also silences FCM push (`forum_host/tasks.py:194,317`), and no web UI can turn
  `User.email_notifications` back on. The reply email is actually gated by
  `ForumProfile.notification_preferences["reply"]["email"]`, which is the cell
  the Settings grid edits (todo 343).

**What was built:**

- **`apps/users/email_unsubscribe.py`**: a `django.core.signing` token under
  its own salt, holding `{u: user.uuid, l: list}`, with a 90-day max age.
  - `read_token` raises `UnsubscribeTokenExpired` for an expired token.
    Everything else raises `UnsubscribeTokenInvalid`: forged, other salt,
    unknown list, or an inactive or deleted user.
  - A `LISTS` registry has one list, `forum_reply`. It turns off the reply-email
    matrix cell only, using the same `merge_preferences` the Settings PATCH
    uses, under `select_for_update`.
- **API:** `POST /api/v1/auth/unsubscribe/check/` (describes the link, changes
  nothing) and `POST /api/v1/auth/unsubscribe/` (idempotent).
  - The token is the only credential: `authentication_classes([])`, so a
    signed-in session never chooses the target.
  - Rate limited to 30/h per IP; GET returns 405; `?user=` is no longer read.
  - An OpenAPI `extend_schema` is added, so spectacular has no new errors.
- **Web:** a public `/unsubscribe?token=` page. Opening it changes nothing;
  only the button acts. It covers the confirm, already-unsubscribed, done,
  invalid, expired and error-with-retry states, and every state links to
  `/settings`. The service sends `credentials: 'omit'`.
- **Email:** `EmailService` adds `unsubscribe_url` only for types in
  `UNSUBSCRIBE_LISTS` (a type with no list gets no link), plus a matching
  RFC 2369 `List-Unsubscribe` header. `preferences_url` is now
  `SITE_URL + "/settings"`, replacing the dead `#!/` fragment.
- **`validate_environment()`:** a missing `SITE_URL` is now a critical error in
  production, and `SITE_URL` is added to both services in `.railway/railway.ts`.

**Production `SITE_URL`:**

- Railway (checked by variable name only) had no `SITE_URL` on either service,
  so every emailed link, both RSS feeds and the sitemap used the default
  `https://plantcommunity.com`.
- With the owner's approval, I set `SITE_URL=https://houseplant-md.com` on
  `plant_id_community` (redeployed) and `forum-prune-cron` (`--skip-deploys`).
  A script confirmed both are present and equal the intended value.

**Mutation checks** (each file copied aside and restored from the copy; the
restore was grep-confirmed). All 8 backend mutations were killed:

- no `max_age`
- signature skipped
- salt kwarg dropped
- inactive user accepted
- unknown list accepted
- check endpoint mutates
- no link for `forum_reply`
- no header

A salt replaced with `''` first SURVIVED. That value differs from Django's
default salt, so it was a bad mutant; the real drop was killed once the
unsalted test case was added.

Both web mutations were killed: the page unsubscribing on load failed 8 tests,
and the service sending cookies failed as well.

### 2026-09-23 - Completed (PR #802)

- **Verification:** all 3 acceptance criteria are met; the evidence is inline
  above.
  - Full backend pytest: 3589 passed, 8 skipped.
  - `apps/users` and `apps/core` re-run after the schema edit: 1554 passed.
  - `check` is clean, `makemigrations --check` reports no changes, and
    `spectacular` exits 0 with no new errors.
  - Web: `tsc`, `eslint`, `prettier` and `check:classes` are clean; vitest 1376
    passed.
- **Review:** bundled `/code-review` found 0 blocking issues. Its three
  non-blocking findings became todos 417 (a non-object body returns a 500, and
  a comment overstates the log exposure) and 416 (RFC 8058 one-click, already
  filed).
- **Also filed:** todo 415 (dead Django email-preferences views).
- **Todo 405 slice 4 is unblocked:** nothing reverses `users:unsubscribe` any
  more.
