---
status: completed
priority: p2
issue_id: "409"
tags: [backend, web, blog, security, email]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
owner_decision: "Owner, 2026-10-09: full wire-up. Anyone may subscribe, with double opt-in. A weekly digest of new posts. Rows from the old endpoint need no handling (only the owner and test accounts exist). Supersedes 'keep blocked' (2026-09-28)."
---

# Blog newsletter: close the abuse surface, then wire it up

## Problem

Blog v1 `newsletter/` is `AllowAny` with no rate limit:

- Anyone can subscribe any email address, with no double opt-in.
- The "already subscribed" response versus a 201 lets anyone enumerate which
  addresses are subscribed.
- `POST newsletter/unsubscribe/ {"email": …}` unsubscribes any address, and its
  404 is a second enumeration oracle.
- No code ever sends a newsletter. `BlogNewsletter` has no sender.

The owner decided (todo 405) to **wire it up**, not remove it.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. **Security first:** add double opt-in (a confirmation email with a signed
   token), rate limits, and responses that are identical whether or not the
   email is subscribed. Unsubscribing should use a signed token, sharing todo
   408's design.
2. Add a signup UI on the web: a blog footer or sidebar.
3. Add a sender. Decide the cadence, the content (new posts?), and the
   provider. Check with the owner before any recurring send.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [x] No endpoint lets a caller learn whether an email is subscribed. A test pins it.
  (Slice A: `SubscribeEndpointTests.test_every_address_state_gets_the_same_answer`)
- [x] Subscribing takes effect only after email confirmation.
  (Slice A: `RequestConfirmationTests`; confirmation is POST-only)
- [x] The owner has agreed a sending cadence, and it is implemented or explicitly deferred.
  (Agreed 2026-10-09: weekly. Slice B: `manage.py send_blog_newsletter`, beat
  entry `blog-weekly-newsletter`, Mondays 10:00 UTC)
- [x] A web signup form, and confirm and unsubscribe pages (slice C).
  (`NewsletterSignup` in the blog list rail and under each article;
  `NewsletterLinkPage` at `/newsletter/confirm` and `/newsletter/unsubscribe`)

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-10-09 - Owner: full wire-up; slice A (security)

The owner chose the full wire-up: anyone can subscribe with double opt-in,
and a weekly digest of new posts goes out. Three slices, each its own PR:

- **A, security (this PR).** The ModelViewSet is gone, and with it listing,
  DELETE and unsubscribe-by-email. `POST newsletter/` validates the address,
  enqueues `send_newsletter_confirmation` on commit and always answers the
  same 202. The task decides whether to mail, so neither the body nor the
  response time depends on the address. Per-IP rate limit (10/h), plus one
  confirmation per address per hour (silently skipped, still 202).
  Confirm and unsubscribe take signed tokens (one salt each, keyed to the
  subscriber's pk). Each confirmation email voids the earlier links, and
  confirmation is POST-only, because mail scanners fetch GET links.
  RFC 8058 one-click lives at `newsletter/unsubscribe/one-click/`. The
  confirmation email links to `SITE_URL/newsletter/confirm`, a page that
  slice C builds.
- **B, sender.** A weekly Celery beat task modelled on `send_forum_digest`:
  run lock, per-row claim on `last_sent_at`, posts since
  `max(last_sent_at, confirmed_at)` by `first_published_at`, skip an empty
  week, `unsubscribe_headers()` on every email. Also prune unconfirmed rows
  whose last confirmation is older than its link (signup creates the row before
  consent, so a scripted signup can pile them up; PR review, slice A).
- **C, web.** A signup rail module on the blog list, an inline form on
  articles, and `/newsletter/confirm` and `/newsletter/unsubscribe` pages
  that POST the token after a click.

### 2026-10-09 - Slice C (web)

- `newsletterService.ts` sends JSON with `credentials: 'omit'`. Signup
  success just says "check your inbox", never "subscribed".
- `NewsletterSignup` appears in the blog list's right rail (xl and up) and
  under every published article. Previews don't show it.
- `NewsletterLinkPage` serves both emailed links. Opening the page does
  nothing, because mail scanners open links; the button acts.
- Checked in a browser against the dev backend: a signup gave the inbox
  message; a confirm link minted for the row showed the page, the click
  subscribed the row and cleared its stamp. Test row deleted afterwards.

### 2026-10-09 - Slice B (sender); todo complete

- `apps/blog/newsletter_digest.py` builds and sends one email, and
  `manage.py send_blog_newsletter [--dry-run]` runs the week. Beat fires
  `apps.blog.tasks.send_blog_weekly_newsletter` on Mondays at 10:00 UTC,
  an hour after the forum digest.
- Only rows that are active and confirmed get it. Each gets the live,
  public posts first published after `max(last_sent_at, confirmed_at)` and
  no later than the run's timestamp, newest first, capped at
  `NEWSLETTER_MAX_POSTS`. A week with no new posts sends nothing and keeps
  `last_sent_at`.
- Overlap safety follows the forum digest: a cache run lock, a conditional
  claim on `last_sent_at` (which also requires the row to still be
  subscribed), and a conditional release on failure or on the soft time
  limit. The task re-enqueues itself after the soft limit.
- Every email has one unsubscribe token, used in both the footer link and
  the List-Unsubscribe headers.
- The run also deletes unconfirmed rows whose link has expired, including
  rows with no stamp at all (a signup from the old endpoint, or a failed
  first send).
- Folded in from slice C's review: focus moves to the status line after a
  signup; a new token on the link page starts over; a test checks that the
  inline form is absent at xl.
- Not done: `NotificationService.send_newsletter` and
  `templates/emails/newsletter.html` are an older, unused newsletter path
  with no consent filter. Nothing calls them. Removing them is todo 533.
