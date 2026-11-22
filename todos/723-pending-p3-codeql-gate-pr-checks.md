---
status: pending
priority: p3
issue_id: "723"
tags: [ci, security, owner]
dependencies: ["718"]
triage: ready
triaged: 2026-11-22
owner_decision: "Owner OK: a worker may open throwaway PRs against main, incl. one with a deliberate critical CodeQL alert and auto-merge armed; each is closed and its branch deleted (owner 2026-11-22)"
---

# CodeQL merge gate: prove it with real PRs (from todo 718)

## Problem

Branch-protection ruleset 9138781 already has a `code_scanning` rule (CodeQL, security_alerts_threshold `critical`; read 2026-11-21). These checks prove it blocks what it should and nothing else.

## Findings

- Requiring the Analyze checks directly deadlocked Dependabot PRs in 2026-09 (docs/LEARNINGS.md); the ruleset rule does not.
- Todo 718 renames `RATELIMIT_CLIENT_IP_META_KEY` to stop a `py/clear-text-logging-sensitive-data` false positive.

## Recommended Action

Open a throwaway PR with a known critical alert and confirm it cannot merge; cite a Dart-only and a docs-only PR merged under the rule; open a PR that logs through `log_safe_ip` after 718 merges.

## Technical Details

- Ruleset: `gh api repos/<owner>/<repo>/rulesets/9138781`.
- Close and delete the throwaway PR's branch afterwards.

## Acceptance Criteria

- [ ] A test PR that adds a known CodeQL alert at or above the threshold cannot be merged, and
      auto-merge does not merge it (record the PR number; moved from 718 on 2026-11-21).
- [ ] A Dart-only PR and a docs-only PR can still merge without waiting on a CodeQL result that
      never arrives (record both PR numbers; moved from 718 on 2026-11-21).
- [ ] A PR that logs a client IP through `log_safe_ip` is not blocked by
      `py/clear-text-logging-sensitive-data` (moved from 718 on 2026-11-21).

## Work Log

### 2026-11-21 - Filed

- Filed from sweep run 2026-11-20-2202 on the owner's decision of 2026-11-21: these criteria were
  re-pointed here because they can only be checked after the parent's PR merges, or need the owner.
