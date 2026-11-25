---
status: pending
priority: p1
issue_id: "701"
tags: [legal, privacy, policy, web, mobile]
dependencies: []
triage: blocked-owner
blocked_on: operator details for the five blanks (owner, at launch)
triaged: 2026-11-25
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
- [x] `LEGAL_POLICY_VERSION` is bumped once and existing users are asked to
      accept the new version.
- [ ] Each legal question above has a dated owner decision recorded in the
      Work Log (no lawyer, owner decision 2026-11-10).

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
- **L12** GitHub sign-in stays in the text: there is no button, but the server
  route completes a sign-in when the GitHub keys are set. Deleted-account hash: removed
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
- **No per-person switch for email click records or blog view logging.** The
  Spanish notice lists both as secondary purposes and points to the right to
  object. Honouring an objection needs a per-user opt-out, which is not built.
- **Forum display name.** With no forum display name set, forum posts show
  the member's first and last name (`serializers.py` author payload). The
  policy now says so; whether that default is wanted is a product question.
- **M16** The checkbox sentence is still English only and still one box.
- **Promises that are manual steps for the operator:** emailing account
  holders before a change, reviewing a rejected private message, sending a
  portable copy, removing a post on request.
- **L17 / H9** Trade-name filing and the US app-store age-signal laws: owner
  items for launch, no code here.

### 2026-11-11 - Re-consent, regions, and the data inventory

Owner decisions (2026-11-11): block at sign-in until the current version is
accepted; production settings may be read for the storage regions; build a
per-person switch for email click records and blog view logging.

- **Re-consent built.** `confirm_current_policy` runs in `login`,
  `token_refresh`, the Firebase exchange and the web OAuth callback and
  finish step: an account not on `LEGAL_POLICY_VERSION` gets 428
  `policy_update_required` until the request carries `accepted_terms: true`.
  Web: the login page shows the consent box when asked; a Google sign-in is
  sent to the finish page, worded as an update. App: the consent sheet is
  worded as an update, and Cancel signs out without deleting the login.
- **Why a new code.** Builds 20 and 21 answer `consent_required` with a
  sheet whose Cancel deletes the Firebase login. For an existing account
  that would destroy the login, so the refusal has its own code. Those
  builds show "Failed to connect to server" until a build with this change
  is installed: merge and ship the build together.
- **Regions sourced.** Sentry: `ingest.us.sentry.io` (the server DSN host on
  Railway), United States. Cloudflare R2: both buckets `WNAM` (western North
  America), jurisdiction `default`. Railway `us-west2`, Firestore `nam5`.
  OpenAI: United States company, no data-residency option set in code. Not
  sourced: Resend's sending region (a dashboard setting).
- **Found on the way.** The published website bundle carries no Sentry DSN,
  so the website sends no error reports or replays today; the policy
  describes them. Harmless over-disclosure, noted for the owner.
- `docs/legal/data-inventory.md` brought level with version 2026-11-10.
- **Blog view logging does not run (read from code, not checked against
  production data).** `BlogViewTrackingMiddleware` only logs when
  `request._wagtail_page` is set, and nothing in the code or in Wagtail sets
  it; only its tests do. So no `BlogPostView` row is written today, and the
  policy describes a record that is not made. Owner decision needed: wire it
  up (the blog is read through the API, where the middleware does not see
  the signed-in user) or remove the logging and its policy sentences.
- The OAuth finish step no longer applies the sign-up block list to an
  account that already exists. `create_test_user` stamps the policy version.
- **Per-person switch built.** `User.usage_records` (migration `0025`, on
  by default). Off, `record_click` writes no `EmailClick` and the blog
  middleware writes no `BlogPostView` for that account; the post's own view
  counter still counts. The toggle is "Usage records" in web Settings and the
  app profile, and the field is in the admin. A signed-out blog visit is
  still logged: there is no account to hold a switch.
- **Policy version `2026-11-11`.** All six documents: a paragraph on the
  switch, the Spanish limit-use list names it, and the change section says a
  new version is asked for at the next sign-in. One bump. With re-consent
  live, every account is asked at its next sign-in.

### 2026-11-12 - Fixed the items found on the way

- **Blog view logging now runs.** The blog API's post route
  (`BlogPostPageViewSet.detail_view`, cached and uncached reads alike) calls
  `record_blog_view`, with the API's own user, so a JWT sign-in is seen and
  the usage-records switch applies. The middleware stays but still never
  fires. Tests: `apps/blog/tests/test_view_recording.py` drive the real
  route. The policy text needed no change: it already described this.
