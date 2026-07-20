---
status: completed
priority: p2
issue_id: "267"
tags: [backend, email, notifications, reliability]
dependencies: []
---

# EmailService: silent-failure modes affect every templated email, app-wide

## Problem

Implementing todo 253 slice 2 (wiring the forum reply-notification email)
surfaced that `apps/core/services/email_service.py::EmailService` has three
compounding defects that make it silently report success when an email did
not actually reach an inbox — and these are NOT forum-specific. They affect
every `EmailType` this service sends: welcome email, plant care reminders,
disease alerts, seasonal care, blog posts, newsletters, identification
results, and forum reply/mention/digest/new-topic.

The forum-reply path (todo 253 slice 2) is now guarded against the worst
instance of this (a blank-email recipient — see `apps/forum_host/tasks.py`'s
`if not user.email:` check), but every OTHER caller of `EmailService` still
has the full exposure.

## Findings

All three were found via multi-angle code review of the todo 253 slice 2 diff
(`/code-review --effort high`, 2026-07-14), not a formal audit — no
`source_review` doc exists to link.

1. **`send_email()` ignores `email.send()`'s return value.**
   `apps/core/services/email_service.py:148` calls `email.send()` but never
   checks the returned int. Django's `EmailMessage.send()` returns `0`
   (without raising) when `EmailMessage.recipients()` filters every address
   to empty — e.g. a user with a blank `.email` field. `send_email()` still
   runs `_track_email_sent(...)`, logs "sent successfully", and returns
   `True` for a message that reached zero inboxes.
   - **Concrete data-corruption path**: `PlantCareReminderService.send_reminder()`
     (`apps/plant_identification/services/plant_care_reminder_service.py:158-168`)
     calls `reminder.mark_reminder_sent()` and advances `next_reminder_date`
     on that same false `True` — a user with an email issue silently never
     gets reminded again, with no error anywhere.
   - This is also *why* `send_forum_email` (todo 253 slice 2) ships with no
     retry around the send call itself: `send_email()`'s internal swallowing
     of `ConnectionError`/`TemplateDoesNotExist`/blanket `Exception` means
     nothing ever reaches a caller as a raised exception on that path.

2. **10 of 11 `EmailType` templates have no `.txt` counterpart.**
   `send_email()` unconditionally renders both `emails/{template}.html` AND
   `emails/{template}.txt` (`email_service.py:123-124`); a missing `.txt`
   raises `TemplateDoesNotExist`, caught and turned into a silent `return
   False` (`:125-127`). Before todo 253 slice 2 added `forum_reply.txt`,
   **zero** `.txt` files existed; now there is exactly one. Still missing:
   `welcome_email.txt`, `plant_care_reminder.txt`, `disease_alert.txt`,
   `seasonal_care.txt`, `blog_post.txt`, `newsletter.txt`,
   `identification_result.txt`, `generic_notification.txt`,
   `forum_mention.txt`, `forum_digest.txt`, `new_forum_topic.txt`.
   `send_welcome_email_on_verification` (`apps/users/signals.py:25-36`) is
   wired to allauth's real `email_confirmed` signal — every new-user welcome
   email has been silently no-op-ing at the render step.

3. **The same context-key mismatch bug class exists at least once more.**
   Todo 253 slice 2 found and fixed one instance (forum_reply's
   `author_name`/`post_excerpt` vs the sender's old `reply_author`/
   `reply_excerpt` keys). A second, independent instance: `send_identification_result_notification`
   (`apps/core/services/notification_service.py` ~line 316-345) supplies
   `{plant_name, confidence, confidence_percent, identifier_name, result_url}`,
   but `identification_result.html` actually references `{{ confidence_text }}`,
   `{{ scientific_name }}`, `{{ care_guide_url }}`, `{{ forum_url }}`,
   `{{ plant_image_url }}` — none of which are ever supplied. Django renders
   an undefined var as `''`, so this ships a mostly-blank identification
   email while `send_email` still logs/returns success. No test exercises
   this render path.

4. **Manual smoke-test script is stale and now gives false-positive results.**
   `backend/test_email_templates.py` (a standalone script, not pytest-collected,
   run manually via `python test_email_templates.py`) still builds the
   `forum_reply` context with the pre-slice-2 `reply_author`/`reply_excerpt`
   keys. Before slice 2, it failed loudly (`TemplateDoesNotExist` — no
   `.txt`). After slice 2, `forum_reply.txt` exists but the script's keys
   don't match the template's `author_name`/`post_excerpt` vars, so it now
   prints a green "✅ Forum Reply Notification" for a render with a blank
   author name and blank excerpt — the script's only check is a minimum
   content-length threshold, satisfied by template boilerplate. This is
   exactly the tool a developer would manually run to sanity-check templates,
   giving a false all-clear for the defect class findings 1-3 describe.

