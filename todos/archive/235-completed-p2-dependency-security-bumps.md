---
status: completed
priority: p2
issue_id: "235"
tags: [security, dependencies, ci]
dependencies: []
---

# Dependency security bumps — npm audit + pip-audit advisories (surfaced on PR #374)

## Problem

The non-required CI security scans (`Frontend npm Security Scan` = `npm audit
--audit-level=moderate`; `Backend Python Security Scan` = `pip-audit`) fail on a
batch of dependency advisories. These are **pre-existing** — they were published
to the live advisory databases after `main` last ran its scans, and are unrelated
to any feature change (PR #374, which surfaced them, changed **zero** dependency
manifests). `main` would fail identically if its scans re-ran today.

These checks are **not** in branch protection's required list, so they don't block
merges — but the advisories are real and most have fixes available, so they should
be cleared rather than left red indefinitely.

## Findings

### Frontend — `npm audit --audit-level=moderate` (web/)

| Package | Affected | Advisory | Severity |
|---------|----------|----------|----------|
| `@babel/core` | <=7.29.0 | GHSA-4x5r-pxfx-6jf8 (arbitrary file read via sourceMappingURL) | moderate |
| `dompurify` | <=3.4.10 | cluster: GHSA-x4vx-rjvf-j5p4, -76mc-f452-cxcm, -hpcv-96wg-7vj8, -r47g-fvhr-h676, -vxr8-fq34-vvx9, -gvmj-g25r-r7wr, -rp9w-3fw7-7cwq, -cmwh-pvxp-8882 | moderate |
| `form-data` | 4.0.0–4.0.5 | GHSA-hmw2-7cc7-3qxx (CRLF injection) | **high** |
| `react-router` / `react-router-dom` | 7.12.0–7.15.0 | GHSA-84g9-w2xq-vcv6 (CSRF via PUT/PATCH/DELETE document requests) | moderate |
| `undici` | 7.0.0–7.27.2 | (see audit) | moderate |

`npm audit fix` reports a fix is available for each. **`dompurify` is used by
`StreamFieldRenderer` for server-content sanitization** — bump it deliberately and
re-run the forum/blog render tests. `react-router` is a transitive bump worth
verifying against the routing tests (and the project's `react-router-dom`-only
import rule).

### Backend — `pip-audit -r requirements.txt` (backend/)

`Found 7 known vulnerabilities, ignored 3 in 4 packages`:

| Package | Version | Advisory | Fix |
|---------|---------|----------|-----|
| `bleach` | 6.3.0 | GHSA-gj48-438w-jh9v, GHSA-8rfp-98v4-mmr6 | 6.4.0 |
| `bleach` | 6.3.0 | GHSA-g75f-g53v-794x | (no fix version listed yet) |
| `msgpack` | 1.1.2 | GHSA-6v7p-g79w-8964 | 1.2.1 |
| `cryptography` | 48.0.0 | GHSA-537c-gmf6-5ccf | 48.0.1 |
| `daphne` | 4.2.1 | PYSEC-2026-213, PYSEC-2026-214 | 4.2.2 |

The scan already suppresses 3 unfixable/disputed advisories (Twisted, Markdown,
nltk, joblib, PyJWT, llm) via `--ignore-vuln` — see the existing suppression
mechanism in `.github/workflows/` and todo 089. Use the same pattern only where
no fix exists and the path is unreachable.

## Recommended Action

1. **Frontend:** run `npm audit fix` in `web/`, then `npm run type-check && npm run
   lint && npm run test`. Bump `dompurify` and `react-router(-dom)` deliberately;
   verify the StreamField render + routing tests. Pin the resulting versions in
   `package.json`/`package-lock.json`.
2. **Backend:** bump `bleach` 6.3.0→6.4.0, `msgpack` 1.1.2→1.2.1, `cryptography`
   48.0.0→48.0.1, `daphne` 4.2.1→4.2.2 in `requirements.txt`; re-run
   `pip-audit` + the backend suite. For the residual `bleach` GHSA-g75f-g53v-794x
   (no fix yet), add a justified `--ignore-vuln` line in the workflow (revisit when
   6.x patches) per the existing suppression convention.
3. Keep this as a **separate dependency-bump PR** — do not fold into feature work.

## Acceptance Criteria

- [x] `cd web && npm audit --audit-level=moderate` exits 0 (or remaining items are
      justified/unfixable and documented). (2026-06-22: exit 0, 0 vulnerabilities.)
- [x] `cd backend && pip-audit -r requirements.txt` (with the documented
      `--ignore-vuln` set) exits 0. (2026-06-22: exit 0; existing ignore set
      unchanged — bleach 6.4.0 cleared the "no-fix" advisory too.)
- [x] Frontend + backend test suites green after the bumps (esp. forum/blog
      StreamField rendering with the new `dompurify`). (2026-06-22: web 551 passed
      incl. StreamFieldRenderer XSS + forum PostCard sanitization; backend 774
      passed / 8 skipped with bumps installed.)
