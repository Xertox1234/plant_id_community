---
status: completed
priority: p4
issue_id: "477"
tags: [harness, todo-sweep]
dependencies: []
triage: ready
triaged: 2026-09-28
owner_decision: "Finding 1: close all the gaps, including the post-cd and pilot linked-worktree gaps (2026-09-28)"
---

# Todo sweep: non-blocking findings from PR #872 round 1 (todo 468 slice B)

## Problem

Round 1 of PR #872 found one regression, fixed in the PR. The guard denied
`cd '<WT>' && git add -A` and `git -C "$WT" add -A` for retry and repair workers,
which run from the main session's cwd. Now a command that changes directory, or a `-C`
value built at runtime, leaves the directory unknown, and it is not checked. These
items were left for later. The guard is a mistake guard, not a security boundary.

## Findings

1. **Gaps in the main-checkout check.**
   - `git -C MAIN --work-tree=S add -A` is allowed but stages into MAIN's index.
   - `GIT_DIR=` and `GIT_WORK_TREE=` environment prefixes are not checked.
   - A `git-add` binary skips the check.
   - After a `cd`, a bare `git add` is not checked. That includes `cd MAIN && git add`.
   - In the pilot layout, the sweep's main root is itself a linked worktree (its `.git`
     is a file), so the check never fires there.
2. **A tracked file listed in `.worktreeinclude` blocks every `git add`.** If a listed
   file is tracked and not ignored, `unignored_includes` denies all staging in that tree.
   Theoretical: the file itself says only ignored files are copied.
3. **The reviewer's read-only set is narrow.** `cat-file`, `ls-tree`, `rev-list`,
   `branch --show-current` and `worktree list` are denied. The bug prompt needs only
   `diff`, so the review stage works, but a reviewer may hit a denial while exploring.
4. **Round 2 notes.**
   - A `cd` inside `$(...)`, a subshell or `eval` also leaves the outer command's
     directory unknown. That misses catches; it never adds a wrong denial.
   - An UNKNOWN `-C` stays unknown even after a later absolute literal
     (`git -C "$WT" -C MAIN add` is allowed). `_join` could restart from an absolute
     path.
   - After a `cd`, the unignored-`.env` staging check is skipped too. Land's backstop
     still refuses the `.env`.
5. **The rename message shows git's C-quoting** for a source path that has a tab or a
   quote in it. This is cosmetic.

## Acceptance Criteria

- [x] Each gap in finding 1 is closed or recorded here as accepted, with a test for
      each one closed.
- [x] A tracked, not-ignored `.worktreeinclude` entry does not block unrelated staging,
      with a test.
- [x] The reviewer's read-only set is widened or recorded as enough.
- [x] The rename message prints unquoted paths.

## Work Log

### 2026-09-28 - Filed from PR #872 round 1

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- Finding 1, every gap closed, each with a hook test: -C and --work-tree are tracked apart and both are
  checked (`-C MAIN --work-tree=S add`); any `GIT_*` assignment is denied (prefix, `env`, `export`); a
  `git-add` binary gets the same main-checkout check; `cd`/`pushd` are followed, so `cd MAIN && git add`
  is denied; and a linked worktree holding the sweep's run file (`todos/.sweep-run-*.json`, the pilot's main
  root) counts as a main checkout.
- Round-2 notes too: a cd inside `( )`, `$(…)`, a pipeline stage or `sh -c` no longer moves the next command
  (no wrong denial), `eval` does; an absolute `-C` after an unknown one is checked; the `.env` check runs
  after a cd.
- A tracked `.worktreeinclude` entry no longer blocks `git add` (`git ls-files --error-unmatch`).
- Reviewers may now use `cat-file` (not `--textconv`/`--filters`), `ls-tree`, `rev-list`, `branch` to list
  only and `worktree list`.
- The rename refusal reads `git diff -z`, so it names the paths unquoted (test in `test_state_flow.py`).

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `bash /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g8/477-ac0.txt`, last lines:

  ```text
  PASS: 477: reviewer cat-file --textconv
  PASS: 477: a worker still may not list branches
  PASS: K10: missing script fails open

  Results: 276 passed, 0 failed
  ```

- AC 2: `bash /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g8/477-ac1.txt`, last lines:

  ```text
  PASS: 477: reviewer cat-file --textconv
  PASS: 477: a worker still may not list branches
  PASS: K10: missing script fails open

  Results: 276 passed, 0 failed
  ```

- AC 3: `bash /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/.claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g8/477-ac2.txt`, last lines:

  ```text
  PASS: 477: reviewer cat-file --textconv
  PASS: 477: a worker still may not list branches
  PASS: K10: missing script fails open

  Results: 276 passed, 0 failed
  ```

- AC 4: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-3/scripts/todos/test_state_flow.py` — evidence `.sweep-evidence/g8/477-ac3.txt`, last lines:

  ```text
    PASS  482: finish still removes the run file when every todo is terminal and none is held
    PASS  473 AC1: the wrap-up lists a landed todo's earlier blocked worktree (not its removed own one)
    PASS  477 AC4: the rename message prints the source and destination unquoted

  All checks passed.
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
