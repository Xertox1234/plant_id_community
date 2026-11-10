# Audit: Auth system — security best practice and legal fit (Canada, US, Mexico)

> **Date:** 2026-11-10
> **Trigger:** Owner request: audit the auth system, check it is legal for Canada, the US and Mexico, and that it follows best practice.
> **Domains:** security, django-drf, react-typescript, flutter, firebase, legal (not a code domain: a gap analysis, not legal advice)
> **Audited commit:** `791d680c` (origin/main; the local `main` was 6 commits behind)
> **Baseline:** backend 6833 passed, 8 skipped (full pytest, 576 s). Web and mobile baselines are taken before the first fix that touches them (no code changed during discovery).

**What this audit can and cannot say.** The legal rows are a gap analysis by
non-lawyers against statute text and regulator guidance opened on 2026-11-10.
It cannot certify that the system "is legal". Rows marked *lawyer* turn on
interpretation, on which province the operator is in, or on sources that could
not be opened. Severity is the auditor's call; where it differs from the
reviewing agent's, the Verification column says so.

**Operator location (owner, 2026-11-10): Alberta.** So Alberta PIPA governs in-province handling and PIPEDA the
flows to processors outside Alberta. Quebec's Law 25, Charter of the French
Language and Consumer Protection Act were analysed as if they applied; whether
they reach an Alberta operator serving Quebec residents is a *lawyer* question.
That turns H3, M9, M16, M20 and the Quebec part of M21 from "gap" into "gap if
Quebec law reaches the operator". Alberta PIPA was then checked against the King's Printer text (current to 2025-09-01; no replacement found): its breach duty (s. 34.1: notify the Commissioner without unreasonable delay) raises H4; its blank-contact duties (ss. 5(3), 13(1), 13.1) raise H1; s. 7(2) (no consent beyond what the service needs) backs M8; it sets no age of consent (H3 stays a Quebec question); access requests get 45 days, so the policy's 30 is inside it.

## Findings

Each finding has a lifecycle: `open` → `fixing` → `verified` or `deferred` or `false-positive`.

### Critical

None.

### High

