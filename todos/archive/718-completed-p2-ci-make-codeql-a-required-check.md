---
status: completed
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

## Decision

- **Mechanism:** the `code_scanning` rule of branch ruleset 9138781 on `main`
  (tool CodeQL), not a required status check. The rule already exists: todo 723
  read it on 2026-11-21 with `security_alerts_threshold` `critical`. Owner
  decision 2026-11-20: keep it. A required `Analyze` check is ruled out because
  it deadlocked every Dependabot PR on 2026-09-05 (`docs/LEARNINGS.md`).
- **Blocking threshold:** security alerts of severity **critical**. A new high or
  lower alert does not block a merge.
- **False positive:** the Django setting `RATELIMIT_CLIENT_IP_META_KEY` is renamed
  `RATELIMIT_CLIENT_IP_HEADER` (and its local variable `meta_key` to `ip_header`).
  The environment variable keeps its old name, which is the one set on Railway.

## Acceptance Criteria

- [x] The chosen mechanism and blocking threshold are recorded in this todo.
- [ ] A test PR that adds a known CodeQL alert at or above the threshold
      cannot be merged, and auto-merge does not merge it (record the PR
      number). → todo 723 (re-pointed 2026-11-21)
- [ ] A Dart-only PR and a docs-only PR can still merge without waiting on a
      CodeQL result that never arrives (record both PR numbers). → todo 723 (re-pointed 2026-11-21)
- [ ] A PR that logs a client IP through `log_safe_ip` is not blocked by
      `py/clear-text-logging-sensitive-data`. → todo 723 (re-pointed 2026-11-21)
- [x] `CLAUDE.md` and the todo skills no longer describe CodeQL as outside
      the merge gate.

## Work Log

### 2026-11-19 - Filed

- Owner: "file a todo to make Code QL required", after arming auto-merge on
  PR #1382 and being told CodeQL would not hold it.

### 2026-11-21 - Implemented by the todo sweep (run 2026-11-20-2202)

- Recorded the mechanism (ruleset 9138781's `code_scanning` rule) and the
  threshold (critical) under Decision, on the owner's decision of 2026-11-20.
- Renamed the Django setting to `RATELIMIT_CLIENT_IP_HEADER` in
  `backend/plant_community_backend/settings.py`, `backend/apps/core/ratelimit.py`
  (also the `meta_key` variable and the `[RATELIMIT-RESOLVE]` label) and a
  docstring in `backend/apps/core/security.py`. Prod is unchanged: settings still
  read the `RATELIMIT_CLIENT_IP_META_KEY` environment variable that Railway holds.
- Two tests that override the setting by name were updated to the new name
  (`backend/apps/core/tests/test_ratelimit_client_ip.py`,
  `backend/apps/users/tests/test_allauth_client_ip.py`).
- `CLAUDE.md` and the `completing-todos` skill now say CodeQL is in the merge
  gate at the critical threshold, and that a new high still merges. Whether the
  rename clears the alert is proven in todo 723.

### 2026-11-21 - Verified by the todo sweep (run 2026-11-20-2202)

- AC 1: `grep -n -A14 "^## Decision" todos/archive/718-completed-p2-ci-make-codeql-a-required-check.md` — evidence `.sweep-evidence/g3/718-ac0.txt` (not committed), last lines:

  ```text
  75-  `RATELIMIT_CLIENT_IP_HEADER` (and its local variable `meta_key` to `ip_header`).
  76-  The environment variable keeps its old name, which is the one set on Railway.
  77-
  78-## Acceptance Criteria
  79-
  ```

- AC 5: `grep -rn -i "codeql" CLAUDE.md .claude/skills/` — evidence `.sweep-evidence/g3/718-ac4.txt` (not committed), last lines:

  ```text
  CLAUDE.md:101:real PRs). A new high or lower alert does not block, so read the CodeQL check of
  CLAUDE.md:103:CodeQL is not a required status check: requiring its `Analyze` contexts
  .claude/skills/completing-todos/SKILL.md:38:alone; it still deletes the remote branch. CodeQL is in the merge gate through ruleset 9138781 at the critical
  .claude/skills/completing-todos/SKILL.md:39:threshold (todo 718): it is configured to stop auto-merge on a new critical CodeQL alert, but a new high still merges,
  .claude/skills/completing-todos/SKILL.md:40:so when an armed PR's CodeQL check reports new alerts, read them and report any high to the owner.
  ```

### 2026-11-21 - Completed by the todo sweep (run 2026-11-20-2202)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-21 - Review round 1: non-blocking findings (PR #1396)

- **Declined:** a reviewer asked that the comment above `RATELIMIT_CLIENT_IP_HEADER` in `settings.py` (and
  `backend/docs/deployment/railway.md`) say the env var and the setting differ in name. Both already say so,
  in the lines right after the env-var name ("The Django setting is RATELIMIT_CLIENT_IP_HEADER (todo 718)").
