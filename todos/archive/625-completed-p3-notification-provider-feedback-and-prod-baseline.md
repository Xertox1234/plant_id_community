---
status: completed
priority: p3
issue_id: "625"
tags: [backend, notifications, email, observability, operations, privacy]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Owner: approved looking up the provider and read-only prod checks (2026-10-12); provider is Resend over SMTP (smtp.resend.com:587 TLS, from houseplant-md.com), so build Resend webhook (Svix-signed) feedback ingestion and suppression. Owner: attribution = first-party signed click redirects only, no opens, no pixel/third-party analytics, 90-day retention, deleted with the account; remove the track_opens promise (2026-10-12). Owner: AC4 baseline re-pointed to todo 638 (2026-10-12). Test sends NOT approved"
---

# Ingest provider delivery feedback, attribute engagement and record a production baseline

## Problem

Split from todo 623 at triage (run 2026-10-12-1616, owner decision 2026-10-12): 623 ships the repo-only slice (outcome vocabulary, track_opens, alert counters, docs). This todo owns the provider-dependent and production-dependent work from 623's AC2, AC3, AC5 and AC6. The deployed email provider is unknown (owner, 2026-10-12).

## Findings

- No bounce/complaint/webhook ingestion exists; `mark_opened`/`mark_clicked` in `backend/apps/core/models.py` have no callers.
- Sender-domain authentication (SPF/DKIM/DMARC), provider settings, worker/beat health and a delivery baseline have never been recorded from production.

## Recommended Action

1. Owner identifies the deployed email provider and its feedback mechanism; then build authenticated, replay-safe, idempotent feedback ingestion and a suppression policy on 623's outcome vocabulary.
2. Decide consent/privacy/retention for click/action attribution; implement it or record a dated decision not to.
3. With owner approval, record production checks and an initial aggregate baseline.

## Acceptance Criteria

- [x] Provider feedback authentication, malformed-event refusal, duplicate/replayed/out-of-order events and message correlation are tested. Bounce/complaint suppression prevents inappropriate future sends under a recorded policy without bypassing account-security controls.
- [x] Click/action attribution is implemented with recorded consent/privacy, retention and deletion rules; tests cover attribution windows and no duplicate counting. Any decision not to collect opens is explicit, and the unused track_opens promise is removed or corrected.
- [x] Owner-approved production checks record dates and observed results for sender-domain authentication, deployed provider settings, worker/beat and push readiness; unknowns stay explicitly open, not marked verified from repository defaults.
- [ ] Controlled test-inbox/device delivery evidence and an initial aggregate baseline are recorded, with observation window, denominators, delivery latency and click/action/unsubscribe outcomes; existing evidence from 547 may be reused with its build/date stated. → todo 638 (re-pointed 2026-10-12)

## Work Log

### 2026-10-12 - Split from 623 at triage

- Criteria 623 AC2, AC3, AC5 and AC6 re-pointed here by owner decision; wording carried over unchanged. 623's slice may already remove track_opens; if so, AC2 here is satisfied for that clause by citing it.

### 2026-10-12 - Triage and owner-approved read-only prod checks (run 2026-10-12-1748)

