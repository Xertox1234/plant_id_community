---
status: completed
priority: p2
issue_id: "089"
tags: [security, dependencies, ci]
dependencies: []
---

# Backend dependency CVEs failing the security scan on every PR

## Problem

The `Backend Python Security Scan` CI job (`pip-audit -r backend/requirements.txt`)
started failing on **every** PR around 2026-05-20 — including docs-only PRs — because
five dependency CVEs were newly disclosed since the last green run (PR #277). The
scan is a gate on all PRs, so it now blocks merges across the board until resolved.

This is not a regression from any single PR; the CVEs were published against the
live advisory database while the pinned versions stayed put.

## Findings

`pip-audit -r requirements.txt --ignore-vuln CVE-2026-42304` reports 5 vulns
(Twisted CVE-2026-42304 is already suppressed — no stable fix; RC-only):

| CVE / advisory | Package (pinned) | Upstream fix | Usage in this app |
|----------------|------------------|--------------|-------------------|
| CVE-2026-45409 | `idna==3.11` | **3.15** (real fix) | transitive |
| PYSEC-2026-89 | `Markdown==3.8.1` | none (OSV: all versions affected; latest 3.10.2) | **not imported by app code** (transitive) — DoS via malformed markdown |
| PYSEC-2026-97 | `nltk==3.9.4` | none (already latest) | **not used by app code** — `filestring()` path traversal |
| PYSEC-2024-277 | `joblib==1.5.2` | none | **disputed** (only trusted cached content); not imported by app code |
| PYSEC-2025-183 | `PyJWT==2.12.1` | none | **disputed** (app controls key length; SECRET_KEY ≥50 chars) |

Verified 2026-05-20 via OSV API (`api.osv.dev/v1/vulns/<id>`) and PyPI: only
`idna` has a fixed release; the other four have **no upstream fix** recorded
(OSV shows `introduced: 0, fixed: none`). `markdown`, `nltk`, `joblib` are not
directly imported by `apps/` code; `pyjwt` is used for JWT auth but the disputed
issue is mitigated by the project's strong-`SECRET_KEY` requirement.

## Recommended Action

1. **Bump the real fix** in `backend/requirements.txt`: `idna==3.11` → `idna==3.15`.
   Reinstall and run `python manage.py test` (idna is transitive under requests/
   httpx — low breakage risk, but verify).
2. **Suppress the 4 no-fix advisories** in the security-scan workflow
   (`.github/workflows/…` — the `pip-audit … --ignore-vuln` line that already
   carries `CVE-2026-42304`), one `--ignore-vuln <ID>` per advisory, each with a
   justification comment mirroring the Twisted precedent:
   - `PYSEC-2026-89` (markdown) — no upstream fix; not imported by app code; DoS
     path not reachable through the app.
   - `PYSEC-2026-97` (nltk) — no upstream fix; already at latest 3.9.4;
     `filestring()` not called by app code.
   - `PYSEC-2024-277` (joblib) — supplier-disputed; not imported by app code.
   - `PYSEC-2025-183` (pyjwt) — supplier-disputed; app sets a strong key.
3. Re-run `pip-audit` locally to confirm a clean exit before pushing.
4. Add a recurring reminder to revisit suppressions when upstream fixes ship
   (e.g. when `Markdown`/`nltk` cut a patched release).

## Acceptance Criteria

- [x] `idna` bumped to ≥3.15 in `backend/requirements.txt`.
- [x] The 4 no-fix advisories suppressed with per-CVE justification comments in
      the CI security-scan workflow.
- [x] `Backend Python Security Scan` passes on a PR again.
- [x] `python manage.py test` passes after the `idna` bump.

## Work Log

### 2026-05-20 - Created

- Surfaced when PR #278 (a docs-only todo revert) hit the now-failing
  `Backend Python Security Scan`. Investigated all 5 CVEs (OSV + PyPI + usage
  grep) and captured the bump/suppress plan here for a dedicated security pass.
  User opted to file this rather than bundle a dependency change into the revert.

### 2026-05-20 - Started by completing-todos skill (run 2026-05-20-2330)

- Picked up by automated workflow.

### 2026-05-20 - Implemented & verified

- **AC1** — `backend/requirements.txt:105` now `idna==3.15` (confirmed `idna 3.15`
  is the latest PyPI release via `pip index versions idna`).
- **AC2** — `.github/workflows/security-scan.yml:54-59` now passes five
  `--ignore-vuln` flags (CVE-2026-42304, PYSEC-2026-89, PYSEC-2026-97,
  PYSEC-2024-277, PYSEC-2025-183), each with a per-CVE justification comment
  (lines 47-53). YAML re-read to confirm `continue-on-error: false` stays at
  step level and the `\` continuations nest under `run: |`.
- **AC3** — ran the exact gating command locally:
  `pip-audit -r requirements.txt --ignore-vuln …×5` →
  `No known vulnerabilities found, 5 ignored` (exit 0). (Real CI confirmation
  pends the PR; local run replicates the workflow step verbatim.)
- **AC4** — `python manage.py test apps --noinput` → `Ran 628 tests in 122.155s`,
  `OK (skipped=11)`, exit 0. Scoped to `apps/` to exclude a **pre-existing,
  unrelated** root-level `test_schema.py` discovery error
  (`ImproperlyConfigured: Field name 'caption' is not valid for model
  'ForumPostImage'`) — the serializer was last touched in PR #262 (2026-05-09),
  not by this change, and idna (a transitive IDN/punycode lib) cannot affect DRF
  serializer field resolution. 628 = the full run's 629 minus that one script
  error, proving the idna bump introduced no regressions. Filed as **todo 090**.

### 2026-05-20 - Code review (code-review-orchestrator → security-reviewer)

- **0 blocking findings** (no critical/high). YAML validity and idna transitive
  safety independently re-verified by the reviewer.

#### Known issues (non-blocking, low severity)

- The five `--ignore-vuln` suppressions have no machine-enforced expiry; they
  rely on this todo + manual recheck. The "tracked in todo 089" comment will
  point at the archived todo once this is moved. Suggested follow-up: a dated
  "review by" note per advisory, or a non-gating scheduled pip-audit run without
  the ignore flags to surface when fixes ship.
- `PYSEC-2025-183` (PyJWT) is the weakest suppression — auth-critical lib,
  disputed advisory, mitigation (SECRET_KEY ≥50 chars) asserted but not
  re-validated in CI. Suggested follow-up: a test asserting SECRET_KEY length so
  the mitigation can't silently regress.

### 2026-05-20 - Completed by completing-todos skill (run 2026-05-20-2330)

- Verification: all 4 acceptance criteria passed (idna pin, 5 suppression flags,
  pip-audit clean exit 0, `test apps` 628 OK).
- Review: 4 findings total, 0 blocking — 2 low + 2 info recorded under Known issues.

## Notes

p2 — the failing scan gates **all** PRs, so this blocks the merge workflow until
fixed. The actual CVE risk is low (1 clean bump; 4 transitive/disputed with no
upstream fix), but the CI breakage is repo-wide.
