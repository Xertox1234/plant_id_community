# Legal policies, sign-up consent and account deletion

Date: 2026-11-06. Status: waiting on the owner's approval (builder check done).

## Why

Houseplant MD has no Privacy Policy and no Terms of Service. The web sign-up
page names both as plain text (`web/src/pages/auth/SignupPage.tsx:306-310`) and
links to nothing. The mobile app, which is the main platform, mentions neither.
`plant_community_mobile/FLUTTER_COMPLETION_PLAN.md:767` still lists "Privacy
policy and terms of service added" as open.

The owner wants what any app or site does: before someone finishes registering,
they can open and read both policies and must accept them. Launch is in
**Canada, the US and Mexico**.

Writing an honest policy showed that users cannot delete their own account.
Only staff can, in the admin, and even that leaves the user's Firestore data and
Firebase login behind. Apple (guideline 5.1.1(v)), Google Play, PIPEDA, Quebec
Law 25, CCPA and Mexico's LFPDPPP all require self-service deletion. The owner:
"Account deletion is of paramount importance." So it is part of this project.

## What the owner decided

1. **Documents.** A Privacy Policy and Terms of Service, in **English, French
   and Spanish** ("If we are gonna do a Spanish version then we need a French
   version as well for Canada").
2. **Company details are blanks.** No company is registered yet; one will be
   before launch. The company name, address, contact email, privacy officer and
   governing law are marked placeholders. The pages cannot go live until they
   are filled.
3. **Consent at sign-up.**
   - One unticked checkbox: "I have read and accept the Privacy Policy and Terms
     of Service".
   - Both names are links that open the full document before ticking ("as long
     as the user can open and read both policies prior to agreeing to them").
   - Create Account **and** Google sign-in stay blocked until it is ticked.
   - The phone app is primary; the web sign-up page gets the same checkbox.
   - Each user sees the documents in their own language.
4. **Who accepts.** Only new sign-ups. The only existing accounts are the
   owner's and test accounts. They are never prompted. The server records which
   policy version each new user accepted and when. Re-acceptance when a policy
   changes is not needed for launch.
5. **Minimum age 13.** The checkbox also confirms "I am 13 or older". No birth
   date is asked. An account found to belong to someone under 13 is deleted.
6. **Hosting.** The policies are pages at houseplant-md.com `/privacy` and
   `/terms`, served by the existing web app on Cloudflare. The phone app opens
   them in an in-app browser.
7. **Premium** is sold only through the App Store and Google Play. The website
   does not sell it; a user who bought it in the app has it on the web too. The
   web shows "Get Premium in the app" with store links.
8. **OpenAI is named** in the Privacy Policy as used only by optional forum
   features while they are switched on. This holds whether or not any is on in
   production today.
9. **Account deletion,** as played back and approved:
   - "Delete account" in the app's settings (required in the app by Apple) and
     on the web settings page.
   - One screen says plainly what will be lost. The user confirms, then proves
     it is them: Firebase re-authentication on mobile (password or Google
     again), and the password or an emailed link on the web.
   - **Immediate.** There is no grace period. The user is told how long it
     takes and gets a "your account is deleted" email when it is done.
   - **Erased:** account, profile and avatar; garden data; scans and their
     photos; Firestore saved plants and the Firebase login; push tokens; the
     newsletter subscription; block and mute lists; the address in the email
     log.
   - **Forum posts:** erased. The body, images and edit history go, and a
     "[deleted]" placeholder keeps each post's place so threads still read.
     This follows Apple's rule that a deleted account's text posts and photos
     must go.
   - **Private messages:** the other person keeps their copy, shown as from
     "[deleted]".
   - **Kept, and disclosed in the policy:** a small record that the account
     existed and was deleted; a hashed "don't email this address" marker;
     moderation records; posts under an open abuse report until it is closed.
10. **Signed-out deletion page.** Google Play requires a public page:
    houseplant-md.com `/delete-account`. Signed out, it confirms by emailed
    link.
11. **Retention.** Blog page-view logs (IP, user agent), the email delivery log
    and the audit log are deleted after **90 days**. The deleted-account record
    and moderation records are not.
12. **Blocked re-sign-up.** An email address deleted by staff for abuse, or
    because the user was under 13, cannot sign up again. Every sign-up path
    (A3) checks the hashed address against the deleted-account record and
    refuses with a plain message. Self-deleted addresses are not blocked. The
    Privacy Policy states this purpose for keeping the hash.
13. **Screens in English.** The new screens and the checkbox stay in English
    ("Keep in English for now"). The policy documents stay in English, French
    and Spanish: Quebec requires the Terms and the Privacy Policy in French, and
    Mexico prescribes the Spanish *aviso de privacidad*.

## Goals

- No account, on any path, is created without a recorded acceptance of the
  current policy version.
- A user can read both documents, in their language, before accepting.
- A user can delete their account themselves, in the app and on the web, and
  afterwards nothing that identifies them is left except what the policy lists.
- Everything the Privacy Policy says matches what the code does.

## Non-goals

- Re-prompting existing users, or re-acceptance when a policy changes.
- Self-service data export, correction or access. The policy promises these by
  email request to the privacy contact, answered within 30 days.
- Selling Premium on the web.
- Legal sign-off. The texts are drafts until a lawyer has reviewed the English
  and fluent reviewers the French and Spanish.

## Anti-goals (a failure even if it "works")

- **Consent only in the form.** Mobile Google sign-in on the *login* screen
  creates accounts (`get_or_create_user_from_firebase` in
  `backend/apps/users/firebase_auth_views.py`), and so does web OAuth
  (`oauth_views.oauth_login`). A checkbox only on the register screens would
  leave both open.
- **Locking out existing accounts.** The owner's and test accounts have no
  acceptance and must keep signing in.
- **"Deletion" that leaves Firestore data or the Firebase login,** or that only
  deactivates. Apple rejects deactivation.
- **A policy that promises what the code doesn't do,** or hides what it keeps.
- **A Spanish policy that is just a translation.** Mexico's LFPDPPP prescribes
  the *aviso de privacidad*: the responsible party's identity, purposes, ARCO
  rights and how to exercise them. Quebec Law 25 needs a named privacy officer,
  a cross-border transfer disclosure, and French equal to the English.

## How it works (my calls are marked)

### Two plans, one design

*(My call)* This ships as two plans that can land separately:

- **A. Policies and consent.** The documents, the pages, the consent gate.
- **B. Account deletion and retention.**

A can land first. The policy text describes B's deletion. The pages stay marked
DRAFT until both have shipped and the blanks are filled.

### A1. The documents

- One Markdown file per document per language: `privacy.en.md`,
  `privacy.fr.md`, `privacy.es.md`, `terms.en.md` and so on, under
  `web/src/content/legal/` *(my call; the builder may pick another folder)*.
  A lawyer edits Markdown, not JSX.
- Each file carries the policy version, its effective date, and a visible
  "DRAFT — pending legal review" banner until it is removed by hand.
- Placeholders look the same everywhere (for example `[[COMPANY_NAME]]`). A
  test or build check fails if a placeholder or the DRAFT banner is still there
  when a `LEGAL_PUBLISH` switch is on *(my call: the switch defaults off)*.
- **What the Privacy Policy covers.** It is written from the data inventory
  done 2026-11-06:
  - What is collected:
    - account and profile;
    - Firebase UID and Google sign-in;
    - avatar;
    - scan photos (EXIF removed; undecided scans deleted after 24 h; kept ones
      until removed or the account is deleted);
    - garden data;
    - forum posts, messages, reports, blocks and mutes;
    - newsletter;
    - push tokens;
    - email delivery and click records;
    - blog page views (IP, user agent, referrer);
    - IP addresses held briefly for rate limiting.
  - Who receives it:
    - Plant.id/Kindwise and PlantNet (photos);
    - Google Firebase (login, saved plants, push), and Apple for push;
    - OpenAI (forum text, only while an optional feature is on);
    - Sentry (crash reports; on the web, a sample of sessions with text masked);
    - Cloudflare (website and file storage);
    - Railway (servers, US);
    - Resend (email);
    - YouTube/Vimeo, for embeds a user posts.
  - No ads, no analytics, no data sales.
  - Data is stored and processed in the US. This is the cross-border disclosure.
  - How long each item is kept, per decisions 9 and 11 and the scan rules.
  - Rights and how to use them: access, correction, deletion (in the app),
    portability, withdrawing consent and complaining to a regulator. Mexico's
    ARCO rights are named in the Spanish text.
  - The privacy officer (a blank).
  - Children: the minimum age is 13, and accounts of under-13s are deleted.
- **What the Terms cover:**
  - Eligibility: 13 and older; under 18 with a parent's OK.
  - **Plant advice is not a guarantee.** Identifications and diagnoses are
    automated and can be wrong. Do not eat a plant, or treat a person or pet, on
    the app's word alone.
  - Forum rules: no harassment, spam, illegal content or other people's private
    information. Moderation and reporting are described.
  - Users keep ownership of their content and license us to show it.
  - Premium is billed, renewed and refunded by Apple or Google under their
    rules.
  - Account deletion is available at any time. We can close accounts that break
    the rules.
  - As-is, limited liability, and governing law (a blank).
  - "Nothing here removes rights your local law gives you", for Quebec and
    Mexico.

### A2. The pages

- Web routes `/privacy`, `/terms` and `/delete-account` in `web/src/App.tsx`.
  One component renders the right Markdown file.
- The language comes from `?lang=en|fr|es`. With none, it uses the browser's
  language, falling back to English. Each page has a language switcher.
- The pages are public, need no login, and work as a plain page in an in-app
  browser.
- The app opens `https://houseplant-md.com/privacy?lang=<app locale>` in an
  in-app browser (`url_launcher` in-app mode or similar; the builder's call).

### A3. Recording consent (server)

- One constant, for example `LEGAL_POLICY_VERSION = "2026-11-06"`, is the
  current version. The page footers show it.
- New nullable fields on the user: `policy_version_accepted` and
  `policy_accepted_at`. Existing users stay null and are never asked (anti-goal
  2).
- **The server stamps its own version.** The client sends only
  `accepted_terms: true`. The server writes the current constant and the time.
  An old app build can never record a stale version.
- **Every path that creates a user requires it:**
  - `POST register/` (web email sign-up; mobile email sign-up goes through
    Firebase and the token exchange, see "Settled after the builder check");
  - `firebase-token-exchange/` when it would create a new user;
  - web OAuth when the callback would create a new user.
- Without the flag, nothing is created and the server answers a distinct error,
  `consent_required` (4xx; the builder picks the status).
- An existing user signing in never needs the flag.

### A4. Consent in the app and on the web

- **Mobile register screen** (`features/auth/register_screen.dart`): the
  checkbox with two links, plus the age line, above Create Account. Create
  Account and "Continue with Google" stay disabled until it is ticked.
- **Mobile login screen:** "Continue with Google" can create an account. When
  the token exchange answers `consent_required`, the app shows the same checkbox
  in a sheet. Ticking it retries with the flag; closing it signs the user back
  out of Firebase and creates nothing.
- **Web sign-up page:** the same checkbox replaces the plain-text line. It
  blocks the submit and the Google button.
- **Web OAuth from the login page** *(my call)*: a new OAuth user lands on a
  short "Finish signing up" page with the checkbox before the account is
  created. The pending sign-in waits in the session for up to 15 minutes. The
  builder may choose to carry the flag through OAuth `state` instead, if that is
  simpler and equally safe.
- **The checkbox text and all new screens are in English.** Owner decision
  2026-11-06: "Keep in English for now." No translation setup is added to
  either app. Only the policy documents come in three languages, and the links
  open them in the user's language (`?lang=` from the device locale).

### B1. Deleting an account

- `POST` an account-deletion endpoint, for the signed-in user only.
  - **Mobile:** Firebase re-authentication first (`reauthenticateWithCredential`;
    Firebase refuses deletion without a recent login). The app then calls the
    endpoint, which checks the Firebase token is fresh *(my call: issued within
    the last 5 minutes)*.
  - **Web:** the password, or for users without one, an emailed confirmation
    link.
- **Signed-out `/delete-account`:** the user enters an email and receives a
  single-use link (valid 1 h *(my call)*). Opening it shows the same confirm
  screen. The page always says "if an account exists, we sent a link", so it
  never reveals whether an address has an account. It is rate-limited per IP and
  per address.
- The endpoint marks the account deleted, signs out every session and refreshes
  token, and queues a Celery job. It answers at once. The app signs out and
  shows "Your account is being deleted; you'll get an email when it's done."
- **The job** runs in idempotent steps, so a retry picks up where it stopped:
  1. **Django data.** User, profile, garden, scans and their R2 photos (the
     existing signals delete files), push and web-push tokens, newsletter, blocks
     and mutes, onboarding events.
  2. **Forum.**
     - Each of the user's posts: the body, images, link-preview images and
       revisions are cleared, and the author is set to none, so it shows as
       "[deleted]".
     - Topics the user started keep their place, and others' replies stay. The
       title becomes "[deleted]" *(my call)*.
     - Posts under an open report are kept until the report closes, then cleared.
     - Private messages: the user's sent messages stay for the other person,
       shown as from "[deleted]".
  3. **Email.** Replace the address in the email log. Keep only the existing
     hashed suppression marker.
  4. **Firestore.** `recursive_delete` of `users/{uid}`, which includes
     `identified_plants`, using the Admin SDK on the server. The builder checks
     whether anything still writes `plant_identifications`, `user_plants`,
     `disease_diagnoses`, `user_preferences` or `sync_queue` (listed in
     `firestore.rules`; no Dart code writes them today). If something does, the
     job deletes those documents by user id too.
  5. **Firebase Auth.** `deleteUser(uid)` for this one user, last of all. A
     web-only user with no Firebase UID skips steps 4 and 5.
  6. **Record and email.** Write the deleted-account record and send the "done"
     email to the address held in memory for this job.
- **The deleted-account record** is its own small table: hashed email, the
  deletion time, the reason (self, staff, under-13), and the policy version they
  had accepted. It is not an audit-log row, because the audit log is pruned at
  90 days.
- **Staff deletion** in the admin runs the same job, so both paths erase the
  same things.
- Failures: the job retries with backoff. After the last retry it alerts through
  Sentry and stays resumable. A retry must not recreate or double-email.

### B2. Retention clean-up

- A nightly task deletes:
  - blog page views older than 90 days;
  - email delivery-log rows older than 90 days (email clicks already have a
    90-day limit);
  - audit-log entries older than 90 days.
- It runs where the other nightly prunes run (`forum-prune-cron` or Celery beat;
  the builder's call). It reports counts and has a `--dry-run`.
- It never touches the deleted-account record or moderation records.

### Small fixes the policy depends on

- Remove the unused iOS location-permission string (`NSLocationWhenInUse…`), or
  the policy would have to explain a permission the app never uses.
- Sentry web session replay stays as it is (10% of sessions, text masked). The
  policy discloses it.

## Edge cases the builder must cover

- Google sign-in on the login screen by someone with no account: consent sheet,
  not an account.
- Someone ticks the box, then the network fails: nothing is half-created, and a
  retry works.
- The owner's and test accounts sign in with no acceptance on record: allowed.
- An old app build without the checkbox: it signs in existing users fine. Its
  new sign-ups get `consent_required`, which that build shows as a sign-up
  failure. This is accepted; only TestFlight builds exist today.
- Delete requested twice, or from two devices: one job, one email.
- The job dies between Firestore and Firebase Auth: the retry finishes it.
- A deleted user's email signs up again. After a self-deletion it is a new
  account, and the suppression marker still blocks mail only if the address had
  bounced or complained. After a staff deletion for abuse or for being under 13,
  the sign-up is refused (decision 12).
- Tests must show that after deletion no row still holds the user's email,
  username or IP, apart from what the policy lists.

## Settled after the builder check (my calls)

- **Mobile email sign-up.**
  - The app creates the Firebase user, sends the verification mail, and the
    Django user is made at the token exchange after verification, possibly
    days later.
  - The app keeps the tick on the device against the Firebase uid and sends
    `accepted_terms` on that exchange. `policy_accepted_at` is the exchange
    time.
  - If the tick was lost (reinstall, other device), the verified user sees the
    consent sheet before the exchange completes.
- **Firebase logins with no account.**
  - When a user closes the consent sheet, or a sign-up is refused with
    `consent_required`, the app deletes the just-created Firebase user. It can,
    because the login is seconds old.
  - A Firebase user left behind anyway (app killed mid-flow) is removed by the
    nightly prune once it is older than 7 days with no Django user. The policy
    mentions this.
- **Premium and in-app purchase.**
  - Owner decision 2026-11-06: App Store and Google Play billing is built
    before launch. It is **a separate project**, not part of this design. Today
    `is_premium` is set by hand.
  - The policies describe it as it will be:
    - The Terms' billing section covers store billing.
    - The Privacy Policy lists purchase and subscription status (from store
      receipts) as collected, and Apple and Google as recipients.
  - The delete screen tells subscribers that deleting the account does not
    cancel the subscription, and links to the store's subscription page. The
    app cannot cancel it for them.
- **Quotes and mentions.**
  - Other users' posts are theirs and are not edited. Text of the deleted user
    that someone else quoted, and an @mention of their old username, stay in
    that other person's post.
  - The policy says so, and the "no row holds the username" test excludes
    other users' post bodies.
  - Notifications that point at the deleted user are deleted.
- **Schema fixes deletion needs.**
  - Today `Message.sender`, the direct-conversation participants, `Report.reporter`
    and `RagAnswerReport.reporter` are `on_delete=CASCADE`. Deleting a user
    would wipe the other person's whole DM thread and every report they filed.
  - These become nullable with `SET_NULL`, so the other person keeps the
    thread and the reports stay.
- **What "moderation records" means.**
  - Reports (filed by or against the user), moderation actions, and
    suspensions.
  - They are kept with the user link cleared. The only identifier left is the
    deleted-account record's id and its hashed email, so repeat abuse can still
    be spotted.
- **Held posts.**
  - The "done" email goes once everything else is erased.
  - A post held under an open report is cleared when the report closes, or
    after 30 days, whichever comes first. That runs in the nightly prune.

## Left to the builder

The endpoint names and shapes, the error status for `consent_required`, the
in-app browser mechanism, where the Markdown lives, the layout of the consent
sheet and delete screens (Canopy tokens, `docs/rules/flutter.md`), and where the
nightly prune runs.
