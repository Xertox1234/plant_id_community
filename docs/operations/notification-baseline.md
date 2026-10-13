# Notification delivery: feedback, suppression, attribution and production baseline

Todo 625 (run 2026-10-12-1748). Code: `backend/apps/core/email_feedback.py`,
`backend/apps/core/api/email_feedback.py`, `backend/apps/core/mail_backends.py`.
Tests: `backend/apps/core/tests/test_email_feedback.py`.

## Provider

The deployed provider is **Resend over SMTP** (`smtp.resend.com:587`, TLS, sending
from `houseplant-md.com`), identified by the owner on 2026-10-12. Resend reports
delivery outcomes through a webhook signed with Svix.

## Feedback ingestion

`POST /api/v1/email/webhooks/resend/` takes Resend's events.

- **Authentication.** The Svix signature on the raw body is the only credential:
  HMAC-SHA256 over `{svix-id}.{svix-timestamp}.{body}` with the base64 secret after
  `whsec_`, compared in constant time, any one of the space-separated `v1,` entries.
  Implemented by hand, following the documented manual scheme, so no dependency was
  added. `RESEND_WEBHOOK_SECRET` unset means 503 and nothing is recorded; a malformed
  secret is also 503, never "accept".
- **Replay.** A timestamp more than five minutes from now is refused (401). Within
  that window, `EmailProviderEvent.svix_id` is unique: a second delivery of the same
  event answers 200 `duplicate` and changes nothing.
- **Malformed events.** Non-JSON, a non-object body, a missing `type`, `created_at`
  or `data`, a `data.to` that is not a list of strings, or a handled event with no
  recipient: 400. An overlong `svix-id` is 400. A body over 256 KB is 413.
- **Out-of-order events.** Each event sets its own timestamp once (the earliest
  wins) and the status only moves up `sent < delivered < bounced < complained`, so
  the result does not depend on arrival order.
- **Correlation.** Each email sent through `EmailService.send_email` carries a
  Message-ID this app sets, `<hpmd.{uuid}@{sender domain}>`, stored on its
  `EmailNotification`. Resend reports it as `data.message_id`; Resend's own
  `data.email_id` is stored from the first match, so later events carrying only that
  id still match. Mail sent outside `EmailService.send_email` (the digests, the
  newsletter, lockout and other account mail) has no `EmailNotification` row; for
  that mail, only address-level suppression applies.
- **Stored data.** Event type, times, Resend's email id and the bounce type and
  subtype. Never an address, a subject or the bounce message text, which can quote
  the address.

Events acted on: `email.delivered`, `email.bounced`, `email.complained`,
`email.suppressed`. Every other event is recorded and ignored.

## Suppression policy

