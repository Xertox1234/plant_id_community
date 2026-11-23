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
- **Other products' mail.** The Resend account also sends for other products
  (ocrecipes.com, lumatuner.com) and its webhooks are account-wide. An event is
  acted on only when its `data.from` is on `DEFAULT_FROM_EMAIL`'s domain or a
  subdomain of it; anything else answers 200 `ignored` and is **not recorded**,
  so another product's complaint never suppresses an address here. A handled
  event with no `from` is ignored too (fail closed). Account-level events with
  no sender (contact, domain) are recorded and ignored as before.
- **Out-of-order events.** Each event sets its own timestamp once (the earliest
  wins) and the status only moves up `sent < delivered < bounced < complained`, so
  the result does not depend on arrival order.
- **Correlation.** Each email sent through `EmailService.send_email` carries a
  Message-ID this app sets, `<hpmd.{uuid}@{sender domain}>`, stored on its
  `EmailNotification`. Resend reports it as `data.message_id`; Resend's own
  `data.email_id` is stored from the first match, so later events carrying only that
  id still match. Mail sent outside `EmailService.send_email` (the digests, the
  newsletter, lockout and other account mail) has no `EmailNotification` row; for
  that mail, only address-level suppression applies. **Not working in
  production:** the 2026-11-21 read found no event linked to its row (see
  "Delivery outcomes (2026-11-21)"; todo 726 stores what Resend sends back,
  and the fix follows the prod read in todo 733).
- **Stored data.** Event type, times, Resend's email id, the event's
  `data.message_id` as reported (since todo 726, on every recorded event,
  `email.sent` included; `redacted:recipient` in its place when it quotes a
  recipient address verbatim) and the bounce
  type and subtype. Never an address, a subject or the bounce message text, which
  can quote the address.

Events acted on: `email.delivered`, `email.bounced`, `email.complained`,
`email.suppressed`. Every other event is recorded and ignored.

## Suppression policy

