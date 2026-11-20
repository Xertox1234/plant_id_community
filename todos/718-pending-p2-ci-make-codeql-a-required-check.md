---
status: pending
priority: p2
issue_id: "718"
tags: [ci, security, github, codeql, owner]
dependencies: []
triage: ready
triaged: 2026-11-20
owner_decision: "Owner: gate through the ruleset code_scanning rule at the critical threshold (keep or confirm), and rename RATELIMIT_CLIENT_IP_META_KEY to stop the false positive (2026-11-20)"
---

# CI: make CodeQL block a merge to main

## Problem

CodeQL runs on every pull request but is not a required check, so a PR armed
with auto-merge merges straight past new CodeQL alerts. The review rounds do
not catch it either: CodeQL runs on the pushed PR, after the reviewers have
finished. The only guard today is a person remembering to read the CodeQL
check's title after arming a PR.

## Findings

- Branch protection on `main` requires five checks (read 2026-11-19 with
  `gh api repos/Xertox1234/plant_id_community/branches/main/protection/required_status_checks`):
  "Install dependencies and run Django checks", "Run backend test suite
  (pytest, postgres + redis)", "Type-check, lint, and unit/component tests",
  "Hook self-tests and Python inject tests" and "mobile-ci-gate". CodeQL is
  not among them.
- CodeQL is on GitHub's default setup (`code-scanning/default-setup` reports
  `configured`). There is no CodeQL workflow file in `.github/workflows/`.
- It has already happened once: on 2026-10-11, PR #1028 was armed and its
  CodeQL check failed with "12 new alerts including 11 high". Auto-merge would
  have merged it. Eleven were `py/clear-text-logging-sensitive-data` false
  positives (CodeQL treats `settings.RATELIMIT_CLIENT_IP_META_KEY`, a header
  name, as a secret because of `*_KEY`); one (`py/stack-trace-exposure`) was
  real and was fixed.
- Not verified: whether default setup reports a CodeQL result on a PR that
  changes none of the analyzed languages (a Dart-only or docs-only PR). If it
  reports nothing, a plain required status check would leave such a PR waiting
  forever.

## Recommended Action

1. Pick the mechanism. GitHub offers two:
   - a repository ruleset on `main` with the "Require code scanning results"
     rule, which names the tool (CodeQL) and the alert severities that block;
   - adding the `CodeQL` check to the required status checks in branch
     protection.
   Prefer the ruleset if it does not block PRs that CodeQL has nothing to
   analyze; settle the "Not verified" finding above first, with a Dart-only
   test PR.
2. Decide the blocking threshold (for example: security alerts high and
   above, errors only) and record it here.
3. Deal with the known false positive before turning it on, or every PR that
   logs a client IP is blocked: either a CodeQL config that excludes
   `py/clear-text-logging-sensitive-data` for that source, or renaming
   `RATELIMIT_CLIENT_IP_META_KEY` so it no longer matches `*_KEY`.
4. Owner (or with the owner's OK, since it changes repository security
   settings): apply the rule.
5. Update the root `CLAUDE.md` and the `completing-todos` skill wherever they
   say main requires five checks or tell the reader to check the CodeQL title
   by hand.

## Acceptance Criteria

- [ ] The chosen mechanism and blocking threshold are recorded in this todo.
- [ ] A test PR that adds a known CodeQL alert at or above the threshold
      cannot be merged, and auto-merge does not merge it (record the PR
      number).
- [ ] A Dart-only PR and a docs-only PR can still merge without waiting on a
      CodeQL result that never arrives (record both PR numbers).
- [ ] A PR that logs a client IP through `log_safe_ip` is not blocked by
      `py/clear-text-logging-sensitive-data`.
- [ ] `CLAUDE.md` and the todo skills no longer describe CodeQL as outside
      the merge gate.

## Work Log

### 2026-11-19 - Filed

- Owner: "file a todo to make Code QL required", after arming auto-merge on
  PR #1382 and being told CodeQL would not hold it.
