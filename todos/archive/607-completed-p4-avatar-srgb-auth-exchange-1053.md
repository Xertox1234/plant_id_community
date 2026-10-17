---
status: completed
priority: p4
issue_id: "607"
tags: [backend, mobile, avatars, auth, openapi, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Item 4 declined: keep the raw IP in the brute_force_login/suspicious_login_frequency alerts (deliberate, security.py:427), record the reason; fix the other items (2026-10-11)"
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-11 - Filed from the PR #1053 review (todo sweep run 2026-10-11-2219)

Filed by the closing step of the run from `state.py followups-md g5`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-0349)

- Items 1/3: `backend/apps/users/avatars.py` takes the alpha channel from the source (`convert("RGBA")`, which applies a tRNS key) before the ICC conversion and puts it back after, so a keyed RGB PNG with a profile stays transparent. Test: `test_a_tagged_png_keeps_its_trns_colour_key` in `backend/apps/users/tests/test_avatar_privacy.py` (fails on the old code with `255 != 0`).
- Item 2: the launch exchange's `ApiException` and catch-all paths in `plant_community_mobile/lib/services/auth_service.dart` now clear through `_clearJWTWhileCurrent`, which re-checks the exchange before each delete and after the last, and only then clear the bearer and write state; `_surfaceAccountConflict` uses the same helper. Two tests in the `todo 607` group of `plant_community_mobile/test/services/auth_service_test.dart` (both fail on the old code). Items 5/9/10: `_Harness`'s doc comment moved back above `_Harness`.
- Item 4: declined (owner decision 2026-10-11). The `brute_force_login` and `suspicious_login_frequency` alerts keep the raw IP on purpose so an operator can block it (`backend/apps/core/security.py`, the comment at the failed-login log line, todo 435 finding 5). The overstated docstring of `test_lockout_security_alert_carries_no_raw_client_ip` (`backend/apps/users/tests/test_account_lockout.py`) now says only the `account_lockout` alert is pseudonymized.
- Items 6/7/8: `backend/apps/core/tests/test_openapi_rate_limit_429.py` now fails on a limited operation missing from the schema (6), walks class-based views and ViewSet actions under `method_decorator` (7), and fails on a 429 documented for a method the limit does not cover (8). Item 7 found 14 undocumented ViewSet operations (garden calendar, disease requests): they are named in a new `_throttled_actions` attribute that the existing schema hook in `backend/plant_community_backend/api_schema.py` reads, and the hook now matches paths with parameter names blanked (a ViewSet's `{pk}` is renamed `{id}` after preprocessing). Item 8 found two GET one-click unsubscribe operations documenting 429: `backend/apps/blog/newsletter_views.py` and `backend/apps/users/email_preferences_views.py` now document GET as a 302 redirect. New canaries cover each check.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-12-0349)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 1 -- venv/bin/python -m pytest apps/users/tests/test_avatar_privacy.py apps/core/tests/test_openapi_rate_limit_429.py apps/users/tests/test_account_lockout.py -p no:cacheprovider -q --create-db && cd ../plant_community_mobile && flutter test test/services/auth_service_test.dart` — evidence `.sweep-evidence/g7/607-ac0.txt` (not committed), last lines:

  ```text
  00:00 +58: todo 607 item 2: a launch exchange failing with an API error, overtaken mid-clear, keeps the newer tokens
  00:00 +59: todo 607 item 2: a launch exchange failing with any other error, overtaken mid-clear, keeps the newer tokens
  00:00 +60: session-expiry exemption signOut's FCM-clear PATCH carries skipSessionExpiryKey
  00:00 +61: session-expiry exemption a real 401 on an exempt request does not trigger the session-expired handler, while an unexempt one does
  00:00 +62: All tests passed!
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-12-0349)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