| ID | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | Live Privacy Policy and Terms show a DRAFT banner and blank operator name, address, contact email, privacy officer and governing law, while sign-up already records consent to version `2026-11-06`. The publish gate only runs when `LEGAL_PUBLISH=1`. Fails PIPEDA Sch. 1 cl. 4.8.2(a), Quebec P-39.1 s. 3.1, LFPDPPP art. 15 I and 29, CalOPPA; every "email us" right has no address. | legal | Canada, US, Mexico | `web/src/content/legal/*.md`, `web/scripts/check-legal-publish.mjs:29` | statute text opened | deferred → todo 701 | Read `privacy.en.md:5-20`. Known to the owner; listed because it gates everything else |
| H2 | No email template carries the sender's legal name or a postal address. Required on commercial email by CASL s. 6(2) + SOR/2012-36 s. 2(1)(d) and CAN-SPAM 15 U.S.C. 7704(a)(5)(A)(iii); consent does not cure it. Newsletter, forum digest and the welcome email are the exposed ones. Filling the policy blanks does not fix this: templates have no slot. | legal | Canada, US, Mexico | `backend/templates/emails/base.html:63-74`, `newsletter_digest.*`, `welcome_email.txt` | statute text opened | deferred → todo 703 | 31 email templates under `backend/**/templates/` (forum package included); 0 contain a postal or mailing address |
| H3 | Age floor is 13 everywhere; Quebec P-39.1 s. 4.1 and s. 14 make consent by a person under 14 invalid without a parent. | legal | Canada | `ConsentCheckbox.tsx:44`, `consent_checkbox.dart:24`, policy + terms ×6 | statute text opened | deferred → todo 701 | Read the checkbox copy and `privacy.en.md:183`. Fix is copy (13 → 14) plus a policy version bump: owner decision **2026-11-10:** addressed in policy version `2026-11-10` (todo 701 Work Log); todo stays open for the operator blanks. |
| H4 | No personal-data breach register or notification runbook. PIPEDA s. 10.3 (record every breach, keep 24 months) is a standing duty; Quebec s. 3.8 (5 years), Cal. Civ. 1798.82 (30 days), LFPDPPP art. 19 need a procedure ready. | legal | Canada, US, Mexico | `docs/DEPLOYMENT_SECURITY_CHECKLIST.md:840-865` (generic, stale Heroku commands) | statute text opened | deferred → todo 702 | Searched docs for a register or runbook: none |
| H5 | The Spanish policy does not work as an *aviso de privacidad*: ARCO answer deadline says "30 días" (law: 20 business days + 15), no ARCO procedure, complaints routed to INAI (dissolved 2025), no "limit use or disclosure" section, no cookies / automatic-collection section, processors and transfers not distinguished. | legal | Mexico | `web/src/content/legal/privacy.es.md:96-97,132-158,205-230` | LFPDPPP 2025 text opened | deferred → todo 701 | grep confirmed "30 días" (:220,:225), INAI (:230), 0 hits for "cookie". Text-only fixes, but they change policy text: owner + lawyer **2026-11-10:** addressed in policy version `2026-11-10` (todo 701 Work Log); todo stays open for the operator blanks. |
| H6 | Web login and sign-up pass the password through `sanitizeInput()` (DOMPurify strip + trim). `x<y 12345678901` is stored as `x…`; leading/trailing spaces are dropped. The stored password differs from what was typed, and the same password then fails from allauth reset or a password manager. ASVS 2.1 (no truncation or transformation). | security | react-typescript-reviewer | `web/src/pages/auth/LoginPage.tsx:66`, `SignupPage.tsx:68`, `web/src/utils/sanitize.ts:287` | — | verified | Read both `handleChange` bodies: every field, password included, is sanitized. Agent ran DOMPurify on the samples. **Fix constraint:** existing web accounts store the sanitized password, so login must try the raw value and fall back to the sanitized one (or those users are locked out). **Fix:** password and confirm-password fields are no longer sanitized on either page; one test per page sends a password with `<`, tags and outer spaces and asserts it arrives unchanged (both failed first). No fallback was added for accounts created under the old behaviour: a password that contained `<` or outer spaces was stored altered, and its owner must type the altered form or use Forgot password. Owner decision 2026-11-10: no fallback, the app is not live and has one real user. **Second fix (found while closing):** the register serializer trimmed the password (DRF default) while login reads it as sent, so once the web stopped trimming, a password with an outer space registered and then failed at login. The three password fields now set `trim_whitespace=False`; `test_password_whitespace.py` registers and logs in with such a password (failed first) |
| H7 | Mobile has no password reset for email/password accounts. Sign-in checks the Firebase credential; the only "Forgot password?" is inside the 409 conflict SnackBar and resets the Django credential instead. A user who forgets their password is locked out. | security | flutter-firebase-reviewer | `plant_community_mobile/lib/features/auth/login_screen.dart`, `password_reset_link.dart:5-11`, `lib/main.dart:118` | — | deferred → todo 704 | grep `sendPasswordResetEmail` in lib: 0 hits |
| H8 | Google sign-in is offered on iOS with no Sign in with Apple. App Store guideline 4.8 requires an equivalent privacy-preserving login when a third-party login is offered. Rejection risk at App Review, not a statute. | store policy | flutter-firebase-reviewer, US | `login_screen.dart:179`, `register_screen.dart:209`, `ios/Runner/*.entitlements` | Apple guideline opened | deferred → todo 704 | grep for sign_in_with_apple / AppleAuthProvider: 0 hits |
| H9 | App-store age-signal laws: Texas SB 2420 (reported in force since a June 2026 appeal-court stay, per Apple's developer notice of 2026-06-03 and secondary sources; no developer size threshold in the enrolled text), Utah and Louisiana oblige developers to consume the store's age signal. No Declared Age Range / Play age-signals code exists. Bites at US store launch, not on TestFlight. | legal | US | `plant_community_mobile/` (absent) | Texas text opened; Utah/Louisiana and litigation status unverified | deferred → todo 701 | *lawyer*. Re-check status before launch: court dates came from search snippets |

### Medium

| ID | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | Both `houseplant-md.com` and `api.houseplant-md.com` answer `strict-transport-security: max-age=0; includeSubDomains`, which switches HSTS off, although Django sets one year. Cause is a hypothesis, not verified: a Cloudflare zone HSTS setting overriding the origin. | security | auditor | live headers; `settings.py:1528` | confirmed (Cloudflare HSTS docs: enabled with max-age 0 is the documented disable; fix in the zone setting) | deferred → todo 706 | `curl -sI` on both hosts, 2026-11-10 |
| M2 | The web app is served with no CSP, no `frame-ancestors` / `X-Frame-Options` and no `Referrer-Policy`. `/delete-account/confirm`, `/verify-email` and `/settings` can be framed. | security | react-typescript-reviewer | `wrangler.jsonc`, no `web/public/_headers` | — | deferred → todo 706 | Live `curl -sI https://houseplant-md.com/privacy`: only HSTS and nosniff. The API does send a CSP |
| M3 | `/accounts/` mounts every allauth view. `/accounts/login/` is a password login that skips the project's lockout and 5/15 min limit, and allauth's own per-IP limits key on `REMOTE_ADDR`, which on Railway is not the client. A session from it works against the API (`SessionAuthentication` is a default authenticator). | security | django-drf-reviewer, cross-cutting-reviewer | `plant_community_backend/urls.py:136`, `settings.py:701-704,1684-1740` | better-fix: set `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` (allauth 65.19.2 `httpkit.py:213-221` falls back to REMOTE_ADDR) and explicit `ACCOUNT_RATE_LIMITS`, or narrow the mount | verified | Read urls + settings: no `ALLAUTH_TRUSTED_*`, no `ACCOUNT_RATE_LIMITS`. Not exercised live. `/accounts/` is kept on purpose (it is the password-reset path; `test_allauth_surface.py`, todo 447), so fix the limiter rather than unmount. **Fix:** `CustomAccountAdapter.get_client_ip` now uses `get_trusted_client_ip`, so allauth's limiter keys on the same client as ours (no new setting to keep in step). `test_allauth_client_ip.py` 3 tests; the throttle test fails with the override removed (mutation-checked, file restored and diffed). The project's SecurityMonitor lockout still does not run on `/accounts/login/`; allauth's own 5 failures / 5 min per login key does. kimi-review NOT run (same rule) |
| M4 | Register reveals whether an email has an account: a fresh username + victim email returns the "already exists" error, otherwise 201. | security | django-drf-reviewer | `apps/users/serializers.py:69-79` | — | deferred → todo 705 | Read the serializer. 3/h per-IP limit slows it |
| M5 | Refresh sessions have no absolute lifetime and reuse of a rotated token is not treated as theft: each refresh mints a new 7-day token; a blacklisted token returns 401 without revoking the family. | security | django-drf-reviewer | `apps/users/views.py:526-604` | better-fix: simplejwt 5.5.1 has no absolute cap or families; carry a session-start claim in the custom view and revoke all outstanding tokens on reuse | deferred → todo 705 | Agent read; auditor did not re-read the full view |
| M6 | Firebase exchange accepts any `sign_in_provider` (no allowlist) and issues tokens to a user whose `is_active` is False; `token_refresh` does not check `is_active` either. Access tokens are then refused, so the effect is a banned user's client that looks signed in and an "active" stamp that keeps moving. `check_revoked` is absent too, but that is a recorded owner decision (todo 567 frontmatter, 2026-10-11: retract the 401 promise, no `check_revoked`). Offered for re-decision: the docs check favours turning it on for an exchange that mints a session. | security | cross-cutting-reviewer, flutter-firebase-reviewer | `apps/users/firebase_auth_views.py:450,484-487,527-561`, `views.py:534` | confirmed (firebase_admin 7.4.0 `check_revoked` also catches disabled users, one network call; stock simplejwt refresh checks `is_active`, the custom view does not) | deferred → todo 705 (`check_revoked` part verified) | grep `is_active` in both files: only in the response body and the lockout branch. Calibrated down from the agent's framing: no access is gained. **Fix (part):** owner said "turn it on" 2026-11-10: the exchange now calls `verify_id_token(check_revoked=True)` whenever the app holds a real credential; revoked, disabled and deleted Firebase users get 401, a failed lookup gets 503; the keyless projectId-only tier skips the lookup. Schema, docstring and `FIREBASE_AUTHENTICATION.md` updated; `test_firebase_auth.py` 57 passed. **Review fix:** a service-account token that cannot be refreshed raises google-auth's own error, not a `FirebaseError`, and answered 500; `GoogleAuthError` now answers 503 too (1 test, failed first). Deferred to todo 705: the `sign_in_provider` allowlist and the `is_active` checks at exchange and refresh |
| M7 | Single-use tokens in the URL (`/delete-account/confirm?token=`, `/verify-email?key=`, `/unsubscribe?token=`) are visible to Sentry tracing and replay, which start at page load with no URL scrubbing; the last two pages never strip the token from the address bar. | security | react-typescript-reviewer | `web/src/config/sentry.ts:82-103`, `VerifyEmailPage.tsx:192`, `UnsubscribePage.tsx:64` | confirmed (Sentry docs: query strings are kept in breadcrumbs, spans and replay; scrub in `beforeSend`, `beforeSendTransaction`, `beforeBreadcrumb`, replay `beforeAddRecordingEvent`) | verified | Read `sentry.ts`: `beforeSend` only drops non-exceptions. Whether Sentry stores the query string: hypothesis, sent to research. **Fix:** new `web/src/config/sentryScrub.ts` drops query strings and fragments from every URL in error events, transactions, breadcrumbs, replay recording events and the replay event's URL list; wired into `beforeSend`, `beforeSendTransaction`, `beforeBreadcrumb`, `beforeAddRecordingEvent` and an event processor. 12 new tests (10 scrubber, 2 wiring). Not verified against a live Sentry project. **Review fix:** the replay library reads `location.href` itself for each snapshot and passes only custom events to `beforeAddRecordingEvent` (`@sentry/replay` 10.73, `maybeApplyCallback`), so the first version still uploaded the token inside a recording; replay is now not started on a page opened with a query string or fragment (3 wiring tests, 2 failed first). Remaining, in todo 706: `/verify-email` and `/unsubscribe` still leave the token in the address bar and browser history |
| M8 | Tracking is on by default with no opt-out: Sentry replay for 10% of all web sessions (signed out included), email click attribution, blog views with IP + user. Disclosed, but Quebec s. 8.1 (as the CAI reads it) wants identify/locate/profile technology off by default, and Mexican rules want non-necessary purposes refusable. | legal | Canada, Mexico, react-typescript-reviewer | `web/src/main.tsx:16`, `sentry.ts:102`, `apps/core/email_feedback.py:519-523`, `apps/blog/middleware.py:97-126` | CAI guideline opened | deferred → todo 707 | *lawyer* on classification. Cheapest fix: replay sample rate 0 (keep on-error). **2026-11-10, part done:** `replaysSessionSampleRate` is 0, so only a session that hits an error is recorded (`sentry.test.ts`, failed first). Click attribution and blog-view logging still wait on the owner |
| M9 | New accounts are not private by default: `profile_visibility="public"`, `show_location=True`, default "My Plants" collection `is_public: True` (Quebec s. 9.1). And `profile_visibility` is enforced nowhere: it appears only in the model, serializer, admin and audit log. | legal + security | Canada | `apps/users/models.py:186-204`, `signup.py:69`, `serializers.py:159` | statute text opened | deferred → todo 707 | grep `profile_visibility` in apps + packages outside tests/migrations/admin/auditlog/models: 1 hit (serializer). A control that does nothing |
| M10 | The under-13 / abuse sign-up block is an unsalted SHA-256 of the lower-cased address: `name+1@gmail.com` walks past it, and anyone with a DB copy can test addresses against it. Rows for those two reasons are kept forever (COPPA 16 CFR 312.10 question). | security + legal | cross-cutting-reviewer, US | `apps/users/deletion.py:65-90`, `apps/core/email_feedback.py:161-165`, `retention.py:136-158` | — | deferred → todo 707 | Agent read. Keyed hash (HMAC with a pepper) keeps the behaviour; *lawyer* on the retention term |
| M11 | Deleting an under-13 account runs the standard job, which by design keeps the other person's DM copy, quoted text, moderation records and report-held posts. COPPA on actual knowledge: delete the child's information. | legal | US | `apps/users/admin.py:189-193`, `privacy.en.md:149-160` | FTC FAQ opened | deferred → todo 707 | *lawyer*. Policy/design change |
| M12 | Policy says OpenAI gets "forum text, only while an optional forum AI feature is switched on"; code sends private-message text from non-trusted senders to the configured spam backend. Policy also says "no analytics or tracking" beside click logs and replay. FTC Act s. 5 accuracy. | legal | US, Canada | `packages/wagtail_forum/wagtail_forum/api/direct_messages.py:140-144`, `privacy.en.md:93,105-106` | — | deferred → todo 701 | Read both. Whether the LLM backend is on in prod was not checked (no prod access) **2026-11-10:** addressed in policy version `2026-11-10` (todo 701 Work Log); todo stays open for the operator blanks. |
| M13 | Mobile: session expiry and external sign-out leave the device's push token registered and clear nothing; plain logout does not clear the Firestore offline cache (unencrypted, unlimited) or sign out of Google. | security | flutter-firebase-reviewer | `plant_community_mobile/lib/services/auth_service.dart:704-743,1267-1288`, `firestore_service.dart:33` | — | deferred → todo 704 | grep: `clearFirestoreOfflineCache` called only from the delete screen; `googleSignIn.signOut` only in `declineTerms` |
| M14 | Mobile token storage: `FlutterSecureStorage()` with default options (the repo already uses `first_unlock_this_device` for the push id); the 7-day refresh token is stored but never read; Android manifest does not disable backup. | security | flutter-firebase-reviewer | `auth_service.dart:187,190`, `android/app/src/main/AndroidManifest.xml` | confirmed (flutter_secure_storage 10.0.0: iOS default `unlocked`, backed up; Android `allowBackup` defaults true, restore gives a silent logout not a leak) | deferred → todo 704 | grep: one reference to `django_refresh_token` (the key constant); no `allowBackup` |
| M15 | Firebase rules never require a verified email, and Storage rules allow 10 MB image uploads (SVG included, `avatars/` world-readable) although no client uses Firebase Storage. Anyone can make a throwaway Firebase account with no consent and no Django account and use it as hosting. | security | flutter-firebase-reviewer | `firebase/storage.rules:6-36`, `firebase/firestore.rules:5-60` | — | deferred → todo 707 | grep `firebase_storage` in mobile and web: 0 hits. Rules not re-read by the auditor. **Correction 2026-11-10:** 0 hits is true of current code only. Mobile builds made before #1251 (2026-11-05) upload each identification photo to Storage, so a deny-all breaks identification on those builds and the bucket may hold photos |
| M16 | One English checkbox bundles age + Terms + Privacy; the interface is English-only. Quebec s. 14 wants consent requests separate from other information (narrow: primary purposes ride on notice, s. 8.3); Charter of the French Language s. 52/55 and LFPC art. 85 want French / Spanish for consumers there. | legal | Canada, Mexico | `ConsentCheckbox.tsx:44-52`, `consent_checkbox.dart:23-25` | statute text opened | deferred → todo 701 | *lawyer*; reverses the owner decision "keep in English for now". Smallest step: localise the checkbox sentence |
| M17 | Password rules differ by door: Django enforces 14 characters, the mobile app (Firebase) 6. | security | flutter-firebase-reviewer | `login_screen.dart:334`, `register_screen.dart:143`, `settings.py:498` | confirmed (Firebase password policy supports min length 6-30, enforced server-side for new users) | deferred → todo 704 | Read both |
| M18 | Web session handling: two tabs refreshing at once can log the loser out (rotation + blacklist); any network blip or 5xx on refresh logs out; a failed logout request still shows "logged out" while the cookies stay valid; no global 401 handling. | security | react-typescript-reviewer | `web/src/contexts/AuthContext.tsx:253-264,401-407`, `authService.ts` | — | deferred → todo 706 | Agent read; the multi-tab race is a hypothesis, not reproduced |
| M19 | Email opt-out gaps: no signed-out "stop all optional email" choice (CAN-SPAM 7704(a)(3)(B)); the welcome email promotes features with only a login-gated preferences link; the newsletter form lacks CASL s. 10(1) content (who is asking, contact, "you can unsubscribe"). | legal | US, Canada | `web/src/pages/UnsubscribePage.tsx`, `welcome_email.txt`, `web/src/components/blog/NewsletterSignup.tsx:68-90` | statute text opened | deferred → todo 703 | Agent read |
| M20 | No privacy impact assessment or processor/DPA register (Quebec s. 17 before sending data outside Quebec; PIPEDA cl. 4.1.3). | legal | Canada | `docs/` (absent) | statute text opened | deferred → todo 702 | Applies in full only if Law 25 reaches the operator: *lawyer* |
| M21 | Terms: unilateral "we may update", liability limit, blank governing law, and "under 18 needs a parent's permission" with nothing collecting it. Quebec CPA ss. 10, 11.2, 19 and LFPC art. 90 void or restrict these for consumers there. | legal | Canada, Mexico, US | `web/src/content/legal/terms.*.md` | statute text opened | deferred → todo 701 | *lawyer* **2026-11-10, part:** see todo 701 Work Log for what version `2026-11-10` changed and what is left. |
| M22 | Staff sign-in (`/cms/login/` Wagtail, `/admin/login/` Django) has no lockout, no rate limit and no second factor in code. Staff can delete accounts and read the DeletedAccount ledger. A Cloudflare rule could cover it outside the repo: not checked. | security | auditor | `plant_community_backend/urls.py:109-111`, `apps/core/security.py:671-700` | — | deferred → todo 705 | grep settings/urls/requirements for axes, otp, 2fa, mfa, ratelimit on those paths: 0 hits; the custom middleware only acts on `/api/` |

### Low

| ID | Finding | Domain | Agent | File(s) | Research | Status | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Google access token is put in the userinfo URL query; the handler logs `str(e)`, so a timeout would log a live token. Failure branches log whole provider responses. | security | cross-cutting-reviewer | `apps/users/oauth_views.py:432-442,466` | — | verified | Read :428-440 and :462-468. **Fix:** Google token sent as `Authorization: Bearer`; failure logs carry only the provider error code, HTTP status or exception type (Google and GitHub). `test_oauth_no_token_in_logs.py` 5 tests, failed first, + OAuth suites: 44 passed; ruff and mypy clean. kimi-review NOT run (same rule) |
| L2 | Login returns 500 on a non-object body or non-string fields, and on an email shared by two legacy accounts (`MultipleObjectsReturned`). | security | django-drf-reviewer | `apps/users/views.py:266-302` | — | verified | Read the view. **Fix:** login treats a non-object body or non-string field as missing credentials (400) and a multiply-held email as unknown (401, same body). `test_login_malformed_input.py` 4 tests + login suites: 50 passed; ruff and mypy clean. kimi-review NOT run (global rule: no kimi on auth code) |
| L3 | Login timing: an account with an empty password (Firebase-created) skips hashing, so a fast 401 means "exists, social-only". | security | django-drf-reviewer | `apps/users/views.py:306-318` | contradicted ⚠ (Django 6.1 `verify_password` burns a hash for an empty or unusable value, `hashers.py:39-72`; no practical oracle) | false-positive | Read the view. Closed on the research verdict: Django hashes either way, so there is no timing difference to measure |
| L4 | Per-account lockout (10 failures → 1 h) lets anyone lock a known username out; counters key on the raw identifier, so username and email count separately. | security | django-drf-reviewer | `apps/core/security.py:86-250` | — | deferred → todo 705 | Design trade-off; agent read |
| L5 | Anyone who knows an address can use up its 3/h deletion-link quota and supersede a link the owner already holds; a link is consumed before the staff/author refusal. | security | cross-cutting-reviewer | `apps/users/deletion_views.py:252-363` | — | deferred → todo 705 | Agent read |
| L6 | Hand-rolled OAuth has no PKCE or nonce; `redirect_uri` is built from the Host header; the parked sign-up profile stays in the session row for 24 h. | security | cross-cutting-reviewer | `apps/users/oauth_views.py:138-176,330-348` | — | deferred → todo 705 | Agent read. State is validated; code exchange is server-side |
| L7 | Password reset link (allauth) lives 3 days (Django default). | security | django-drf-reviewer | `settings.py` (no `PASSWORD_RESET_TIMEOUT`) | — | deferred → todo 705 | grep: not set |
| L8 | Mobile shows raw exception text to the user in five places. | security | flutter-firebase-reviewer | `auth_service.dart:363,365,458,637,739` | — | deferred → todo 704 | Agent read |
| L9 | Declining the terms can leave the Firebase user alive if `delete()` throws; bounded by the orphan prune, which is log-only. | security | flutter-firebase-reviewer | `auth_service.dart:1203-1236` | — | deferred → todo 704 | Agent read |
| L10 | Web keeps the whole user object in `sessionStorage`; it survives passive expiry; cross-tab logout waits for focus + 30 s; `oauth_url` from the server is followed without an origin check. | security | react-typescript-reviewer | `authService.ts:119,198,304`, `AuthContext.tsx:324-345`, `GoogleSignInButton.tsx:61` | — | deferred → todo 706 | Agent read |
| L11 | Account deletion has no Firebase Storage step (moot while nothing writes there; closes with M15). **Correction 2026-11-10:** not moot, older mobile builds wrote there (see M15); it closes when the bucket is emptied as well. | security | flutter-firebase-reviewer | `apps/users/deletion.py:392` | — | deferred → todo 707 | Agent read |
| L12 | Policy accuracy: "stored in the United States" unverified for Plant.id (Czech operator) and PlantNet (France); "crash report from the app" though mobile has no Sentry; the 90-day hash thinning is not reflected; GitHub sign-in listed with no button. | legal | Canada, US | `privacy.*.md` | — | deferred → todo 701 | Agent read **2026-11-10, part:** see todo 701 Work Log for what version `2026-11-10` changed and what is left. |
| L13 | Access and portability are by email with no procedure or export tool; dead `zip_code` / `latitude` / `longitude` columns on `User`. | legal | Canada | `apps/users/models.py:96-134` | — | deferred → todo 707 | Agent read |
| L14 | Small policy sentences missing: how material changes are notified (CalOPPA 22575(b)(3), Quebec s. 8.2, LFPDPPP art. 15 VI), third-party collection by embeds, how to remove your own content (Cal. B&P 22581), automated DM rejection and how to ask for review (Quebec s. 12.1, LFPDPPP art. 26 II), no sensitive-data statement. | legal | US, Canada, Mexico | `privacy.*.md`, `terms.*.md` | statute text opened | deferred → todo 701 | Agent read **2026-11-10:** addressed in policy version `2026-11-10` (todo 701 Work Log); todo stays open for the operator blanks. |
| L15 | Deletion is not propagated to Sentry, Resend, Plant.id/PlantNet or OpenAI; Mexican "bloqueo" period not addressed. | legal | Mexico | `apps/users/deletion.py` | LFPDPPP text opened | deferred → todo 707 | *lawyer* |
| L16 | Alberta PIPA s. 6(2): the policy must name every country where a service provider outside Canada handles data, and s. 13.1 a contact for questions about them. It names only the United States; Plant.id (Czech operator) and PlantNet (France) are unconfirmed. The Alberta OIPC is missing from the complaint list. | legal | Alberta | `privacy.en.md:116-120,175-179` | PIPA text opened | deferred → todo 701 | Processor regions taken from the brief, not checked. Joins the policy-text batch **2026-11-10, part:** see todo 701 Work Log for what version `2026-11-10` changed and what is left. |
| L17 | Whether the "Houseplant MD" name needs a trade-name declaration (Alberta Partnership Act s. 110). | legal | Alberta | — | Act text opened | deferred → todo 701 | *lawyer*; owner action, not code |

### False positives

| ID | Claim | Agent | Evidence |
| --- | --- | --- | --- |
| FP1 | Android release build has no INTERNET permission | flutter-firebase-reviewer | `firebase_messaging`'s own manifest declares it and is merged into every build |
| FP2 | Per-IP limits share Cloudflare buckets (client IP wrong behind the proxy) | cross-cutting-reviewer | Fixed and live-verified 2026-10-20: `RATELIMIT_CLIENT_IP_META_KEY=HTTP_X_REAL_IP`. Does not cover allauth's own limiter: see M3 |
| FP3 | Email change without re-auth (todo 404) | — | `email` is read-only in the serializer; pinned by `test_allauth_surface.py` |

### Checked and found sound

Tokens only in HttpOnly cookies on web and Keychain/Keystore-backed storage on
mobile; CSRF on every cookie-authenticated unsafe method; JWT signing key
separate from `SECRET_KEY`; rotation + blacklist on; OAuth `state` random,
single-use, constant-time compared; no open redirect; provider email must be
verified before linking, and linking revokes the squatter's tokens; Firebase
exchange enforces `email_verified` for every provider; consent and the block
list are enforced server-side on all four user-creating paths, with version
and time recorded; deletion links are single-use, POST-only and
scanner-safe; mobile deletion needs a sign-in less than 5 minutes old;
WebSocket origin check and connect limit run before auth; unsubscribe works
signed-out and takes effect at once; newsletter is double opt-in; no ads, no
analytics SDK, no sale of data; CCPA and the threshold-based US state privacy
laws do not apply at this size.

## Deferred Items

| ID | Todo | Rationale |
| --- | --- | --- |
| H1, H3, H5, H9, M12, M16, M21, L12, L14, L16, L17 | [701](../../todos/701-pending-p1-legal-policy-text-revision.md) | All change policy text or are lawyer questions; one revision, one `LEGAL_POLICY_VERSION` bump, after the owner fills the blanks |
| H4, M20 | [702](../../todos/702-pending-p1-breach-runbook-and-processor-register.md) | Documents, not code; the owner should read the runbook before relying on it |
| H2, M19 | [703](../../todos/703-pending-p1-email-sender-identity-and-opt-out.md) | Needs the sender name and mailing address |
| H7, H8, M13, M14, M17, L8, L9 | [704](../../todos/704-pending-p2-mobile-auth-gaps.md) | Device checks and an owner console change; no mobile code was touched in this audit |
| M6 (rest), M4, M5, M22, L4, L5, L6, L7 | [705](../../todos/705-pending-p2-backend-auth-hardening.md) | Code-only; kept out to hold this PR to a reviewable size |
| M1, M2, M7 (rest), M18, L10 | [706](../../todos/706-pending-p2-web-headers-and-session-lifecycle.md) | Headers can only be checked after a deploy (the CMS frames the blog preview); M1 is a Cloudflare setting |
| M8, M9, M10, M11, M15, L11, L13, L15 | [707](../../todos/707-pending-p2-privacy-defaults-and-data-handling.md) | Product and legal decisions first; a Firebase rules change is live on deploy |

## Summary

| Severity | Found | Verified | Deferred | False positive | Open |
| --- | --- | --- | --- | --- | --- |
| Critical | 0 | 0 | 0 | 0 | 0 |
| High | 9 | 1 | 8 | 0 | 0 |
| Medium | 22 | 2 | 20 | 0 | 0 |
| Low | 17 | 2 | 14 | 1 | 0 |

Three more claims were rejected during discovery (FP1 to FP3 above) and are not
counted as findings.

Fixed (5): H6, M3, M7, L1, L2, plus the `check_revoked` part of M6 (the rest of
M6 is counted as deferred). kimi-review was not run on any fix: the owner's
standing rule forbids pointing it at authentication code, and the owner
approved committing with `SKIP_KIMI_REVIEW=1` on 2026-11-10. The bundled
security review was run on the diff instead; it found no new vulnerability and two
gaps in the fixes (M7 replay, M6 status code), both fixed above.

Not checked: M7 against a live Sentry project (unit tests only); the Firebase
revocation lookup against the production credential (if it cannot look users
up, every mobile sign-in answers 503 `verifier_unavailable`: check one mobile
sign-in after deploy). H6 has no fallback for a web account whose password was
altered by the old sanitizer: its owner types the altered form or uses
"Forgot password" (owner decision 2026-11-10: no fallback, the app is not live).

Backend full suite 6858 passed, 8 skipped (`pytest --create-db`); `ruff` and `mypy` clean on `apps/users`; `spectacular --validate --fail-on-warn` exit 0. Web 2153 passed (143 files); `tsc` and `eslint` clean. Mobile not re-run: no mobile file changed.

Review round 1 (django-drf, react-typescript, cross-cutting reviewers) found
nothing blocking. Non-blocking items declined, with the reason:

- `test_oauth_no_token_in_logs.py` covers the GitHub path thinly (no
  token-exchange-failure or exception-path test): the change there is the same
  two lines as the Google path, which is covered.
- A permanent permission error from Firebase answers 503 on every exchange
  rather than a distinct error: it is logged at error level, and the
  post-deploy sign-in check catches it.
- No test pins that an unrelated `FirebaseError` gives 503: that behaviour
  predates this audit.
- The Sentry wiring test mocks `@sentry/react`, so the `replay_event`
  processor is checked by wiring only; M7 stays partly open in todo 706.
- The replay gate looks only at the address the page was opened with: noted in
  a code comment, rest of M7 in todo 706.
