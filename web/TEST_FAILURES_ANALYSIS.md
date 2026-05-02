# Web Test Suite Baseline

**Date**: May 1, 2026  
**Status**: ✅ Clean Vitest baseline

## Current Result

Command:

```bash
npm run test -- --run --reporter=dot
```

Result:

- Test files: 24 passed / 24 total
- Tests: 659 passed, 1 skipped / 660 total
- TypeScript: `npm run type-check` passes

## Fixes Applied

- Updated React Router 7 tests to mock `useParams` with a partial `vi.mock('react-router-dom', ...)` instead of redefining ESM module properties with `vi.spyOn`.
- Updated Header authentication fixtures to use the current `username`/`email` display behavior.
- Updated service tests to use the centralized CSRF utility behavior:
  - Primary source: `<meta name="csrf-token">`
  - Fallback endpoint: `/api/csrf/`
  - Cached token reset between tests with `clearCsrfToken()`
- Updated `StreamFieldRenderer` to support current backend StreamField names and legacy aliases used by existing fixtures without unsafe `any` types.

## Notes

The suite still prints some non-failing React `act(...)` warnings and intentional logger output from error-path tests. These do not fail the current baseline and can be cleaned up separately if desired.
