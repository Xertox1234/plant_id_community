---
status: completed
priority: p4
issue_id: "632"
tags: [api, mobile, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1077 (todo 607, 429 schema gate, auth exchange)

## Problem

Todo-sweep run 2026-10-12-0349 merged PR #1077 (todo 607, 429 schema gate, auth exchange). The non-blocking review findings are below.
The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: follow-ups from this run get one extra
sweep pass.

## Findings

PR #1077 (todo sweep run 2026-10-12-0349, group g7, todos 607); follow-ups: verified.

1. **low** `backend/plant_community_backend/api_schema.py:130` `by_shape` keys every schema path with its parameter names blanked. Two paths that differ only in parameter name (e.g. `/x/{slug}/` and `/x/{id}/`) collapse to one key, so a recorded 429 could be added to the wrong operation or dropped. No such collision exists today (latent). | also: by_shape blanks all parameter names, so two schema paths that differ only in parameter name (e.g. /x/{id}/ from <int:pk> and /x/{slug}/ from <slug:slug>) collapse to one key. The dict keeps the last one, and a 429 recorded for either path is added to the wrong operation or dropped. I checked all 145 current paths and none collide, so this is latent. | `by_shape` keys every schema path with its parameter names blanked. Two paths that differ only in parameter name (e.g. `/x/{slug}/` and `/x/{id}/`) collapse to one key, so a recorded 429 could be added to the wrong operation. No such collision exists today. | `by_shape` keys every path with its parameter names blanked. If two paths share a shape (e.g. /x/{slug}/ and /x/{id}/), the later one silently wins, and a 429 can land on the wrong operation or go missing. There are no collisions today: I generated the schema and found zero. | `by_shape` keys paths with their parameter names blanked. If two schema paths share a shape (e.g. `/x/{id}/` and `/x/{slug}/`), the later one overwrites the earlier, and the 429 can land on the wrong operation or be lost. I found no such pair today; this is a latent risk. | document_throttle_429 matches paths by blanked parameter names (by_shape). Two schema paths that differ only in param names would collapse into one dict entry, so a 429 could land on the wrong operation or be dropped. No such pair exists today.
2. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:106` The `extra` check runs only when the handler has some ratelimit (`if methods and ...`). An action left in a ViewSet's `_throttled_actions` after its ratelimit decorator is removed (or overridden undecorated) still gets a documented 429 that no gate catches. | also: The 'extra' check fires only when the view has some limiter (`methods` is non-empty). A _throttled_actions entry left behind after its @method_decorator(ratelimit) is removed therefore keeps documenting a false 429, and no test fails. | The `extra` check only runs when the handler has some ratelimit (`if methods and ...`). If an action is left in a ViewSet's hand-kept `_throttled_actions` after its ratelimit decorator is removed, the hook still documents a 429 that no gate catches. The api_schema docstring says only that a missing marker fails. | Nothing checks the reverse of the new `_throttled_actions` marker. If an action is listed but not rate-limited (its decorator removed, or a subclass overrides it undecorated), it still gets a 429 in the schema. The `extra` check misses this because it needs `methods` to be non-empty.
3. **low** `plant_community_mobile/lib/services/auth_service.dart:878` The new `_clearJWTWhileCurrent` was inserted under the old `/// Clear stored JWT tokens` line, so that line now opens the new helper's doc comment and `_clearJWT` is left with no doc. | also: The new helper was inserted under the old `/// Clear stored JWT tokens` line. That line now opens _clearJWTWhileCurrent's doc comment, and_clearJWT is left with no doc. | The old `/// Clear stored JWT tokens` doc line now sits on top of the new `_clearJWTWhileCurrent` doc block. The two doc comments are merged, and `_clearJWT` lost its own doc. | The existing `/// Clear stored JWT tokens` doc line now sits above the new `_clearJWTWhileCurrent` doc and merges into it, leaving `_clearJWT` undocumented. | The existing doc comment '/// Clear stored JWT tokens' now sits directly above the new _clearJWTWhileCurrent doc, merging into one comment. The unconditional_clearJWT below it loses its doc. | The existing '/// Clear stored JWT tokens' doc line now sits directly above the new _clearJWTWhileCurrent doc, so the two merge into one comment._clearJWT (below) loses its doc. | The new _clearJWTWhileCurrent was inserted between the `/// Clear stored JWT tokens` doc comment and_clearJWT, so that comment now sits above the wrong method and _clearJWT loses its doc. | The new helper went in under the old `/// Clear stored JWT tokens` line. Its doc comment now opens with that stale sentence, and `_clearJWT()` at line 892 has lost its own doc. | The old `/// Clear stored JWT tokens` line now sits on top of `_clearJWTWhileCurrent`'s doc comment, so the new helper's doc starts with a stale first line and `_clearJWT` has no doc. This is the same kind of misplaced doc comment that items 5/9/10 fixed for `_Harness`. | The existing doc line '/// Clear stored JWT tokens' was left above the new_clearJWTWhileCurrent doc, so it merges into that doc. _clearJWT() below it now has no doc comment. | The '/// Clear stored JWT tokens' doc line for_clearJWT now sits above the new _clearJWTWhileCurrent doc block, so it merges into that doc and_clearJWT loses its own doc comment. | The new _clearJWTWhileCurrent was inserted between the '/// Clear stored JWT tokens' doc line and_clearJWT(), so that comment now sits on the wrong method and _clearJWT lost its doc.
4. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:107` A limited endpoint missing from the schema counts as `unmatched` (hard failure), but `_get_paths_and_endpoints` also yields `@extend_schema(exclude=True)` views, so a deliberately hidden rate-limited view would fail with a misleading 'path trimming drifted' message. | also: A limited endpoint not found in the schema now counts as `unmatched` (a hard failure). But `_get_paths_and_endpoints` also yields views marked `extend_schema(exclude=True)`, so a deliberately hidden rate-limited view would fail the gate when nothing is wrong. | The `unmatched` comment says the generator yields only public endpoints. It does not: `_get_paths_and_endpoints` also yields views marked `@extend_schema(exclude=True)`. A rate-limited view excluded from the schema would fail the gate with a misleading 'path trimming drifted' message.

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1077 review (todo sweep run 2026-10-12-0349)

Filed by the closing step of the run from `state.py followups-md g7`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Item 1 (fixed): `backend/plant_community_backend/api_schema.py` now matches a recorded path exactly first, then by shape only when exactly one schema path fits and every parameter name agrees except a `{pk}` / `{x_pk}` the generator renames. An ambiguous match documents nothing, so the gate reports it as missing instead of a 429 landing on the wrong operation. New test `test_hook_does_not_mix_up_paths_that_differ_only_in_parameter_name` fails against the old hook.
- Item 2 (fixed): the gate in `backend/apps/core/tests/test_openapi_rate_limit_429.py` now counts a 429 as `extra` when a `_throttled_actions` / `_forum_throttled_methods` marker names an operation that no ratelimit covers. Canary `test_gate_catches_a_stale_marker_and_skips_an_excluded_view` covers it.
- Item 4 (fixed): a rate-limited view that `extend_schema(exclude=True)` keeps out of the schema is now skipped, not counted as `unmatched`. The same canary covers it, and the misleading comment is corrected.
- Item 3 (fixed, doc only): `plant_community_mobile/lib/services/auth_service.dart` moves `/// Clear stored JWT tokens` back onto `_clearJWT`, so `_clearJWTWhileCurrent` keeps only its own doc. This changes no behaviour, so it has no test.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 6 -- venv/bin/python -m pytest apps/core/tests/test_openapi_rate_limit_429.py apps/forum_host/tests/test_schema_429.py --create-db -v -p no:warnings && grep -n -B1 -A1 'Future<void> _clearJWT() async' ../plant_community_mobile/lib/services/auth_service.dart && grep -n -A5 'Implemented by the todo sweep (run 2026-10-12-1724)' ../todos/archive/632-completed-p4-throttle-429-gate-1077.md` — evidence `.sweep-evidence/g6/632-ac0.txt` (not committed), last lines:

  ```text
  41-
  42-- Item 1 (fixed): `backend/plant_community_backend/api_schema.py` now matches a recorded path exactly first, then by shape only when exactly one schema path fits and every parameter name agrees except a `{pk}` / `{x_pk}` the generator renames. An ambiguous match documents nothing, so the gate reports it as missing instead of a 429 landing on the wrong operation. New test `test_hook_does_not_mix_up_paths_that_differ_only_in_parameter_name` fails against the old hook.
  43-- Item 2 (fixed): the gate in `backend/apps/core/tests/test_openapi_rate_limit_429.py` now counts a 429 as `extra` when a `_throttled_actions` / `_forum_throttled_methods` marker names an operation that no ratelimit covers. Canary `test_gate_catches_a_stale_marker_and_skips_an_excluded_view` covers it.
  44-- Item 4 (fixed): a rate-limited view that `extend_schema(exclude=True)` keeps out of the schema is now skipped, not counted as `unmatched`. The same canary covers it, and the misleading comment is corrected.
  45-- Item 3 (fixed, doc only): `plant_community_mobile/lib/services/auth_service.dart` moves `/// Clear stored JWT tokens` back onto `_clearJWT`, so `_clearJWTWhileCurrent` keeps only its own doc. This changes no behaviour, so it has no test.
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
