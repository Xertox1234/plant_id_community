---
status: pending
priority: p1
issue_id: "701"
tags: [legal, privacy, policy, web, mobile]
dependencies: []
triage: blocked-owner
blocked_on: operator details for the five blanks (owner, at launch)
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
- [x] `grep -c "INAI\|30 días" web/src/content/legal/privacy.es.md` prints 0.
- [ ] The policy names every processor country and the Alberta OIPC.
- [x] The OpenAI and tracking sentences match what the code does (M12).
- [ ] `LEGAL_POLICY_VERSION` is bumped once and existing users are asked to
      accept the new version.
- [ ] Each lawyer question above has a dated answer recorded in the Work Log.

## Work Log

### 2026-11-10 - Filed from the auth + legal audit

- Deferred by the audit: every item changes policy text or needs the owner or
  a lawyer.

### 2026-11-10 - Version 2026-11-10: code-matching and statute-driven text

Owner decisions (2026-11-10): no lawyer will review; legal questions are
settled by the statute text, strictest of the three countries; the five
operator blanks wait for launch. Everything below is a reading of the text,
not legal advice.

Changed in `privacy.{en,es,fr}.md`, `terms.{en,es,fr}.md`, both consent
checkboxes and `LEGAL_POLICY_VERSION` (one bump, to `2026-11-10`):

- **H3** Age floor 13 to 14 everywhere (Quebec P-39.1 s. 4.1, the highest
  floor found among the three countries; s. 4.1 was read from a law-firm
  summary this session because Légis Québec and CanLII refused the fetch).
  The admin action label now says "under the minimum age"; the stored reason
  stays `under_13`. An installed app build shows 13 until the next build.
- **H5** Spanish notice rebuilt on LFPDPPP (DOF 20-03-2025, last reform
  14-11-2025) arts. 7, 15 I-VI, 26, 28, 31, 34, 35-36 and 40: twenty business
  days to answer and fifteen to act, one extension, free, what a request must
  contain, how to revoke, options to limit use, primary and secondary
  purposes, processors told apart from transfers, a cookies section, and
  complaints to the Secretaría Anticorrupción y Buen Gobierno.
- **M12** OpenAI: the spam screen of posts and private messages from members
  not yet trusted, and the optional AI features. "No analytics or tracking"
  now says what is recorded (email clicks, blog views). Error replay only for
  a session that hits an error (707). The app sends no error reports.
- **L12** GitHub sign-in removed (no button). Deleted-account hash: removed
  after 90 days for a self-deletion. Plant.id named as FlowerChecker s.r.o.,
  Czech Republic (its own privacy notice); PlantNet as France.
- **L14** Change notice, embeds as third parties, how to remove your own
  content, automated rejection of a private message and how to ask a person
  to review it, a sensitive-data statement, what is public on a profile.
- **L16** Alberta PIPA s. 6(2) and s. 13.1(3) (King's Printer PDF read):
  countries named, the policy stated to be the written information about
  providers outside Canada, a contact for questions; Alberta OIPC added.
- **M21, part** Terms: 30 days' notice of a change that affects rights, with
  the right to leave; how to remove content. Liability, governing law and the
  under-18 sentence are unchanged.
- The under-age deletion paragraph describes what 707 shipped (#1296).

Not done, and why:

- **H1** The DRAFT banner and the five blanks stay. The publish gate still
  exits 1 by design.
- **Processor countries (acceptance box open).** Sourced: Railway us-west2
  (`.railway/railway.ts`), Firestore nam5 (`firebase.json`), FlowerChecker in
  Brno. Not sourced: where Sentry, Resend, Cloudflare storage, OpenAI and
  PlantNet actually store data. The policy names each operator's country and
  says processing may occur elsewhere.
- **Re-consent.** No code asks an existing account to accept a new version
  (`consent.py` asks only at sign-up). The app is not live, so none was built.
  It is needed before a policy change after launch.
- **M16** The checkbox sentence is still English only and still one box.
- **Promises that are manual steps for the operator:** emailing account
  holders before a change, reviewing a rejected private message, sending a
  portable copy, removing a post on request.
- **L17 / H9** Trade-name filing and the US app-store age-signal laws: owner
  items for launch, no code here.

## Notes

P1 because consent is already being recorded against a draft. Not legal
advice: the audit is a gap analysis against statute text opened 2026-11-10.