- [x] `Security Scan Summary` check green on the bump PR. (2026-06-22: PR #384 —
      all 14 checks green incl. `Security Scan Summary`, `Frontend npm Security
      Scan`, `Backend Python Security Scan`, and the full backend pytest suite on
      Postgres+Redis. Merged to main as d20f708.)

## Work Log

### 2026-06-22 - Completed by completing-todos skill (sweep run 2026-06-22-0205)

- Verification: all 4 acceptance criteria passed. C1–C3 verified locally; C4
  (`Security Scan Summary`) confirmed green on PR #384 (14/14 checks), merged to
  main as d20f708.
- Review: 1 independent diff review, 0 blocking findings (2 low/informational
  notes, accepted). CI's kimi-review gate also passed on both commits.

### 2026-06-22 - Bumps applied + verified (C1–C3 green; C4 pending the PR)

**Changes made:**

- `backend/requirements.txt`: `bleach` 6.3.0→6.4.0, `cryptography` 48.0.0→48.0.1,
  `daphne` 4.2.1→4.2.2, `msgpack` 1.1.2→1.2.1.
- `web/package.json`: raised the two security-relevant DIRECT caret floors —
  `dompurify` ^3.4.2→^3.4.11, `react-router-dom` ^7.9.5→^7.18.0.
- `web/package-lock.json`: regenerated by `npm audit fix` (no `--force`) + `npm
  install`. Transitive fixes (lockfile only): `undici`→7.28.0, `vite`→8.0.16,
  `@babel/core`→7.29.7, `form-data`→4.0.6. All bumps stayed within their existing
  major — no breaking major jumps.

**Deviations from the todo's plan (both make it simpler, not bigger):**

- **No `security-scan.yml` change.** The todo expected to add a justified
  `--ignore-vuln` for the residual `bleach GHSA-g75f-g53v-794x` ("no fix version
  listed yet"). After bumping to 6.4.0, pip-audit reports that advisory gone too —
  6.4.0 is outside its affected range (the empty "Fix Versions" column at baseline
  was just pip-audit not listing a fixed version). So the existing 6-entry ignore
  set is unchanged.
- **`package.json` direct-dep caret floors raised** rather than left at the old
  carets. `npm audit fix` only touched the lockfile (the old carets already
  permitted the fixed versions); bumping the two floors makes the security floor
  explicit per the todo's "pin the resulting versions" instruction. Transitive
  fixes stay lockfile-only (correct).

**Verification (evidence):**

- C1 `cd web && npm audit --audit-level=moderate` → exit 0, "found 0 vulnerabilities".
- C2 `cd backend && venv/bin/pip-audit -r requirements.txt` + existing 6 `--ignore-vuln`
  flags → exit 0, "No known vulnerabilities found, 3 ignored". (`wagtail-forum`
  local pkg is a non-fatal "not on PyPI" skip.)
- C3 web: `npm run type-check` clean, `npm run lint` 0 errors, `npm run test`
  **551 passed (36 files)** incl. StreamFieldRenderer XSS-protection suite + forum
  PostCard sanitization against dompurify 3.4.11.
- C3 backend: bumps installed into `backend/venv`; `manage.py check` → "no issues";
  full pytest suite `venv/bin/pytest --reuse-db` → **774 passed, 8 skipped** (fresh
  test DB built via `--create-db`; an earlier 81-fail run was a stale `--reuse-db`
  artifact, not the bumps — re-ran clean on a fresh DB).
- C4 NOT satisfiable locally — needs the bump PR so CI's "Security Scan Summary"
  runs. **This todo stays `in_progress`; its deliverable is the PR.** `bleach` is
  not imported by app code (transitive only), so the bump carries no app-behavior risk.

**Code review (independent agent, 2026-06-22):** CLEAN — no blocking findings.
Lockfile integrity verified authoritatively (byte-identical `npm install
--package-lock-only` regen; 0 packages added/removed; all majors preserved). Two
low/informational notes, neither blocking: the wider dev-toolchain churn
(@babel/*, vite, rolldown) is the expected result of `npm audit fix` + the raised
caret floors; `undici` is a build/test (dev) dep, not shipped.

### 2026-06-22 - Started by completing-todos skill (sweep run 2026-06-22-0205)

- Picked up by automated workflow. Driven directly (security-sensitive — not delegated).
- Env confirmed: node v24.9.0 / npm 11.6.0, web/node_modules present; backend/venv
  has pip-audit + pytest (Python 3.13.9). Existing pip-audit `--ignore-vuln` set
  lives in `.github/workflows/security-scan.yml` (lines 55-61), one documented line
  per suppression — will follow that convention for the residual bleach advisory.

### 2026-06-21 - Created

- Surfaced during PR #374 (Forum Spec 2 Phase 1) review. The PR itself changed no
  dependency manifests; these advisories are pre-existing and time-based (live
  advisory DB). Filed as a standalone dependency-bump follow-up. Related: todo 089
  (pip-audit suppression mechanism).
