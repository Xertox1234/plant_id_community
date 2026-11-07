# Legal Policies and Sign-up Consent Implementation Plan (Plan A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a Privacy Policy and Terms of Service (EN/FR/ES) at `/privacy` and `/terms`, and make every account-creating path require a recorded acceptance of them.

**Architecture:**

- **Server.** The server is the gate. Each path that would create a `User` refuses with HTTP 428 `consent_required` unless the request carries `accepted_terms: true`. The server stamps its own `LEGAL_POLICY_VERSION`. Existing users are never asked.
- **Documents.** Markdown files in the web app, rendered by one React page.
- **Mobile.** The app links to those pages in an in-app browser. A consent sheet covers Google sign-in from the login screen, and covers a verified email user whose tick was lost.

**Tech Stack:** Django/DRF, React 19 + Vite (`marked` + existing `dompurify`), Flutter + Riverpod 3 + `url_launcher`.

**Spec:** `docs/superpowers/specs/2026-11-06-legal-policies-and-account-deletion-design.md` (Plan A = spec sections A1–A4 and "Small fixes"; account deletion, `/delete-account` and retention are Plan B).

## Global Constraints

- Version constant: `LEGAL_POLICY_VERSION = "2026-11-06"` in `backend/apps/users/constants.py`. The client never sends a version.
- Refusal: HTTP **428**, body `{"error": "Please accept the Privacy Policy and Terms of Service to create an account.", "code": "consent_required"}`. Not 403: the app reads a JSON 403 from the exchange as "email not verified" (`auth_service.dart`, `emailUnverified`).
- Only the JSON boolean `true` counts as acceptance. `"true"`, `1` and a missing field do not.
- An existing user signing in never needs the flag, and their null acceptance fields are never written.
- Checkbox copy, exact, everywhere: **"I am 13 or older, and I have read and accept the Privacy Policy and Terms of Service."** "Privacy Policy" and "Terms of Service" are links. The box is unticked by default.
- All new UI is English only (owner decision 2026-11-06). Only the documents come in `en`, `fr`, `es`.
- Document URLs: `https://houseplant-md.com/privacy?lang=<en|fr|es>` and `/terms?lang=…`. Locale mapping: language code `fr*` → `fr`, `es*` → `es`, anything else → `en`.
- Placeholders are written `[[NAME]]` (for example `[[COMPANY_NAME]]`). Each document carries the line `> DRAFT — pending legal review` and the comment `<!-- version: 2026-11-06 -->`.
- Backend config goes in `apps/users/constants.py` (no magic numbers). Log prefixes are bracketed (`[AUTH]`, `[SECURITY]`).
- Commits end with the attribution lines from the session. Use `SKIP_KIMI_REVIEW=1` (kimi is out of credits). Flutter commands need the sandbox disabled.

## Review Focus

1. **An existing account signs in with Google from the login screen (mobile and web) and has no acceptance on record.** It must sign in normally, with no 428 and no sheet. Tests: T3 `test_existing_user_signs_in_without_flag`, T4 `test_callback_existing_user_logs_in_without_consent`.
2. **An email user verifies days later on a new device**, so the local tick is gone. They get the consent sheet, not an error or a loop. Test: T9 `consent sheet shows on 428 and retry sends accepted_terms`.
3. **`accepted_terms` arrives as `"true"`, `"false"`, `1` or `null`.** Only boolean `true` creates an account. Tests: T2 and T3 parametrized refusals.
4. **The web OAuth pending sign-up is older than 15 minutes, or there is none, when Finish is pressed.** No account is created; the response is 400 `signup_expired`, and the page sends the user back to sign in. Test: T4 `test_finish_expired_pending_refused`.
5. **Device or browser language `fr-CA`, `es-MX`, `pt-BR`, or none.** These map to `fr`, `es`, `en` and `en`. Tests: T5 `pickLanguage` and T8 `legalLangFor`.

---

### Task 1: Consent fields, constant and helper (backend)

**Files:**

- Modify: `backend/apps/users/constants.py`, `backend/apps/users/models.py` (User)
- Create: `backend/apps/users/migrations/0022_user_policy_acceptance.py`, `backend/apps/users/consent.py`
- Test: `backend/apps/users/tests/test_consent.py`

**Interfaces:**

