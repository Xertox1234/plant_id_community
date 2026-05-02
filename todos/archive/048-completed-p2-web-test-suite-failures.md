---
status: completed
priority: p2
issue_id: "048"
tags: [frontend, tests, vitest, react-router, quality, stabilization]
dependencies: ["047"]
completed_at: "2026-05-01"
archived_at: "2026-05-02"
---

# Fix Web Vitest Suite Failures

## Problem

The web unit test suite had substantial failures, reducing confidence in future frontend changes. Some failures were stale tests rather than production defects, but the signal was too noisy for reliable development.

## Findings

- Initial May 1, 2026 baseline:
  - 543 passing
  - 113 failing
  - 1 skipped
  - 7 failed test files
- Main failure categories:
  - Header tests expected `name`, while the current UI displays `username` or `email`.
  - Forum page tests used `vi.spyOn` against React Router 7 ESM exports, causing `TypeError: Cannot redefine property: useParams`.
  - Service tests expected cookie-based CSRF lookup and stale CSRF endpoint paths, while production code uses the centralized CSRF meta-tag utility with `/api/csrf/` fallback.
  - `StreamFieldRenderer` did not support legacy fixture aliases for quote, plant spotlight, and call-to-action blocks.
  - Existing `web/TEST_FAILURES_ANALYSIS.md` was stale relative to the current suite.

## Resolution

- Updated React Router tests to use a partial `vi.mock('react-router-dom', ...)` and configure mocked `useParams` return values directly.
- Updated Header auth fixtures to use `username` where the component intentionally displays `username || email`.
- Updated service tests to seed `<meta name="csrf-token" content="test-csrf-token">`, clear the cached CSRF token between tests, and assert the current `/api/csrf/` fallback endpoint.
- Updated `StreamFieldRenderer` to handle current backend field names and legacy test aliases without unsafe `any` types.
- Replaced stale `web/TEST_FAILURES_ANALYSIS.md` with the current clean test baseline.

## Acceptance Criteria

- [x] Current failure list is documented with accurate counts.
- [x] React Router `useParams` test failures are fixed.
- [x] Header/auth test expectations match intended UI behavior.
- [x] `cd web && npm run test -- --run` has a clean or explicitly documented baseline.
- [x] `web/TEST_FAILURES_ANALYSIS.md` is updated or replaced.

## Verification

```bash
cd web
npm run type-check
npm run test -- --run --reporter=dot
```

Results:

- `npm run type-check`: passes
- `npm run test -- --run --reporter=dot`: 24 test files passed; 659 tests passed; 1 skipped

## Work Log

### 2026-05-01 - Codebase Assessment

- Confirmed current Vitest failures were materially different from the older documented failure analysis.
- Classified P2 because the app may still run, but test confidence was poor.

### 2026-05-01 - Follow-up From TODO 047

- Targeted service test run after the web build/type-check fix still failed: 3 failed files, 1 passed file, 68 failed tests, 37 passed tests.
- Failures appeared runtime/mock related rather than TypeScript build blockers.

### 2026-05-01 - Completed

- Reduced the full web suite from 113 failures to a clean baseline.
- Validated TypeScript and all Vitest files successfully.

### 2026-05-02 - Archived

- Archived after commit `220dd31` was pushed to `origin/main`.