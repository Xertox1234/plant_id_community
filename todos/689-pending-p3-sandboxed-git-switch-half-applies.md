---
status: pending
priority: p3
issue_id: "689"
tags: [harness, git, sandbox, worktrees]
dependencies: []
---

# A sandboxed `git switch -c` in a worktree half-applies, and the cause is unknown

## Problem

From a `.claude/worktrees/*` checkout inside the Bash sandbox, `git switch -c <new> origin/main`:

- creates the branch
- moves the index and working tree
- but leaves HEAD on the old branch

The result looks like a large staged change on the wrong branch. Merges and rebases there have failed the same way. Each agent rediscovers this and has to repair it by hand.

## Findings

- **2026-11-03 (this todo's branch).** `git switch -c chore/todos-agent-friction origin/main` from `claude/brave-babbage-ee00a5` left HEAD on the old branch, with the 2 files from main's newer commit staged. `git diff --name-only HEAD origin/main` showed only `.github/security-suppressions.yml` and one todo file. **No `.claude/hooks` or `.claude/skills` path differed.** That contradicts the earlier guess, from the 2026-09-24 memory note, that a denied write under `.claude/hooks/` aborted the checkout. The command's full stderr was cut off by `| tail -2`, so the real error is unknown.
- **Repair that worked, without losing anything:** `git symbolic-ref HEAD refs/heads/<new>`. The new branch, index and tree all already matched `origin/main`.
- **2026-10-09 (memory, PR #944).** A sandboxed `git merge origin/main` failed with "unable to unlink old '.claude/agents/…'" and left untracked residue. `.claude/agents` now appears in the sandbox write allowlist. This session's sandbox still denies writes to the worktree's `.claude/skills` and `.claude/hooks` (`denyWithinAllow`).
- **The desktop app offers a supported path** for bringing a worktree up to date: the `sync_with_base_branch` host tool, which merges on the host where those paths are writable.

## Proposed Solutions

### Option 1: find the cause, then write a rule (recommended)

- **Implementation:**
  1. Reproduce with full stderr: `git switch -c x origin/main 2>&1`, in a fresh worktree, sandboxed.
  2. Record the exact failing path or step.
  3. Then add a `docs/rules/triggers.json` entry, or a short CLAUDE.md gotcha, that names the safe paths:
     - updating a worktree: `sync_with_base_branch`
     - a fresh branch: `git worktree add <scratchpad>/<name> -b <new> origin/main`, or the switch with the sandbox disabled
     - repair: `git symbolic-ref`
- **Effort:** 1 hour.
- **Risk:** low (docs/rules only).

## Recommended Action

1. Reproduce with the full stderr captured and record the cause here.
2. If the cause is a sandbox deny path, write the rule above. If it is something else (a hook, or rtk wrapping `git`), fix that instead.
3. Add the `git symbolic-ref` repair to the rule, since it is non-destructive (unlike `reset --hard`, which the project forbids without asking).

## Technical Details

- Related memory notes: sandbox git switch partial checkout, sandbox git merge `.claude/agents`, worktree session gotchas.
- Sandbox `denyWithinAllow` for this worktree includes `<worktree>/.claude/skills` and `<worktree>/.claude/hooks`.

## Acceptance Criteria

- [ ] The cause of the half-applied switch is recorded with the exact error text (a reproduction log in this todo).
- [ ] A rule or trigger tells agents the safe way to branch and to sync a worktree, and includes the `symbolic-ref` repair.

## Work Log

### 2026-11-03 - Filed

- Hit while creating this todo's branch. Repaired with `git symbolic-ref`; nothing was lost. The owner asked for todos for repeated agent friction.
