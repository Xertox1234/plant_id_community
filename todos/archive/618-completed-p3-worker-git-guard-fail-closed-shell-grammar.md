---
status: completed
priority: p3
issue_id: "618"
tags: [todo-sweep, harness, guard]
dependencies: []
owner_decision: "Relative -C paths are denied outright; only an absolute -C/--work-tree resolving inside .claude/worktrees/ is allowed (2026-10-12)"
triage: ready
triaged: 2026-10-12
---

# Worker git guard: fail closed on shell grammar it cannot model, instead of patching bypasses one by one

## Problem

`scripts/todos/worker_git_guard.py` tracks the working directory through a hand-written shell tokenizer
(`segments()`, `compound_delta()`, `OPENERS`/`CLOSERS`, function-body deferral, `lastpipe`). That way
`git add` in a main checkout is denied even after a `cd`. Every run fixes some bypasses, and reviewers probe
new ones:

- Todos 468, 477 and 584 each closed a set of bypasses.
- PR #1049 (run 2026-10-11-2219) closed several more. Round 2 then probed eight new fail-opens, now todo 604.

The eight share one root cause: the guard applies zsh-only grammar to every shell.

- A trailing `}` closes a group in zsh but is plain data in bash.
- `foreach`/`end` are zsh keywords.
- Reserved words in case patterns are counted as openers and closers.
- `chdir` is a zsh synonym for `cd`.
- A `shopt -s lastpipe` that never runs still counts.

The docstring calls this "a mistake guard, not a security boundary". It also says "when it cannot tell what a
guarded agent's command runs ... it denies". The bypass list shows that promise does not hold for cwd
tracking: an ambiguous construct is resolved optimistically, not denied.

## Proposed Solution

Decide between these and record the decision:

1. **Fail closed on ambiguity.** For a guarded agent's `git add/mv/rm`, deny when the command contains any
   construct the tracker models differently per shell: a group or compound command spanning the git
   segment, a function definition, `shopt`, `chdir`/`pushd`/`popd`, or `bash -c`/`zsh -c`. The workers'
   real commands are simple (`git -C <wt> add <paths>`), so check the denial rate against recorded worker
   transcripts before choosing this.
2. **Require `-C <worktree>`.** Allow `git add/mv/rm` only with an explicit `-C`, or a `--work-tree`
   inside `.claude/worktrees/`, and ignore cwd tracking for them entirely.

Either way, todo 604's probes become regression tests that must all be DENIED.

## Acceptance Criteria

- [x] The chosen approach is recorded in the Work Log with the owner's decision and its date.
- [x] Every probe in todo 604 is denied, with a test in `.claude/hooks/test-guard-todo-worker-git.sh`.
- [x] The real worker command shapes from at least one recent run's transcripts are still allowed, with
      tests.
- [x] The docstring's "it denies when it cannot tell" claim is true for cwd tracking, or reworded to match.

## Work Log

### 2026-10-11 - Filed from run 2026-10-11-2219 (owner request)

The owner asked for a todo after the run's pattern review. Todo 604 holds the individual probes. This todo is
the structural fix that would retire that list.

### 2026-10-11 - Owner decision: option 2, require `-C`

The owner chose **option 2**. A guarded agent's `git add`, `git mv` and `git rm` are allowed only with an explicit
`-C <path>` (or `--work-tree <path>`) that resolves inside `.claude/worktrees/`. The guard stops tracking cwd for
these commands, so `segments()`/`compound_delta()` no longer decide them. Workers already stage this way
(`/usr/bin/git -C WT add …`, todo-worker.md step 1). Remove any cwd-tracking code that no other check uses.
Todo 604's probes become regression tests that must all be DENIED (AC 2), and 604 closes once this lands.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-1724)

- Chosen approach: **option 2, require `-C`** (owner decision 2026-10-11), with the owner's refinement of
  2026-10-12: "Relative -C paths are denied outright; only an absolute -C/--work-tree resolving inside
  .claude/worktrees/ is allowed". `scripts/todos/worker_git_guard.py` now allows a guarded agent's
  `git add`/`mv`/`rm` only with a literal absolute `-C` whose realpath is inside a `.claude/worktrees/<name>/`
  worktree and is not a main checkout (the pilot run-file rule and the unignored-`.env` check stay). A
  relative or runtime-built `-C`/`--work-tree`, a missing `-C` and a `git-add` binary are denied, each with a
  reason that names the fix.
- `--work-tree` alone is not enough: git still finds the repository, and the index it stages into, from the
  directory it runs in (todo 477), so a `-C` is always required and a `--work-tree`, when given, must pass the
  same test.
- The cwd tracker is gone: `compound_delta`, `function_body_start`, the piped-stage and function-body
  machinery, `cd`/`chdir` following, wrapper chdir options, `lastpipe` and `$SHELL` modelling. Todo 604's
  probes are tests in `.claude/hooks/test-guard-todo-worker-git.sh` and are all denied; item 9's formatting
  slip is fixed. The docstring now says staging is decided by `-C` alone and never from the working directory.
- Census of the last four days' todo-worker transcripts: 102 of 133 staging calls already used a literal
  absolute `-C` (allowed, now with tests); 15 used `-C "$WT"`, 14 a bare git after `cd` and 2 a relative `-C`,
  which are now denied. 33 existing tests whose verdict depended on cwd tracking were converted (renamed
  `618 (was ...)`), and the fixture worktree moved under `MAIN/.claude/worktrees/`.
  `.claude/agents/todo-worker.md` tells workers to write `WT` out literally.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-1724)

- AC 1: `sed -n '/^## Work Log/,$p' todos/archive/618-completed-p3-worker-git-guard-fail-closed-shell-grammar.md` — evidence `.sweep-evidence/g1/618-ac0.txt` (not committed), last lines:

  ```text
  - Census of the last four days' todo-worker transcripts: 102 of 133 staging calls already used a literal
    absolute `-C` (allowed, now with tests); 15 used `-C "$WT"`, 14 a bare git after `cd` and 2 a relative `-C`,
    which are now denied. 33 existing tests whose verdict depended on cwd tracking were converted (renamed
    `618 (was ...)`), and the fixture worktree moved under `MAIN/.claude/worktrees/`.
    `.claude/agents/todo-worker.md` tells workers to write `WT` out literally.
  ```

- AC 2: `bash .claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g1/618-ac1.txt` (not committed), last lines:

  ```text
  PASS: 496.R3: mapfile -C 'git push' callback
  PASS: 496.R3: trap cleanup / hash -r / alias list
  PASS: K10: missing script fails open

  Results: 538 passed, 0 failed
  ```

- AC 3: `bash .claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g1/618-ac2.txt` (not committed), last lines:

  ```text
  PASS: 496.R3: mapfile -C 'git push' callback
  PASS: 496.R3: trap cleanup / hash -r / alias list
  PASS: K10: missing script fails open

  Results: 538 passed, 0 failed
  ```

- AC 4: `sed -n '1,40p' scripts/todos/worker_git_guard.py` — evidence `.sweep-evidence/g1/618-ac3.txt` (not committed), last lines:

  ```text

  Tests: .claude/hooks/test-guard-todo-worker-git.sh
  """

  import glob
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-1724)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