| Provider says | Effect |
| --- | --- |
| `email.bounced` with `bounce.type = Permanent` | The address gets **no mail** at all |
| `email.suppressed` (on Resend's own suppression list) | Same as a permanent bounce |
| `email.complained` (marked as spam) | The address gets **no optional mail**. Account mail still goes |
| `email.bounced`, Transient or Undetermined | Recorded on the email. Nothing is suppressed |

- **Optional mail** means forum notification emails, the forum digest and the blog
  newsletter. **Account mail** means verification, password reset and sign-in
  notices, account lockout and newsletter confirmation.
- A suppression is keyed by an HMAC-SHA256 (server secret) of the normalized address, `+tag` dropped, so it outlives the
  account without keeping the address. That hash is a pseudonym, not anonymity:
  anyone who holds a list of addresses can hash it and test it against the table. It
  is deliberately not keyed (an HMAC on `SECRET_KEY`), because rotating that key would
  silently lift every suppression. A later event can only strengthen it
  (complaint to hard bounce), never weaken it. A suppression does not expire.
  An account that changes its address is not affected.
- **Lifting a suppression.** Do this when a member reports that mail stopped and
  the address works again (the mailbox was full, a typo has been fixed at the
  provider). In Django admin (`/admin/`, not the Wagtail `/cms/`), open **Core ›
  Email suppressions**. Search for the full address: the search box hashes what you
  type, because rows hold only the hash. Then delete the row. The next send goes out.
  If the address really is dead, Resend reports a fresh permanent bounce and the row
  comes back. Rows cannot be added or edited by hand.
- **Where it applies.** `EmailService.send_email` and `send_transactional_email`
  check before sending and report `EmailOutcome.SUPPRESSED`, a terminal outcome the
  forum outbox does not retry and records as `address_suppressed`, not
  `preference_off`. The account-mail tasks (`apps/users/tasks.py`) mark
  their outbox row `suppressed` / `address_suppressed` and do not retry. The SMTP
  backend (`ConfiguredSMTPBackend`) also removes suppressed recipients from every
  message, which covers the paths that never ask. That backstop treats a message
  as optional mail when it carries `List-Unsubscribe` or the explicit
  `X-Optional-Mail` marker. The forum digest and the blog newsletter set that marker
  themselves, so a digest whose unsubscribe hook failed is still optional. Where the
  backstop drops every recipient, `send()` returns 0, and every send path reports
  that as suppressed, not as sent:
  - `send_email` and `send_transactional_email` report `SUPPRESSED` /
    `address_suppressed`.
  - The lockout task marks its row `address_suppressed`.
  - The newsletter confirmation gives its stamp back and records
    `address_suppressed`.
  - The forum digest and the newsletter keep no claim, so the member stays due. They
    count the member as `suppressed=N` in the run summary, not as `failed=N`, so the
    weekly recovery run (which reads only `failed=`) is not triggered.
- **Fails open.** If the suppression lookup hits a database error, the message is
  sent: Resend still drops a suppressed address, and account mail is not lost during
  an outage.
- **Account-security controls are unchanged; their mail is not.** Suppression only
  stops the send. The verification allowance is still charged, the address stays
  unverified, a lockout is still enforced, tokens are still issued, and every
  anti-enumeration response is the same. A suppressed send is never recorded as
  sent. But a **hard bounce blocks password reset, verification, sign-in notices and
  lockout mail to that address** until staff lift the suppression (above). A member
  whose address hard-bounced cannot recover the account by email alone. A complaint
  never blocks account mail.

## Sender identity and stopping all optional email

Todo 703 (CASL s. 6(2) with SOR/2012-36 s. 2(1)(d); CAN-SPAM 15 U.S.C.
7704(a)(5)(A)(iii)).

- **Sender footer.** Every email prints `EMAIL_SENDER_NAME` and
  `EMAIL_SENDER_ADDRESS` (the operator's name and postal address) in its footer:
  `emails/base.html` outside its `footer` block, each `.txt` template, the forum
  digest through the package's `wagtail_forum/email/_footer.*` slot, and allauth's
  text mail through the host's `account/email/base_message.txt`. Both are blank
  until launch (todo 724), and a blank value prints nothing.
  `apps/core/tests/test_email_template_sender_footer.py` renders every email
  template and fails when either is missing.
- **Stop all optional email.** Any signed unsubscribe link's page offers "Stop all
  optional email" (`POST /api/v1/auth/unsubscribe/all/`): it turns the account's
  `email_notifications` master switch off and unsubscribes a blog newsletter row
  for the account's address. Account mail still goes. Settings turns the switch
  back on. The welcome email links to the same action (the `all_optional` list).

## Click attribution and opens

Owner decision, 2026-10-12: first-party signed click redirects only. No open
tracking, no pixel, no third-party analytics. 90-day retention, deleted with the
account.

- **Opens are not collected.** The unused `track_opens` parameter, the
  `opened_at`/`open_count` fields, the `opened` status and `mark_opened` were removed
  (migration `core.0009`). The unused `clicked_at`/`click_count`/`mark_clicked`
  moved to `EmailClick`. The model has dropped the four fields, but `core.0009` keeps
  their columns, with a database default of 0 on the two counters, so a worker still
  running the previous release can insert during the rollout. A follow-up migration
  drops the columns. Any row that was left `opened` or `clicked` goes back to
  `sent`.
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

## Initial baseline (2026-11-03)

Todo 638. Window **2026-10-04T19:57Z → 2026-11-03T19:57Z (30 days)**, read on
production with the owner's approval. The read was aggregate-only (counts, no
addresses or bodies), run by the owner over `railway ssh … manage.py shell`.
Production is tiny (13 active accounts), so these are a starting point, not rates
to set thresholds on.

**Controlled sends (evidence reused):**

- Email: all 10 families sent from prod with `send_inbox_samples` to the owner's
  own inbox at 2026-10-27 23:27 UTC; all 10 arrived (Gmail, Outlook for iOS;
  todo 626). Arrival time was not recorded.
- Push: forum-reply push foreground/background on iPhone (TestFlight build 16)
  and a Samsung SM-A376B (Android 16, release build), and a care-task push on
  both, all received on 2026-11-02 (todos 547, 648, 387). The Android background
  case first showed nothing because the notification permission was never asked
  for (todo 685).

**Configuration at read time:** `RESEND_WEBHOOK_SECRET` **unset**, `API_PUBLIC_URL`
set, `EMAIL_CLICK_TRACKING_ENABLED` at its default (on).

| Measure | Value |
|---|---|
| Active accounts (denominator) | 13 |
| Opted out of email / forum / care-reminder notifications | 0 / 0 / 0 (all 13 on) |
| Accounts with a push device | 2 (4 devices: 3 iOS, 1 Android) |
| Forum emails sent (`EmailNotification`) | 9 (8 reply, 1 mention); all carry our Message-ID, none a provider id |
| Delivered / bounced / complained | **not collected**: no provider events (webhook unset) |
| Suppressed addresses | 0 |
| Email link clicks | 0 of 9 emails |
| Delivery queue, rows kept 14 days (`DELIVERY_RETENTION_DAYS`) | forum email 7 sent; mobile push 6 sent, 1 suppressed (`no_destination`); web push 7 suppressed (`no_destination`) |
| Care tasks due in window | 5, of which 4 marked sent |

What the numbers can't show:

- **Delivery latency.** `EmailNotification` is written at send time, so
  created→sent reads as 0 and measures nothing. Send→delivered needs the
  webhook's `delivered_at`. Both were re-pointed to todo 692. The Resend-side
  figure (`email.sent` → `email.delivered`) is now recorded below under
  "Delivery outcomes (2026-11-21)". `delivered_at − sent_at` on
  `EmailNotification` still cannot be computed, because no provider event links
  to its row, so `delivered_at` is never set: [todo 733](../../todos/733-pending-p3-observe-resend-event-linkage-in-prod.md).
- **Reminder lateness.** A care task stores only `notification_sent`, not when
  it was sent. The beat sweep runs every 15 minutes, which bounds the lateness;
  nothing records it.
- **Unsubscribe and complaint rates.** 0 opt-outs and 0 complaints out of 13
  accounts says nothing yet; complaints are not collected anyway without the
  webhook.
- **Clicks.** 0 of 9 is a real zero only if a click reaches our redirect.
  Whether Resend's own click tracking is on (item 2 below) was not checked; if
  it is, it wraps our tracked link rather than replacing it, so a click should
  still be counted. Not observed either way.
- **Web push.** No member has a browser push subscription, so every forum
  web-push intent is suppressed `no_destination`. That is expected, not a fault.

## Delivery outcomes (2026-11-21)

Todo 692. Window **2026-11-03T20:52:57Z → 2026-11-22T01:57Z (about 18 days)**,
from the moment the webhook was connected. Read on production with the owner's
approval (2026-11-20): read-only and counts-only, over `railway ssh … manage.py
shell`, run by Claude in the remote session. No addresses, subjects or ids were
printed.

**Configuration at read time:** `RESEND_WEBHOOK_SECRET` set on
`plant_id_community` since 2026-11-03 20:52:57 UTC and declared `preserve()` in
`.railway/railway.ts` (PR #1259); the Resend webhook sends All Events (the
dashboard's event picker would not narrow). Resend's own open and click
tracking was never set up for `houseplant-md.com` (no tracking subdomain).

| Measure | Value |
|---|---|
| `EmailProviderEvent` rows (signed, recorded) | 9, over 4 emails |
| By type | 4 `email.sent`, 3 `email.delivered`, 1 `email.bounced` (Permanent), 1 `suppression.added` |
| Delivered / bounced / complained (emails) | 3 / 1 (Permanent) / 0 |
| Suppressed addresses | 1 |
| Events carrying Resend's email id | 8 of 9 |
| Forum emails sent (`EmailNotification`) | 1 (forum_reply, 2026-11-04), with our Message-ID, no provider email id |
| Events linked to an `EmailNotification` | **0**. Only handled types (`email.delivered`, `email.bounced`, `email.complained`, `email.suppressed`) are ever matched; `email.sent` and `suppression.added` are ignored by design. Of the 4 handled events, only the forum email's `email.delivered` had a row to link to: **n = 1** |
| Sent→delivered latency, Resend side (`email.sent` → `email.delivered`, paired by Resend's email id) | 0.8 s, 0.9 s, 1.1 s: n = 3, p50 0.9 s, p90 ≈ 1.1 s |
| `delivered_at − sent_at` on `EmailNotification` | **not computable**: no row is linked, so `delivered_at` is never set |

What the numbers can't show:

- **Linkage.** The forum email's `email.delivered` event arrived within 10
  minutes of its send, yet did not link to its row (its `email.sent` event is
  never matched by design, and the other 3 emails have no `EmailNotification`
  row). The evidence is that one event: n = 1.
  Hypothesis, not verified (the event's `data.message_id` was not stored at read
  time, so what Resend sent back is unknown; it is stored from todo 726 on,
  `EmailProviderEvent.message_id`): Resend over SMTP does not echo our client-set
  Message-ID. Until that is fixed, outcomes are recorded per event and
  address-level suppression works, but no `EmailNotification` gets a
  delivered, bounced or complained status. The fix follows the prod read in
  [todo 733](../../todos/733-pending-p3-observe-resend-event-linkage-in-prod.md).
- **Rates.** Four emails is far too few for a bounce or complaint rate; these
  are counts, not rates to set thresholds on.
- **`suppression.added`.** Prod recorded one, but the code acts only on
  `email.suppressed`, so this event is stored and ignored. The 1 suppressed
  address came from the Permanent bounce. Whether Resend ever sends
  `email.suppressed` is checked in todo 733.
- **Latency.** n = 3 and Resend-side only: it measures Resend accepting the
  message to the receiving server accepting it, not our send call to delivery.

## Still open

These need the owner. None of them can be settled from the repository.

1. Done 2026-11-03 (todo 692): the Resend webhook is connected and
   `RESEND_WEBHOOK_SECRET` is set on Railway and declared in `.railway/railway.ts`
   (PR #1259). Signed events are recorded (see "Delivery outcomes (2026-11-21)").
2. Done 2026-11-03 (todo 692): Resend's own open and click tracking was never set
   up for `houseplant-md.com` (no tracking subdomain), so there is nothing to
   turn off.
3. **Events do not link to their email.** The 2026-11-21 read found the one
   eligible event (the forum email's `email.delivered`, n = 1) not linked to its
   `EmailNotification` (hypothesis, not verified:
   Resend over SMTP does not echo our client-set Message-ID). Address-level
   suppression works either way. Per-email outcomes and `delivered_at − sent_at`
   wait on [todo 733](../../todos/733-pending-p3-observe-resend-event-linkage-in-prod.md).
4. The initial baseline (todo 638) and the delivery outcomes (todo 692) are
   recorded above.
5. **Sentry alert rules** (todo 623). The code sends Cron Monitor check-ins for
   every beat entry and ERROR events for broker, retry-exhaustion, outbox-lag
   and missing-push-config failures (`backend/docs/patterns/domain/celery.md`,
   "Outcomes and alerts"). Who is notified is configured in Sentry: add an
   alert rule on monitor failures and on new error events. `SENTRY_DSN` must be
   set on Railway for any of it to report.
6. Pre-existing and unchanged: `EmailNotification.user` is `SET_NULL`, so a
   delivery-ledger row keeps `recipient_email` after its account is deleted.
   Click attribution rows do cascade.
