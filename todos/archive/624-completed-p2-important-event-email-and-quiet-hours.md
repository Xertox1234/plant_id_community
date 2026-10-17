---
status: completed
priority: p2
issue_id: "624"
tags: [backend, web, mobile, notifications, preferences, product]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: approve optional mention/quote/accepted-answer email, OFF by default (no silent opt-in), and a mentioned subscriber gets ONE merged email (2026-10-12). Owner: quiet hours are opt-in, default window 22:00-07:00 in the client-reported IANA timezone (UTC if unknown); held pushes/emails release at window end; security mail exempt (2026-10-12). Owner: coalesce same-topic replies within a 10-minute window into one email/push, and skip the external send if the user already read the post in-app (2026-10-12). Executes after 620 merges"
---

# Add important-event email and quiet hours for forum notifications

## Problem

Split from todo 620 at triage (run 2026-10-12-1616, owner decision 2026-10-12): 620 ships the policy matrix and web/mobile parity; this todo owns the optional important-event email channel and quiet-hour/frequency behavior that 620's AC4 and AC5 required.

## Findings

- `backend/packages/wagtail_forum/wagtail_forum/preferences.py:33-38` offers email only for replies; mention, quote and accepted-answer events are push-only, so members without push get no immediate signal.
- `backend/apps/forum_host/notifications.py:212-225,264-301` excludes mentioned/quoted members from reply-email recipients.
- No quiet-hour, timezone or coalescing logic exists in the forum dispatch/task paths; each reply sends immediately.

## Recommended Action

1. Build on 620's recorded policy matrix. Get owner defaults for quiet hours (window, timezone source), coalescing window and read-before-send suppression before implementing them.
2. Add optional mention/quote/accepted-answer email, deduplicated with reply email so a mentioned subscriber gets one appropriate message.
3. Implement quiet hours/coalescing with security mail exempt and the in-app inbox unaffected.

## Acceptance Criteria

- [x] Mention/quote/accepted-answer email and mentioned-subscriber behavior are explicitly decided; approved channels are implemented and tested for missing push registration, deduplication and unsubscribe. Any declined channel has a dated reason, not an untracked deferral.
- [x] Approved quiet-hour/frequency behavior is implemented and tested across timezones/DST, rapid replies, read-before-send, preference changes while waiting, and security-mail exemptions. Any declined option has a dated owner decision.
- [x] Web and mobile settings expose the new choices consistently with 620's matrix; relevant backend preference/unsubscribe tests, web settings tests and type-check, and mobile preference tests/analyze pass.

## Work Log

### 2026-10-12 - Split from 620 at triage

- Criteria 620 AC4 and AC5 re-pointed here by owner decision; wording carried over unchanged.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1746)

