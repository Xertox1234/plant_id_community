---
status: pending
priority: p3
issue_id: "618"
tags: [todo-sweep, harness, guard]
dependencies: []
owner_decision: "Option 2, require -C: git add/mv/rm allowed only with an explicit -C (or --work-tree) inside .claude/worktrees/; cwd tracking dropped for them (2026-10-11)"
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

- [ ] The chosen approach is recorded in the Work Log with the owner's decision and its date.
- [ ] Every probe in todo 604 is denied, with a test in `.claude/hooks/test-guard-todo-worker-git.sh`.
- [ ] The real worker command shapes from at least one recent run's transcripts are still allowed, with
      tests.
- [ ] The docstring's "it denies when it cannot tell" claim is true for cwd tracking, or reworded to match.

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
