---
status: pending
priority: p4
issue_id: "249"
tags: [security, ci, github-actions, review]
dependencies: ["239"]
---

# Add a fail-on-severity gate to the PR Security Review (true merge-block)

## Problem

Todo 239 decided to keep `.github/workflows/security-review.yml` **advisory**,
because the upstream `anthropics/claude-code-security-review` action **never exits
non-zero on findings** — it counts `findings_count`, posts PR comments, and exits
`success` regardless. Consequence: promoting the check to a *required* branch-
protection check would only enforce "the job ran", not block a merge on an actual
security finding. The only way to get a real merge-gate is a **workflow change**
that fails the job when findings cross a severity threshold. This todo captures
that future option so it isn't lost.

## Findings

- Upstream `action.yml` (pinned commit `0c6a49f1…` in our workflow) has no
  `exit 1` on findings; the only non-zero exit is a missing API key, which our
  `check-key` step already guards. Verified during todo 239.
- The action exposes two outputs usable by a downstream gate step:
  - `findings-count` — total number of findings (post false-positive filtering).
  - `results-file` — path to `claudecode-results.json`; the action also copies
    `findings.json` and `claudecode-results.json` to `${{ github.workspace }}`.
- Observed signal to date (todo 239): 0 findings / 0 false positives across
  ~17 real PRs since #398. No demonstrated catch yet — so there is currently no
  evidence-based pressure to gate. This todo is appetite-driven, not bug-driven.

## Proposed Solutions

### Option 1: Severity-filtered gate (Recommended)

- **Implementation:** add a step after "Run Claude Code security review" that
  reads `${{ github.workspace }}/claudecode-results.json`, counts findings whose
  severity is at/above a chosen threshold (e.g. `HIGH`/`CRITICAL`), and
  `exit 1` if any exist. Guard it with
  `if: steps.check-key.outputs.enabled == 'true'` so fork PRs (scan skipped)
  are never blocked. Then promote to a required check in branch protection.
- **Pros:** real merge-block on high-severity findings; low-severity findings
  stay advisory (comments only); fork-safe.
- **Cons:** only as trustworthy as the false-positive rate — a noisy gate that
  blocks merges on bad findings is worse than no gate. Needs FP tuning first.
- **Effort:** ~1–2 hours (step + a dry-run period before flipping to required).
- **Risk:** medium — a false positive at/above threshold blocks a legitimate
  merge until dismissed. Mitigate with a tuning/observation window.

### Option 2: Count-based gate (any finding fails)

- **Implementation:** `if: steps.review.outputs.findings-count != '0'` → fail.
- **Pros:** trivial.
- **Cons:** too aggressive — every finding, including low-impact/FP-prone ones,
  blocks the merge. Rejected unless the FP rate is proven ~0 over a long window.

### Option 3: Do nothing (status quo)

- Keep advisory indefinitely; rely on the `kimi-review` commit gate +
  `code-review-orchestrator` + CodeQL (`github-advanced-security[bot]`) for
  actual blocking signal. Valid until a real finding shows the advisory comment
  was missed.

## Recommended Action

1. Tune first: set `false-positive-filtering-instructions` (and, if useful,
   `custom-security-scan-instructions`) on the action step and observe a few PRs.
2. Add the severity-filtered gate step (Option 1), guarded on
   `enabled == 'true'`, parsing `claudecode-results.json` for severity.
3. Run it **non-blocking first** (e.g. `continue-on-error: true` or log-only) for
   a 2–3 PR window to confirm it only trips on real high-severity findings.
4. Remove the soft-fail, then promote "Claude Code Security Review" to a required
   status check in branch protection.
5. Re-confirm fork-PR semantics: the gate step must be skipped (not failed) when
   the scan is skipped, so a fork PR's job still concludes `success`.

## Technical Details

- Workflow: `.github/workflows/security-review.yml`. Today: `check-key` →
  `Checkout PR head` (if enabled) → `Run Claude Code security review` (if enabled).
  The gate step inserts after the review step, same `if` guard.
- Results JSON shape: `{"findings": [{"severity": "...", ...}], ...}` (confirm
  exact severity field/enum from a run artifact — the workflow already uploads
  `security-review-results` for 7 days when `upload-results` is on, or read the
  copied `${{ github.workspace }}/claudecode-results.json`).
- Promotion itself is a repo-settings change (branch protection), mirroring how
  the Cloudflare Workers check is treated (project_cloudflare_workers_check).
- Parent decision + full evidence: `todos/archive/239-completed-p3-promote-security-review-required-check.md`.

## Acceptance Criteria

- [ ] Gate step added, guarded on `enabled == 'true'`, parsing severity from the
      results JSON (not just a raw count).
- [ ] Soft-fail observation window completed: the gate tripped only on genuine
      at/above-threshold findings (or there were none) across ≥2 PRs.
- [ ] Gate made blocking and "Claude Code Security Review" added to
      branch-protection required checks.
- [ ] Fork-PR semantics re-confirmed: a skipped-scan job still concludes
      `success` (gate step skipped, not failed).

## Work Log

### 2026-06-27 - Created

- Filed from todo 239's "documented future option". 239 kept the check advisory
  because the action can't block on findings; this todo tracks the workflow
  change that would make a real merge-gate possible, if/when there's appetite.

## Notes

- **Priority p4 (deferred, appetite-driven):** there is no demonstrated need —
  0 findings over ~17 real PRs, and three other layers already provide blocking
  signal (kimi-review, code-review-orchestrator, CodeQL). Bump to p3 if a real
  high-severity finding is ever posted and slips through as a mere comment.
- Depends on 239 only for lineage (239 is already complete/archived).
