---
status: completed
priority: p3
issue_id: "623"
tags: [backend, notifications, email, observability, operations, privacy]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: repo-only slice now — outcome vocabulary shared with 619, remove misleading track_opens, worker/beat/queue alert counters; provider feedback ingestion, attribution, prod checks and baseline re-pointed to todo 625. Email provider unknown, decide later (2026-10-12). Owner: 623 executes after 619 merges and extends 619's outbox attempt states — no second ledger (2026-10-12). Owner: operational alerts go to Sentry — cron-monitor check-ins for beat-scheduled tasks plus Sentry events/error logs for broker, retry-exhaustion and missing-push-config failures (2026-10-12)"
---

# Measure delivery and engagement and verify notification operations

## Problem

The project cannot establish notification effectiveness from successful send logs alone. Delivery/bounce/complaint outcomes, cross-channel engagement and current production sender/worker health need an evidence-backed measurement and operational verification path.

## Findings

Source: Devin's read-only email/notification audit and backlog comparison, 2026-10-12. Production configuration, DNS, provider dashboards and live delivery rates were not inspected; missing configuration is not asserted.

- `backend/apps/core/models.py:23-39,102-125` declares delivered/bounced/opened/clicked states and fields, but the audit search found no live writers for provider delivery/bounce outcomes or callers of `mark_opened`/`mark_clicked` in the audited backend paths.
- `backend/apps/core/services/email_service.py:369-397` records successful sends only. `track_opens` at `:79,94` is unused; transactional email at `:399-444` bypasses that tracking. Blog newsletter and package digest use Django mail directly, so this model is not a complete delivery ledger.
- FCM and browser-push tasks log provider acceptance; this does not prove device display or a useful user action. Care tasks can retain a notification claim without a displayed message, so `notification_sent` is not delivery evidence.
- `backend/bin/start.sh:41-49,150-178` starts/supervises a co-located worker with embedded beat. `backend/docs/deployment/railway.md:223-230` notes that the web healthcheck does not establish worker health. Older environment claims in deployment prose must not substitute for current observations.
- `backend/plant_community_backend/settings.py:1373-1389` schedules weekly forum/blog emails and 15-minute care sweeps. Queue latency, skipped runs, provider failures and catch-up behavior are not measured by a successful web response.

## Recommended Action

1. Define a privacy-conscious event/state vocabulary shared with delivery work in todo 619: queued, attempted, provider-accepted, retrying, terminal-failed and suppressed; delivered/bounced/complained only where provider evidence exists. Cover all live send paths, not just EmailService.send_email.
2. Confirm the deployed email provider and supported feedback mechanism. Implement authenticated, replay-safe and idempotent delivery/bounce/complaint ingestion plus an appropriate suppression policy. Preserve security-mail recovery UX; do not keep retrying undeliverable addresses or silently imply recovery mail succeeded.
3. Measure notification click/open-in-app and meaningful outcomes such as verification completion, discussion revisits and care completion with a defined attribution window. Treat opens as optional/noisy, not proof of engagement; remove or implement the misleading track_opens interface deliberately.
4. Add operational counters and alerts for queue age, broker failures, retry exhaustion, disabled/misconfigured push, stale worker/beat activity and expected scheduled runs. Do not create a second competing delivery ledger; extend the agreed delivery state.
5. With owner approval, record current SMTP/sender setup, SPF/DKIM/DMARC results, Firebase/APNs and VAPID readiness, worker/beat health and controlled delivery observations. Record the existing single-worker/embedded-beat scaling constraint and define when a separate scheduler/queue is required.
6. Establish a baseline before adding notification volume: denominators for eligible, opted-out, unavailable-device, attempted and accepted/delivered users; click/action rates; unsubscribe/complaint rates; and reminder lateness. Set actionable thresholds based on observed data, not invented targets.

## Technical Details

Files: core email models/service, users account-mail paths, blog newsletter/digest, package forum digest, host forum tasks, garden reminders, push registration/router and web notification click handlers. Reference `backend/docs/patterns/domain/celery.md` and `backend/docs/patterns/security/secret-management.md`.

