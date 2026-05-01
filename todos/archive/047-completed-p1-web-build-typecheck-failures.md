---
status: completed
priority: p1
issue_id: "047"
tags: [frontend, react, typescript, build, production-blocker, stabilization]
dependencies: []
---

# Fix Web Production Build and TypeScript Check Failures

## Problem

The React web app currently fails `npm run build` because TypeScript checking reports errors in both production code and test files. This blocks production web deployment and undermines CI confidence.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Commands run:
  ```bash
  cd web
  npm ci
  npm run build
  ```
- Build failed during `tsc --noEmit`.
- Production-code error:
  - `web/src/services/authService.ts`: `logger.warn('[authService] Token refresh failed:', response.status)` passes a number where the logger expects a context object.
- Test typing errors:
  - Several `global.fetch = fetchMock` assignments in service tests are incompatible with the DOM `fetch` type.
- `web/tsconfig.json` currently includes `src/**/*`, which means `*.test.ts` files inside `src` are type-checked as part of the production build.

## Recommended Action

1. Fix the production logger call in `authService.ts`.
2. Decide whether production builds should type-check tests:
   - Option A: keep tests included and fix fetch mock typing.
   - Option B: split TypeScript configs into production and test configs.
3. Re-run `npm run build`.
4. Document the chosen TypeScript build/test strategy.

## Technical Details

Recommended production-code fix pattern:

```typescript
logger.warn('[authService] Token refresh failed', { status: response.status });
```

Recommended test mock pattern:

```typescript
global.fetch = fetchMock as unknown as typeof fetch;
```

Alternative config approach:

- `tsconfig.app.json`: excludes tests, used by `npm run build`.
- `tsconfig.test.json`: includes tests, used by a dedicated test type-check command.

## Acceptance Criteria

- [x] `cd web && npm run build` passes.
- [x] Production TypeScript errors are fixed, not suppressed with broad `any` usage.
- [x] Test type-checking strategy is explicit and documented.
- [x] No regression in web unit test execution caused by the config change.

## Work Log

### 2026-05-01 - Codebase Assessment

- Confirmed `npm run build` fails on current `main` checkout after fresh `npm ci`.
- Classified P1 because production web build is blocked.

### 2026-05-01 - Build Fix Completed

- Fixed `authService` token-refresh warning to pass logger context as `{ status: response.status }`.
- Kept the existing TypeScript strategy: production build still type-checks `src/**/*`, including tests.
- Fixed fetch mock assignments in service tests with `as unknown as typeof fetch` so test files type-check under the production build.
- Verified `cd web && npm run build` passes.
- Ran affected service tests; they still have existing runtime expectation/mock failures covered by TODO 048, but no new TypeScript build blockers remain.
