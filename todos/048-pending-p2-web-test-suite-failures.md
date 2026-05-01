---
status: pending
priority: p2
issue_id: "048"
tags: [frontend, tests, vitest, react-router, quality, stabilization]
dependencies: ["047"]
---

# Fix Web Vitest Suite Failures

## Problem

The web unit test suite has substantial failures, reducing confidence in future frontend changes. Some failures appear to be stale tests rather than production defects, but the current signal is too noisy for reliable development.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Command run:
  ```bash
  cd web
  npm run test -- --run --reporter=dot
  ```
- Result:
  - 543 passing
  - 113 failing
  - 1 skipped
  - 7 failed test files
- Observed failure categories:
  - Header tests expecting `Test User`, while rendered output shows `test@example.com`.
  - Forum page tests fail with `TypeError: Cannot redefine property: useParams`, likely due to React Router 7 module export behavior and `vi.spyOn` usage.
  - Service tests in `authService.test.ts`, `forumService.test.ts`, and `plantIdService.test.ts` have stale fetch/mock ordering or expectation failures after the TypeScript-only build fix in TODO 047.
  - Existing `web/TEST_FAILURES_ANALYSIS.md` is stale relative to current failures.

## Recommended Action

1. Run the suite with a full reporter and group failures by root cause.
2. Update React Router mocks to a supported Vitest pattern.
3. Update stale expectations in Header/auth tests.
4. Revisit `web/TEST_FAILURES_ANALYSIS.md` and replace stale numbers/categories.
5. Add CI gating only after the suite has a stable baseline.

## Technical Details

Potential React Router mocking strategy:

```typescript
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(),
  };
});
```

Then configure return values through the mocked `useParams` rather than redefining the module property with `vi.spyOn`.

## Acceptance Criteria

- [ ] Current failure list is documented with accurate counts.
- [ ] React Router `useParams` test failures are fixed.
- [ ] Header/auth test expectations match intended UI behavior.
- [ ] `cd web && npm run test -- --run` has a clean or explicitly documented baseline.
- [ ] `web/TEST_FAILURES_ANALYSIS.md` is updated or replaced.

## Work Log

### 2026-05-01 - Codebase Assessment

- Confirmed current Vitest failures are materially different from the older documented failure analysis.
- Classified P2 because the app may still run, but test confidence is poor.

### 2026-05-01 - Follow-up From TODO 047

- Targeted service test run after the web build/type-check fix still failed: 3 failed files, 1 passed file, 68 failed tests, 37 passed tests.
- Failures appear runtime/mock related rather than TypeScript build blockers.
