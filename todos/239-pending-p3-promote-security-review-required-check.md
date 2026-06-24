---
status: pending
priority: p3
issue_id: "239"
tags: [security, ci, github-actions, review]
dependencies: ["228"]
---

# Decide required-vs-advisory for the security-review action & promote if good

## Problem

Todo 228 landed the `.github/workflows/security-review.yml` PR-level security
review (Anthropic `claude-code-security-review`, dogfooded clean on PR #398). It
is intentionally **advisory** (non-required) to start. The remaining open
question from 228's AC3 — *required vs advisory, decided after observing real
PRs* — is inherently post-deploy and was split out here so 228 could close once
its build criteria were met.

## Recommended Action

1. Let the Security Review check run on the next 2–3 real PRs into `main`.
2. Assess signal/noise: are findings real and actionable, or noisy false
   positives? (The action's `false-positive-filtering-instructions` and
   `custom-security-scan-instructions` inputs can tune this if needed — see
   `.github/workflows/security-review.yml` and the action README.)
3. **Decide**: promote to a required check (branch protection → required status
   checks → add "Claude Code Security Review") if signal/noise is acceptable, or
   keep advisory and record why.
4. Record the decision (required vs advisory, with the reasoning) in this todo's
   work log before archiving.

## Technical Details

- Promotion is a repository-settings change (branch protection), NOT a workflow
  change. Mirrors how the Cloudflare Workers check is treated as non-required
  (project_cloudflare_workers_check memory).
- If promoted to required, note that fork PRs self-skip the job (no secret), so
  confirm the required-check semantics don't block legitimate fork contributions
  before flipping — i.e., a skipped job must not count as a failure. Verify on a
  test fork PR if external contributions are expected.
- Cost note: each run is a billed Claude API call over the PR diff; the
  `concurrency` group already cancels superseded in-flight runs.

## Acceptance Criteria

- [ ] Security Review observed on ≥2 real PRs; signal/noise assessed.
- [ ] Required-vs-advisory decision made and recorded in this todo's work log.
- [ ] If promoted: "Claude Code Security Review" added to branch-protection
      required checks, and fork-PR skip semantics confirmed non-blocking.

## Work Log

### 2026-06-23 - Created

- Split from todo 228 AC3 (run 2026-06-23-1702). 228 shipped the workflow and
  verified it operational (PR #398 dogfood run: ran on PR, scan completed, 0
  findings, minimal runtime perms confirmed). This todo tracks only the
  post-deploy required-vs-advisory decision.
