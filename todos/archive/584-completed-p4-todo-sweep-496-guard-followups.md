---
status: completed
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

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason.

## Work Log

### 2026-10-11 - Filed from todo-sweep run 2026-10-11-1434

Follow-ups for PR #1023 (todo 496).

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-2219)

- Fixed with tests in `scripts/todos/worker_git_guard.py` and `.claude/hooks/test-guard-todo-worker-git.sh`
  (52 new `584.*` cases, additions only; 433 to 485 passing). Findings 1 and 5: a trap action, a
  `mapfile -C` callback and a function body (`NAME()`, `function NAME`, up to its matching closer) are judged
  as deferred code: any `cd`/`pushd`/`popd` in them is refused, a staging git must carry an absolute `-C`,
  and a DEBUG/ERR/ZERR/RETURN trap is refused outright. That also closes `f(){ git add -A; }; cd MAIN; f`.
- Finding 2: `shopt -u lastpipe` and `bash +O lastpipe` clear lastpipe; a runtime `shopt -s/-u` operand
  and `set ±o lastpipe` (not a bash option: bash 5.3 prints "invalid option name" and changes nothing) leave
  it unknown, and an unknown last stage resolves through `either_main`. Finding 3: keyword (`set -k`,
  `set -o keyword`, `setopt keyword`, `bash -k`, `bash -o keyword`, `zsh --keyword`) is refused like allexport.
- Finding 4 (owner decision: track the cwd): a compound command (`{ }`, if, while, until, for, case, select)
  that is a pipeline stage keeps its cd for the rest of the stage, and the stage rule (restore, keep for a zsh
  or lastpipe last stage, `either_main` when unknown) applies once where it ends. A piped `( )` no longer
  restores per segment. This also covers a first-stage `{ cd WT; } | cat; git add -A` from MAIN.
- Finding 6: `SHELL=/bin/bash` variants of the 496.2 and brace-group cases. Finding 7: a note at
  `denied_option`. Finding 8 declined: the `.sweep-evidence` files and the mutation script it cites went with
  the 496 worktree, so their output cannot be quoted without inventing it; the counts stay as the 496 workers
  reported them. Reverting each fix here in a temporary copy fails its own cases: 1: 8, 2: 5, 3: 9, 4: 4, 5: 2.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-2219)

- AC 1: `bash .claude/hooks/test-guard-todo-worker-git.sh && python3 .sweep-evidence/g2/mutate584.py .` — evidence `.sweep-evidence/g2/584-ac0.txt` (not committed), last lines:

  ```text
      FAIL: 584.4: SHELL=bash: true | { cd MAIN; git add -A; } from WT (expected deny)
  finding 5 function body reverted: 2 failing, 2 of them 584.5 cases
      FAIL: 584.5: f() { cd MAIN; }; cd WT; f; git add -A (expected deny)
      FAIL: 584.5: f(){ git add -A; }; cd MAIN; f (a bare git add in a body) (expected deny)
  restored: True
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-2219)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
