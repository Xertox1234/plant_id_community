---
status: pending
priority: p4
issue_id: "651"
tags: [notifications, preferences, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Finding 5: keep the shared 30/h profile_updates throttle; on a 429 the web and mobile master-switch toggles roll back and show a friendly 'too many changes, try again in a few minutes' message, with tests. Fix the other findings where cheap; record any declined finding in the Work Log with a reason; file no new todos (2026-10-12)"
---

# Follow-ups from PR #1122 (todo 620, notification preferences)

## Problem

Todo-sweep run 2026-10-12-1700 merged PR #1122 (todo 620, the notification policy matrix and web/mobile
preference parity). The non-blocking review findings are below. The curator merged duplicates and checked each
item against main, and the refuter tried to refute what was left; the items that survived are listed.

## Findings

PR #1122 (todo sweep run 2026-10-12-1700, group g1, todos 620); follow-ups: verified.

1. **low** `plant_community_mobile/lib/features/profile/profile_screen.dart:468` The mobile 'Email notifications' subtitle says turning it off 'stops every optional email', but the blog newsletter is deliberately not gated (notification_policy.py, docs/notifications-policy.md). A member who turns it off in the app still gets the newsletter. Web copy states the exemption; mobile does not.
2. **low** `plant_community_mobile/lib/features/profile/forum_notification_settings_card.dart:93` The save-failure snackbar and the load-error subtitle interpolate the raw exception ($e, $error). An ApiException/DioException toString can show request URLs, server detail or a Dio dump to the user. | also: The save-failure snackbar and the load-error subtitle interpolate the raw exception (`$e`, `$error`). An ApiException/DioException toString can show request URLs or server detail to the user. | The failure snackbar and the load-error subtitle (line 161) interpolate the raw exception ($e), which can show a DioException dump to the user.
3. **low** `plant_community_mobile/lib/features/forum/models/forum_notification_settings.dart:64` fromJson turns a missing or non-string digest_frequency into 'off', so a skewed response shows the digest as off and the next tap PATCHes weekly. Web Settings treats missing fields as a load problem and never guesses.
4. **low** `backend/apps/users/tests/test_notification_policy.py:336` The second half of the newsletter test proves nothing. It creates a user and asserts no BlogNewsletter row exists, but no code path could create one, and the master switch is never toggled.
5. **low** `web/src/pages/SettingsPage.tsx:829` Master-switch toggles go through PATCH /auth/user/update/, which shares the 30/h profile_updates throttle with the profile form. Rapid toggling across both clients can hit it, and the user then sees only a raw throttle error.
6. **low** `web/src/pages/SettingsPage.tsx:172` The optimistic PATCH replaces profile with the server response wholesale. If the response omits a switch field (deploy skew), that switch disappears after a successful save.
7. **low** `plant_community_mobile/lib/features/profile/forum_notification_settings_card.dart:129` The card never checks brightness and colours only through theme tokens. That is fine for dark mode, but no dark-theme test covers the `_Note` text.
8. **low** `web/src/pages/SettingsPage.tsx:1061` The new user-facing flow (account-wide master switches on Settings, shared with mobile) has unit coverage but no E2E case, which the checklist asks for new user-facing flows (web/E2E_TESTING_GUIDE.md).

11 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: web/src/pages/SettingsPage.test.tsx:1030 Destructured `_e`/`_f` unused variables used to strip fields may trip no-unused-vars lint, depending on the config's underscore ignore pattern. (fixed on main: Code is unchanged at test:1021, but origin/main web/eslint.config.js sets @typescript-eslint/no-unused-vars varsIgnorePattern '^[A-Z_]', which matches `_e`/`_f`, so the lint concern does not apply.; the refuter agreed: web/eslint.config.js:67-69 sets @typescript-eslint/no-unused-vars with varsIgnorePattern '^[A-Z_]' for ts/tsx files, so the `_e` and `_f` destructured vars at test:1021 are exempt. The lint concern does not apply.)

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1122 review (todo sweep run 2026-10-12-1700)

Filed by the closing step of the run from `state.py followups-md g1`.