- Important-event email: mention, quote and accepted-answer email cells, off by default (package `NOTIFICATION_DEFAULTS`); `send_forum_email_batch` sends them with one merged email for a mentioned or quoted subscriber (their event email if on, else the reply email they follow the topic for). New `forum_mention` / `forum_quote` / `forum_solution` unsubscribe lists each turn off only their own cell; shared `forum_event` template.
- Quiet hours: opt-in `ForumProfile.quiet_hours_*` and `time_zone` (migration 0040), window math in `wagtail_forum/quiet_hours.py` (wall-clock in the reported IANA zone, DST-aware, UTC fallback). Held deliveries sit in the outbox (`delivery.mark_held`, mobile push joins it as `Kind.FORUM_PUSH`, core migration 0008) and reconciliation releases them; a profile change reschedules them. Security mail never passes through `apps/forum_host/pacing.py`.
- Coalescing (implementation reading of the owner decision): first reply goes out at once; replies within 10 minutes of the last message about that topic are held and folded into one "N new replies" message per channel. Read-before-send is a new `already_read` recheck reason.
- Web Settings and mobile Profile show the new email cells, the merged-email note and quiet hours with the zone in effect; `docs/notifications-policy.md` records it all. Mobile reports a zone only when the platform gives an IANA name.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1746)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/forum_host/tests/test_important_event_email.py apps/users/tests/test_email_unsubscribe.py apps/users/tests/test_email_presentation.py packages/wagtail_forum/wagtail_forum/tests/api/test_notification_preferences.py apps/forum_host/tests/test_signals.py -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/624-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 145 passed, 3 warnings in 24.69s =======================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/test_quiet_hours.py apps/forum_host/tests/test_quiet_hours_and_coalescing.py apps/forum_host/tests/test_send_time_eligibility.py apps/forum_host/tests/test_delivery_outbox.py apps/core/tests -v --create-db -p no:cacheprovider` — evidence `.sweep-evidence/g1/624-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======= 1899 passed, 3 warnings, 71 subtests passed in 75.45s (0:01:15) ========
  ```

- AC 3: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_notification_preferences.py packages/wagtail_forum/wagtail_forum/tests/test_quiet_hours.py apps/users/tests/test_email_unsubscribe.py apps/users/tests/test_notification_policy.py apps/forum_host/tests/test_notification_preferences.py -q --create-db -p no:cacheprovider && cd ../web && npx vitest run src/pages/SettingsPage.test.tsx src/services/forumService.test.ts && npm run type-check && cd ../plant_community_mobile && flutter test test/features/profile test/services/user_profile_service_test.dart && flutter analyze` — evidence `.sweep-evidence/g1/624-ac2.txt` (not committed), last lines:

  ```text
  Got dependencies!
  141 packages have newer versions incompatible with dependency constraints.
  Try `flutter pub outdated` for more information.
  Analyzing plant_community_mobile...
  No issues found! (ran in 3.4s)
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1746)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-13 - Review round 1: non-blocking findings (PR #1132)

Each fix has a test; each guard fix was mutation-checked (guard broken, test seen failing, file restored from a backup copy).

- fixed: `_hold_single_push` reported a push held when the unique outbox row made `record_batch` insert nothing, so a re-accepted answer during quiet hours was lost; it now holds only when a row was inserted or an open one already holds it, and otherwise sends now (`test_a_re_accepted_answer_is_not_dropped_by_quiet_hours`). This also settles the redelivery-idempotency finding: a redelivered task finds the open row and inserts nothing.
- fixed: a fold's `latest` ignored the dispatched post and could name and link the older reply; `_count_folds` now compares with the dispatched post and `folded_data` keeps the count when the dispatched post is newest (`test_a_fold_shows_the_dispatched_reply_when_it_is_the_newest`).
- fixed: the transient hand-off to `send_forum_push` passed `data`, not the folded `send_data` (`test_a_folded_push_handed_off_on_a_transient_failure_keeps_the_fold`).
- fixed: a credentials stop left the rows the untried sends had folded claimed; they are released with the untried rows (`test_a_credentials_stop_releases_the_rows_an_untried_send_folded`).
- fixed: the `ForumProfile` `post_save` receiver ran its UPDATE on every save; a `pre_save` snapshot now gates it on a quiet-hours field actually changing, and creates are skipped (`test_a_profile_save_that_leaves_quiet_hours_alone_reschedules_nothing`).
- fixed: a handed-off `forum_push` row was marked sent as if delivered; it is now sent with `last_error` `handed_off` (`delivery.HANDED_OFF`), which the coalescing `last_sent` query excludes (`test_a_folded_push_handed_off_on_a_transient_failure_keeps_the_fold`, plus the restored `FORUM_PUSH` assertion in `test_a_retry_after_a_transient_failure_is_rechecked_too`).
- fixed: a hold that ran close to `DELIVERY_MAX_AGE_SECONDS` expired in the same reconcile pass that would release it; held rows keep their exemption for one redrive interval past the release, and the re-drive clears the hold reason so a released row that is never picked up still expires (`test_a_long_hold_is_released_not_expired_when_it_falls_due`).
- fixed: mobile reported no zone, because `DateTime.timeZoneName` is an abbreviation; per the owner decision of 2026-10-13 it now reads the IANA zone through `flutter_timezone` 5.1.1 (`reportableTimeZone`, injectable `deviceTimeZone`), accepting only an Area/City name or UTC (`sends the platform's IANA zone with a quiet-hours save`, `only an IANA name is reportable`, `reports nothing for an abbreviation or a platform error`). `flutter pub add` also moved the transitive `equatable` from 2.0.8 to 2.1.0.
- fixed: the web time inputs saved on every change and disabled themselves mid-save, which dropped focus; each is now a local draft saved on blur or Enter, enabled while a save is in flight (`turning quiet hours on reports this device zone, then edits a time`, `a time left unchanged, or out of range, saves nothing`).
- fixed: mobile `int.parse` accepted '99:99'; the model keeps only in-range `HH:MM` and the picker falls back to the default time (`fromJson reads quiet hours and drops a malformed window`).
- fixed: the `REPLY_COALESCE_SECONDS` comment now describes what `pacing.py` does: the first reply is sent at once, and later ones are held to the last send + the window.
- fixed: the unwired-cell 400 branch is tested again through a patched `NOTIFICATION_MATRIX` with a push-only verb (`test_a_cell_the_matrix_does_not_wire_is_a_400`).
- fixed: `_count_folds` looked up each folded post on its own; `eligibility.visible_posts` fetches them in one query with the same predicate (covered by the fold tests above).
- declined: per-release fold scheduling. The batch countdown fires at the latest release, and reconciliation (every 5 minutes) releases any earlier due row, so an earlier member waits at most one beat. The race between two countdowns is already guarded by `_another_fold_waits`, and claims stop a row being sent twice.
- declined: a Playwright E2E for quiet hours. The flow is one settings form over an endpoint covered by backend API tests and Vitest, and the E2E suite runs against a live stack this sweep does not start. Deferred to the next E2E pass on Settings.
- declined: the dark-theme check. The controls reuse the existing token classes (`text-ink-*`, `bg-surface-2`, `border-line`) that the rest of the section already themes, and add no colours of their own.