- Produces:
  - `LEGAL_POLICY_VERSION: str = "2026-11-06"`
  - `CONSENT_REQUIRED_CODE = "consent_required"`
  - `CONSENT_REQUIRED_MESSAGE` (the exact error text from Global Constraints)
  - `User.policy_version_accepted: CharField(max_length=20, null=True, blank=True)`
  - `User.policy_accepted_at: DateTimeField(null=True, blank=True)`
  - In `apps/users/consent.py`:
    - `class ConsentRequired(Exception)`
    - `def is_accepted(value: object) -> bool`, true only for `value is True`
    - `def record_policy_acceptance(user: User) -> None`, which sets both fields to the constant and `timezone.now()` and saves with `update_fields`
    - `def consent_required_response() -> Response`, the 428 response

- [ ] **Step 1: Write the failing tests.**
  - `test_is_accepted_only_true`: parametrize `[(True, True), ("true", False), (1, False), (None, False), (False, False)]`.
  - `test_record_policy_acceptance_stamps_server_version`: freeze time, then call it and assert `policy_version_accepted == "2026-11-06"` and `policy_accepted_at` equals the frozen time.
  - `test_existing_users_have_null_acceptance`: a user created by the ORM has both fields `None`.
  - `test_consent_required_response`: status 428 and the body equals the constant message and code.
- [ ] **Step 2:** Run `cd backend && venv/bin/pytest apps/users/tests/test_consent.py -q`. Expected: FAIL, import error.
- [ ] **Step 3:** Add the constants, the fields, and `consent.py`. Run `venv/bin/python manage.py makemigrations users -n user_policy_acceptance`.
- [ ] **Step 4:** Run the same pytest. Expected: PASS. Run `venv/bin/python manage.py makemigrations --check --dry-run`. Expected: "No changes detected".
- [ ] **Step 5:** Commit: `feat(users): record policy acceptance fields and consent helper`.

### Task 2: Email registration requires acceptance (backend, `POST register/`)

**Files:**

- Modify: `backend/apps/users/serializers.py` (`UserRegistrationSerializer`), `backend/apps/users/views.py` (`register`)
- Modify: every existing test that posts to `register/`. Find them with `grep -rn "register/\|auth:register\|'register'" backend/apps --include=*.py`; they add `"accepted_terms": True`. Report the count found and the count changed.
- Test: `backend/apps/users/tests/test_signup.py`

**Interfaces:**

- Consumes: T1 `is_accepted`, `record_policy_acceptance`, `consent_required_response`.

- [ ] **Step 1: Write the failing tests.**
  - `test_register_without_accepted_terms_returns_428_and_creates_nothing`: parametrize the body without the field, then with `"true"`, `False` and `1`. Each one asserts status 428, `code == "consent_required"`, and that `User.objects.count()` is unchanged.
  - `test_register_with_accepted_terms_records_version`: status 201, and the new user has `policy_version_accepted == LEGAL_POLICY_VERSION`.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_signup.py -q`. Expected: the new tests fail.
- [ ] **Step 3:** In `register`, check `is_accepted(request.data.get("accepted_terms"))` before the serializer runs. If false, return `consent_required_response()`. After `serializer.save()`, call `record_policy_acceptance(user)` inside the same transaction. Leave the serializer's fields alone; the flag never reaches the model.
- [ ] **Step 4:** Run `venv/bin/pytest apps/users -q`. Expected: PASS, with the updated callers included.
- [ ] **Step 5:** Commit: `feat(users): email registration requires accepted_terms`.

### Task 3: Firebase token exchange requires acceptance for new users (backend)

**Files:**

- Modify: `backend/apps/users/firebase_auth_views.py`
- Test: `backend/apps/users/tests/test_firebase_auth.py`

**Interfaces:**

- Consumes: T1 helpers.
- Produces: `get_or_create_user_from_firebase(..., accepted_terms: bool = False)`. It raises `ConsentRequired` at the point where it would create a user, after every existing refusal check and before `User.objects.create`. With `accepted_terms=True`, it calls `record_policy_acceptance` on the new user. The exchange view reads `is_accepted(request.data.get("accepted_terms"))`, passes it in, and maps `ConsentRequired` to `consent_required_response()`. That `except` must come before the generic `except ValueError` and `except Exception`.
  - **The check order is deliberate; don't simplify it.** The existing unverified-email 403 runs before the consent check. On mobile, the listener-triggered exchange can fire before `accepted_terms_uid` is written, and for an email sign-up it must hit "verify your email" first, not a consent refusal.

- [ ] **Step 1: Write the failing tests.** Mock token verification the way the file already does.
  - `test_new_firebase_user_without_flag_gets_428_and_no_user`: a fresh uid and a verified email, with no flag. Expect 428 `consent_required`, no `User` row, and no default collection created.
  - `test_new_firebase_user_with_flag_is_created_with_version`: expect 200, and `policy_version_accepted == "2026-11-06"`.
  - `test_existing_user_signs_in_without_flag`: a user bound to the uid exists and has null acceptance. Expect 200, and the fields are still `None`.
  - `test_existing_user_with_flag_is_not_restamped`: an existing user plus the flag gives 200 with the fields still `None`.
  - `test_unverified_email_still_403_before_consent`: an unverified email with no flag still returns the existing 403, not 428.
  - `test_flag_must_be_boolean_true`: `"true"` on a new uid returns 428.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_firebase_auth.py -q`. Expected: the new tests fail.
