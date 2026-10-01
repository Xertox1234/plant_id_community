---
status: completed
priority: p4
issue_id: "489"
tags: [web, backend, blog]
dependencies: []
source_review: "PR #882"
triage: ready
triaged: 2026-09-30
owner_decision: "A response-less AxiosError with a code other than ERR_NETWORK/ECONNABORTED/ETIMEDOUT is returned unchanged, not wrapped (2026-09-30)"
---

# HTTP error translator and preview expiry: non-blocking findings from PR #882 (todo 434)

## Problem

PR #882 merged the web HTTP error translators into `toHttpError` and moved preview-token expiry
into the model. Both review rounds were clean. These are the non-blocking findings.

## Findings

1. **`BlogPostPreviewAPIViewSet.PREVIEW_TOKEN_MAX_AGE` is dead.** The model now reads the
   constant, so overriding the attribute does nothing. `test_expired_token_is_404`
   (`test_page_preview.py:225`) still reads it, so it looks like a working security setting
   (`viewsets.py:838`).
2. **Client bugs read as connection problems.** Every response-less `AxiosError` becomes
   `NETWORK_ERROR_MESSAGE`, including `ERR_INVALID_URL`, `ERR_BAD_OPTION_VALUE` and interceptor
   rejections (`httpError.ts:48`).
3. **Stale test rows.** The `notificationService.test.ts` `it.each` rows still pass by substring
   against `'Request failed (HTTP 500)'`, and their labels describe the old wording
   (`notificationService.test.ts:94`).
4. **A stale header comment** in `httpClient.test.ts:7` says the tests avoid the full axios
   instance. The new Error logging block drives it.

## Acceptance Criteria

- [x] The viewset attribute is removed, and the expiry test reads `constants.PREVIEW_TOKEN_MAX_AGE`.
- [x] Only `ERR_NETWORK`, `ECONNABORTED` and `ETIMEDOUT` get the connection message, with a test
      for another code.
- [x] The notification rows assert the full message.
- [x] The header comment is corrected.

## Work Log

### 2026-09-28 - Filed from PR #882 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Removed the dead `BlogPostPreviewAPIViewSet.PREVIEW_TOKEN_MAX_AGE` attribute and its import;
  the class docstring now says the model reads `apps/blog/constants.py`. `test_expired_token_is_404`
  reads the constant directly, and the now-unused viewset import left the test module.
- `toHttpError` gives `NETWORK_ERROR_MESSAGE` only to `ERR_NETWORK`, `ECONNABORTED` and `ETIMEDOUT`.
  Any other response-less axios error is returned unchanged (owner decision), so a client bug keeps
  its own code and text. New `httpError.test.ts` rows cover `ETIMEDOUT`, `ERR_INVALID_URL`,
  `ERR_BAD_OPTION_VALUE` and a code-less axios error.
- The `notificationService.test.ts` error rows now assert the whole message
  (`'Request failed (HTTP 500)'`), and their labels match the current wording.
- Corrected the `httpClient.test.ts` header: the Error logging block drives the real `apiClient`
  through the stub adapter.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-3/backend && echo "viewset assignments of PREVIEW_TOKEN_MAX_AGE:" && (grep -n "PREVIEW_TOKEN_MAX_AGE *=" apps/blog/api/viewsets.py || echo none) && echo "test module references:" && grep -n "PREVIEW_TOKEN_MAX_AGE\|BlogPostPreviewAPIViewSet" apps/blog/tests/test_page_preview.py && python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-3/scripts/todos/slot_env.py 3 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/blog/tests/test_page_preview.py --create-db -v -p no:warnings` — evidence `.sweep-evidence/g9/489-ac0.txt`, last lines:

  ```text
  apps/blog/tests/test_page_preview.py::BlogPostPreviewAPITestCase::test_well_signed_but_unknown_token_is_404 PASSED [100%]

  ==================== 20 passed, 4 subtests passed in 16.89s ====================

  [exit 0]
  ```

- AC 2: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-3/web && grep -n -A4 "CONNECTION_ERROR_CODES" src/utils/httpError.ts && npx vitest run src/utils/httpError.test.ts src/services/profileService.test.ts --reporter=verbose` — evidence `.sweep-evidence/g9/489-ac1.txt`, last lines:

  ```text
  (!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
    - `__dirname` (vitest.config.ts:62:25). Use `import.meta.dirname` instead
  Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  [exit 0]
  ```

- AC 3: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-3/web && grep -n -B10 -A7 "rejects with %s" src/services/notificationService.test.ts && npx vitest run src/services/notificationService.test.ts --reporter=verbose` — evidence `.sweep-evidence/g9/489-ac2.txt`, last lines:

  ```text
  (!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
    - `__dirname` (vitest.config.ts:62:25). Use `import.meta.dirname` instead
  Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  [exit 0]
  ```

- AC 4: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-3/web && sed -n 1,11p src/utils/httpClient.test.ts && npx vitest run src/utils/httpClient.test.ts --reporter=verbose` — evidence `.sweep-evidence/g9/489-ac3.txt`, last lines:

  ```text
  (!) Your Vite config uses features that are unsupported by `configLoader: 'native'`, which is planned to become the default in a future major version of Vite:
    - `__dirname` (vitest.config.ts:62:25). Use `import.meta.dirname` instead
  Set `VITE_CONFIG_NATIVE_IGNORE_WARNING=true` to suppress this warning.

  [exit 0]
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
