---
status: pending
priority: p3
issue_id: "712"
tags: [web, dependencies, dependabot, upgrade]
dependencies: []
---

# Web majors: Vitest 5, jsdom 31, jest-dom 7, Sentry 11, TypeScript 7

## Problem

Five web packages are a major behind. All but Sentry are build and test
tooling. Dependabot will open a PR for each until it is taken or declined.

## Findings

Source: `npm outdated` in `web/`, 2026-11-15; installed versions read from
`web/package-lock.json`.

| Package | Locked | Latest |
|---|---|---|
| vitest, @vitest/ui, @vitest/coverage-v8 | 4.1.12 | 5.1.0 |
| jsdom | 29.1.1 | 31.0.1 |
| @testing-library/jest-dom | 6.9.1 | 7.0.1 |
| @sentry/react | 10.73.0 | 11.12.0 |
| typescript | 6.0.3 | 7.0.2 |

- `@sentry/react` is in `devDependencies` although it ships in the bundle.
  Vite bundles it either way; moving it is tidiness, not a fix.
- `@types/node` 26 is ignored in `.github/dependabot.yml`: it follows `.nvmrc`
  (Node 24).
- `web/package.json` carries `"overrides": {"minimatch": "^11.0.3"}` (PR
  #1242). Recheck whether it is still needed after these bumps.
- Changelogs were not read for this todo.

## Recommended Action

One PR per row, in this order:

1. Vitest 5 (the three packages together), then jsdom 31 and jest-dom 7:
   config and matcher changes only; the suite is the check.
2. Sentry 11: read the migration guide for the init options in use; check an
   event reaches Sentry from a preview build.
3. TypeScript 7 last: it is the largest. Check `typescript-eslint` supports
   it first; if it does not yet, decline with
   `@dependabot ignore this major version` and note the version to wait for.
4. For anything not taken, decline on the Dependabot PR and record the reason.

## Technical Details

- `web/package.json`, `web/package-lock.json`
- `web/vite.config.*`, `web/vitest.config.*`, `web/tsconfig*.json`,
  `web/eslint.config.*`
- `web/docs/patterns/testing.md`, `react-typescript.md`
- Vitest has a known unhandled-rejection flake on this project; do not read a
  flake as a regression without a rerun.

## Acceptance Criteria

- [ ] Each of the five rows is bumped in a merged PR or declined on its
      Dependabot PR, with the PR number and reason in the Work Log.
- [ ] `npm run type-check`, `npm run lint`, `npx vitest run` and
      `npm run build` pass on each PR.
- [ ] Playwright suite passes after the TypeScript and Vitest PRs.
- [ ] After Sentry 11: one test event from the deployed site appears in Sentry
      (date and event id recorded here).

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit.
