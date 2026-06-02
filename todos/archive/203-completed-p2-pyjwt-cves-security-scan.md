---
status: completed
priority: p2
issue_id: "203"
tags: [security, dependencies, ci, backend]
dependencies: []
---

# Backend security scan red: 4 new pyjwt 2.12.1 CVEs (fix = bump to 2.13.0)

## Problem

The `Backend Python Security Scan` CI job (`pip-audit -r backend/requirements.txt`)
started failing on **every** PR on 2026-06-02 — including frontend-only PRs (first
observed on PR #324, the Green Thumb web migration, which changed zero Python) —
because four `pyjwt` CVEs were newly disclosed against the pinned `PyJWT==2.12.1`.
Unlike the previously-suppressed advisories, **these have a real upstream fix**
(`pyjwt 2.13.0`), so the correct action is a version bump, not a suppression.

This is not a regression from any single PR; the advisories were published against
the live OSV/PyPI database while the pinned version stayed put. `pyjwt` is the JWT
auth dependency (SIMPLE_JWT signs/verifies with it), so this is security-relevant,
not merely a scan-hygiene nuisance.

## Findings

- `pip-audit` output (run `26837363493`, 2026-06-02) reported, after the existing
  `--ignore-vuln` suppressions: `Found 4 known vulnerabilities, ignored 2 in 1 package`:

  | Advisory | Package (pinned) | Fix version |
  |----------|------------------|-------------|
  | PYSEC-2026-175 | `pyjwt==2.12.1` | **2.13.0** |
  | PYSEC-2026-177 | `pyjwt==2.12.1` | **2.13.0** |
  | PYSEC-2026-178 | `pyjwt==2.12.1` | **2.13.0** |
  | PYSEC-2026-179 | `pyjwt==2.12.1` | **2.13.0** |

- These are **distinct** from the already-suppressed `PYSEC-2025-183` (pyjwt,
  supplier-disputed, mitigated by the ≥50-char `JWT_SECRET_KEY` fail-fast at
  `backend/<settings>.py`). Do not conflate; #203 is the fixable set.
- The check is **not a required status check**: PR #324 auto-merged (`aee51fb`)
  with this scan red. So it blocks nothing mechanically, but it leaves the security
  gate red on all PRs and masks any *future* genuinely-blocking CVE.
- The same workflow's **last green `main` run was the day before** (`f46898a`,
  2026-06-01) — confirming the failure is a live-advisory-DB event, not code.
- Adjacent suppression work appears to be in flight: an
  `origin/fix/pip-audit-cve-2026-31236` branch was pruned around the same time
  (likely merged). **Coordinate** so the pyjwt bump and any CVE-2026-31236
  suppression don't conflict in `requirements.txt` / the workflow's `--ignore-vuln`
  line. Discovered while reviewing PR #324 CI (2026-06-02).

## Recommended Action

1. On a **new backend branch** (never direct to `main` — JWT/auth-sensitive),
   bump in `backend/requirements.txt`: `PyJWT==2.12.1` → `PyJWT==2.13.0`
   (verify the exact case/pin format used in the file).
2. Reinstall (`pip install -r backend/requirements.txt`) and run the **full backend
   test suite** — auth/JWT paths especially: `python manage.py test apps.users
   --noinput` plus the broader suite. Token issue/refresh/verify must still pass.
3. Run `pip-audit -r backend/requirements.txt <existing --ignore-vuln flags>`
   locally and confirm a **clean exit (0)** — the 4 PYSEC-2026-17x advisories
   should disappear once on 2.13.0; do **not** add `--ignore-vuln` for them.
4. Rebase onto latest `main` first if the `fix/pip-audit-cve-2026-31236` work has
   landed, to avoid clobbering its suppression entries.
5. Open a PR; confirm `Backend Python Security Scan` + `Security Scan Summary`
   go green.

## Technical Details

- Failing jobs: `Backend Python Security Scan` → `Security Scan Summary`
  (workflow under `.github/workflows/`; the `pip-audit … --ignore-vuln …` step).
- Pin lives in `backend/requirements.txt`.
- Suppression precedent + the disputed-pyjwt rationale are documented in
  `todos/archive/089-completed-p2-backend-dependency-cves.md` and
  `todos/archive/136-completed-p2-add-cve-2026-31236-to-pip-audit-ignore.md`.
- JWT key-length fail-fast guard (the existing PYSEC-2025-183 mitigation) is in the
  backend settings module — keep it; it is independent of this bump.

## Acceptance Criteria

- [x] `backend/requirements.txt` pins `PyJWT==2.13.0` (or newer).
- [x] `pip-audit -r backend/requirements.txt` (with current suppression flags) exits 0 locally.
- [x] No new `--ignore-vuln` entry was added for PYSEC-2026-175/177/178/179 (they are fixed, not suppressed).
- [x] Backend test suite passes, including `apps.users` JWT token issue/refresh/verify.
- [x] `Backend Python Security Scan` + `Security Scan Summary` are green on the fix PR.

## Work Log

### 2026-06-02 - Filed

