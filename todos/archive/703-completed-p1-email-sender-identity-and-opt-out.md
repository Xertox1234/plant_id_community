---
status: completed
priority: p1
issue_id: "703"
tags: [legal, email, casl, can-spam, backend, web]
dependencies: []
triage: ready
triaged: 2026-11-20
owner_decision: "Owner: ship the code now (settings, footer slot, every-template test, signed-out stop-all, newsletter lines) with sender name and mailing address blank until launch; re-point the Railway-values criterion to a launch todo (2026-11-20)"
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

- [x] A test renders every template under `backend/**/templates/` that is an
      email and asserts the sender name and address appear.
- [x] A signed-out visitor with a valid unsubscribe link can stop all optional
      email in one step (test).
- [x] The newsletter form states who is asking, a contact, and that the reader
      can unsubscribe.
- [ ] Both settings are set on Railway — record the date and one received
      email's footer here. → todo 724 (re-pointed 2026-11-21)

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: needs the owner's sender name and mailing address.

### 2026-11-21 - Implemented by the todo sweep (run 2026-11-20-2202)

- Added `EMAIL_SENDER_NAME` and `EMAIL_SENDER_ADDRESS` (blank until launch, todo
  724) and one helper, `apps.core.context_processors.email_sender`, which the new
  `email_sender` template tags call at render time, so every send path gets them.
  They are not yet in `.railway/railway.ts`: a variable is declared there only
  after it is set on Railway.
- The footer is in `emails/base.html` outside the `footer` block, at the end of
  every `.txt` email, in a new package slot (`wagtail_forum/email/_footer.*`)
  that the host shadows, and in a host copy of allauth's
  `account/email/base_message.txt`. `apps/core/tests/test_email_template_sender_footer.py`
  renders every email template's own source and fails on a missing footer.
- New `POST /api/v1/auth/unsubscribe/all/` and an `all_optional` list: any signed
  link stops all optional email in one step (the master switch, plus a blog
  newsletter row for the account's address). The web `/unsubscribe` page offers
  it, and the welcome email links to it.
- The newsletter form now says who is asking (Houseplant MD), that every email
  can be unsubscribed from, and links the Privacy Policy for contact. That
  policy's contact is still the `[[CONTACT_EMAIL]]` launch blank.
- `emails/disease_alert.html` and the core `emails/forum_digest.html` reverse
  retired `forum:` and `plant_identification:` URL names and cannot render; the
  footer test stubs those routes. Recorded here, not fixed.

### 2026-11-21 - Verified by the todo sweep (run 2026-11-20-2202)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/core/tests/test_email_template_sender_footer.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g3/703-ac0.txt` (not committed), last lines:

  ```text
    backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ============== 8 passed, 2 warnings, 31 subtests passed in 0.32s ===============
  ```

- AC 2: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/users/tests/test_email_unsubscribe.py -k StopAllOptionalEmailTests --create-db -v -p no:cacheprovider && cd ../web && npx vitest run src/pages/UnsubscribePage.test.tsx src/services/unsubscribeService.test.ts` — evidence `.sweep-evidence/g3/703-ac1.txt` (not committed), last lines:

  ```text
  ================ 9 passed, 37 deselected, 3 warnings in 20.83s =================
  …

   Test Files  2 passed (2)
        Tests  20 passed (20)
     Start at  07:27:15
     Duration  618ms (environment 54%, tests 25%, setup 10%, transform 6%, import 4%, worker 1%)
  ```

- AC 3: `cd web && npx vitest run src/components/blog/NewsletterSignup.test.tsx` — evidence `.sweep-evidence/g3/703-ac2.txt` (not committed), last lines:

  ```text

   Test Files  1 passed (1)
        Tests  5 passed (5)
     Start at  07:26:52
     Duration  567ms (environment 42%, tests 39%, setup 8%, import 7%, transform 4%)
  ```

### 2026-11-21 - Completed by the todo sweep (run 2026-11-20-2202)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

## Notes

P1: applies to every optional email already going out.
