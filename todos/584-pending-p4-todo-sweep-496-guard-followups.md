---
status: pending
priority: p4
issue_id: "584"
tags: [harness, todo-sweep, security, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Item 4: track cwd through the piped { }/if/while stage (owner, 2026-10-11)"
---

# Follow-ups from PR #1023 (todo 496, worker git-guard bypasses)

## Problem

Todo-sweep run 2026-10-11-1434 merged PR #1023 (the worker git-guard bypasses). Its review rounds reported the non-blocking
findings below. The curator merged duplicates and checked each item against main; the refuter dismissed
what is listed as dropped. Line numbers are as of the PR head, so re-check each against main before acting on it.

## Findings

PR #1023 (todo sweep run 2026-10-11-1434, group g2, todos 496); hand round 3 (owner-approved). The stored list hit the cap of 10 and dropped 16 locations, so round 3's findings below were added by hand from that round's review output. Three stored items the curator did not return (allexport `${GIT_*:=}`, zsh `read 'NAME?p'`/multi-name `for`, bash lastpipe) are left out: they repeat items the curator and refuter dropped as fixed on main.

1. **medium** `scripts/todos/worker_git_guard.py:660` check_definitions judges a trap action where the trap is set, at depth+1, and throws away any cd inside it, but the action runs later. `trap 'git add -A' EXIT; cd MAIN` and `trap 'cd MAIN' DEBUG; git add -A` both return None. Fail closed: deny a trap action containing cd/pushd/popd or a git write without -C, or a DEBUG/ZERR/ERR trap; `mapfile -C` callbacks need the same treatment.
2. **medium** `scripts/todos/worker_git_guard.py:648` The lastpipe state is only ever set, never cleared. From MAIN, `bash -c 'shopt -s lastpipe; shopt -u lastpipe; true | cd WT; git add -A'` is allowed: the guard thinks the cd stuck in WT, bash undoes it, and git add runs in MAIN. This is looser than main before #1023. Make `shopt -u lastpipe` / `set +o lastpipe` clear it, and fail closed in both directions for a runtime operand.
3. **medium** `scripts/todos/worker_git_guard.py:593` bash's keyword option (`set -k`, `set -o keyword`, `bash -k -c`) exports any NAME=value argument, so a GIT_* assignment after git takes effect. Same class as the allexport bypass #1023 closed; deny it with allexport.
4. **medium** `scripts/todos/worker_git_guard.py:425` For bash, the cwd is restored after each piped segment, not after the whole pipeline stage. From WT, `bash -c 'true | { cd MAIN; git add -A; }'` is allowed, yet the group runs in one subshell, so git add runs in MAIN. Same with SHELL=bash at top level. Track the cwd through a `{ }`/if/while stage and restore it only at the stage's end, or use either_main inside piped compounds.
5. **low** `scripts/todos/worker_git_guard.py:678` (pre-existing) A function body's cd is followed when the function is defined, not when it is called: `f() { cd MAIN; }; cd WT; f; git add -A` is allowed and stages into MAIN. Deny a function body that changes directory, as for alias.
6. **low** `.claude/hooks/test-guard-todo-worker-git.sh:13` The bash top-level model (SHELL=/bin/bash, the CI default) is covered only by the 7 shell_raw cases. Add SHELL=/bin/bash variants of the 496.2 and brace-group cases.
7. **low** `scripts/todos/worker_git_guard.py:1047` denied_option denies any non-empty prefix; the recorded owner decision says 2+ letters. The 1-letter widening was the round-1 repair (owner-approved 2026-10-11) and is only in the Work Log. Note it beside the code so the next reader does not see drift.
8. **low** `todos/archive/496-completed-p3-worker-git-guard-bypasses.md:119` The per-fix mutation-revert counts cite uncommitted `.sweep-evidence` files. Quote the revert summary inline, as the AC 1 and AC 2 blocks already do.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1023 (todo 496).
