---
name: add-web-ci-typecheck-tests
status: in_progress
priority: p1
created: 2026-05-30
tags: [harness, ci, web, typescript, testing]
source_review: "docs/audits/2026-05-30-harness.md"
source_finding: "F1"
---

# Add a web CI workflow (type-check + tests)

## Problem

`.github/workflows/` has `backend-ci.yml`, `mobile-ci.yml`, `security-scan.yml`,
`kimi-review.yml` — but **no `web-ci.yml`**. Backend CI runs Django tests
(matrix job w/ postgres+redis), flake8, black; mobile CI runs `flutter analyze` +
`flutter test`. The **web stack has none of this in CI**:

- No `tsc`/type-check in any workflow.
- No `vitest`/`playwright` run in any workflow.
- The only web check in CI is `npm audit` (security-scan.yml).
- Pre-commit web hooks are **eslint + prettier only** — no type-check, no tests,
  and pre-commit is locally bypassable with `--no-verify`.

Net: a TypeScript type error or a failing web unit/e2e test can merge to `main`
with zero gate. For an audit whose primary lens is "produce higher-quality code,"
this is the single largest real gap found.

## Acceptance criteria

- [x] A `web-ci.yml` runs on PRs touching `web/**` (mirror the backend-ci
      paths-filter + required-check pattern so branch protection is satisfiable).
- [x] It runs at minimum: `npm ci`, `npm run type-check` (tsc), `npm run test`
      (vitest). Add Playwright e2e if the suite is CI-stable; otherwise note why
      it's deferred (no silent omission).
- [x] The workflow is blocking (a type error or failing test fails the check).
- [x] Confirm `web/package.json` exposes the `type-check` and `test` scripts the
      workflow calls; add them if missing.

## Notes

Workflow files are NOT under `.claude/`, so this is editable directly (no Auto
Mode block). Verify the exact script names in `web/package.json` before wiring.

## Work Log

### 2026-05-30 - Started by completing-todos skill (run 2026-05-30-1511)

- Picked up by automated workflow.

### 2026-05-30 - Implemented `.github/workflows/web-ci.yml`

Created `.github/workflows/web-ci.yml` mirroring `backend-ci.yml`'s required-check
pattern. Design notes:

- `push` filtered on `web/**`; `pull_request` has **no** paths filter so it is
  safe as a required status check (a path-filtered required check never reports on
  non-matching PRs and blocks merge — the gotcha at `backend-ci.yml:12-15`).
- Node from root `.nvmrc` (24); `npm ci` (lockfile present); `working-directory:
  web`.
- Runs `type-check` → `lint` → `vitest --run`. Lint added beyond the minimum
  because finding F1 flags web lint as pre-commit-only/bypassable.
- **Playwright e2e deferred** (not silently omitted): `web/playwright.config.ts`
  has a `webServer` block and the specs hit the live backend (per `web/CLAUDE.md`),
  so e2e needs Django + Postgres/Redis stood up — out of scope for a web-only gate.

Verification — ran each gate command locally on current `main`:

```text
npm run type-check   → TYPECHECK_EXIT=0
npm run lint         → LINT_EXIT=0
npm run test -- --run→ VITEST_EXIT=0   (Test Files 9 passed (9) | Tests 72 passed (72))
```

YAML validated with `yaml.safe_load`: `name: Web CI`; triggers `push` +
`pull_request`; `PR_HAS_PATHS_FILTER: False`. `web/package.json` confirmed to
expose `type-check` (`tsc --noEmit`) and `test` (`vitest`) — nothing to add.
All 4 acceptance criteria flipped with evidence above.
