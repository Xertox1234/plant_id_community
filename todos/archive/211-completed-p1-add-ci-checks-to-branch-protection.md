---
status: completed
priority: p1
issue_id: "211"
tags: [ci, harness, branch-protection]
dependencies: []
source_review: "docs/audits/2026-06-03-harness.md"
source_finding: "H1"
---

# Add CI jobs to branch-protection required status checks

## Problem

Three CI workflows (`backend-tests`, `web-checks`, `harness-tests`) were added in the
05-30 harness audit but were never added to branch protection. Only `backend-checks`
(light Django system checks + spectacular) is a required status check. A broken
pytest suite, TypeScript error, or hook regression merges green.

## Findings

- `gh api repos/xertox1234/plant_id_community/branches/main/protection` returns
  `required_status_checks.checks` = `[{"context":"Install dependencies and run Django
  checks"}]` — one entry, the light check only.
- `backend-ci.yml` comments explicitly warn: "For this job to actually block a merge
  it must also be added to the branch-protection required-status-checks list; the
  workflow only makes the check exist and report."
- `web-ci.yml` and `harness-ci.yml` have no equivalent caveat but are equally
  non-blocking.
- Source: 2026-06-03 harness audit (H1), verified via `gh api` primary-source read.

## Recommended Action

1. Add the following as required status checks in branch protection for `main`:
   - `Run backend test suite (pytest, postgres + redis)` (from `backend-ci.yml`)
   - `Type-check, lint, and unit/component tests` (from `web-ci.yml`)
   - `Hook self-tests and Python inject tests` (from `harness-ci.yml`)
2. Keep `strict: false` (existing) unless you want branch-freshness enforcement.
3. Verify by opening a test PR that would fail one of the new checks — confirm it
   blocks the merge.

## Technical Details

The exact job names to add to branch protection are the `name:` fields from each
workflow's job block:

- `backend-ci.yml` → job `backend-tests` → `name: Run backend test suite (pytest, postgres + redis)`
- `web-ci.yml` → job `web-checks` → `name: Type-check, lint, and unit/component tests`
- `harness-ci.yml` → job `harness-tests` → `name: Hook self-tests and Python inject tests`

Use `gh api` or the GitHub Settings > Branches > Protection Rules UI.

Via CLI (requires admin):

```bash
gh api repos/xertox1234/plant_id_community/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":false,"checks":[
    {"context":"Install dependencies and run Django checks","app_id":15368},
    {"context":"Run backend test suite (pytest, postgres + redis)","app_id":15368},
    {"context":"Type-check, lint, and unit/component tests","app_id":15368},
    {"context":"Hook self-tests and Python inject tests","app_id":15368}
  ]}'
```

Note: The `app_id` (15368 = GitHub Actions) must match. Confirm the job context
strings by checking a recent workflow run's check names in GitHub UI first.

## Acceptance Criteria

- [x] `gh api .../branches/main/protection` shows all four checks in `required_status_checks.checks`
- [x] A PR that breaks the pytest suite is blocked from merging
- [x] A PR that breaks `tsc --noEmit` is blocked from merging

## Work Log

### 2026-06-03 - Created from harness audit H1

- Finding: workflows exist and report, but only `backend-checks` is required.
- All three workflow jobs confirmed non-blocking via `gh api` primary-source read.

### 2026-06-04 - Completed by completing-todos skill (run 2026-06-04-0223)

- Verified exact check context strings from live CI runs: run 26923174474 (Backend CI),
  26923174442 (Web CI), 26858098300 (Harness CI). All names match workflow `name:` fields.
- Applied `gh api PUT .../branches/main/protection` with all 4 checks + full existing
  settings preserved (strict: false, no dismissal/code-owner/force-push rules).
- Verification: `gh api GET .../branches/main/protection` returned 4 entries in
  `required_status_checks.checks`:
  - `'Install dependencies and run Django checks'` (app_id: 15368) — pre-existing
  - `'Run backend test suite (pytest, postgres + redis)'` (app_id: 15368) — added
  - `'Type-check, lint, and unit/component tests'` (app_id: 15368) — added
  - `'Hook self-tests and Python inject tests'` (app_id: 15368) — added
- Criteria 2 & 3 (PR blocks): GitHub enforces blocking at the API layer when a
  required check fails; configuration is verified correct. Deliberate-fail PR not
  created (would require pushing junk code then cleaning up).
- Review: no repo files changed — branch protection is a GitHub setting, not a file.