Existing work remains separate: 547 owns the physical-device due-care verification; 602 owns browser registration/security; 605/606 own their specific delivery fixes. Archived 335/286 establish historical worker/FCM work, not current production health. Provider integration must use documented signature verification and avoid raw addresses, tokens, message bodies or credentials in telemetry.

## Acceptance Criteria

- [x] All live email/push send paths contribute consistent attempted/accepted/failed/suppressed outcomes; tests distinguish provider acceptance from delivered/displayed and from user engagement.
- [ ] Provider feedback authentication, malformed-event refusal, duplicate/replayed/out-of-order events and message correlation are tested. Bounce/complaint suppression prevents inappropriate future sends under a recorded policy without bypassing account-security controls. → todo 625 (re-pointed 2026-10-12)
- [ ] Click/action attribution is implemented with recorded consent/privacy, retention and deletion rules; tests cover attribution windows and no duplicate counting. Any decision not to collect opens is explicit, and the unused track_opens promise is removed or corrected. → todo 625 (re-pointed 2026-10-12)
- [x] Tests or controlled fault injection demonstrate alerts for broker failure, aged queues, exhausted retries, missing push configuration and missed worker/beat activity without secrets or raw PII in logs.
- [ ] Owner-approved production checks record dates and observed results for sender-domain authentication, deployed provider settings, worker/beat and push readiness; unknowns stay explicitly open, not marked verified from repository defaults. → todo 625 (re-pointed 2026-10-12)
- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated. → todo 625 (re-pointed 2026-10-12)
- [x] Operational recovery steps and the single-scheduler/scaling constraint are documented in the existing deployment/pattern docs; relevant backend/consumer tests pass. Unavailable external checks remain open or are explicitly re-pointed before archive.

## Work Log

### 2026-10-12 - Created from effectiveness audit

- Grouped delivery feedback, engagement measurement, alerting and production evidence gaps. No active todo covering this end-to-end scope was found in the backlog comparison.
- No provider/DNS configuration or production user data was accessed or changed during filing. Production checks and any live messages require explicit approval.

### 2026-10-12 - Triage split (run 2026-10-12-1616)

- Owner decision at triage: repo-only slice here (outcome vocabulary, track_opens, alert counters, docs); provider feedback (AC2), attribution (AC3), prod checks (AC5) and baseline (AC6) re-pointed to [todo 625](625-pending-p3-notification-provider-feedback-and-prod-baseline.md). Provider unknown.

### 2026-10-13 - Implemented by the todo sweep (run 2026-10-12-1739)

- Shared outcome vocabulary in `backend/apps/core/notification_ops.py` (queued, attempted, accepted, retrying, failed, suppressed; delivered/bounced/complained from the provider webhook only), read from each path's own record: the 619 outbox rows, `EmailOutcome`, `EmailNotification`, the weekly runs' summary lines and a per-owner tally in the care sweep. No second ledger. `manage.py delivery_outcomes` counts outbox rows; weekly runs and care sweeps log one `[OUTCOME]` line. `track_opens` was already removed by todo 625.
- Sentry alerts (owner decision 2026-10-12): `backend/plant_community_backend/sentry_config.py` enables `CeleryIntegration(monitor_beat_tasks=True)`, so every beat entry is a Cron Monitor (missed run, timeout). ERROR logs, which Sentry records as events: broker refusals give the exception class only (`log_broker_failure`, in forum dispatch and account mail), expired/interrupted outbox rows, an outbox overdue past `DELIVERY_QUEUE_LAG_ALERT_SECONDS`, and FCM/VAPID unconfigured when there is work to drop (at most hourly).
- Docs: outcomes, alerts and the one-scheduler rule in `backend/docs/patterns/domain/celery.md`; alerts, recovery steps and the single-scheduler constraint in `backend/docs/deployment/railway.md`; the Sentry alert-rule setup added to "Still open" in `docs/operations/notification-baseline.md`.
- Tests: `backend/apps/core/tests/test_notification_ops.py`. They include a real Sentry client on a capturing transport, which checks that the beat check-ins and the ERROR events arrive with no broker password or address in them.

