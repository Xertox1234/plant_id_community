---
status: pending
priority: p1
issue_id: "717"
tags: [mobile, ios, auth, firebase, app-store, owner]
dependencies: []
---

# Mobile: add "Continue with Apple" for App Store review

## Problem

The iOS app offers Google sign-in (`google_sign_in`, `AuthService.signInWithGoogle`
in `plant_community_mobile/lib/services/auth_service.dart`) next to email and
password. App Store Review Guideline 4.8 (Login Services): an app that uses a
third-party login such as Google must also offer an equivalent login option
that limits data collection to name and email, lets the user keep their email
private, and does not track them without consent. Sign in with Apple is the
standard way to meet this, and the owner decided to use it (2026-11-19). Without
it, App Review will reject the public release.

## Findings

- The backend is already prepared. `FIREBASE_ALLOWED_SIGN_IN_PROVIDERS`
  (`backend/apps/users/constants.py`) accepts `apple.com`, and
  `account_links.PROVIDER_NAMES` labels it "Apple". The Firebase token
  exchange (`firebase_auth_views.py`) treats Apple like Google for linking and
  verified email.
- The mobile app has no Apple sign-in code and no `sign_in_with_apple`
  dependency. Firebase Auth does Apple natively (`AppleAuthProvider` with
  `FirebaseAuth.signInWithProvider`), so a separate plugin may not be needed.
- An Apple user can hide their email. Firebase then receives a
  `@privaterelay.appleid.com` address. Apple delivers mail to that address
  only from a sender domain registered under Sign in with Apple → Email
  Communication in the Apple Developer account. Without that, the backend's
  verification, notification and digest emails (sent through Resend) are
  silently dropped.
- Apple sends the user's name only on the first sign-in. If the app does not
  pass it on that first sign-in, it is lost.
- Guideline 5.1.1(v): an app with Sign in with Apple must revoke the user's
  Apple tokens when the account is deleted (FlutterFire:
  `FirebaseAuth.revokeTokenWithAuthorizationCode`). The current deletion flow
  is `request_account_deletion` in `backend/apps/users/deletion.py` plus
  `delete_account_screen.dart` on mobile.
- Web sign-in is Django Google OAuth only (GitHub was removed on 2026-11-19).
  Guideline 4.8 applies to the iOS app. Apple on the web is optional, and out
  of scope here.

## Recommended Action

1. Owner setup:
   - In the Apple Developer account, enable the Sign in with Apple capability
     on the app ID `com.plantcommunity.plantCommunityMobile`.
   - Register the email sender domain under Sign in with Apple → Email
     Communication.
   - In Firebase Authentication (project `plant-community-prod`), enable the
     Apple provider.
2. Add the capability to the iOS Runner entitlements. Add a "Continue with
   Apple" button to the login and register screens using Apple's button style,
   placed at least as prominently as Google. It runs through the existing
   Firebase → Django exchange with the same `accepted_terms` consent gate.
3. On the first sign-in, pass Apple's given and family name to the backend
   exchange.
4. On account deletion for an Apple-linked user, revoke the Apple token
   before the account is removed.
5. Android: hide the button, or use Firebase's web flow, as the owner decides
   during triage. Guideline 4.8 is iOS-only.
6. Update the privacy policy (en/es/fr in `web/src/content/legal/`) to name
   Apple sign-in and the private relay address. Decide during triage whether
   this is a material change that needs a `LEGAL_POLICY_VERSION` bump.

## Acceptance Criteria

- [ ] iOS login and register screens show "Continue with Apple" in Apple's
      button style; a widget test covers both screens.
- [ ] A new Apple sign-up goes through the consent step and creates one
      Django account; a returning Apple sign-in reaches the same account.
      Backend tests cover an `apple.com` exchange with a
      `privaterelay.appleid.com` email.
- [ ] Apple's name from the first sign-in is stored on the new account
      (test).
- [ ] Deleting an Apple-linked account revokes the Apple token (test with
      the revoke call mocked).
- [ ] Owner: on a real iPhone (TestFlight), sign up with Apple using "Hide My
      Email", receive the verification or welcome email at the relay address,
      then delete the account — record the date and build number.
- [ ] Privacy policy (en/es/fr) mentions Apple sign-in.

## Work Log

### 2026-11-19 - Filed

- Owner: "create a todo to add continue with apple as it is required by
  Apple". Filed alongside the GitHub sign-in removal PR.
