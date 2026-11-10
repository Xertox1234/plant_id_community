---
status: pending
priority: p1
issue_id: "703"
tags: [legal, email, casl, can-spam, backend, web]
dependencies: []
triage: blocked-owner
blocked_on: the sender name and mailing address to print in emails
triaged: 2026-11-10
---

# Emails: sender name and postal address, and a signed-out "stop all email"

## Problem

No email the app sends names its sender or gives a mailing address. CASL
s. 6(2) with SOR/2012-36 s. 2(1)(d), and CAN-SPAM 15 U.S.C. 7704(a)(5)(A)(iii),
require both on commercial email; consent does not cure it. Three smaller
opt-out gaps sit beside it.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md`, rows H2 and M19.

- **H2** 31 email templates under `backend/**/templates/` (the forum package
  included); none contains a postal address. The shared footer is
  `backend/templates/emails/base.html:63-74`. The newsletter, the forum digest
  and the welcome email are the exposed ones. The templates have no slot, so
  filling the policy blanks does not fix this.
- **M19** `web/src/pages/UnsubscribePage.tsx` has no signed-out "stop all
  optional email" choice; `welcome_email.txt` promotes features with only a
  login-gated preferences link; `web/src/components/blog/NewsletterSignup.tsx:68-90`
  lacks the CASL s. 10(1) content (who is asking, a contact, "you can
  unsubscribe").

## Recommended Action

1. Add `EMAIL_SENDER_NAME` and `EMAIL_SENDER_ADDRESS` settings, read from the
   environment and declared in `.railway/railway.ts`; expose them to templates
   through one context helper.
2. Print both in the shared HTML and text footers, and in any template that
   does not extend the base.
3. Add a test that renders every email template and fails when the address is
   missing, so a new template cannot ship without it.
4. Add "stop all optional email" to the signed-out unsubscribe page, a working
   unsubscribe link to the welcome email, and the s. 10(1) lines to the
   newsletter form.

## Technical Details

- Unsubscribe plumbing: `backend/apps/users/` email-unsubscribe views and
  `apps/core/email_feedback.py`.
- Policy on which emails are optional: `docs/operations/notification-baseline.md`.

## Acceptance Criteria

- [ ] A test renders every template under `backend/**/templates/` that is an
      email and asserts the sender name and address appear.
- [ ] A signed-out visitor with a valid unsubscribe link can stop all optional
      email in one step (test).
- [ ] The newsletter form states who is asking, a contact, and that the reader
      can unsubscribe.
- [ ] Both settings are set on Railway — record the date and one received
      email's footer here.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: needs the owner's sender name and mailing address.

## Notes

P1: applies to every optional email already going out.