- [ ] **Step 3:** Implement as stated in Interfaces. Update the view's docstring: the request body now accepts `accepted_terms`. Add `accepted_terms` to the view's `@extend_schema` request body, if it has one.
- [ ] **Step 4:** Run `venv/bin/pytest apps/users -q` and `venv/bin/python manage.py spectacular --validate --fail-on-warn > /dev/null`. Expected: PASS, with no warnings.
- [ ] **Step 5:** Commit: `feat(users): token exchange requires accepted_terms to create a user`.

### Task 4: Web OAuth requires acceptance for new users (backend)

**Files:**

- Modify: `backend/apps/users/oauth_views.py`, `backend/apps/users/urls.py`, `backend/apps/users/constants.py`
- Test: `backend/apps/users/tests/test_oauth_google.py`

**Interfaces:**

- Consumes: T1 helpers.
- Produces:
  - **`oauth_login`.** `GET oauth/<provider>/login/?accepted_terms=1` stores `request.session["oauth_accepted_terms"] = True`. Without the parameter it pops the key. The web sign-up page sends it; the login page does not.
  - **`_find_or_create_user(provider, user_data, accepted_terms: bool = False)`.** It raises `ConsentRequired` just before the create block, after every existing refusal. When it creates a user, it calls `record_policy_acceptance` inside the existing `transaction.atomic()`.
  - **`oauth_callback`.** It pops `oauth_accepted_terms` from the session and passes it through. On `ConsentRequired` it stores `request.session["oauth_pending_signup"] = {"provider": provider, "user_data": user_data, "created_at": <epoch seconds>}` and redirects to `{SITE_URL or the frontend base used by get_oauth_redirect_url}/signup/finish`.
  - **`POST oauth/finish/`**, a new view `oauth_finish_signup`, name `oauth_finish_signup`, with CSRF and rate limiting like `register`. It takes `{"accepted_terms": true}`.
    - Without the flag: 428 `consent_required`, and the pending entry is kept.
    - No pending entry, or one older than `OAUTH_PENDING_SIGNUP_TTL_SECONDS = 900`: 400 `{"error": "Your sign-up expired. Please sign in again.", "code": "signup_expired"}`, and the entry is dropped.
    - Otherwise: pop the entry, call `_find_or_create_user(provider, user_data, accepted_terms=True)`, `django_login`, and return 200 `{"success": true}` with `set_jwt_cookies`.

- [ ] **Step 1: Write the failing tests.** Mock `_handle_google_callback` the way the file already does.
  - `test_callback_new_user_without_consent_redirects_to_finish`: the response is a 302 to a URL ending `/signup/finish`, no `User` row exists, and the session holds `oauth_pending_signup`.
  - `test_login_with_accepted_terms_then_callback_creates_user`: hit login with `?accepted_terms=1`, then the callback. A user exists with the version stamped.
  - `test_callback_existing_user_logs_in_without_consent`: an existing verified user gets the same success redirect as today, and their fields stay null.
  - `test_finish_with_flag_creates_user_and_sets_cookies`: 200, a user with the version, and the JWT cookies present.
  - `test_finish_without_flag_428_keeps_pending`.
  - `test_finish_expired_pending_refused`: with `created_at` 901 s ago, expect 400 `signup_expired`, no user, and the key removed.
  - `test_finish_without_pending_refused`: 400 `signup_expired`.
  - `test_github_callback_new_user_also_gated`: the backend supports GitHub OAuth (`SUPPORTED_PROVIDERS`) even though the web has no GitHub button. A new GitHub user without consent is redirected to `/signup/finish` the same way.
