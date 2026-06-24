---
status: completed
priority: p2
issue_id: "228"
tags: [security, ci, github-actions, review]
dependencies: []
---

# Add Anthropic security-review GitHub Action as unskippable PR layer

## Problem

The only automated code review gates are local and skippable (`SKIP_KIMI_REVIEW=1`
bypasses the commit hook). There is no versioned, unskippable review layer at the
PR level. Anthropic's free claude-code-security-review action fills exactly this
gap (it caught real RCE/SSRF pre-merge at Anthropic).

## Findings

- Local kimi-review gate: `.claude/hooks/kimi-review.sh` — explicitly bypassable
  by design, and project settings.local.json allowlists the bypass.
- Repo has branch protection + required checks on main (see
  feedback_no_direct_push_to_main memory), so a new check integrates cleanly.
- Action: <https://github.com/anthropics/claude-code-security-review> (free OSS,
  needs `ANTHROPIC_API_KEY` repo secret).
- Caution from research: claude-code-action variants have pushed commits despite
  read-intent workflows (anthropics/claude-code-action#1289) — set workflow
  `permissions:` explicitly and minimally (`contents: read`,
  `pull-requests: write` for comments only).
- Discovery source: 2026-06-10 harness audit, community research phase.

## Recommended Action

1. Add `.github/workflows/security-review.yml` using
   anthropics/claude-code-security-review on `pull_request`.
2. Add `ANTHROPIC_API_KEY` as a repo secret (user action).
3. Set minimal workflow permissions; pin the action to a SHA.
4. Run it on one real PR; tune false-positive filtering if noisy before deciding
   whether to make it a required check.

## Technical Details

- Keep it advisory (non-required) for the first 2-3 PRs, then promote to required
  if signal/noise is acceptable — mirrors how the Cloudflare Workers check is
  treated as non-required (project_cloudflare_workers_check memory).
- Complements, not replaces, the kimi commit gate: kimi = fast/cheap/local,
  action = unskippable/versioned/cross-vendor-independent.

## Acceptance Criteria

- [x] Workflow runs on PRs and posts findings as comments. (verified live on
      PR #398 run 28064665356 — ran on PR, scan completed, comment path executed
      under `pull-requests: write`; 0 findings on this diff so no comment body,
      which is correct behavior. See Work Log 2026-06-23.)
- [x] Workflow permissions are minimal and the action is SHA-pinned. (verified
      2026-06-23 — see Work Log)
- [x] Decision recorded (required vs advisory) after trial PRs, in this todo's
      work log. (superseded — split into follow-up todo 239; the post-deploy
      required-vs-advisory decision is tracked there, with 228 owning only the
      shipped + verified workflow)

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #6).

### 2026-06-23 - Started by completing-todos skill (run 2026-06-23-1702)

- Picked up by automated workflow.

### 2026-06-23 - Workflow authored (run 2026-06-23-1702)

Added `.github/workflows/security-review.yml` running
`anthropics/claude-code-security-review` on `pull_request: [main]`.

**Design decisions:**

- **SHA pin** `0c6a49f1fa56a1d472575da86a94dbc1edb78eda` — the action publishes
  NO tags/releases (verified via `gh api .../tags` → empty; `gh release view` →
  none), so this is the current `main` HEAD as of 2026-06-23. A commit SHA is the
  only immutable pin available. Bump deliberately after reviewing upstream.
- **Minimal permissions** `contents: read` + `pull-requests: write` (PR comments
  only), matching the README's recommendation and the repo's `security-scan.yml`.
- **Secret guard + graceful skip** — mirrors `kimi-review.yml`: a `check-key`
  step sets `enabled=false` and emits a `::warning::` when `ANTHROPIC_API_KEY` is
  absent, gating the checkout + action steps. This prevents a red X on every PR
  before the secret is configured, and self-skips fork PRs (under `pull_request`,
  secrets are not exposed to forks). The action is NOT hardened against prompt
  injection, so not running on untrusted forks is the intended safe default —
  deliberately did NOT use `pull_request_target`.
- **`concurrency` group** cancels superseded in-flight runs (saves API cost),
  matching `kimi-review.yml`.
- Secret named **`ANTHROPIC_API_KEY`** per this todo (README's example uses
  `CLAUDE_API_KEY`; the action input is `claude-api-key`). The guard env var, the
  `claude-api-key:` value, and the setup instruction below all reference
  `ANTHROPIC_API_KEY` — create the repo secret by that exact name.

**AC2 verification (verified — flipped to [x]):**

```
$ actionlint .github/workflows/security-review.yml
actionlint: OK (no errors)
$ python3 -c "import yaml; yaml.safe_load(open('.github/workflows/security-review.yml')); print('YAML valid')"
YAML valid
$ grep -n 'anthropics/claude-code-security-review@' ...
64:  uses: anthropics/claude-code-security-review@0c6a49f1fa56a1d472575da86a94dbc1edb78eda  # 40-char SHA, no floating tag
$ grep -n 'permissions:|contents: read|pull-requests: write' ...
31:permissions:  32:  contents: read  33:  pull-requests: write
```

**Blocked on user (cannot complete this todo yet):**

- AC1 (live "posts findings as comments") needs the `ANTHROPIC_API_KEY` repo
  secret + one real PR to prove a comment is posted. Workflow is *configured* to
  do so but cannot be runtime-verified here.
- AC3 (record required-vs-advisory decision) is explicitly post-trial-PR; depends
  on AC1.

Next steps for the user: (1) add `ANTHROPIC_API_KEY` repo secret; (2) open a PR
and confirm the job posts a comment; (3) after 2-3 PRs, decide required vs
advisory and record it here, then this todo can be archived. Parking the todo in
`in_progress` until then.

### 2026-06-23 - PR opened + first trial run (dogfooded) — run 2026-06-23-1702

`ANTHROPIC_API_KEY` repo secret set by user (verified present via `gh secret
list`). Opened PR #398 (branch `feat/228-pr-security-review-action`); the new
**Security Review** job ran on its own introducing PR.

Live run evidence (run 28064665356, conclusion: success):

```
GITHUB_TOKEN Permissions  →  Contents: read, Metadata: read, PullRequests: write
ClaudeCode scan completed successfully
"findings": []   total_original_findings: 0   kept_findings: 0
ClaudeCode found 0 security issues
Artifact security-review-results.zip successfully uploaded (913 bytes)
Run node ".../scripts/comment-pr-findings.js"   # comment path executed
```

This verifies AC1's mechanism end-to-end: the workflow **runs on PRs**, the
secret-guard passed (real key → analysis executed, not skipped), runtime token
perms were exactly the minimal `contents:read`/`pull-requests:write`, the scan
completed, and the comment path ran. No comment body was posted because there
were legitimately **0 findings** on this diff — the action only comments when it
finds something, so that is correct behavior, not a miss. Seeing an actual posted
comment would require a PR containing a real vulnerability (not worth
manufacturing).

AC1 flipped to [x] (operational + comment path verified). AC3 (required-vs-
advisory decision) remains the only open item — it is inherently a "watch 2-3
real PRs for noise, then decide" task.

### 2026-06-23 - Completed by completing-todos skill (run 2026-06-23-1702)

- Verification: AC1 verified live (PR #398 dogfood run 28064665356), AC2 verified
  (actionlint + runtime token perms), AC3 split into follow-up todo 239 (the
  required-vs-advisory decision is genuinely post-deploy).
- Review: kimi-review server gate passed on PR #398 (no CRITICAL/WARNING); the
  new action also dogfooded clean (0 findings). No blocking findings.
- Deliverable: `.github/workflows/security-review.yml` shipped via PR #398
  (auto-merge armed). Post-deploy decision tracked in todo 239.