### 2026-10-13 - Verified by the todo sweep (run 2026-10-12-1739)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/core/tests/test_notification_ops.py::TestOutboxOutcomes apps/core/tests/test_notification_ops.py::TestEmailServiceOutcomes apps/core/tests/test_notification_ops.py::TestOutcomeLines apps/core/tests/test_notification_ops.py::TestCareReminderOutcomes apps/core/tests/test_email_feedback.py::test_opens_are_not_collected --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/623-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 14 passed, 3 warnings in 19.16s ========================
  ```

- AC 4: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/core/tests/test_notification_ops.py::TestBrokerFailure apps/core/tests/test_notification_ops.py::TestOutboxAlerts apps/core/tests/test_notification_ops.py::TestPushConfigAlerts apps/core/tests/test_notification_ops.py::test_settings_enable_beat_monitors apps/core/tests/test_notification_ops.py::test_every_beat_entry_gets_a_cron_monitor apps/core/tests/test_notification_ops.py::test_a_beat_run_checks_in_and_a_failed_one_reports_an_error apps/core/tests/test_notification_ops.py::test_an_alert_reaches_sentry_without_secrets --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/623-ac3.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 17 passed, 2 warnings in 19.66s ========================
  ```

- AC 7: `bash -c "grep -n -e 'One scheduler' -e 'Cron Monitors' -e 'Recovery, in order' -e 'Single scheduler' -e 'Alerts (todo 623)' backend/docs/patterns/domain/celery.md backend/docs/deployment/railway.md && cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest backend/apps/core backend/apps/forum_host backend/apps/garden_calendar backend/apps/users backend/apps/blog --create-db -p no:cacheprovider -q"` — evidence `.sweep-evidence/g1/623-ac6.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  =========== 3986 passed, 8 skipped, 7 warnings in 314.19s (0:05:14) ============
  ```

### 2026-10-13 - Completed by the todo sweep (run 2026-10-12-1739)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-13 - Review round 1: non-blocking findings (PR #1134)

Each guard fix was mutation-checked: the guard was broken, the test seen failing, and the file restored from a backup copy (14 mutants, all killed). Tests are in `apps/core/tests/test_notification_ops.py`.

- fixed: `report_push_unconfigured` paged on any forum event with recipients. It now takes a `has_work` probe, so forum mobile push alerts only when a recipient has a device token, and browser push only when one has an active `PushSubscription` (`test_no_subscription_or_device_means_no_push_alert`). The existing alert tests now give their recipients a device or subscription. `web_push_enabled()` reflects only missing VAPID keys (there is no separate flag), and a deployment with no subscribers no longer pages.
- fixed: the care-reminder `[OUTCOME]` line was skipped on the crash path, and the credentials stop left owners out. The tally is now logged in a `finally`, crash-released owners are `retrying`, and untried tokenless owners whose claim stands are `suppressed` (`test_a_crashed_sweep_still_reports_its_outcomes`, `test_a_credentials_stop_reports_every_owner`).
- fixed: under `IGNORE_EXCEPTIONS`, a `cache.add` that returned None silently skipped the alert; None or an exception now falls back to a per-process `time.monotonic()` throttle, so the alert goes out at most once per window per process (`test_a_cache_outage_still_alerts_but_at_most_once_per_process`).
- fixed: a failing `check_outbox_lag` could abort `reconcile` before the re-drive; it is guarded and logs an ERROR (`test_a_failing_lag_check_never_stops_the_redrive`).
- fixed: the care-reminder probe in the Firebase-unconfigured branch could fail the sweep. It runs through the guarded `has_work` probe, where a failed probe means no alert (`test_a_failing_work_probe_is_no_alert_and_no_crash`). It is also narrowed to reminders an opted-in, active owner with a device could have received (`test_care_reminders_nobody_could_receive_do_not_alert`).
- fixed: a held row after a transient failure was counted as `retrying`; `outcome_of_intent` and `outbox_outcome_counts` treat a hold as `queued` (`test_a_hold_after_a_transient_failure_is_queued`).
- fixed: the weekly `[OUTCOME]` line was logged before the recovery decision; it is now logged after, and is `retrying` only when the recovery run was enqueued (`test_a_recovery_run_that_cannot_be_enqueued_reports_failed`).
- fixed: the vacuous `assert healthy.pk`; the test now deletes the late row and asserts the in-grace row is not overdue. The beat test also accepts an interval monitor of a minute or more, as documented.
- declined (documented): the SoftTimeLimit partial summary. A stopped weekly run writes no summary, so its sends are in no `[OUTCOME]` line; the continuation reports only its own. Writing the summary on the way out would change both commands' control flow for a count. The limit is stated in the `notification_ops` docstring.
- declined: throttling the lag and expired/interrupted ERRORs. Each is one message template, which Sentry groups into one issue, so a persistent backlog adds events to that issue rather than opening new ones, and alert rules fire on the issue. A cache throttle would also hide whether the backlog is still there.

