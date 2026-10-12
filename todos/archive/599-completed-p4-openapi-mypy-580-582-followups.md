---
status: completed
priority: p4
issue_id: "599"
tags: [backend, api-docs, ci, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
---

# Follow-ups from PR #1040 (todos 580-582, mypy gate, spectacular fail-on-warn, request examples)

## Problem

Todo-sweep run 2026-10-11-1929 merged PR #1040, which added the mypy CI gate on apps/users, made
`spectacular --fail-on-warn` pass, and added request examples. Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Item 6 of the generated list repeated item 5 (the collection DELETE 204 body) and
was folded into it by hand. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1040 (todo sweep run 2026-10-11-1929, group g1, todos 580, 581, 582); follow-ups: verified; 1 item(s) the curator did not return were kept as stored.

1. **medium** `backend/apps/users/view_schemas.py:81` Only LOGIN_SCHEMA documents 429. REGISTER, VERIFY_EMAIL, RESEND_VERIFICATION and UPDATE_PROFILE are @ratelimit(block=True) endpoints, but their schemas omit 429.
2. **medium** `backend/apps/plant_identification/api/simple_views.py:99` identify_plant is @ratelimit(block=True), but its new extend_schema lists only 200/400/500 and documents no 429.
3. **low** `backend/apps/core/tests/test_schema_request_examples.py:97` The 'obviously fake' check is a denylist. It inspects only '@' values and keys containing a SECRET_KEYS word, so a real-looking secret under another key passes, and 'example' in text accepts `'example-<real token>'`.
4. **low** `.github/workflows/backend-ci.yml:96` The new mypy gate on apps/users has no self-test. Nothing proves follow_imports=silent still reports errors in the named app, so config drift could turn the gate green by emptiness.
5. **low** `backend/apps/users/view_schemas.py:226` COLLECTION_DELETE_SCHEMA documents `204: None` (no body), but user_collection_detail's DELETE returns {"message": "Collection deleted successfully"} with status 204. This predates the PR, which only made it visible. | also: COLLECTION_DELETE_SCHEMA documents 204 with no body, but user_collection_detail's DELETE returns {"message": ...} with status 204. The docs and the wire disagree. This predates the PR, which only made it visible. (reported at view_schemas.py:231)

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:164 MyForumImagesView declared 200 as the full page dict on a paginated ListAPIView, so drf-spectacular wrapped it twice: /forum/images/mine/ documented {next, previous, results:[{next, previous, results:[image]}]}. (fixed on main: On main the @extend_schema declares 200 as FORUM_IMAGE_SCHEMA, the item shape, with a comment that spectacular adds the page wrapper. test_paginated_image_list_is_wrapped_once asserts the response is wrapped only once.; the refuter agreed: On origin/main image_management.py:56 declares responses={200: FORUM_IMAGE_SCHEMA} (the item shape) on the paginated ListAPIView, and test_paginated_image_list_is_wrapped_once asserts the item has no nested results. The double wrap is gone.)
- low: backend/apps/users/view_schemas.py:214 COLLECTION_UPDATE_SCHEMA used UserPlantCollectionSerializer as the PUT request, so the docs marked `name` and other fields required, but the view saves with partial=True. (fixed on main: On main line 217 is request=UserPlantCollectionSerializer(partial=True), with a comment that no field is required in the body.; the refuter agreed: On main, view_schemas.py:217 is request=UserPlantCollectionSerializer(partial=True), so the PUT body is documented with no required fields, which matches the view's partial save.)
- low: backend/apps/core/tests/test_openapi_schema_warnings.py:18 The test reads drf-spectacular's private GENERATOR_STATS._warn_cache and _error_cache. An upgrade that renames them could leave an empty set that passes silently. (fixed on main: On main a hasattr assertion fails the test if either cache is renamed. test_gate_catches_a_view_without_a_serializer is a canary that proves the caches still fill. It still uses private internals, but the silent-pass risk is covered.; the refuter agreed: On main, test_openapi_schema_warnings.py fails if either private cache attribute is missing (hasattr assertion). test_gate_catches_a_view_without_a_serializer proves the caches still fill, so the test can no longer pass silently with nothing checked.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Items 1 and 2: new `RATE_LIMITED` response in `backend/apps/core/openapi.py`. Every `@ratelimit(block=True)` function view now lists it as its 429: the users auth views, identify_plant, oauth, email unsubscribe and blog newsletter.
- `backend/apps/core/tests/test_openapi_rate_limit_429.py` finds blocking ratelimit wrappers on each schema operation and fails when one has no 429. A canary checks that it still detects them.
- Item 3: in `test_schema_request_examples.py`, a secret-like value must now fully match `example-<short-lowercase-words>`, and a run of 20+ token characters fails under any key. Canary tests reject real-looking values.
- Item 4: `backend/bin/test-mypy-gate.sh` plants a type error in `apps/users`, runs the CI gate command, and requires that the gate fails on that file. backend-ci runs it after the gate.
- Item 5: fixed on the wire. The collection DELETE now returns a 204 with no body, which matches the schema. A grep of `web/src` and `plant_community_mobile/lib` found no client that reads that body. Test: `backend/apps/users/tests/test_collections.py`.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash -c 'cd backend && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python -m pytest apps/core/tests/test_openapi_rate_limit_429.py apps/core/tests/test_schema_request_examples.py apps/core/tests/test_openapi_schema_warnings.py apps/users/tests/test_collections.py --create-db -q -p no:cacheprovider && python3 scripts/todos/slot_env.py --main-root . 5 -- env PATH=backend/venv/bin:/usr/bin:/bin bash bin/test-mypy-gate.sh && python3 scripts/todos/slot_env.py --main-root . 5 -- backend/venv/bin/python manage.py spectacular --file /dev/null --validate --fail-on-warn; echo EXIT=$?'` — evidence `.sweep-evidence/g5/599-ac0.txt` (not committed), last lines:

  ```text
  backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
    from wagtail.images import permissions as image_permissions
  [settings] ENABLE_FILE_LOGGING=True (argv=['manage.py', 'spectacular', '--file', '/dev/null', '--validate', '--fail-on-warn'])
  ✅ Environment configuration validated successfully
  EXIT=0
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