## Recommended Action

Sequenced cheapest/highest-impact first:

1. **Fix `send_email()`'s ignored return value** (finding 1) — check
   `email.send()`'s return count; treat `0` as a failure (log + return
   `False`), not a success. This is the root fix; it also means removing the
   `apps/forum_host/tasks.py` `if not user.email:` guard becomes safe later
   (though leave it — cheap, explicit, no reason to remove).
2. **Audit `PlantCareReminderService.send_reminder()`'s blast radius** —
   confirm no reminders have been silently "consumed" (marked sent,
   `next_reminder_date` advanced) for users with a bad email, and decide
   whether a backfill/re-notify is needed for affected users.
3. **Add the 10 missing `.txt` templates**, OR make `send_email()` tolerate
   a missing `.txt` (e.g. a `strip_tags(html_content)` fallback) so a future
   new `EmailType` can't reintroduce this — the fallback approach is more
   defensive and doesn't require hand-authoring 10 files.
4. **Fix `send_identification_result_notification`'s context-key mismatch**
   (finding 3) — align context dict keys to `identification_result.html`'s
   actual vars, add a render-content test (assert plant name/confidence
   actually appear, not just `len(mail.outbox) == 1`), mirroring the pattern
   `apps/forum_host/tests/test_tasks.py::test_send_forum_email_sends_reply_notification`
   established.
5. **Fix or retire `backend/test_email_templates.py`** (finding 4) — either
   update its context dicts to match current template vars (cheap), or
   replace it with real pytest coverage (assert-on-content, per the pattern
   in finding 4 above) and delete the manual script.

## Technical Details

- `apps/core/services/email_service.py` — `send_email()` (line 64),
  `_should_send_email()` (line 230), template render (lines 123-127).
- `apps/core/services/notification_service.py` — `_get_email_template_for_type`
  (line 237) maps `EmailType` → template base name; every `send_*_notification`
  method builds its own context dict by hand (no schema/dataclass ties a
  sender's context keys to its template's actual vars — this is *why* the
  mismatch class keeps recurring; consider a lightweight assertion or a
  shared dataclass-per-template as a structural fix, not just per-instance patches).
- `apps/plant_identification/services/plant_care_reminder_service.py:158-168`
  — the concrete data-loss caller for finding 1.
- Precedent for the "assert on rendered content, not send-count" test pattern:
  `apps/forum_host/tests/test_tasks.py` (todo 253 slice 2).

## Acceptance Criteria

- [x] `send_email()` returns `False` (and logs) when `email.send()` reports
      zero recipients delivered
- [x] `PlantCareReminderService`'s false-success blast radius investigated;
      remediation decided (backfill or accepted as low-impact)
- [x] Every `EmailType` template renders both `.html` and `.txt` without
      `TemplateDoesNotExist` (test: loop `EmailType` values, assert both
      templates render)
- [x] `send_identification_result_notification`'s context keys match
      `identification_result.html`'s actual vars, with a content-assertion test
- [x] `backend/test_email_templates.py` either fixed to use current context
      keys or retired in favor of real pytest coverage

## Work Log

### 2026-07-14 - Created from todo 253 slice 2 code review

- Surfaced via `/code-review --effort high` + `code-review-orchestrator` on
  the todo-253 slice-2 diff (forum reply-email wiring). All 3 findings are
  pre-existing in shared `EmailService`/`NotificationService` code, not
  introduced by that diff — the diff's own new caller
  (`apps/forum_host/tasks.py::send_forum_email`) is already guarded against
  finding 1's worst case (blank email) and ships its own `.txt` template
  (finding 2, one of eleven) and correct context keys (finding 3, the first
  fixed instance of that bug class).

### 2026-07-20 - Implemented (completing-todos run, todo-sweep)