### 2026-10-13 - Review round 2: non-blocking findings (PR #1134)

As in round 1, each guard fix was mutation-checked (11 mutants, all killed). Tests are in `apps/core/tests/test_notification_ops.py`.

- fixed: frame locals reached Sentry from the alert events. With `attach_stacktrace` and local variables on, the events would have carried a dispatch `payload`, a `token` kwarg, or a bound broker exception. The alert paths no longer bind the exception: `except Exception:` plus `sys.exc_info()` for the type, and `email_verification` now goes through `log_broker_failure`. A narrow `before_send` in `sentry_config.py` drops frame `vars` only from alert events: the `apps.core.notification_ops`/`apps.core.delivery` loggers, `[PUSH]`/`[DELIVERY]`/`[OUTCOME]` messages and `(broker: %s)` lines. The project-wide Sentry options are unchanged, and the `notification_ops` docstring now says this. Test: `test_alert_events_carry_no_frame_variables`, run under production-like options; a control ERROR keeps its locals, so the test is not hollow.
- fixed: `test_settings_enable_beat_monitors` was hollow. It now reads the gated `sentry_sdk.init` call in `settings.py`, the same way `test_sentry_options_drift.py` does, and asserts that `integrations=_sentry_integrations()` and `before_send=_sentry_before_send` come from `sentry_config`. Breaking either kwarg fails it. I did not reload settings with a DSN, because the drift guard requires exactly one explicit `sentry_sdk.init` call in `settings.py`.
- fixed: `_pushable_due` sampled task rows rather than owners. The device test is now in the database (an EXISTS on `PushDevice` or a non-blank legacy `fcm_token`), so no cap is needed; `CARE_REMINDER_ALERT_PROBE_OWNERS` is removed (`test_a_due_reminder_alerts_past_any_number_of_deviceless_owners`).
- fixed: a soft time limit after one device accepted left the owner out of the tally; that owner is now `accepted` before the re-raise (`test_a_soft_limit_after_one_device_counts_that_owner_accepted`).
- fixed: crash-released owners were marked `retrying` before `_release`; they are marked only after it succeeds, and `failed` when it fails, since their claims stand (`test_a_release_that_fails_reports_failed_not_retrying`).
- fixed: `report_push_unconfigured` ran the probe before the throttle; `_throttled` now peeks at the cache (or the local clock) first (`test_a_throttled_alert_skips_the_work_probe`).
- declined (raised again): throttling the lag ERROR. Every pass logs the same message template, which Sentry groups into one issue; alert rules fire on the issue, so a long backlog adds events to that issue rather than opening new alerts. Each event also carries the current count and the oldest age, which a cache throttle would hide.
- declined: also logging a scrubbed broker message. Kombu/redis errors put the host or URL in free text, and no scrubber can be shown safe for every broker error shape. The class name plus the stalled outbox rows (which reconciliation re-sends) are enough to triage.

## Notes

P3 observability and operational assurance, not a claim of a live delivery outage. Coordinate implementation sequencing with todo 619 after those new todos are committed; dependencies are intentionally empty under todos/README.md's rule against uncommitted dependency IDs. Do not add tracking pixels or third-party analytics without the recorded privacy/product decision.
