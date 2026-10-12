---
status: completed
priority: p4
issue_id: "644"
tags: [api, tests, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1100 (todo 632, 429 schema gate)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1100 (todo 632, 429 schema gate). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1100 (todo sweep run 2026-10-12-1724, group g6, todos 632); follow-ups: verified.

1. **low** `backend/plant_community_backend/api_schema.py:154` _schema_path_item treats two shape-matching candidates as ambiguous without checking the method: with /x/{id}/ (post) and /x/{slug}/ (get only), a recorded ('/x/{pk}/','post') resolves to None and the 429 is dropped; the gate then fails with an avoidable missing 429. | also:_schema_path_item resolves ambiguity per path, not per method. Take /x/{id}/ (POST) and /x/{slug}/ (GET only) with a recorded /x/{pk}/ POST. Only one candidate has the method, but the hook drops the 429 as ambiguous. The gate does report it as missing, so this cannot ship silently, but the error is avoidable. | The ambiguity check ignores the HTTP method. Recorded /x/{pk}/ POST is dropped when same-shape /x/{slug}/ exists, even if only one candidate has a POST operation. The gate then reports a spurious missing 429 rather than resolving the match.
2. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:100` _excluded() calls schema.is_excluded() on fresh views from _get_paths_and_endpoints where get_operation never ran; for extend_schema(exclude=True, methods=[...]) is_in_scope reads an unset or stale ext_schema.method, raising AttributeError or misjudging the exclusion. Latent: no view uses it today. | also:_excluded() calls schema.is_excluded() outside get_operation. With extend_schema(methods=[...], exclude=True), is_in_scope reads ext_schema.method, which a fresh per-action schema never set (AttributeError). A shared class-level schema may still hold another method's value, so an unrelated POST drift could be skipped. | _excluded calls schema.is_excluded() on the fresh view from _get_paths_and_endpoints. For extend_schema(exclude=True, methods=[...]), is_in_scope reads ext_schema.method, a stale value left by the last get_operation (or unset). A method-scoped exclude can then be misjudged, or raise AttributeError. |_excluded() calls schema.is_excluded() with nothing set up. drf-spectacular's ExtendedSchema.is_excluded reads self.method, which only get_operation sets, so extend_schema(exclude=True, methods=[...]) either raises AttributeError or reads a method left over from the last generated op. A drifted op could then be skipped silently.
3. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:340` The new hook test sets the thread-local api_schema._state.throttled_operations and resets it to set() in finally instead of restoring the prior value (test-only thread state; existing-test edits judged justified).
4. **low** `plant_community_mobile/lib/services/auth_service.dart:891` Comment-only edit to a codegen-backed @riverpod file; auth_service.g.dart not in the diff. Likely harmless (hash covers the build method, not a private helper's doc comment), but unverified.
5. **low** `backend/apps/core/tests/test_openapi_rate_limit_429.py:319` The item-1 test covers {pk} coercion and ambiguity but not the `{<x>_pk}` suffix branch of_coerced_name_matches, and no test pins that a non-coerced name mismatch (recorded {slug} vs lone schema {id}) documents nothing.

1 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- low: backend/apps/core/tests/test_openapi_rate_limit_429.py:124 Verifier flagged edits to the existing gate; they are justified: the extra branch only gets stricter (adds the marker case), comment fixes are accurate, and the one narrowing (skipping excluded views) is limited to extend_schema(exclude=True) with a canary. No assertion weakened. (refuted: No defect. On origin/main the extra branch only adds the (methods or_marked_throttled) case, and the_excluded skip is pinned by test_gate_catches_a_stale_marker_and_skips_an_excluded_view. No assertion is weakened, so there is nothing to follow up.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1100 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g6`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-2056)

- Item 1 (fixed): `_schema_path_item` became `_schema_operation(path, method, ...)` in `backend/plant_community_backend/api_schema.py`; a shape-match candidate must now have the recorded method, so `/x/{pk}/` POST lands on `/x/{id}/` when `/x/{slug}/` has only a GET. An exact key still returns early (`paths[path].get(method)`) and never falls through to a shape match. Test: `test_hook_resolves_a_shape_match_by_the_recorded_method` (also pins that two candidates with the method stay ambiguous).
- Item 2 (fixed): the gate's `_excluded(view, method)` sets `schema.method` as `get_operation` does before calling `is_excluded()`. Canary `test_gate_honours_a_method_scoped_exclude` (`extend_schema(exclude=True, methods=["POST"])`) raised `AttributeError: 'ExtendedSchema' object has no attribute 'method'` before the fix.
- Item 3 (fixed): the hook tests now go through `_documented_429`, which restores the thread's prior `throttled_operations` (or deletes it if absent); pinned by `test_hook_test_helper_restores_the_thread_state`.
- Item 4 (verified, no change): `dart run build_runner build` in `plant_community_mobile` wrote 18 outputs and left `git status` clean, so `auth_service.g.dart` is current. A `--build-filter` run first deleted nine other `.g.dart` files; the full build restored them byte-identical.
- Item 5 (fixed): the 632-item-1 test adds a `{topic_pk}` -> lone `{topic_id}` case (documented) and a `{slug}` vs lone `{id}` case (nothing documented). All in `backend/apps/core/tests/test_openapi_rate_limit_429.py`, 8 passed.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-2056)

- AC 1: `cd backend && python3 ../scripts/todos/slot_env.py --main-root .. 5 -- venv/bin/python -m pytest apps/core/tests/test_openapi_rate_limit_429.py --create-db -v -p no:warnings` — evidence `.sweep-evidence/g5/644-ac0.txt` (not committed), last lines:

  ```text
  ============================== ENVIRONMENT DRIFT ===============================
  backend/venv does not match backend/requirements.txt — these results describe a tree CI does not run.
    mismatched: pyjwt (pinned 2.15.0, installed 2.13.0), urllib3 (pinned 2.8.0, installed 2.7.0)
  Fix: pip install -r backend/requirements.txt (see todo 378).
  ============================== 8 passed in 0.67s ===============================
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-2056)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