- Owner approved identifying the provider and read-only production checks; test sends were not approved. AC4 (baseline) re-pointed to [todo 638](638-pending-p3-notification-delivery-baseline.md).
- Observed 2026-10-12T17:50Z. Provider: Resend over SMTP. Railway `production` has `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, and `DEFAULT_FROM_EMAIL` at `houseplant-md.com`. Only variable names and non-secret values were read.
- DNS, via 1.1.1.1: `_dmarc.houseplant-md.com` = `v=DMARC1; p=none; rua=mailto:…@dmarc-reports.cloudflare.net`. `resend._domainkey.houseplant-md.com` has a published DKIM key (`p=MIGfMA0…`). `send.houseplant-md.com` TXT = `v=spf1 include:amazonses.com ~all` and its MX = `10 feedback-smtp.us-east-1.amazonses.com`. The root `houseplant-md.com` has no SPF TXT and no MX. DMARC is monitor-only (`p=none`), which is an open hardening item, not verified enforcement.
- Worker/beat: Railway logs show `[start] worker pid 5 (celery … worker -B --schedule=/tmp/celerybeat-schedule --concurrency=2 …)`, `beat: Starting...` and `celery@8571ef8ca71b ready.` at 2026-10-12 17:27:57, then `Scheduler: Sending due task care-task-reminders` at 17:30:00 and 17:45:00. The embedded beat is on schedule.
- Push readiness: `FIREBASE_CREDENTIALS_B64`, `FIREBASE_PROJECT_ID`, `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` are set. Names only; that the values are valid is not proven by presence.

### 2026-10-13 - Implemented by the todo sweep (run 2026-10-12-1748)

- Resend webhook `POST /api/v1/email/webhooks/resend/` (`backend/apps/core/api/email_feedback.py`, `backend/apps/core/email_feedback.py`): Svix signature verified by hand on the raw body (no new dependency), a 5-minute timestamp window, a unique `svix-id` per `EmailProviderEvent` so duplicates apply once, order-independent status updates, and correlation by a Message-ID this app sets (`<hpmd.{uuid}@domain>`) and then Resend's `email_id`. `RESEND_WEBHOOK_SECRET` unset = 503.
- Suppression (`EmailSuppression`, keyed by an address hash): a permanent bounce or `email.suppressed` stops all mail, a complaint stops optional mail only. It is enforced in `EmailService`, in the account-mail tasks (terminal `address_suppressed`, no retry) and as a backstop in `ConfiguredSMTPBackend`. Allowance, lockout and responses are unchanged.
- Click attribution (owner decision 2026-10-12): forum email content links go through a signed first-party redirect `GET /api/v1/email/click/<token>/` (site-origin targets only). A click counts within 7 days of the send, once per email and link. `EmailClick` cascades with the account and is pruned after 90 days with provider events (`prune_email_feedback` beat task). `track_opens`, the open fields and state, and `mark_opened`/`mark_clicked` are removed (migration `core.0009`).
- Policy, production checks and owner follow-ups are recorded in `docs/operations/notification-baseline.md`. Still open for the owner: create the Resend webhook, set `RESEND_WEBHOOK_SECRET` on Railway, turn off Resend's own open and click tracking. Message-ID round-trip over SMTP has not been observed yet (todo 638).

### 2026-10-13 - Verified by the todo sweep (run 2026-10-12-1748)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/core/tests/test_email_feedback.py::TestWebhookAuthentication apps/core/tests/test_email_feedback.py::TestEventsAndCorrelation apps/core/tests/test_email_feedback.py::TestSuppressionPolicy apps/core/tests/test_email_feedback.py::TestBackendBackstop apps/core/tests/test_email_feedback.py::TestAccountSecurityUnchanged --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/625-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 38 passed, 3 warnings in 19.35s ========================
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/core/tests/test_email_feedback.py::TestClickLinks apps/core/tests/test_email_feedback.py::TestClickRedirect apps/core/tests/test_email_feedback.py::TestRetentionAndDeletion apps/core/tests/test_email_feedback.py::test_opens_are_not_collected --create-db -p no:cacheprovider -v` — evidence `.sweep-evidence/g1/625-ac1.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ======================= 18 passed, 3 warnings in 19.01s ========================
  ```

### 2026-10-13 - Confirmed by the owner, ticked by the todo sweep (run 2026-10-12-1748)

- AC 3: confirmed by the owner on 2026-10-12: "Owner approved the read-only production checks ('You may look it up + check', 2026-10-12); results observed 2026-10-12T17:50Z are recorded in the Work Log: Resend SMTP provider, DKIM present, DMARC p=none (monitor-only, open), send-subdomain SPF, worker+embedded beat running on schedule, FCM/VAPID vars present" (`state.py confirm`; no command or evidence)

### 2026-10-13 - Completed by the todo sweep (run 2026-10-12-1748)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-13 - Review round 1: non-blocking findings (PR #1133)

Each guard fix was mutation-checked: the guard was broken, the test seen failing, and the file restored from a backup copy (13 mutants, all killed).

- fixed: a `DatabaseError` in `record_click` turned the click redirect into a 500; the count is best-effort, the type is logged, and the 302 always goes out (`test_a_database_error_while_counting_a_click_still_redirects`).
- fixed: Message-ID correlation needed a byte-exact match; `normalize_message_id` strips whitespace and angle brackets and lowercases, the stored id is lowercased in its header form, and the lookup tries both forms (`test_a_message_id_is_matched_in_any_spelling`, `test_the_stored_message_id_is_lowercased`).
- fixed: `blocked_reasons` kept one spelling per address, so another spelling or case escaped the backstop; it returns `{hash: reason}`, and every caller looks up `address_hash(address)` (`test_every_spelling_of_a_suppressed_address_is_blocked`).
- fixed: the forum outbox recorded a provider suppression as `preference_off`; `EmailService.last_suppression_reason` names it, and the outbox records `address_suppressed` (`test_the_forum_outbox_records_a_provider_suppression_as_such`).
- fixed: `send_transactional_email` ignored the 0 that `send_mail` returns when the backstop drops the recipient; it now reports `SUPPRESSED`/`address_suppressed` and returns False (`test_a_transactional_send_the_backstop_drops_is_not_a_send`).
- fixed: the removed-recipient count could go negative on a blank address; it counts what `keep()` removed and logs only a positive count (`test_the_removed_count_ignores_blank_entries`).
- fixed: the 413 guard had no test, and a body with no Content-Length was read whole; the view reads at most `EMAIL_WEBHOOK_MAX_BODY_BYTES + 1` bytes (`test_an_oversized_content_length_is_refused`, `test_a_non_numeric_content_length_is_refused`, `test_a_body_with_no_length_is_read_only_up_to_the_cap`).
- fixed: dropping the NOT NULL open/click columns in the deploy that stops writing them would break previous-release workers. `core.0009` now removes the four fields from the model state only. The columns stay, the two counters get `db_default=0`, and `message_id` and `provider_email_id` get `db_default=""` so old-worker inserts succeed. A data step moves `opened`/`clicked` rows back to `sent` (`test_the_open_and_click_columns_stay_for_a_previous_release_worker`, `test_rows_left_opened_or_clicked_go_back_to_sent`). Dropping the columns needs a follow-up todo, to be filed once this has deployed.
- fixed: anonymous badly signed webhook requests logged at WARNING; they now log at INFO, so they cannot flood alerting (`test_a_refused_signature_is_logged_below_warning`).
- declined (doc narrowed): the forum digest and the blog newsletter and confirmation ignore `send()`'s 0. Returning False there would count a suppressed member as a failed send, and the weekly recovery runs re-try failures until their cap. So the fix touches the recovery semantics of three send paths and is not small. `docs/operations/notification-baseline.md` now confines "never recorded as sent" to the `send_email`, `send_transactional_email` and account-task paths, and says what the digests do.
- declined: HMAC instead of plain SHA-256 for `address_hash`. Keying it on `SECRET_KEY` would silently lift every suppression when that key rotates. The residual linkability (anyone holding an address list can test it) is now stated in the baseline doc.
- declined: GET-prefetch click noise. It is inherent to a redirect, and "Known noise" in the baseline doc already says to treat the click rate as an upper bound. HEAD never counts, and a scanner heuristic would need request details that the design deliberately does not store.

