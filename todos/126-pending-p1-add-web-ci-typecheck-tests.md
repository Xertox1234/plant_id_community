---
name: add-web-ci-typecheck-tests
status: pending
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

- [ ] A `web-ci.yml` runs on PRs touching `web/**` (mirror the backend-ci
      paths-filter + required-check pattern so branch protection is satisfiable).
- [ ] It runs at minimum: `npm ci`, `npm run type-check` (tsc), `npm run test`
      (vitest). Add Playwright e2e if the suite is CI-stable; otherwise note why
      it's deferred (no silent omission).
- [ ] The workflow is blocking (a type error or failing test fails the check).
- [ ] Confirm `web/package.json` exposes the `type-check` and `test` scripts the
      workflow calls; add them if missing.

## Notes

Workflow files are NOT under `.claude/`, so this is editable directly (no Auto
Mode block). Verify the exact script names in `web/package.json` before wiring.
