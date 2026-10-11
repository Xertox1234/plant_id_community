---
status: pending
priority: p4
issue_id: "567"
tags: [mobile, backend, auth, follow-ups]
dependencies: []
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

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log