- [ ] **Step 2:** Run `venv/bin/pytest apps/users/tests/test_oauth_google.py -q`. Expected: the new tests fail.
- [ ] **Step 3:** Implement as stated in Interfaces. Remember `get_permissions` / `@permission_classes([AllowAny])` the way `register` does it, and `@extend_schema` for spectacular.
- [ ] **Step 4:** Run `venv/bin/pytest apps/users -q` and the spectacular check from T3. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(users): web OAuth sign-up waits for consent on a finish step`.

### Task 5: Legal document pages (web)

**Files:**

- Create: `web/src/content/legal/{privacy,terms}.{en,fr,es}.md`. These are stub content for now; T6 writes the text. Each stub has the version comment, the DRAFT line, an H1 and one paragraph.
- Create: `web/src/content/legal/index.ts`, `web/src/pages/legal/LegalDocumentPage.tsx` and its test, and `web/scripts/check-legal-publish.mjs` with `web/scripts/check-legal-publish.test.mjs` (or a `.test.ts` beside it that Vitest picks up)
- Modify: `web/src/App.tsx` (public routes `/privacy` and `/terms`), `web/package.json` (add `marked`, and a `prebuild` script `node scripts/check-legal-publish.mjs`), and the site footer component (links "Privacy" and "Terms"; find it with `grep -rn "footer" web/src/components -il`)
- Test: `web/src/content/legal/index.test.ts`, `web/src/pages/legal/LegalDocumentPage.test.tsx`

**Interfaces:**

- Produces:
  - `type LegalDoc = 'privacy' | 'terms'` and `type LegalLang = 'en' | 'fr' | 'es'`
  - `pickLanguage(param: string | null, navigatorLanguage: string | undefined): LegalLang`
  - `getLegalMarkdown(doc: LegalDoc, lang: LegalLang): string`, loaded with Vite `?raw` imports
  - `<LegalDocumentPage doc="privacy" />`
    - Reads `?lang`.
    - Renders `DOMPurify.sanitize(marked.parse(md))`.
    - Shows a language switcher of three links (English, Français, Español) that set `?lang`.
    - Sets the document title.
  - `check-legal-publish.mjs`
    - When `process.env.LEGAL_PUBLISH === '1'`, it exits 1 and lists each file that still contains `[[` or `DRAFT — pending legal review`.
    - Otherwise it exits 0 silently.
    - It exports `findUnpublishable(files: {name, text}[]): string[]` for the test.

- [ ] **Step 1: Write the failing tests.**
  - `pickLanguage`:
    - `('fr', 'en-US')` → `fr`
    - `(null, 'fr-CA')` → `fr`
    - `(null, 'es-MX')` → `es`
    - `(null, 'pt-BR')` → `en`
    - `(null, undefined)` → `en`
    - `('de', 'es-ES')` → `es`: an unknown parameter falls back to the browser language.
  - Every doc×lang returns a non-empty string that contains `<!-- version: 2026-11-06 -->`.
  - `LegalDocumentPage`:
    - At `/privacy?lang=fr` it renders the French H1.
    - The switcher links point to `?lang=en|fr|es`.
    - A `<script>` placed in the markdown, through a mocked `getLegalMarkdown`, is not in the DOM.
  - `findUnpublishable`: it flags a file with `[[COMPANY_NAME]]` and a file with the DRAFT line, and passes a clean one.
- [ ] **Step 2:** Run `cd web && npx vitest run src/content/legal src/pages/legal scripts`. Expected: FAIL.
- [ ] **Step 3:** Implement. Run `npm install marked` and keep the exact version npm writes. Make the routes public, outside `ProtectedLayout`, and lazy-load them like the other pages.
- [ ] **Step 4:** Run the same vitest, then `npm run type-check && npm run lint`, then `npm run build`. The build runs with `LEGAL_PUBLISH` unset, so it passes. Run `LEGAL_PUBLISH=1 node scripts/check-legal-publish.mjs; echo $?`. Expected: tests pass, and the last command prints the six files and `1`.
- [ ] **Step 5:** Commit: `feat(web): /privacy and /terms pages from markdown, with a publish guard`.

### Task 6: Write the policy texts (content)

**Files:**

- Create: `docs/legal/data-inventory.md`, the source of truth the policy is written from. Copy it from the list below.
- Replace the six stubs in `web/src/content/legal/`.
- Test: the T5 tests still pass. Add a backend test, `backend/apps/users/tests/test_legal_documents.py`:
  - `test_documents_carry_current_version`: it reads the six files via a path relative to `settings.BASE_DIR.parent / "web/src/content/legal"` and asserts each contains `<!-- version: {LEGAL_POLICY_VERSION} -->`.

**Required content.** These are spec sections A1 and decisions 5–13. The implementer writes the prose, plainly worded, with these facts and no others.

- **Data inventory** (write this into `docs/legal/data-inventory.md` and use it for the policy):
  - **Account.** Email, username, first and last name, bio, free-text location, website, avatar (public storage, EXIF removed), Firebase UID, Google or GitHub sign-in, and the policy version accepted.
  - **Scans.** Photos are stored privately and re-encoded without EXIF. Undecided scans are deleted after 24 h; kept ones stay until removed or the account is deleted. Results go to Plant.id/Kindwise and PlantNet.
  - **Garden data**, and Firestore saved plants (`users/{uid}/identified_plants`).
  - **Forum.** Posts, topics, private messages, reports, blocks and mutes.
  - **Newsletter.** The subscription.
  - **Push tokens.** FCM/APNs on mobile and web push.
  - **Email.** Delivery and bounce records (90 days), click records (90 days), and a hashed suppression marker kept indefinitely.
  - **Blog page views.** IP, user agent and referrer, for 90 days.
  - **Rate limiting.** IP addresses held briefly in memory.
  - **Audit log.** 90 days.
  - **Processors:**
    - Plant.id/Kindwise and PlantNet: photos.
    - Google Firebase: login, saved plants, push.
    - Apple: push.
    - OpenAI: forum text, only while an optional forum AI feature is switched on.
    - Sentry: crash reports. On the web, about 10% of sessions and every session with an error are recorded, with text masked.
    - Cloudflare: website and file storage.
    - Railway: servers in the US.
    - Resend: email.
    - YouTube/Vimeo: embeds a user posts.
    - Apple and Google: in-app purchase status from store receipts. In-app purchase is being built before launch.
  - **Not done:** no ads, no analytics or tracking SDKs, and no sale of data.
  - **Storage location.** In the United States. This is the cross-border transfer disclosure.
- **Privacy Policy sections:**
  - Who we are (`[[COMPANY_NAME]]`, `[[COMPANY_ADDRESS]]`, `[[CONTACT_EMAIL]]`)
  - Privacy officer (`[[PRIVACY_OFFICER_NAME]]`)
  - What we collect and why
  - Who receives it
  - Where it is stored
  - How long it is kept. Include account deletion: what is erased, and what is kept (a deleted-account record with a hashed email; addresses deleted for abuse or under-13 are blocked from signing up again; moderation records; quoted text and mentions in other people's posts; the other person's copy of private messages).
  - Your rights: access, correction, deletion in the app or at `/delete-account`, portability, and withdrawing consent, all by email to `[[CONTACT_EMAIL]]` within 30 days. Also how to complain to the regulator: the OPC (Canada), the CAI (Quebec) and the INAI or its successor (Mexico).
  - Children: the minimum age is 13, and those accounts are deleted.
  - Changes to the policy
  - The effective date (the version)
- **Spanish Privacy Policy.** It is structured as an *aviso de privacidad* (LFPDPPP): the identity and address of the *responsable*, the purposes (primary and secondary), the data, transfers, ARCO rights and how to exercise them, revoking consent, and changes to the notice.
- **French Privacy Policy.** It is equal in content to the English, with the *responsable de la protection des renseignements personnels* named.
- **Terms:**
  - Eligibility: 13 and older, and under 18 with a parent's permission.
  - Plant advice is not a guarantee. Identifications and diagnoses are automated and can be wrong. Do not eat a plant, or treat a person or pet, on the app's word alone.
  - Forum rules and moderation.
  - Users own their content and license it to us for display.
  - Premium is billed, renewed and refunded by Apple or Google under their rules. Deleting the account does not cancel a subscription.
  - Account deletion is available at any time, and we may close accounts that break the rules.
  - Provided as is, with limited liability.
  - Governing law: `[[GOVERNING_LAW]]`.
  - "Nothing here removes rights your local law gives you."
  - Changes to the Terms, and contact.

- [ ] **Step 1:** Write `test_legal_documents.py`. Run `cd backend && venv/bin/pytest apps/users/tests/test_legal_documents.py -q`. Expected: PASS against the stubs. It guards the version only.
- [ ] **Step 2:** Write the inventory doc and the six documents. Each one keeps the version comment and the DRAFT line.
- [ ] **Step 3:** Run `grep -c "\[\[" web/src/content/legal/*.md` (each file has at least 1) and the T5 vitest plus the backend test. Expected: PASS.
- [ ] **Step 4:** Commit: `docs(legal): draft privacy policy and terms in en/fr/es`.

### Task 7: Consent on the web sign-up and finish pages

**Files:**

- Modify: `web/src/pages/auth/SignupPage.tsx` and its test, `web/src/services/authService.ts`, `web/src/components/auth/GoogleSignInButton.tsx` and its test
- Create: `web/src/components/auth/ConsentCheckbox.tsx` and its test, `web/src/pages/auth/FinishSignupPage.tsx` and its test
- Modify: `web/src/App.tsx` (public route `/signup/finish`), and the backend error-code messages in `GoogleCallbackPage.tsx` if a new code is added

**Interfaces:**

- Consumes: T2 `register/` with `accepted_terms`; T4 `oauth/<provider>/login/?accepted_terms=1` and `POST /api/auth/oauth/finish/`; T5 routes.
- Produces:
  - `<ConsentCheckbox checked onChange />`, with the exact copy. Its links open `/privacy` and `/terms` in a new tab (`target="_blank" rel="noopener"`), so the form keeps its state.
  - `authService.register(...)` sends `accepted_terms: true`.
  - `getGoogleOAuthUrl({ acceptedTerms }: { acceptedTerms?: boolean })` appends `?accepted_terms=1` when it is true.
  - `GoogleSignInButton` takes `acceptedTerms?: boolean` and passes it on.
  - `finishOAuthSignup(): Promise<void>` posts with CSRF and credentials.

- [ ] **Step 1: Write the failing tests.**
  - **SignupPage:**
    - Create account and "Sign up with Google" are disabled until the box is ticked.
    - The two links have `href="/privacy"` and `"/terms"`.
    - Submitting sends `accepted_terms: true`.
    - The old plain-text "By creating an account…" line is gone.
  - **GoogleSignInButton:** with `acceptedTerms`, the fetched URL ends `?accepted_terms=1`; without it, there is no query.
  - **FinishSignupPage:**
    - It shows the checkbox and a "Finish signing up" button that stays disabled until the box is ticked.
    - On success it calls `refreshUser` and navigates to `/`.
    - On `signup_expired` it shows "Your sign-up expired. Please sign in again." with a link to `/login`.
- [ ] **Step 2:** Run `cd web && npx vitest run src/pages/auth src/components/auth`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the same vitest, plus `npm run type-check && npm run lint`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(web): consent checkbox on sign-up and an OAuth finish step`.

### Task 8: Legal links and the register-screen checkbox (mobile)

**Files:**

- Create: `plant_community_mobile/lib/features/legal/legal_links.dart`, `plant_community_mobile/lib/features/auth/consent_checkbox.dart`
- Modify: `plant_community_mobile/lib/features/auth/register_screen.dart`, `plant_community_mobile/lib/features/settings/settings_screen.dart` (two tiles, "Privacy Policy" and "Terms of Service")
- Test: `plant_community_mobile/test/features/legal/legal_links_test.dart`, `plant_community_mobile/test/features/auth/register_screen_test.dart` (extend or create)

**Interfaces:**

- Produces:
  - `enum LegalDoc { privacy, terms }`
  - `String legalLangFor(Locale locale)`
  - `Uri legalUri(LegalDoc doc, Locale locale)`, giving `https://houseplant-md.com/<privacy|terms>?lang=<x>`
  - `Future<void> openLegalDoc(BuildContext context, LegalDoc doc)`, which uses `launchUrl(uri, mode: LaunchMode.inAppBrowserView)` and shows a SnackBar "Couldn't open the page" if that fails
  - `ConsentCheckbox({required bool value, required ValueChanged<bool> onChanged})`, the exact copy with two tappable links (`TextSpan` + `TapGestureRecognizer`, disposed properly), and a tap target of at least 48 dp
  - `RegisterScreen` keeps `_acceptedTerms`. Create Account and `GoogleSignInButton(enabled: …)` are enabled only when it is true.
  - `GoogleSignInButton` gains `acceptedTerms: bool = false` and passes it to `signInWithGoogle(acceptedTerms:)`, which T9 implements. For this task, only the parameter is plumbed.

- [ ] **Step 1: Write the failing tests.**
  - `legalLangFor`: `fr_CA` → `fr`, `es_MX` → `es`, `pt_BR` → `en`, `en_US` → `en`.
  - `legalUri(privacy, Locale('fr','CA'))` is `https://houseplant-md.com/privacy?lang=fr`.
  - Register screen:
    - Create Account and Continue with Google are disabled at first.
    - Tapping the checkbox enables both.
    - The checkbox text contains the exact copy.
- [ ] **Step 2:** Run `cd plant_community_mobile && flutter test test/features/legal test/features/auth/register_screen_test.dart` (sandbox disabled). Expected: FAIL.
- [ ] **Step 3:** Implement, using Canopy tokens and following `docs/rules/flutter.md`.
- [ ] **Step 4:** Run the same tests and `flutter analyze`. Expected: PASS, with no issues.
- [ ] **Step 5:** Commit: `feat(mobile): consent checkbox on register and legal links`.

### Task 9: Consent through the token exchange (mobile)

**Files:**

- Modify: `plant_community_mobile/lib/services/auth_service.dart`, `plant_community_mobile/lib/features/auth/login_screen.dart` (`GoogleSignInButton`)
- Create: `plant_community_mobile/lib/features/auth/consent_sheet.dart`, and wire it where the auth state is listened to at the root (`main.dart` or the app shell, wherever `emailVerificationRequired` is handled today)
- Test: `plant_community_mobile/test/services/auth_service_consent_test.dart`, `plant_community_mobile/test/features/auth/consent_sheet_test.dart`

**Interfaces:**

- Consumes: T3 (428 `consent_required`; `accepted_terms` in the exchange body), T8 `ConsentCheckbox` and `acceptedTerms` plumbing.
- Produces:
  - **`AuthState.consentRequired`** (bool), true after a 428 `consent_required` from either exchange call: the launch/sign-in exchange and the refresh exchange near line 850.
  - **Accepted-terms storage.** `flutter_secure_storage` key `accepted_terms_uid` stores the Firebase uid whose owner ticked the box.
    - It is written by `registerWithEmailPassword` after `createUserWithEmailAndPassword` (the register screen only calls it when ticked), and by `signInWithGoogle(acceptedTerms: true)` once `signInWithCredential` returns.
    - A private in-memory `_acceptedTermsPending` flag covers the gap before the uid is known, so the immediate listener-triggered exchange sends the flag. It is set at the start of `signInWithGoogle(acceptedTerms: true)` and cleared in `finally`.
    - The key is deleted after a successful exchange.
  - **The exchange body.** `{'firebase_token': token, if (_acceptedTermsPending || storedUid == user.uid) 'accepted_terms': true}`.
  - **`Future<void> acceptTermsAndRetry()`.** Stores the current uid, clears `consentRequired`, and reruns `_exchangeFirebaseTokenForJWT(currentUser)`.
  - **`Future<void> declineTerms()`.**
    - Tries `currentUser.delete()`. On `requires-recent-login` or any error it falls through.
    - Then signs out of Firebase and Google, and clears the key.
    - Never throws.
  - **`ConsentSheet`.** A modal bottom sheet shown when `consentRequired` turns true.
    - Title "One more step".
    - The `ConsentCheckbox`.
    - A "Continue" button, enabled when ticked, that calls `acceptTermsAndRetry`.
    - A "Cancel" button that calls `declineTerms`.
    - Dismissing it by dragging or tapping outside counts as Cancel.

- [ ] **Step 1: Write the failing tests.** Use the existing fakes or mocks for `FirebaseAuth`, the API service and secure storage, matching the patterns in the existing auth_service tests.
  - **`exchange sends accepted_terms when stored uid matches`:** stored uid `u1`, current user `u1`. The posted body contains `accepted_terms: true`.
  - **`exchange omits accepted_terms for an existing user with no stored uid`.**
  - **`consent sheet shows on 428 and retry sends accepted_terms`:**
    - The first exchange returns 428 `consent_required`, so `state.consentRequired` is true.
    - `acceptTermsAndRetry()` sends a second exchange with the flag.
    - On 200, `consentRequired` is false and the key is deleted.
  - **`declineTerms deletes the firebase user and signs out`:** `delete` is called, then `signOut`. When `delete` throws, `signOut` still runs.
  - **`google sign-in with acceptedTerms sends the flag on the first exchange`.**
  - **`428 is not mistaken for unverified email`:** `emailVerificationRequired` stays false.
  - **ConsentSheet widget:** Continue is disabled until ticked, and Cancel calls `declineTerms`.
- [ ] **Step 2:** Run `flutter test test/services/auth_service_consent_test.dart test/features/auth/consent_sheet_test.dart`. Expected: FAIL.
- [ ] **Step 3:** Implement. Run `flutter pub run build_runner build --delete-conflicting-outputs` if a provider annotation changes.
- [ ] **Step 4:** Run `flutter test` (the full suite) and `flutter analyze`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(mobile): consent sheet for sign-ups the server refuses without acceptance`.

### Task 10: Remove the unused location permission (mobile)

**Files:**

- Modify: `plant_community_mobile/pubspec.yaml` (drop `geolocator`; nothing in `lib/` imports it), `plant_community_mobile/ios/Runner/Info.plist` (drop `NSLocationWhenInUseUsageDescription` and its string), `pubspec.lock` (from `flutter pub get`), and `ios/Podfile.lock` if `pod install` changes it

- [ ] **Step 1:** Run `grep -rn "geolocator\|Geolocator" plant_community_mobile/lib plant_community_mobile/test`. Expected: no output. If anything matches, stop and report.
- [ ] **Step 2:** Remove both entries, then run `flutter pub get`.
- [ ] **Step 3:** Run `flutter analyze && flutter test`. Expected: PASS. Run `grep -c NSLocation plant_community_mobile/ios/Runner/Info.plist`. Expected: `0`.
- [ ] **Step 4:** Commit: `chore(mobile): drop unused geolocator and location permission string`.

### Task 11: Docs and full verification

**Files:**

- Modify: root `CLAUDE.md`. Add one Critical-Gotcha-style line under Working Conventions or the users section: "Every path that creates a `User` must require `accepted_terms` (428 `consent_required`); see `apps/users/consent.py`."
- Modify: `plant_community_mobile/FLUTTER_COMPLETION_PLAN.md:767`. Tick the item and note "drafts; legal review and company details pending".
- Modify: `docs/LEARNINGS.md` only if something non-obvious bit during the build.

- [ ] **Step 1:** Backend: `cd backend && venv/bin/pytest -q -p no:cacheprovider`, `venv/bin/ruff check .`, `venv/bin/python -m mypy`, `venv/bin/python manage.py check`, `venv/bin/python manage.py makemigrations --check --dry-run`, and `venv/bin/python manage.py spectacular --validate --fail-on-warn > /dev/null`. Expected: all clean, with the pass count recorded.
- [ ] **Step 2:** Web: `cd web && npm run test -- --run && npm run type-check && npm run lint && npm run build`. Expected: clean.
- [ ] **Step 3:** Mobile: `cd plant_community_mobile && flutter analyze && flutter test`. Expected: clean, with the count recorded.
- [ ] **Step 4:** Commit: `docs: consent gate notes and completion-plan tick`.

## Owner follow-ups (not tasks)

- Fill in the `[[…]]` blanks once the company is registered. Get a lawyer review of the English, and fluent reviews of the French and Spanish. Then remove the DRAFT lines and set `LEGAL_PUBLISH=1` in the Cloudflare build. **Not before Plan B is live in prod:** the policy describes in-app deletion and `/delete-account`, which Plan B builds.
- Enter `https://houseplant-md.com/privacy` as the Privacy Policy URL in App Store Connect and Google Play Console.
