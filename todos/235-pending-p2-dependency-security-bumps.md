---
status: pending
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

- [ ] `cd web && npm audit --audit-level=moderate` exits 0 (or remaining items are
      justified/unfixable and documented).
- [ ] `cd backend && pip-audit -r requirements.txt` (with the documented
      `--ignore-vuln` set) exits 0.
- [ ] Frontend + backend test suites green after the bumps (esp. forum/blog
      StreamField rendering with the new `dompurify`).
- [ ] `Security Scan Summary` check green on the bump PR.

## Work Log

### 2026-06-21 - Created

- Surfaced during PR #374 (Forum Spec 2 Phase 1) review. The PR itself changed no
  dependency manifests; these advisories are pre-existing and time-based (live
  advisory DB). Filed as a standalone dependency-bump follow-up. Related: todo 089
  (pip-audit suppression mechanism).
