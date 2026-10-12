---
status: pending
priority: p4
issue_id: "607"
tags: [backend, mobile, avatars, auth, openapi, follow-ups]
dependencies: []
---

# Follow-ups from PR #1053 (todos 587 and 599, avatar sRGB conversion, auth exchange and OpenAPI 429 gate)

## Problem

Todo-sweep run 2026-10-11-2219 merged PR #1053 (todos 587 and 599, avatar sRGB conversion, auth exchange and OpenAPI 429 gate). The non-blocking review findings are below. The curator merged duplicates and checked each item against main, and the refuter dismissed what is listed as dropped. An item the curator did not return was kept as stored, unchecked. Line numbers are as of the PR head, so re-check each against main before acting on it.

**Item 1/3** (one bug, two locations) is a regression from #1053: an RGB PNG with a tRNS colour key and an iCCP profile loses its transparency in the new sRGB conversion. The cap of 10 left out 9 more locations.

## Findings

PR #1053 (todo sweep run 2026-10-11-2219, group g5, todos 587, 599); follow-ups: verified; 3 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/users/avatars.py:156` An RGB PNG with both a tRNS colour key and an iCCP profile loses its transparency: has_alpha makes mode RGBA, and_to_srgb's profileToProfile(RGB->RGBA) returns opaque pixels (key pixel alpha 255). The old convert('RGBA') applied the key (alpha 0). Reproduced on Pillow 12.3. | also: avatars.py:492 An RGB PNG that has both a tRNS colour key and an iCCP profile loses its transparency. has_alpha is true, so mode is RGBA, and profileToProfile(RGB->RGBA) returns opaque pixels with info['transparency'] gone. Key pixel came back (1,2,3,255) instead of (1,2,3,0).
2. **medium** `plant_community_mobile/lib/services/auth_service.dart:530` Item 2 fixed only _surfaceAccountConflict. The launch exchange's ApiException and catch-all paths (530, 557) check_isCurrentExchange once, await _clearJWT(), then setAuthToken(null) and write state with no re-check, so an overtaken exchange can wipe a newer one's tokens, bearer and state.
3. **medium** `backend/apps/users/avatars.py:492` An RGB PNG that has both a tRNS colour key and an iCCP profile loses its transparency. has_alpha is true, so mode is RGBA, and profileToProfile(RGB->RGBA) returns opaque pixels with info['transparency'] gone. Before this change, convert('RGBA') applied the key. Reproduced with Pillow 12.3: the key pixel came back as (1,2,3,255) instead of (1,2,3,0).
4. **low** `backend/apps/core/security.py:417` Item 6 pseudonymizes IPs only in the account_lockout alert. The brute_force_login alert (raw ip_address and usernames, line 417) and suspicious_login_frequency (raw username and IP, line 484) still go out as ERROR logs to Sentry; the new test docstring overstates the coverage.
5. **low** `plant_community_mobile/test/services/auth_service_test.dart:1569` _OnRemoveMap was inserted between_Harness's doc comment and the _Harness class, so the 'Wires a [ProviderContainer]...' doc now merges into_OnRemoveMap's doc block and _Harness has no doc comment. | also: auth_service_test.dart:1571 The new_OnRemoveMap class was inserted between _Harness's doc comment and_Harness. That comment now documents _OnRemoveMap, and_Harness has no doc comment. | auth_service_test.dart:1568 The existing doc comment for _Harness now sits above the new_OnRemoveMap class, so _Harness lost its doc and_OnRemoveMap has a misleading two-part doc. | _OnRemoveMap's doc now opens with the 'Wires a [ProviderContainer]...' text, and_Harness has no doc. | The two doc comments merge into one doc block on _OnRemoveMap, and_Harness loses its doc.
6. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:243` _missing_429 silently skips any rate-limited route whose trimmed path is not in schema['paths'], so if the prefix trimming drifts, coverage shrinks without a failure. Only the three hardcoded 'known' operations guard against this.
7. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:231` The 429 gate detects only function-based @api_view views through django-ratelimit's closure. Class-based views using method_decorator are skipped by design, so they can omit 429 without a failure. The docstring says so, but nothing else covers them.
8. **low** `backend/apps/blog/newsletter_views.py:172` newsletter_unsubscribe_one_click documents 429 for both GET and POST, but its @ratelimit uses method='POST', so a GET never gets a 429. The gate only checks for a missing 429, never an extra one, so it misses this.
9. **low** `plant_community_mobile/test/services/auth_service_test.dart:1571` The new _OnRemoveMap class was inserted between_Harness's doc comment and _Harness. That comment ('Wires a [ProviderContainer] with fakes…') now documents_OnRemoveMap, and _Harness has no doc comment.
10. **low** `plant_community_mobile/test/services/auth_service_test.dart:1568` The existing doc comment for _Harness ('Wires a ProviderContainer...') now sits above the new_OnRemoveMap class, so _Harness lost its doc and_OnRemoveMap has a misleading two-part doc. | also: The existing doc comment on _Harness ('Wires a ProviderContainer...') now sits above the new_OnRemoveMap class, so the two doc comments are merged and _Harness lost its own.

9 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1053 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g5`.
