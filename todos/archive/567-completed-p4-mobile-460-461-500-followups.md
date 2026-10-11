---
status: completed
priority: p4
issue_id: "567"
tags: [mobile, backend, auth, follow-ups]
dependencies: []
triage: needs-design
triaged: 2026-10-11
blocked_on: "Owner choice for finding 1: turn revocation checking on, or retract the documented 401 promise"
owner_decision: "F1: retract the promise. Drop the revoked/disabled 401 from the schema and docs, delete the dead UserDisabledError branch, no check_revoked. Findings 2-9 are mechanical (2026-10-11)"
---

# Follow-ups from PR #1006 (todos 460, 461, 500, mobile blog/diagnose/token refresh)

## Problem

Todo-sweep run 2026-10-11-0053 merged PR #1006. Its two review rounds reported the non-blocking
findings below. The curator merged duplicates and confirmed each item is still on main; the refuter dismissed none.
Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1006 (todo sweep run 2026-10-11-0053, group g5, todos 460, 461, 500); follow-ups: verified.

1. **medium** `backend/apps/users/firebase_auth_views.py:378` Schema, docstring and FIREBASE_AUTHENTICATION.md promise a 401 for a revoked token or disabled Firebase account, but verify_id_token is called without check_revoked=True, so the UserDisabledError branch is dead and disabled/revoked users still get Django JWTs until the ID token expires. | also: The schema, docstring and FIREBASE_AUTHENTICATION.md now promise a 401 for a revoked token or a disabled Firebase account. verify_id_token is called without check_revoked=True, so neither is checked: the new UserDisabledError branch is dead, and a disabled user can still get fresh Django JWTs until the ID token expires (about 1h).
2. **medium** `plant_community_mobile/lib/services/auth_service.dart:664` F2 incomplete: in _refreshAccessToken the getIdToken FirebaseAuthException refusal branch returns null without checking_isCurrentExchange, so A's refused getIdToken after currentUser switched to B reads as _Refused and signs B out. The ApiException branch does check first.
3. **medium** `plant_community_mobile/lib/features/blog/services/blog_api.dart:336` blogInlineImageUrlProvider is a plain FutureProvider.family with no retry override, so Riverpod 3 retries a 404/deleted inline image id up to 10 times (~40 s) per image; blog_providers.dart guards this with blogRetry.
4. **medium** `backend/apps/users/firebase_auth_views.py:232` New @extend_schema on the rate-limited token exchange documents 400/401/403/409/503 but no 429, though the view is wrapped in @ratelimit.
5. **medium** `plant_community_mobile/lib/services/auth_service.dart:1028` On a refresh 409, _surfaceAccountConflict keeps state.jwtToken, so isAuthenticated stays true and the expired bearer stays stored, unlike the launch 409 it claims to mirror; every later 401 re-runs the exchange and gets 409 again. The F1 test never pins jwtToken.
6. **medium** `backend/apps/users/firebase_auth_views.py:496` Comments/docs say a post-verification bug (e.g. claim KeyError) is a 500 'Sentry sees', but the outer except Exception uses logger.error(f"...{e}") with no exc_info, so Sentry gets a message with no traceback. | also: Code moved out of the inner try now ends up in the outer `except Exception`, which calls logger.error(str(e)) with no exc_info. The new comment says a KeyError on a claim is 'a 500 that Sentry sees', but Sentry receives only a message with no traceback. | The outer `except Exception` returns 500 with `logger.error(str(e))` and no traceback. The new docstring and docs say 'Sentry sees it', but the event would carry only a message, so a post-verification bug is hard to debug. | The docstring and tests now say a post-verification bug is a 500 'Sentry sees', but the catch-all uses logger.error(str(e)) with no traceback, so the 500 has no stack trace to debug. | (merged duplicate originally reported as low at backend/apps/users/firebase_auth_views.py:495)
7. **medium** `plant_community_mobile/lib/features/blog/widgets/blog_block_view.dart:667` The link() helper wraps an InkWell in Semantics(link: true) without excludeSemantics: true, so the InkWell may add its own unlabeled focusable tap node under the link node; no test asserts the node has no children.
8. **low** `plant_community_mobile/lib/features/diagnose/diagnose_screen.dart:292` cacheWidth is the 4:3 box width but the image uses BoxFit.cover, so a photo wider than 4:3 (e.g. 16:9) decodes shorter than the box and cover upscales it ~1.33x, blurring the preview.
9. **low** `plant_community_mobile/lib/services/api_service.dart:326` When the refresher throws RefreshSupersededException only because _authGeneration moved (e.g. launch double-exchange, same user), the API session is still current but the request fails with the raw 401 'session expired' and is not re-sent.

