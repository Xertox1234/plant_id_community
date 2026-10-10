---
status: completed
priority: p4
issue_id: "454"
tags: [django, email, testing]
dependencies: []
source_review: "todos/364-pending-p3-mailers-migration-and-warning-gate.md"
triage: ready
triaged: 2026-10-10
owner_decision: "Cover all five swallowing send sites: digest.py, security.py, blog/newsletter.py, blog/newsletter_digest.py, core/services/email_service.py (2026-10-10)"
---

# Todo 364 review follow-ups: the gate can be swallowed; SMTP subclasses lose credentials

## Problem

From the todo 364 review (PR #850, bundled `/code-review`, not blocking).
`pytest.ini` turns a `RemovedInDjango70Warning` into an exception. The two remaining
mail call sites catch every `Exception`, log it, and return, so a first-party
deprecation added there would not fail the run:

- `wagtail_forum/digest.py` `send_digest`;
- `apps/core/security.py` `_send_lockout_notification`.

(A third, `CareReminderService.send_care_reminder_email`, was deleted with
todo 410 slice B, PR #854.)

A future `message.send(fail_silently=False)`, `connection=` or `auth_user=`
would log "[EMAIL] … failed" and stay green unless a test checks the outbox
or the return value.

## Recommended Action

Either re-raise `Warning` subclasses from those `except` blocks
(`except Warning: raise` ahead of `except Exception`), or give each call
site a test that sends through locmem and asserts `mail.outbox` has the
message. The outbox tests prove delivery as well as the gate.

## Second finding: SMTP subclasses lose credentials (django-drf review)

`apps/core/mail_config.build_default_mailer` routes only the exact
`django.core.mail.backends.smtp.EmailBackend` path through
`ConfiguredSMTPBackend`. Any other backend, including a custom SMTP
subclass set through `EMAIL_BACKEND`, gets plain `username`/`password`
OPTIONS. It would lose them to Wagtail's `get_connection(username=None,
password=None)`, the bug round 1 fixed for vanilla SMTP. Production uses
vanilla SMTP today. Either wrap any SMTP subclass (import it and
`issubclass`-check in `core.E364`), or refuse a non-vanilla SMTP-like
backend in the check.

## Acceptance Criteria

- [x] Planting a deprecated argument at each remaining mail call site fails a test
- [x] A non-vanilla SMTP backend either keeps its configured credentials under a
      `get_connection(username=None, password=None)` call or fails `core.E364`

## Work Log

### 2026-09-26 - Filed from the todo 364 review (PR #850)

### 2026-10-09 - Implemented by the todo sweep (run 2026-10-10-0234)

- Every send site the owner named now re-raises `Warning` ahead of its `except Exception`: `wagtail_forum/digest.py` `send_digest`, `apps/core/security.py` `_send_lockout_notification`, `apps/blog/newsletter.py` `_send_confirmation_email`, `apps/blog/newsletter_digest.py` `send`, and `EmailService.send_email` / `send_transactional_email` / `send_bulk_email`. `send_bulk_email` is included because it wraps `send_email` in its own `except Exception` and would swallow the re-raise. Outside pytest's `error::` filter, `warnings.warn` never raises, so production behaviour is unchanged.
- New `apps/core/tests/test_mail_call_sites_deprecation_gate.py`, plus one test in `wagtail_forum/tests/test_digest.py`, plant a real deprecated argument at each site. The plant is `fail_silently=True`, deprecated in Django 6.1, injected through `EmailMessage.send` or the module's `send_mail`. Each test expects `RemovedInDjango70Warning` to reach it. Before the re-raises were added, all 7 site tests failed with `DID NOT RAISE`.
- `core.E364` (`apps/core/checks.py`) now refuses any SMTP backend that loses its credentials to the legacy `get_connection(username=None, password=None)` merge. Wrapping the backend in `mail_config` was ruled out because that module must not import Django. The check rebuilds the default mailer from its OPTIONS with `username`/`password` set to `None`, the way `MailersHandler.create_connection` does, and compares the credentials. It tests the credentials, not the class, so these cases are refused:
  - a plain SMTP subclass set through `EMAIL_BACKEND`;
  - `ConfiguredSMTPBackend` or a subclass of it set through the env, which gets plain OPTIONS.

  These cases pass:
  - vanilla SMTP, with or without credentials;
  - a `ConfiguredSMTPBackend` subclass given `configured_*` OPTIONS;
  - a non-SMTP backend.

  `manage.py check` with `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` reports no issues.

### 2026-10-10 - Verified by the todo sweep (run 2026-10-10-0234)

- AC 1: `python3 scripts/todos/slot_env.py --worktree . 1 -- backend/venv/bin/python -m pytest backend/apps/core/tests/test_mail_call_sites_deprecation_gate.py backend/packages/wagtail_forum/wagtail_forum/tests/test_digest.py::test_a_deprecated_mail_argument_is_never_swallowed_as_a_send_failure --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/454-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 9 passed, 3 warnings in 18.46s ========================
  ```

- AC 2: `python3 scripts/todos/slot_env.py --worktree . 1 -- backend/venv/bin/python -m pytest backend/apps/core/tests/test_mailers_and_deprecation_gate.py --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/454-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================== 14 passed, 2 warnings in 0.29s ========================
  ```

### 2026-10-10 - Completed by the todo sweep (run 2026-10-10-0234)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
