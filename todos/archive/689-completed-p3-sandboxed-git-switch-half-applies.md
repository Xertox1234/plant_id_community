---
status: completed
priority: p3
issue_id: "689"
tags: [harness, git, sandbox, worktrees]
dependencies: []
triage: ready
triaged: 2026-11-03
owner_decision: "(b) Hook only: a warn-only Bash PreToolUse hook on git switch -c / checkout -b from origin/ without --no-track; no CLAUDE.md entry (2026-11-03)"
---

# A sandboxed `git switch -c` in a worktree half-applies (cause: `.git/config` is write-protected)

## Problem

From a `.claude/worktrees/*` checkout inside the Bash sandbox, `git switch -c <new> origin/main`:

- creates the branch
- moves the index and working tree
- but leaves HEAD on the old branch

The result looks like a large staged change on the wrong branch. Merges and rebases there have failed the same way. Each agent rediscovers this and has to repair it by hand.

## Findings

- **Root cause (2026-11-03, reproduced with full stderr).** `git switch -c chore/close-todo-690 origin/main` printed `error: could not lock config file /Users/williamtower/projects/plant_id_community/.git/config: Operation not permitted` / `error: unable to write upstream branch configuration`, then left HEAD on the old branch. Starting a branch from a remote ref turns on upstream tracking, which writes `.git/config`, and the sandbox refuses every write to that file.
- **Probe of the cause:** `git branch --track probe origin/main` fails with the same config-lock error, while `git branch --no-track probe origin/main` succeeds (exit 0). The same lock explains the upstream warning `git push -u` prints in a sandbox. The push itself succeeds.
- **Fix:** add `--no-track`, as in `git switch -c <new> --no-track origin/main`. A bare `git push origin HEAD` works and sets no upstream. Nothing needs the sandbox turned off.
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

1. ~~Reproduce and record the cause.~~ Done 2026-11-03 (see Findings): the write to `.git/config` for upstream tracking is refused.
2. Add a `docs/rules/triggers.json` entry that matches `git switch -c … origin/` and `git checkout -b … origin/`. It should say: add `--no-track`, since the sandbox refuses the `.git/config` write and leaves HEAD behind.
3. Add the `git symbolic-ref HEAD refs/heads/<new>` repair to that rule. It is non-destructive, unlike `reset --hard`, which the project forbids without asking.
4. Check whether the merge failure on `.claude/agents` (2026-10-09) still happens. If it does, point merges at `sync_with_base_branch`.

## Technical Details

- Related memory notes: sandbox git switch partial checkout, sandbox git merge `.claude/agents`, worktree session gotchas.
- Sandbox `denyWithinAllow` for this worktree includes `<worktree>/.claude/skills` and `<worktree>/.claude/hooks`.

## Acceptance Criteria

- [x] The cause of the half-applied switch is recorded with the exact error text. 2026-11-03: "could not lock config file …/.git/config: Operation not permitted", and the `--track` / `--no-track` probe in Findings.
- [x] A rule or trigger tells agents the safe way to branch and to sync a worktree, and includes the `symbolic-ref` repair.

## Work Log

### 2026-11-03 - Filed

- Hit while creating this todo's branch. Repaired with `git symbolic-ref`; nothing was lost. The owner asked for todos for repeated agent friction.

### 2026-11-03 - Root cause found

- Hit again while branching to close todo 690, this time with full stderr: `.git/config` lock refused while setting upstream tracking. A `--track` / `--no-track` probe confirmed it. The probe branches were deleted afterwards. Remaining work: the trigger rule (steps 2–4).

### 2026-11-03 - Implemented by the todo sweep (run 2026-11-03-2214)

- Owner chose (b), a hook and no CLAUDE.md entry: new `.claude/hooks/warn-git-track.sh`, registered as a Bash PreToolUse hook in `.claude/settings.json`. It warns (additionalContext + systemMessage, no permission decision, always exit 0) on `git switch -c/-C/--create/--force-create` or `git checkout -b/-B` from `origin/`, `remotes/` or `refs/remotes/`, or with `--track`, unless that same simple command has `--no-track`.
- The warning names the safe paths: `--no-track`, `git push origin HEAD` (no `-u`), `sync_with_base_branch` for syncing a worktree, and the non-destructive `git symbolic-ref HEAD refs/heads/<new>` repair.
- `.claude/hooks/test-warn-git-track.sh` (25 cases) covers the warn and quiet forms, compound commands and fail-open input; it is added to `.github/workflows/harness-ci.yml`.
- Not done: step 4 (re-checking the 2026-10-09 `.claude/agents` merge failure). The warning points merges at `sync_with_base_branch` regardless.

### 2026-11-03 - Verified by the todo sweep (run 2026-11-03-2214)

- AC 2: `bash .claude/hooks/test-warn-git-track.sh` — evidence `.sweep-evidence/g2/689-ac1.txt` (not committed), last lines:

  ```text
  PASS: --no-track elsewhere does not excuse a tracking switch
  PASS: exits 0 on a warning
  PASS: warning names branch, push, sync and symbolic-ref repair

  Results: 25 passed, 0 failed
  ```

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-03 - Review round 1: non-blocking findings (PR #1263)

- FIXED (medium, line 49): newline-separated commands landed in one segment, so `git fetch origin` + newline + `git switch -c x origin/main` stayed quiet, and a `--no-track` on line 1 silenced a tracking switch on line 2. Unquoted newlines are now separators (a backslash-newline continuation stays one command). Three new tests; mutation check: with `\n` removed from the separators the two newline tests fail (26 passed, 2 failed); restored, 28 passed.
- FIXED (low, test line 51): the misnamed test is now "--no-track switch followed by an unrelated segment stays quiet".
- DECLINED (low, line 42): a trailing `# --no-track` comment, or `-- origin/<path>` after a bare `--`, can mis-read. The hook is warn-only, so the worst case is one missing or one extra warning; not worth extra parsing.
- DECLINED (low, line 79): `git switch <name>` DWIM, `checkout --track` without `-b` and `worktree add -b … origin/x` are not detected. The owner scoped the rule to `switch -c`/`checkout -b` (decision 2026-11-03); the sweep runbook already uses `worktree add --no-track`.
- DECLINED (low, settings.json line 59): adding a `warn-git-track.sh` bullet to CLAUDE.md. The owner chose "hook only … no CLAUDE.md entry" (2026-11-03).