16 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1448)

- F1 (owner decision, retract): the schema, docstring and `backend/docs/FIREBASE_AUTHENTICATION.md` now say revocation is not checked: a revoked token or a disabled account is accepted until it expires. The dead `UserDisabledError` branch is gone, and no `check_revoked`. Its test (`test_disabled_firebase_account_is_a_refusal`) only drove that dead branch; it is replaced by `test_revocation_is_not_checked`, which pins the plain `verify_id_token(token)` call. F4: the schema documents the 429 (`rate_limit_exceeded`). F6: the outer `except` uses `logger.exception`. Both are tested (schema generation, `exc_info` is the `KeyError`).
- F2: in `_refreshAccessToken`, a `FirebaseAuthException` is checked against `_isCurrentExchange` before it counts as a refusal, so a refusal for A after a switch to B throws `RefreshSupersededException`. F5: `_surfaceAccountConflict` deletes the stored JWT and leaves `jwtToken` null, as the launch 409 does. The bearer stays installed, so the request still fails with the conflict and not as overtaken. Tests pin `jwtToken`, `isAuthenticated` and storage.
- F3: `blogInlineImageUrlProvider` moved to `blog_providers.dart` with `retry: blogRetry`; tests show a 404 is looked up once and a 503 is retried. F7: the credit link's `Semantics` has a label and `onTap`, and sets `excludeSemantics`. The test asserts one link node with no children and a working semantics tap, and was mutation-checked.
- F8: `previewCacheWidth` decodes at 4/3 of the box width, which is enough for photos up to 16:9 under `BoxFit.cover`. The existing decode-width test now expects that factor, and a new test checks aspects from 9:16 to 16:9. F9: every `_authGeneration` bump comes with a new API session, so the reported case reduces to a refresh overtaken within the same session after a token was installed. `ApiService` now re-sends with that token (an `_authEpoch` change, `_authToken` set), tested with a control that re-sends nothing.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1448)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 1 -- backend/venv/bin/python -m pytest apps/users/tests/test_firebase_auth.py --create-db -q -p no:randomly && cd plant_community_mobile && flutter test test/services/auth_service_test.dart test/api_service_test.dart test/features/blog/blog_screens_test.dart test/features/diagnose/diagnose_test.dart'` — evidence `.sweep-evidence/g1/567-ac0.txt` (not committed), last lines:

  ```text
  00:02 +165 ~3: plant_community_mobile/test/features/blog/blog_screens_test.dart: todo 460 spotlight an Unsplash credit links the photographer and Unsplash separately
  00:02 +166 ~3: plant_community_mobile/test/features/blog/blog_screens_test.dart: todo 460 spotlight each credit link is ONE labelled link node with the tap (todo 567 finding 7)
  00:02 +167 ~3: plant_community_mobile/test/features/blog/blog_screens_test.dart: todo 460 spotlight each credit link is a full-size tap target
  00:02 +168 ~3: plant_community_mobile/test/features/blog/blog_screens_test.dart: todo 460 spotlight a photo that fails to load leaves no empty 2:1 box
  00:02 +169 ~3: All tests passed!
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1448)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
