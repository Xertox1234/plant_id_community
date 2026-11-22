---
status: completed
priority: p3
issue_id: "712"
tags: [web, dependencies, dependabot, upgrade]
dependencies: []
triage: ready
triaged: 2026-11-20
owner_decision: "Owner: ship jsdom 31 plus the Playwright run now; move the TypeScript 7 and Sentry-dashboard criteria to a follow-up todo (2026-11-20)"
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
      Dependabot PR, with the PR number and reason in the Work Log. → todo 722 (re-pointed 2026-11-21)
- [x] `npm run type-check`, `npm run lint`, `npx vitest run` and
      `npm run build` pass on each PR.
- [x] Playwright suite passes after the TypeScript and Vitest PRs.
- [ ] After Sentry 11: one test event from the deployed site appears in Sentry
      (date and event id recorded here). → todo 722 (re-pointed 2026-11-21)

## Work Log

### 2026-11-15 - Filed

- Filed from the stack audit.

### 2026-11-15 - Sentry 11 (#1329)

- `@sentry/react` 10.73.0 -> 11.8.0. As Dependabot wrote it the PR was green
  and wrong: Sentry 11 streams spans by default and no longer calls
  `beforeSendTransaction`, so a traced page's token URL left the browser
  unscrubbed. `web/src/config/sentry.wire.test.ts` runs the real SDK and
  failed on that; `sentry.test.ts` mocks the SDK and could not see it.
- Fixed with `traceLifecycle: 'static'` (keeps the transaction model and the
  existing scrub) and an explicit `dataCollection` set to the v10 baseline.
- STILL OPEN: `'static'` is a compatibility mode Sentry plans to remove in a
  later major. Before then, move the scrub to `beforeSendSpan` (streamed span
  format) and drop `traceLifecycle`. The wire test stays as the proof.
- `dataCollection` has no test: nothing observable in jsdom changed with it.

### 2026-11-15 - Vitest 5 and jest-dom 7 merged; TypeScript 7 declined for now

- #1324 (merged): @testing-library/jest-dom 6.9.1 -> 7.0.1.
- #1328 (merged): vitest, @vitest/ui, @vitest/coverage-v8 4.1.12 -> 5.0.5.
  Vitest 5 changed `Assertion<T>` to `Assertion<R, T>`, so jest-dom's own
  type augmentation stopped merging; `web/src/tests/jest-dom-vitest.d.ts`
  attaches the matchers to `Matchers<R, T>`. Delete it when jest-dom ships
  Vitest 5 types.
- #1330 (TypeScript 6.0.3 -> 7.0.2): DECLINED for now. `npm ci` fails:
  @typescript-eslint/eslint-plugin 8.72.2 (latest) and 8.72.3-alpha.8
  (canary) both require `typescript >=4.8.4 <6.1.0`. `dependabot.yml`
  ignores the TypeScript major until typescript-eslint accepts 7; remove
  that entry then.
- jsdom 31: no Dependabot PR yet.
- Playwright suite not run after the Vitest PR.

### 2026-11-21 - Implemented by the todo sweep (run 2026-11-20-2202)

- jsdom 30.1.3 -> 31.0.1 (`web/package.json`, `web/package-lock.json`); only jsdom's own subtree changed in the lock. jsdom 31 asks Node `^22.22.2 || ^24.15.0 || >=26`; `.nvmrc` is 24.
- `npm run type-check`, `npm run lint`, `npx vitest run` (145 files, 2204 tests) and `npm run build` pass with it; no config or test change was needed.
- The TypeScript 7 hold comment in `.github/dependabot.yml` now names todo 722, where that criterion moved.

### 2026-11-21 - Verified by the todo sweep (run 2026-11-20-2202)

- AC 2: `cd web && npm run type-check && npm run lint && npx vitest run && npm run build` — evidence `.sweep-evidence/g4/712-ac1.txt` (not committed), last lines:

  ```text
  dist/assets/LegalDocumentPage-Chc_KGZE.js         103.79 kB │ gzip:  35.01 kB
  dist/assets/vendor-1smKqyG9.js                    251.42 kB │ gzip:  79.84 kB
  dist/assets/TipTapEditor-G7yjD2JR.js              466.56 kB │ gzip: 148.49 kB

  ✓ built in 1.73s
  ```

### 2026-11-21 - Confirmed by the owner, ticked by the todo sweep (run 2026-11-20-2202)

- AC 3: confirmed by the owner on 2026-11-21: "Owner chose 'Confirm; file the main failure': at the owner's request Claude ran the full Playwright suite on the g2 tree (jsdom 31, Vitest 5): 235 passed, 3 failed, 7 skipped. forum-responsive re-run alone: 50/50 passed (load timeout). The forum-authenticated write-lifecycle test fails identically on origin/main 5ce82c65 (chromium-authenticated and firefox-authenticated), so it predates this change; filed as todo 725 (2026-11-21)" (`state.py confirm`; no command or evidence)

### 2026-11-21 - Completed by the todo sweep (run 2026-11-20-2202)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-21 - Review round 1: non-blocking findings (PR #1397)

- **Declined:** a reviewer noted the ticked Playwright criterion has 3 failures in its run, and that the run
  was on the first attempt's tree. The owner confirmed it knowing that: the counts and the reason are quoted
  in the entry above. Two of the failures are the forum write-lifecycle test, which fails the same way on
  main (todo 725); the third passed 50/50 when re-run alone. This tree has the same jsdom 31.0.1 and Vitest
  5. Acceptance criteria are not reworded after the fact.
