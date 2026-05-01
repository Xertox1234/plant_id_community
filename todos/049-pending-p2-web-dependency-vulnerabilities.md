---
status: pending
priority: p2
issue_id: "049"
tags: [frontend, dependencies, security, npm, audit, stabilization]
dependencies: ["047"]
---

# Resolve Web npm Audit Vulnerabilities

## Problem

The web dependency tree currently reports multiple moderate and high npm audit findings. These should be triaged before production deployment.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Command run:
  ```bash
  cd web
  npm ci
  npm audit --audit-level=moderate
  ```
- Summary:
  - 16 total vulnerabilities
  - 9 moderate
  - 7 high
  - 0 critical
- Packages reported in audit summary included:
  - `axios`
  - `dompurify`
  - `react-router`
  - `react-router-dom`
  - `vite`
  - `rollup`
  - `postcss`
  - `uuid`
  - `minimatch`
  - `picomatch`

## Recommended Action

1. Run `npm audit` and save the full current report.
2. Update non-breaking dependencies first.
3. Review breaking updates separately, especially router/build-tool changes.
4. Re-run build and tests after each update group.
5. Keep `package-lock.json` updated and committed.

## Technical Details

Recommended workflow:

```bash
cd web
npm audit
npm update
npm run build
npm run test -- --run
npm audit --audit-level=moderate
```

Use `npm audit fix --force` only if the resulting major-version changes are reviewed and tested.

## Acceptance Criteria

- [ ] High severity vulnerabilities are resolved or documented with justification.
- [ ] Moderate vulnerabilities are resolved or documented with justification.
- [ ] `cd web && npm audit --audit-level=moderate` passes, or accepted exceptions are documented.
- [ ] `cd web && npm run build` passes after dependency changes.
- [ ] Web tests are run after dependency changes.

## Work Log

### 2026-05-01 - Codebase Assessment

- Confirmed web dependency audit issues after fresh install.
- Classified P2 because there are high findings but no critical findings.
