---
status: pending
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

- [ ] `idna` bumped to ≥3.15 in `backend/requirements.txt`.
- [ ] The 4 no-fix advisories suppressed with per-CVE justification comments in
      the CI security-scan workflow.
- [ ] `Backend Python Security Scan` passes on a PR again.
- [ ] `python manage.py test` passes after the `idna` bump.

## Work Log

### 2026-05-20 - Created

- Surfaced when PR #278 (a docs-only todo revert) hit the now-failing
  `Backend Python Security Scan`. Investigated all 5 CVEs (OSV + PyPI + usage
  grep) and captured the bump/suppress plan here for a dedicated security pass.
  User opted to file this rather than bundle a dependency change into the revert.

## Notes

p2 — the failing scan gates **all** PRs, so this blocks the merge workflow until
fixed. The actual CVE risk is low (1 clean bump; 4 transitive/disputed with no
upstream fix), but the CI breakage is repo-wide.
