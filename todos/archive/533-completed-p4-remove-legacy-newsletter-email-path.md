---
status: completed
priority: p4
issue_id: "533"
tags: [backend, core, email, dead-code]
dependencies: ["409"]
triage: ready
triaged: 2026-10-10
---

# Remove the legacy newsletter email path

## Problem

Todo 409 built the real newsletter sender (`apps/blog/newsletter_digest.py`,
`manage.py send_blog_newsletter`). An older, never-wired path is still in the tree:

- `NotificationService.send_newsletter` in
  `backend/apps/core/services/notification_service.py`. Nothing calls it
  (grep, 2026-10-09). It mails any list it is given, with no consent check
  and no List-Unsubscribe header.
- `backend/templates/emails/newsletter.html`, its template. It links to
  `preferences_url` and `forum_url`, which nothing supplies.
- `EmailType.NEWSLETTER` and the `"newsletter"` entries in
  `apps/core/management/commands/test_email.py` and
  `apps/core/tests/test_email_service_silent_failures.py`, if nothing else
  uses them.

A future caller could pick up `send_newsletter` and mail people who never
confirmed.

## Acceptance Criteria

- [x] `send_newsletter` and `emails/newsletter.html` are deleted, or a
  reason to keep each is recorded here.
- [x] `EmailType.NEWSLETTER` and its test/command references are removed or
  kept with a reason. `pytest apps/core` passes.

## Work Log

### 2026-10-09 - Filed from todo 409 slice B

Left out of 409 to keep that PR to the sender.

### 2026-10-09 - Implemented by the todo sweep (run 2026-10-10-0234)

- Deleted `NotificationService.send_newsletter` and `templates/emails/newsletter.html`. The `EmailType.NEWSLETTER: "newsletter"` template-map entry and the `"newsletter"` preheader in `template_service` went with them.
- Removed `EmailType.NEWSLETTER` and its entries in `manage.py test_email`'s listings. `EmailNotification.email_type` has no `choices`, so no migration was needed (`makemigrations --check`: no changes).
- Tests that used `EmailType.NEWSLETTER` as an arbitrary type now use `EmailType.COMMUNITY_UPDATE`, which behaves the same way: it is in no preference map, is not a system type and has no unsubscribe list. `"newsletter"` was dropped from `FALLBACK_RENDERABLE_TEMPLATES` because the template is gone.
- `EmailService.send_bulk_email` now has no caller. It is kept, because removing it is outside this todo.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-0234)

- AC 1: `bash -c 'test ! -e backend/templates/emails/newsletter.html && echo "templates/emails/newsletter.html: deleted" && ! grep -rnE "def send_newsletter\b|emails/newsletter\.html|template_name=\"newsletter\"" backend/apps backend/packages backend/templates && echo "send_newsletter and emails/newsletter.html: no definition or reference left under backend/apps, backend/packages, backend/templates"'` — evidence `.sweep-evidence/g1/533-ac0.txt` (not committed), last lines:

  ```text
  templates/emails/newsletter.html: deleted
  send_newsletter and emails/newsletter.html: no definition or reference left under backend/apps, backend/packages, backend/templates
  ```

- AC 2: `bash -c '! grep -rnE "EmailType\.NEWSLETTER|NEWSLETTER = \"newsletter\"" backend/apps backend/packages && echo "EmailType.NEWSLETTER: removed, no reference left" && python3 scripts/todos/slot_env.py --worktree . 1 -- backend/venv/bin/python -m pytest backend/apps/core --create-db -p no:cacheprovider'` — evidence `.sweep-evidence/g1/533-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======= 1586 passed, 3 warnings, 47 subtests passed in 76.19s (0:01:16) ========
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-0234)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
