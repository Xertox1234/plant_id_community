---
status: pending
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

- [ ] `send_email()` returns `False` (and logs) when `email.send()` reports
      zero recipients delivered
- [ ] `PlantCareReminderService`'s false-success blast radius investigated;
      remediation decided (backfill or accepted as low-impact)
- [ ] Every `EmailType` template renders both `.html` and `.txt` without
      `TemplateDoesNotExist` (test: loop `EmailType` values, assert both
      templates render)
- [ ] `send_identification_result_notification`'s context keys match
      `identification_result.html`'s actual vars, with a content-assertion test
- [ ] `backend/test_email_templates.py` either fixed to use current context
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

## Notes

p2: no active security hole, no live user-reported incident — a latent
silent-failure class found via code review. Finding 1 (ignored return value)
is the highest-impact single fix; do it first even if the rest is deferred
further. Related: todo 253 (forum notifications epic) is the origin context;
this todo is intentionally scoped to `EmailService` broadly, not forum-specific.