- Branch `todo-267-email-silent-failures` off fresh `main` (@3e1f434, after
  todo 268 / PR #476 merged).
- **Finding 1** — `send_email()` now captures `email.send()`'s return count and
  returns `False` (+ warns) on `0` recipients instead of tracking a phantom
  send and returning `True`. Django's `EmailMessage.send()` returns `0` without
  raising when `recipients()` filters every address (e.g. a blank `To`). Test:
  `SendEmailZeroRecipientsTests` (blank recipient → `False`, empty outbox, no
  `EmailNotification` row). Discriminating: under the old code this returned
  `True`.
- **Finding 2** — split the render into two try blocks: the `.html` body stays a
  HARD failure (`return False`), but a missing/broken `.txt` falls back to
  `strip_tags(html_content)` instead of the old shared-`try` that turned a
  missing `.txt` into a silent `return False`. So the 10 `.html`-only templates
  (incl. `welcome_email`, wired to allauth's `email_confirmed`) now actually
  send. Tests: `TxtFallbackTests` + `WelcomeEmailCanaryTests`.
- **Finding 3** — `send_identification_result_notification` is UNCALLED anywhere
  (grep: zero call sites), so aligned the TEMPLATE DOWN to the 5 keys the sender
  actually supplies rather than inventing `scientific_name`/`care_guide_url`/
  `plant_image_url` on the sender: `identification_result.html` now uses
  `{{ confidence_percent }}` (was the never-supplied `{{ confidence_text }}` →
  blank) and dropped the `care_guide_url` button + `forum_url` link (both
  rendered as empty `href=""`). Guarded refs (`plant_emoji|default`,
  `{% if plant_image_url %}`, `{% if scientific_name %}`) already degrade safely
  and were left. Test: `IdentificationResultContentTests` asserts the real
  values render + no empty `href=""`.
- **Finding 4** — retired `backend/test_email_templates.py` (a stale, non-
  pytest-collected manual script that false-greened `forum_reply` with
  pre-slice-2 keys); its coverage is superseded by the real pytest tests above.
- **Blast-radius decision (accept as low-impact, no backfill):** confirmed the
  data-loss path — `PlantCareReminderService.send_reminder` calls
  `reminder.mark_reminder_sent()` (advances `next_reminder_date`) on the false
  `True`, silently consuming a reminder for a bad-email user. A precise
  retroactive backfill is NOT feasible: `_track_email_sent` wrote `STATUS_SENT`
  even on the 0-recipient path, and a since-changed email can't be
  reconstructed, so affected rows aren't identifiable. Finding 1 is the real
  remediation (stops recurrence going forward). Recorded here + surfaced in the
  PR so the user can veto.
- **AC3 caveat + discovered follow-up:** the `.txt` fallback removes the
  `TemplateDoesNotExist` silent no-op for all templates (AC met). En route, the
  fix EXPOSED that 6 templates' `.html` can't render from a generic context —
  `blog_post`→needs `post`, `new_forum_topic`→`subscriber`, `forum_mention`→
  `mentioned_user`; `seasonal_care`/`forum_digest`→`{% url 'forum:…' %}`
  (`NoReverseMatch`), `disease_alert`→`{% url 'diagnosis' %}`. These were masked
  until now (every one no-op'd at the missing-`.txt` step) and are handled
  NON-silently by the `.html` hard-failure path (`return False` + log). Fixing
  them (context requirements + URL namespaces) is a separate task, out of scope
  here — flagged for a follow-up todo.
- **Coupling with todo 268:** 268's `send_forum_email_batch` relies on
  `send_email` never raising; finding 1 still returns a bool (never raises) and
  268 pre-guards blank emails before calling send, so no break. Verified by
  running `apps/forum_host/tests/` alongside core: **226 passed** on a fresh DB.

### 2026-07-20 - Reviewed + completed (code-review-orchestrator)

- 0 critical / 0 high / 0 medium; 4 low + 5 info. Core correctness, the
  `if not sent_count` check, the never-raises coupling guarantee, and the
  template alignment were all explicitly verification-PASSED.
- Actioned: updated a now-stale comment in `send_forum_email_batch`
  (`forum_host/tasks.py`) that described the pre-267 `send_email` behavior.
- Accepted (low/info, non-blocking): `strip_tags` leaves HTML entities as
  literal text in the plain-text fallback (fine for `text/plain`, not XSS); a
  care reminder to a blank-email user now re-fires each cycle instead of being
  silently consumed (the intended blast-radius tradeoff — more correct, bounded
  log churn for a rare edge); finding 3 fixes an uncalled method (fix-before-
  use); deleting the manual script drops only its (never-CI'd) allauth
  password-reset smoke check.
- Verification: all 5 acceptance criteria passed with quoted evidence above.
- Landing on branch `todo-267-email-silent-failures`; per-todo PR to follow.

## Notes

p2: no active security hole, no live user-reported incident — a latent
silent-failure class found via code review. Finding 1 (ignored return value)
is the highest-impact single fix; do it first even if the rest is deferred
further. Related: todo 253 (forum notifications epic) is the origin context;
this todo is intentionally scoped to `EmailService` broadly, not forum-specific.