- Surfaced while reviewing PR #324 (Green Thumb web migration) CI: the only red
  check was this backend dependency scan, unrelated to the frontend change.
  Diagnosed the 4 new fixable pyjwt advisories and confirmed the prior-day green
  `main` run. Created as a backend follow-up.

### 2026-06-02 - Started by completing-todos skill (run 2026-06-02-1833)

- Picked up by automated workflow on branch `fix/pyjwt-2.13.0-security-cves`.
- Orientation confirmed: `backend/requirements.txt:160` pins `PyJWT==2.12.1`;
  `djangorestframework_simplejwt==5.5.1` requires only `pyjwt>=1.7.1` (no upper
  bound) so 2.13.0 is compatible; the `CVE-2026-31236` suppression already landed
  on `main` (`security-scan.yml:54,61`) so no rebase/coordination conflict; the
  4 PYSEC-2026-17x advisories are NOT in the workflow `--ignore-vuln` list.

### 2026-06-02 - Local verification (criteria 1–4 passed)

- **Criterion 1 (pin):** `grep "^PyJWT==" backend/requirements.txt` → `160:PyJWT==2.13.0`.
- **Criterion 2 (pip-audit clean):** ran with the exact six CI `--ignore-vuln`
  flags from `security-scan.yml:56-61` against `backend/requirements.txt` →
  `No known vulnerabilities found, 2 ignored` / `PIP_AUDIT_EXIT=0`. The four
  PYSEC-2026-175/177/178/179 advisories no longer appear — fixed by 2.13.0.
- **Criterion 3 (no over-suppression):** `grep -E "PYSEC-2026-17[5789]"
  .github/workflows/security-scan.yml` → none present. The fixed advisories were
  cleared by the bump, not papered over with new ignore flags.
- **Criterion 4 (JWT tests):** `python manage.py test apps.users --noinput` →
  `Ran 99 tests in 15.107s / OK`. Run explicitly exercised token issue/refresh
  (valid, invalid, rotation, last_login, CSRF, missing-token), JWT cookie
  set/verify, and the Firebase→Django auth suite. PyJWT is used only by
  SIMPLE_JWT sign/verify, so `apps.users` is the comprehensive coverage for this
  bump; the full backend suite runs via CI `backend-tests` on the PR.
- **Criterion 5** remains open pending PR push + `Backend Python Security Scan` /
  `Security Scan Summary` reporting green on the PR.

### 2026-06-02 - Code review (security/dependency lens)

- Verdict: **APPROVE, nothing blocking.** Independent review confirmed (primary
  source): no direct PyJWT API usage anywhere in `backend/` app code (only
  `simplejwt`'s `TokenError` wrapper) — the new CVEs concern `PyJWKClient`/JWK/URI
  paths the app (HS256 + string `SIGNING_KEY`) never exercises; the PYSEC-2025-183
  `JWT_SECRET_KEY` >=50-char fail-fast guard (`settings.py`) is intact and untouched.

#### Known issues (non-blocking)

- **LOW — FIXED in this PR:** `security-scan.yml:53` suppression comment said
  `(PyJWT 2.12.1)`, made stale by this bump → updated to `(PyJWT 2.13.0)`.
  Did **not** remove the `--ignore-vuln PYSEC-2025-183` flag (reviewer's optional
  "cleaner" suggestion): it is currently vestigial on 2.13.0 but keeping it is the
  advisory-DB-resilient choice — suppressed-vs-fixed status shifts over time (this
  todo is itself proof), and the flag is harmless while matched-to-nothing.
- **INFO — out of scope:** `requirements-dev.txt:124` still pins `PyJWT==2.10.1`
  (inside the affected range of the 4 CVEs). Not gated — CI installs only
  `requirements.txt` (`backend-ci.yml:56,164`; `security-scan.yml` audits only
  `requirements.txt`) — and that dev file is already broadly stale vs prod. Left
  for a separate dependency-hygiene follow-up; bumping only its PyJWT line would be
  an arbitrary touch on an already-divergent file.

### 2026-06-02 - Completed by completing-todos skill (run 2026-06-02-1833)

- PR #326 (`fix/pyjwt-2.13.0-security-cves`) opened against `main`.
- Verification: all 5 acceptance criteria passed. Criterion 5 confirmed on the PR —
  `Backend Python Security Scan` **pass** (1m2s), `Security Scan Summary` **pass**,
  and `Run backend test suite (pytest, postgres + redis)` **pass** (5m43s, full
  backend suite). Every PR check green.
- Review: 2 findings, 0 blocking — 1 LOW fixed in-PR (stale workflow comment),
  1 INFO left as out-of-scope dependency-hygiene follow-up (`requirements-dev.txt`
  PyJWT==2.10.1).

## Notes

- **P2**: real security fix with an available upstream patch, but the check is
  non-required so it isn't blocking merges today. Should be done promptly — a red
  security gate normalizes ignoring it and hides the next blocking CVE.
- Related: [089] (no-fix advisory suppressions), [136] (CVE-2026-31236 suppression).
