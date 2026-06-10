---
status: pending
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

- [ ] Workflow runs on PRs and posts findings as comments.
- [ ] Workflow permissions are minimal and the action is SHA-pinned.
- [ ] Decision recorded (required vs advisory) after trial PRs, in this todo's
      work log.

## Work Log

### 2026-06-10 - Created

- Filed from harness audit session (recommendation #6).