- **Session sign-ins wait for the current version.** The API ignores a
  session of an account that must accept; `/cms/`, `/admin/` and allauth's
  pages refuse it and point to the website. Tests:
  `apps/users/tests/test_policy_session_paths.py`. Each guard's test failed
  with the guard disabled.
- **Website Sentry still off.** Needs the owner: a DSN and the Cloudflare
  Workers Builds variable `VITE_SENTRY_DSN` (the Cloudflare token here cannot
  write build settings).

### 2026-11-24 - Merged main into the branch

- Policy version is now `2026-11-24`: `main` added the 90-day rule for removed
  private messages to all three policies without a new version, so one bump
  covers both. Set it to the release date if the merge waits.
- Migration renumbered `0026_usage_records_switch`.
- Sign-in checks for a disabled account before asking for consent on every
  path, so a disabled account is never stamped.
- App: declining an update flushes the offline writes, as a sign-out does. A
  declined new account still drops them.

### 2026-11-25 - Policy date, Android release sign-in

- Policy version is now `2026-11-25`, the merge day.
- Google sign-in failed in the release APK only: the resource shrinker removed
  `default_web_client_id`, which google_sign_in_android reads by name. Kept with
  `res/raw/keep.xml`; `aapt2 dump resources` shows the ID in the rebuilt APK.
- The owner signed in on both phones with build 29, against the server as it was
  before this merge.

### 2026-11-25 - Checked against main and the live site; minors' laws

No policy text changed. The publish gate still exits 1: the five blanks and the
DRAFT line are in all six documents.

- **Website Sentry is on.** The 2026-11-12 entry is out of date: todo 716 set
  `VITE_SENTRY_DSN`. The live bundle holds a DSN on `ingest.us.sentry.io`.
- **Resend sourced.** Its docs: account data, email metadata, logs and API
  records are stored in the United States whatever the sending region.
- **Still not sourced:** OpenAI's default country, PlantNet's hosting, and R2
  (the `WNAM` hint is best effort, not a guarantee). The policy already says
  providers may process in other countries.
- **Missing from the policy's provider list:** Google for website sign-in, and
  the browser push services. Add both in the launch revision, so one version
  bump covers them and the blanks.

Owner decisions (2026-11-25): the minimum age stays 14 everywhere, with no 18+
limit and the US included; the "under 18 needs a parent's permission" sentence
comes out of the Terms (en, es, fr) in the launch revision; the store age
signals are handled at launch.

Read for ages 14 to 17 (a reading of the text, not legal advice):

- No duty to collect a parent's permission found in COPPA (16 CFR 312.2,
  312.5: under 13), PIPEDA s. 6.1 (no age; the OPC guidance says under 13),
  Alberta PIPA s. 61(1)(b) (an under-18 who understands acts for themselves)
  or Mexico's LFPDPPP (no mention of minors). Civil Code arts. 450, 635, 637
  and 646: a minor's contract can be void, but only the minor or their
  representative may claim that. Quebec P-39.1 s. 4.1 (under 14) is still from
  the law-firm summary; Légis Québec refused the fetch again.
- Mississippi HB 1126 (Act read) and Tenn. Code 47-18-5702 and 5703 (read in
  the Sixth Circuit opinion of 2026-08-28) cover services with accounts and
  posts, whatever the topic: an age check and a parent's consent under 18.
  Mississippi has no size exemption; the full Tennessee definition was not
  read. The Fifth Circuit vacated the Mississippi injunction on 2026-11-19;
  the Sixth Circuit sent Tennessee's back.
- Texas SB 2420 (Act read; reported enforceable while on appeal): the store
  collects the consent; a developer checks the store's signal, rates the app
  and reports significant changes. Reported to follow: Alabama and California
  (Jan 2027), Utah (May 2027), Louisiana (July 2027).

To do before launch: re-check these laws and the ones not read (Florida,
Virginia, Georgia, Nebraska, Utah, Louisiana, Alabama, California); build the
Apple Declared Age Range and Google Play Age Signals checks; then the owner
decides on Mississippi and Tennessee (smallest fix seen: no forum, messages or
public profile there, to be checked against both laws).

Still open for the owner: the five blanks, the liability sentence, M16 (one
English checkbox), the trade-name filing.

## Notes

P1 because consent is already being recorded against a draft. Not legal
advice: the audit is a gap analysis against statute text opened 2026-11-10.
