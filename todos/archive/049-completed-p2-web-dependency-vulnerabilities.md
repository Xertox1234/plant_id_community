---
status: completed
priority: p2
issue_id: "049"
tags: [frontend, dependencies, security, npm, audit, stabilization]
dependencies: ["047"]
---

# Resolve Web npm Audit Vulnerabilities

## Problem

The web dependency tree reported multiple moderate and high npm audit findings that needed triage before production deployment.

## Findings

- Discovered during May 1, 2026 codebase assessment.
- Initial command:
  ```bash
  cd web
  npm ci
  npm audit --audit-level=moderate
  ```
- Initial summary:
  - 16 total vulnerabilities
  - 9 moderate
  - 7 high
  - 0 critical
- Packages reported in the audit summary included:
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

## Resolution

- Applied non-breaking npm audit fixes to update vulnerable transitive and direct dependencies.
- Removed the `uuid` dependency instead of forcing a breaking major upgrade.
- Replaced the `uuid` fallback in `RequestContext` with a Web Crypto-based request ID generator.
- Centralized request ID lookup so React context, logging, and HTTP headers share the same storage-backed or in-memory fallback value.
- Added request ID rotation notifications so context consumers stay aligned after login/signup, and added a one-shot CSRF retry guard while touching the HTTP client.
- Updated request context tests to remove the `uuid` mock.
- Refreshed `web/package-lock.json`.

## Acceptance Criteria

- [x] High severity vulnerabilities are resolved or documented with justification.
- [x] Moderate vulnerabilities are resolved or documented with justification.
- [x] `cd web && npm audit --audit-level=moderate` passes, or accepted exceptions are documented.
- [x] `cd web && npm run build` passes after dependency changes.
- [x] Web tests are run after dependency changes.

## Work Log

### 2026-05-01 - Codebase Assessment

- Confirmed web dependency audit issues after fresh install.
- Classified P2 because there were high findings but no critical findings.

### 2026-05-02 - Dependency Audit Resolved

- Ran `npm audit fix` and removed the remaining vulnerable `uuid` dependency by using platform request ID generation.
- Verified `npm audit --audit-level=moderate` reports 0 vulnerabilities.
- Verified `npm run build` passes, including TypeScript type-check.
- Verified `npm run test -- --run` passes: 24 files, 663 tests passed.