| Provider says | Effect |
|---|---|
| `email.bounced` with `bounce.type = Permanent` | The address gets **no mail** at all |
| `email.suppressed` (on Resend's own suppression list) | Same as a permanent bounce |
| `email.complained` (marked as spam) | The address gets **no optional mail**. Account mail still goes |
| `email.bounced`, Transient or Undetermined | Recorded on the email. Nothing is suppressed |

- **Optional mail** means forum notification emails, the forum digest and the blog
  newsletter. **Account mail** means verification, password reset and sign-in
  notices, account lockout and newsletter confirmation.
- A suppression is keyed by a SHA-256 of the normalized address, so it outlives the
  account without keeping the address. A later event can only strengthen it
  (complaint to hard bounce), never weaken it. Staff lift one by deleting its
  `EmailSuppression` row. An account that changes its address is not affected.
- **Where it applies.** `EmailService.send_email` and `send_transactional_email`
  check before sending and report `EmailOutcome.SUPPRESSED`, a terminal outcome the
  forum outbox does not retry. The account-mail tasks (`apps/users/tasks.py`) mark
  their outbox row `suppressed` / `address_suppressed` and do not retry. The SMTP
  backend (`ConfiguredSMTPBackend`) also removes suppressed recipients from every
  message, which covers the paths that never ask. That backstop treats a message
  that carries `List-Unsubscribe` as optional mail, because that header is on exactly
  the optional families.
- **Fails open.** If the suppression lookup hits a database error, the message is
  sent: Resend still drops a suppressed address, and account mail is not lost during
  an outage.
- **Account-security controls are unchanged.** Suppression only stops the send.
  The verification allowance is still charged, the address stays unverified, a
  lockout is still enforced, tokens are still issued, and every anti-enumeration
  response is the same. A suppressed send is never recorded as sent.

## Click attribution and opens

Owner decision, 2026-10-12: first-party signed click redirects only. No open
tracking, no pixel, no third-party analytics. 90-day retention, deleted with the
account.

- **Opens are not collected.** The unused `track_opens` parameter, the
  `opened_at`/`open_count` fields, the `opened` status and `mark_opened` were removed
  (migration `core.0009`). The unused `clicked_at`/`click_count`/`mark_clicked`
  moved to `EmailClick`.
- **Links tracked.** Only the forum notification emails' content links
  (`post_url`, `topic_url`; `EMAIL_TRACKED_LINK_KEYS`), in both the HTML and text
  parts. Never an unsubscribe link, the List-Unsubscribe header, the settings link
  or any account-mail link.
- **The redirect.** `GET /api/v1/email/click/<token>/` on `API_PUBLIC_URL`. The
  token is signed with Django's `signing` and carries the email's uuid, the link name
  and the target. The target must be on `SITE_URL`'s origin, both when the token is
  signed and when it is followed, so the redirect is never an open redirect. A token
  that is not genuine redirects to the site home. Tracking is off when
  `API_PUBLIC_URL` is unset or `EMAIL_CLICK_TRACKING_ENABLED=False`.
- **Counting.** A click counts only within 7 days of the send
  (`EMAIL_CLICK_ATTRIBUTION_DAYS`) and only once per email and link (a unique
  constraint). A later click still redirects. HEAD requests never count.
- **What is stored.** The email, the account, the link name and the time. No IP
  address, user agent or URL.
- **Retention and deletion.** `EmailClick` and `EmailProviderEvent` rows are
  deleted after 90 days (`EMAIL_FEEDBACK_RETENTION_DAYS`) by the daily beat task
  `apps.core.tasks.prune_email_feedback`. `EmailClick.user` is `CASCADE`, so an
  account's clicks go with it.
- **Known noise.** Mail scanners that prefetch links with GET can register a
  click the reader never made. Treat the click rate as an upper bound.

## Production checks (owner-approved, read-only)

Observed **2026-10-12T17:50Z**, with the owner's approval ("You may look it up +
check"). Test sends were not approved.

- **Provider settings.** Railway `production` has
  `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`,
  `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=587`, `EMAIL_USE_TLS=True`, and
  `DEFAULT_FROM_EMAIL` at `houseplant-md.com`. Only variable names and non-secret
  values were read.
- **Sender-domain authentication** (DNS via 1.1.1.1). `resend._domainkey.houseplant-md.com`
  publishes a DKIM key. `send.houseplant-md.com` has the SPF record
  `v=spf1 include:amazonses.com ~all` and the MX `10 feedback-smtp.us-east-1.amazonses.com`.
  The root `houseplant-md.com` has no SPF TXT and no MX. `_dmarc.houseplant-md.com` is
  `v=DMARC1; p=none; rua=…@dmarc-reports.cloudflare.net`.
  **Open:** DMARC is monitor-only (`p=none`). That is not enforcement. Moving to
  `quarantine`/`reject` is an owner decision, once the reports are clean.
- **Worker and beat.** Railway logs show the co-located worker with embedded beat
  started (`worker -B --schedule=/tmp/celerybeat-schedule --concurrency=2`, `beat:
  Starting...`, `celery@… ready.` at 2026-10-12 17:27:57), then
  `Scheduler: Sending due task care-task-reminders` at 17:30:00 and 17:45:00. The
  beat is on schedule.
- **Push readiness.** `FIREBASE_CREDENTIALS_B64`, `FIREBASE_PROJECT_ID`,
  `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` are set. **Open:** only presence was
  checked. Whether the values are valid is not proven.

## Still open

These need the owner. None of them can be settled from the repository.

1. In the Resend dashboard, create a webhook for `email.delivered`, `email.bounced`,
   `email.complained` and `email.suppressed`, pointed at
   `https://api.houseplant-md.com/api/v1/email/webhooks/resend/`, and set its signing
   secret as `RESEND_WEBHOOK_SECRET` on Railway. Until then, no feedback is
   recorded.
2. **Turn off Resend's own open and click tracking** for `houseplant-md.com`. That
   is third-party tracking, which the owner ruled out, and only the dashboard can
   switch it off.
3. That Resend keeps a client-set Message-ID over SMTP is documented for its API
   but not yet observed for this sender. The first real event confirms it
   (`EmailProviderEvent.notification` set). Address-level suppression works
   either way.
4. The controlled delivery test and the initial aggregate baseline are
   [todo 638](../../todos/638-pending-p3-notification-delivery-baseline.md).
5. Pre-existing and unchanged: `EmailNotification.user` is `SET_NULL`, so a
   delivery-ledger row keeps `recipient_email` after its account is deleted.
   Click attribution rows do cascade.