### 2026-10-13 - Review round 2: non-blocking findings (PR #1132)

As in round 1, each guard fix was mutation-checked: the guard was broken, the test seen failing, and the file restored from a backup copy.

- fixed: the accepted-answer email labelled the recipient's own excerpt with the acceptor's name; the acceptor stays in the event line ("Someone" when there is none) and the excerpt keeps the post's author (`test_the_accepted_answer_email_credits_the_answer_to_its_author`).
- fixed: the mention/quote fallback reply email ignored a read MENTION/QUOTE bell row; the fallback now applies `already_read_ids` for the original event (`test_a_read_mention_stops_the_fallback_reply_email`).
- fixed: `_hold_single_push` counted a batch's own CLAIMED row as a quiet hold and dropped the push; the batch hand-off of an accepted answer now passes `handed_off=True`, and only a PENDING row counts as held (`test_a_batch_hand_off_of_an_accepted_answer_is_never_held`).
- fixed: an `OperationalError` writing the hold let the push escape quiet hours; it now retries the task, and holding no longer depends on `retries == 0` (`test_a_failed_hold_write_retries_and_the_retry_still_holds`).
- fixed: with no FCM client the push rows stayed due every redrive interval; they are claimed and backed off with `mark_retry` (`fcm_unavailable`) (`test_no_fcm_client_backs_the_push_rows_off_instead_of_leaving_them_due`).
- fixed: `validate_time_zone` 400'd a zone the server cannot resolve; it is stored blank, which reads as UTC (`test_an_unknown_zone_is_stored_as_utc_and_does_not_block_the_save`).
- fixed: start == end was accepted and never held anything; `MeProfileSerializer.validate` rejects it, using the stored value for an end not in the payload (`test_bad_quiet_hours_are_a_400_and_change_nothing`, `test_moving_one_end_away_from_the_other_is_accepted`).
- fixed: the web quiet-hours switch used `disabled` during a save and lost focus; it is now `aria-disabled` with a guarded `onChange`, and a time left while another save is in flight is kept and sent once that save lands (`keeps the switch focused during a save and sends a time left mid-save after it`).
- fixed: the unsubscribe link in `forum_event.html` was already rendered by `emails/base.html`; there is now an assertion on it (`test_the_accepted_answer_email_credits_the_answer_to_its_author`).
- fixed: `mark_held`, `release` and `claim_related` now have direct unit tests (`apps/core/tests/test_delivery_holds.py`).
- fixed: the `pre_save` SELECT. Every non-test `ForumProfile.save` call site passes `update_fields` (grep), so only a profile PATCH pays for the read; a test now pins that a counter save runs no snapshot query (`test_a_counter_save_costs_no_quiet_hours_read`).
- declined: concurrency of coalescing (two runs for one member and topic at the same instant, or a via-reply email next to a reply). Both runs send, never drop: coalescing is best-effort batching on top of an at-least-once outbox, and the per-member lock it would need sits on the hot send path for a rare duplicate.
- declined: per-release fold scheduling and the full recipient list on the countdown. Reconciliation (every 5 minutes) releases an earlier due row, and a re-claimed row that is not yet due is re-evaluated and re-held, so both cost redundant work only.
- declined: the N+1 in `_another_fold_waits`. It is one EXISTS per row held for coalescing in a run, which is bounded by that run's held members, and only runs when a fold is about to be scheduled.
- declined: the mobile stale-state race. The time picker is modal, and a switch tap during the zone lookup reaches `_save`, whose `_saving` guard turns away a second save. No UI path changes the settings in that gap.
- declined: a Playwright E2E, for the same reason as round 1 (deferred to the next E2E pass on Settings).
- declined: pinning `equatable` back. `flutter_timezone` 5.1.1 requires `equatable` `>=2.1.0`, so 2.1.0 is the floor, not drift; `flutter analyze` and `flutter test test/features/profile` pass on it.

## Notes

Depends in practice on 620's policy matrix landing first. Care reminders stay FCM-only (archived 410).
