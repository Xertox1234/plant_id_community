---
status: pending
priority: p1
issue_id: "701"
tags: [legal, privacy, policy, web, mobile]
dependencies: []
triage: blocked-owner
blocked_on: operator details for the blanks, and a lawyer pass on the questions below
triaged: 2026-11-10
---

# Legal policy text: one revision closing the audit's policy findings

## Problem

The auth + legal audit of 2026-11-10 found several gaps that are all changes
to the Privacy Policy, the Terms or the consent sentence. Each change to that
text needs a `LEGAL_POLICY_VERSION` bump and re-consent, so they ship as one
revision, after the owner fills the blanks and a lawyer has answered the open
questions.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md` (rows named below).

- **H1** The live policies carry a DRAFT banner and blank `[[COMPANY_NAME]]`,
  `[[COMPANY_ADDRESS]]`, `[[CONTACT_EMAIL]]`, `[[PRIVACY_OFFICER_NAME]]` and
  `[[GOVERNING_LAW]]`, while sign-up already records consent to version
  `2026-11-06`. The gate `web/scripts/check-legal-publish.mjs:29` only runs
  with `LEGAL_PUBLISH=1`. Every "email us" right has no address.
- **H3** Age floor is 13 everywhere (`ConsentCheckbox.tsx:44`,
  `consent_checkbox.dart:24`, policy and terms). Quebec P-39.1 ss. 4.1 and 14
  put it at 14, if Quebec law reaches the operator.
- **H5** `web/src/content/legal/privacy.es.md` does not work as a Mexican
  *aviso de privacidad*: "30 días" for ARCO answers (:220, :225; the law says
  20 business days + 15), no ARCO procedure, complaints sent to INAI (:230,
  dissolved 2025), no limit-use section, no cookies section, processors and
  transfers not told apart.
- **M12** The policy says OpenAI gets "forum text, only while an optional
  forum AI feature is switched on" (`privacy.en.md:93,105-106`); the code also
  screens private messages from untrusted senders
  (`packages/wagtail_forum/wagtail_forum/api/direct_messages.py:140-144`). It
  also says "no analytics or tracking" beside click logs and session replay.
- **M16** One English checkbox bundles age, Terms and Privacy; the interface
  is English-only.
- **M21** Terms: unilateral "we may update", the liability limit, blank
  governing law, and "under 18 needs a parent's permission" with nothing
  collecting it.
- **L12** "Stored in the United States" is unverified for Plant.id and
  PlantNet; "crash report from the app" although mobile has no Sentry; the
  90-day hash thinning is not described; GitHub sign-in is listed with no
  button.
- **L14** Missing sentences: how material changes are notified, third-party
  collection by embeds, how to remove your own content, automated DM rejection
  and how to ask for a review, a sensitive-data statement.
- **L16** Alberta PIPA s. 6(2) and s. 13.1: name every country where a
  provider outside Canada handles data, and a contact for questions about
  them. Add the Alberta OIPC to the complaint list
  (`privacy.en.md:116-120,175-179`).
- **L17 / H9 (questions only, no code here)** Trade-name filing, and the US
  app-store age-signal laws (Texas SB 2420, Utah, Louisiana), whose status
  must be re-checked before a US store launch.

## Recommended Action

1. Owner: supply the five blank values.
2. Owner: put these to a lawyer: does Quebec law (Law 25, French-language
   Charter, Consumer Protection Act) reach the operator; does Mexico's 2025
   LFPDPPP; which age floor to use; the Terms clauses in M21; whether the
   app-store age-signal laws apply at launch; the trade-name filing.
3. Confirm each processor's storage country from its own documentation.
4. Edit `privacy.en.md`, `privacy.es.md`, `terms.en.md`, `terms.es.md` and the
   two consent checkboxes in one PR; bump `LEGAL_POLICY_VERSION` once.
5. Run `LEGAL_PUBLISH=1 node web/scripts/check-legal-publish.mjs` and make the
   gate part of the normal build once the blanks are filled.

## Technical Details

- Policy files: `web/src/content/legal/*.md`.
- Consent copy: `web/src/components/auth/ConsentCheckbox.tsx`,
  `plant_community_mobile/lib/features/auth/consent_checkbox.dart`.
- Version constant: `backend/apps/users/consent.py`.

## Acceptance Criteria

- [ ] `LEGAL_PUBLISH=1 node web/scripts/check-legal-publish.mjs` exits 0.
- [ ] `grep -c "INAI\|30 días" web/src/content/legal/privacy.es.md` prints 0.
- [ ] The policy names every processor country and the Alberta OIPC.
- [ ] The OpenAI and tracking sentences match what the code does (M12).
- [ ] `LEGAL_POLICY_VERSION` is bumped once and existing users are asked to
      accept the new version.
- [ ] Each lawyer question above has a dated answer recorded in the Work Log.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: every item changes policy text or needs the owner or
  a lawyer.

## Notes

P1 because consent is already being recorded against a draft. Not legal
advice: the audit is a gap analysis against statute text opened 2026-11-10.