### 2026-10-13 - Review round 2: non-blocking findings (PR #1133)

Each guard fix was mutation-checked as in round 1 (15 mutants, all killed); new tests live in `apps/core/tests/test_email_suppression_paths.py` unless named otherwise.

- fixed: the forum digest, the newsletter and the newsletter confirmation recorded "sent" when the backstop dropped the mail (round 1 had declined this). Each now returns a distinct `SUPPRESSED` result.
  - The digests keep no claim, so the member stays due, and count `suppressed=N`. The weekly recovery parser reads only `failed=`, so suppressed members never trigger a recovery run.
  - The confirmation gives its stamp back and records `address_suppressed`.
  - Tests: `test_a_suppressed_digest_is_not_stamped_or_counted_as_failed`, `test_a_suppressed_newsletter_is_not_stamped_or_counted_as_failed`, `test_a_suppressed_confirmation_gives_its_stamp_back_and_is_not_retried`.
- fixed: in `send_email`, a 0 send count for a real address is `SUPPRESSED`/`address_suppressed`; a blank address stays `PERMANENT` (`test_send_email_reports_a_backstop_drop_as_an_address_suppression`).
- fixed: `_send_lockout_notification` ignored the 0 that `send_mail` returns; it reports `SUPPRESSED`, and the task marks the row `address_suppressed` (`test_a_lockout_notice_the_backstop_drops_is_recorded_suppressed`).
- fixed: `email_click` returned a 406 for `Accept: text/html`; a content negotiation that never refuses means every Accept header gets the 302 (`test_the_click_redirect_answers_any_accept_header`).
- fixed: there was no way to lift a suppression. `EmailSuppression` is in Django admin: the search box takes the address and looks up its hash, and rows can be viewed and deleted only (`test_staff_find_a_suppression_by_its_address_and_can_only_delete_it`). The lift procedure is in `docs/operations/notification-baseline.md`. Stated plainly there and here: a hard bounce DOES block password reset, verification, sign-in notices and lockout mail to that address until staff lift it. "Unchanged" covers the security controls (allowance, lockout, tokens, anti-enumeration responses), not the delivery of their mail.
- fixed: optional mail was classified only by List-Unsubscribe; the forum digest and the newsletter also set an explicit `X-Optional-Mail` marker, so a digest whose unsubscribe hook failed is still optional (`test_the_digest_and_newsletter_carry_the_optional_mail_marker`, and the digest test above with the hook off).
- fixed: the rollout test now does a raw previous-release INSERT that names the old columns and omits `message_id`/`provider_email_id`, and asserts both default to `''` (`test_a_previous_release_insert_gets_the_new_column_defaults`).
- fixed: `prune` deletes in batches of `EMAIL_FEEDBACK_PRUNE_BATCH` (`test_the_prune_deletes_in_batches`).
- fixed: the `_request.read` call now has a comment explaining why it is used and naming the body-limit tests as the canary for an upgrade.
- declined: HMAC for `address_hash`, again for the round-1 reason. Keying it on `SECRET_KEY` would silently lift every suppression on key rotation. The residual linkability is stated in the baseline doc, and rows are kept indefinitely on purpose, because a dead address stays dead after its account is deleted.
- declined: GET-prefetch click noise. "Known noise" in the baseline doc already says to treat the click rate as an upper bound. A scanner heuristic would need user agents or IPs, which the design deliberately does not store.
- declined: a concurrent index build. `core_emailnotification` is not on the hot-table list, and the two indexes are on columns added empty in the same migration, so the build covers only the table's existing rows. Its prod row count was not measured for this review: if that table turns out large, the drop-columns follow-up can build these two indexes concurrently in a non-atomic migration.
- follow-up: drop the four open/click columns that `core.0009` kept for the rollout, in a later migration once this has deployed.

## Notes

Production checks and live messages require explicit owner approval; never read production unasked. No tracking pixels or third-party analytics without a recorded privacy decision.
