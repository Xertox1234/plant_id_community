---
status: completed
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

- [x] Security Review observed on ≥2 real PRs; signal/noise assessed.
      (Ran on ~17 distinct real PR branches since #398; all runs `success`;
      0 findings / 0 false positives. Evidence in 2026-06-27 work-log entry.)
- [x] Required-vs-advisory decision made and recorded in this todo's work log.
      (Decision: **keep advisory**. See 2026-06-27 entry.)
- [x] If promoted: "Claude Code Security Review" added to branch-protection
      required checks, and fork-PR skip semantics confirmed non-blocking.
      **N/A — not promoted.** Fork-skip semantics reasoned from the workflow
      YAML (job concludes `success` with inner steps skipped when the secret
      is absent) but left untested and moot, since the check stays advisory.

## Work Log

### 2026-06-23 - Created

- Split from todo 228 AC3 (run 2026-06-23-1702). 228 shipped the workflow and
  verified it operational (PR #398 dogfood run: ran on PR, scan completed, 0
  findings, minimal runtime perms confirmed). This todo tracks only the
  post-deploy required-vs-advisory decision.

### 2026-06-27 - Started by completing-todos skill (run 2026-06-27-1451)

- Picked up by automated workflow.

### 2026-06-27 - Decision: KEEP ADVISORY (do not promote to required)

**Observed coverage (AC1).** Since the workflow landed in #398 (todo 228), the
Security Review ran on ~17 distinct real PR branches (#399–#415 range), every run
`conclusion: success` (`gh run list --workflow=security-review.yml`). That far
exceeds the ≥2-PR bar. Scan execution (not a silent skip) confirmed on a sample:
on runs for #412 and #414 the gated steps "Checkout PR head" and "Run Claude Code
security review" report `success`, not `skipped` — which only happens when
`enabled=true`, i.e. the `ANTHROPIC_API_KEY` secret is present (verified set,
`gh secret list`). The action stays silent on zero findings
(`scripts/comment-pr-findings.js` L103: `if (newFindings.length === 0) return`),
and 0 security-review comments appeared on the 4 sampled post-#398 PRs
(#400/#406/#412/#414). #395/#396 are *not* data points — they merged before the
workflow existed; the only inline findings there are from CodeQL
(`github-advanced-security[bot]`), a separate always-on tool.

**Signal/noise (AC1).** Acceptable: 0 false positives across the sample. By the
todo's literal bar ("promote if signal/noise is acceptable"), that condition is
*met*. Caveat: 0 true positives too — no demonstrated catch yet. These diffs
already clear two prior review layers (the `kimi-review` commit gate and
`code-review-orchestrator`), so a near-zero finding rate is expected, not proof
of a weak scanner.

**Why advisory still wins despite acceptable signal/noise (AC2).** Promotion is
the toothless option here, by the action's design:
- The action **never fails the job on findings.** It counts `findings_count` and
  posts PR comments, but there is no `exit 1` on findings anywhere in upstream
  `action.yml` (the only non-zero exit is a missing API key, which our `check-key`
  guard already prevents). The job concludes `success` whether findings exist or
  not.
- Therefore a *required* check could only enforce "the review job completed
  before merge" — it can **not** block a merge on an actual security finding.
- Under the repo's auto-merge habit (`gh pr merge --auto --squash`), the job
  always reports success, so auto-merge fires regardless. The only practical
  deltas of promotion are (a) added merge latency — every merge waits on the
  billed Claude API call to finish — and (b) coupling every merge to Anthropic
  API availability/quota. No security gate is gained for that cost.

**Fork semantics (AC3, conditional → N/A).** Not promoting, so this is moot. For
the record: the job has no job-level `if`; on a fork PR the secret is absent, the
`check-key` step sets `enabled=false`, the inner steps skip, and the **job still
concludes `success`** (skipped steps don't fail a job). So even if it were
required, fork PRs would not be blocked. Reasoned from the YAML, not tested — the
repo has no external fork contributions to exercise it, and it doesn't matter
while the check is advisory.

**Documented future option (out of scope here).** If a genuine hard merge-gate on
security findings is ever wanted, that is a *workflow change*, not a settings
change: add a step that fails the job when `findings-count` exceeds a severity
threshold, after tuning `false-positive-filtering-instructions`. The todo
deliberately scopes promotion as a settings-only change, so that path is left as
a future todo if desired.

**Outcome.** Branch protection unchanged; "Claude Code Security Review" stays off
the required-checks list. Re-evaluate only if (a) a real finding is ever posted
and acted on, or (b) we add a fail-on-severity workflow step worth gating on.

### 2026-06-27 - Completed by completing-todos skill (run 2026-06-27-1451)

- Verification: all 3 acceptance criteria passed (AC1/AC2 evidence-backed; AC3
  N/A — not promoted).
- Review: no source-code changes (todo markdown only) — `code-review-orchestrator`
  routes zero reviewers for a docs-only diff; code review is a no-op. 0 findings.
- Decision recorded: keep the Security Review action **advisory**, not required.
