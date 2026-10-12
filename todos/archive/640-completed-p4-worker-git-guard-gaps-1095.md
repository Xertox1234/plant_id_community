---
status: completed
priority: p4
issue_id: "640"
tags: [todo-sweep, harness, security, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
---

# Follow-ups from PR #1095 (todo 618, worker git guard fail-closed)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1095 (todo 618, worker git guard fail-closed). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1095 (todo sweep run 2026-10-12-1724, group g1, todos 618); follow-ups: verified.

1. **medium** `scripts/todos/worker_git_guard.py:926` _absolute accepts a -C that xargs -I builds at runtime. `echo ../../.. | xargs -I % git -C /x/.claude/worktrees/g1/% add -A` is allowed because % is not in NOT_LITERAL, and git then stages in the main checkout. This breaks the todo 618 rule that a runtime-built -C is denied.
2. **medium** `scripts/todos/worker_git_guard.py:120` The xargs WRAPPERS entry leaves out the BSD/macOS value options -J, -R and -S. In `xargs -J % git push` the value is read as the program word, so git push is allowed.
3. **medium** `scripts/todos/worker_git_guard.py:210` read_word ends a word at a mid-word '('. zsh reads that as a glob qualifier, so `git -C <MAIN>(/) add -A` or `git -C /usr(/) push` gets no deny, and zsh runs it against the bare directory.
4. **medium** `scripts/todos/worker_git_guard.py:998` forces() reads only literal word values, so a -f built at runtime (`$(printf -- -f)`, `"$F"`, or fed through xargs) gets past it and force-stages a copied-in backend/.env.
5. **medium** `.claude/hooks/test-guard-todo-worker-git.sh:784` About 20 GIT_*deny tests (496.G/H/I) end in a bare `git add x`, which is now denied for having no -C. They pass even if the GIT_* detection they were written for is removed.
6. **low** `.claude/hooks/test-guard-todo-worker-git.sh:94` The test case labelled 'a relative -C into WT from MAIN's cwd' passes an absolute -C, so the label no longer matches what it tests.
7. **low** `scripts/todos/worker_git_guard.py:1300` in_worktrees accepts any `.claude/worktrees/<name>` directory on disk, including another project's, because nothing anchors it to this repo's main root.
8. **low** `scripts/todos/worker_git_guard.py:1270` The main-checkout and in-worktree checks read the disk when the hook runs, so one command can change it first: `rm /abs/WT/.git && git -C /abs/WT add -A` passes, and git then finds MAIN's .git.
9. **low** `scripts/todos/state.py:2217` execute-args still takes any --worktree-root, and its help text says nothing of the guard rule. A root outside .claude/worktrees/ creates worktrees in which workers can never stage.

6 more location(s) were dropped by the cap of 10 (the most severe are kept).

Dropped by curation (fixed on main, refuted, or not a reported location):

- medium: scripts/todos/state.py:2116 ensure-worktree re-adds a lost worktree at `<scratch>/<gid>`. With --scratch outside .claude/worktrees/, in_worktrees() denies every git add/mv/rm that a round-1 repair worker runs there. (fixed on main: state.py:2116 still uses Path(scratch)/gid. The SKILL.md:190 call site now passes `--scratch REPO/.claude/worktrees`, and line 191 explains why it must stay under .claude/worktrees/. The re-added worktree passes the guard.; the refuter agreed: Fixed: every ensure-worktree invocation routes to SKILL.md:190, which passes --scratch REPO/.claude/worktrees (191 explains why), so the re-added worktree at `<scratch>/<gid>` is under .claude/worktrees and passes in_worktrees.)

## Acceptance Criteria

- [x] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1095 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g1`.

### 2026-10-12 - Implemented by the todo sweep (run 2026-10-12-2056)

- #1, #2, #4 fixed in `scripts/todos/worker_git_guard.py`: a staging git (add/mv/rm) run by xargs is denied,
  since xargs builds its words at runtime (an `-I`/`-J` replstr inside `-C`, or an appended `-f`); xargs's
  BSD/macOS `-J`, `-R` and `-S` take a value; a staging option word built at runtime (`$(printf -- -f)`,
  `"$F"`, a backtick) is denied unless it follows `--`.
- #3 fixed: a `(` glued inside a word (a zsh glob qualifier such as `MAIN(/)`, or an extglob) is a parse
  failure, so it is denied; `f()` and `NAME=( )` still split as before.
- #7 fixed where the hook event names the agent's cwd (the harness always sends it): the worktree must sit
  under `.claude/worktrees/` of the cwd repository's main root (its common `.git`'s parent, so a linked-worktree
  cwd anchors to the same root). With no cwd, or one outside any repository, nothing is anchored, as before.
  #8 fixed narrowly: `rm`/`mv`/`unlink`/`rmdir` of a `.git` is denied. The guard still reads the disk when the
  hook runs; other ways to delete a `.git` stay out of scope for a mistake guard (module docstring).
- #5 and #6 fixed in `.claude/hooks/test-guard-todo-worker-git.sh`: the 21 GIT_* deny cases end in
  `git -C /wt/.claude/worktrees/g1 add x` and check their own reason, with a control case that the same git
  alone is allowed; the mislabelled case is now "an absolute -C", plus a real relative-`-C` case.
- #9 fixed in `scripts/todos/state.py`: `execute-args` refuses a `--worktree-root` that is not a
  `.claude/worktrees` directory at or above the main root, and its help text says why. Tests: 34 new guard
  cases (23 fail on the old guard) and `test_state_flow.py` 640 #9.

### 2026-10-12 - Verified by the todo sweep (run 2026-10-12-2056)

- AC 1: `bash .claude/hooks/test-guard-todo-worker-git.sh && python3 scripts/todos/test_state_flow.py && grep -n -E '^- #(1|5|7|9)' todos/archive/640-completed-p4-worker-git-guard-gaps-1095.md` — evidence `.sweep-evidence/g1/640-ac0.txt` (not committed), last lines:

  ```text
  All checks passed.
  53:- #1, #2, #4 fixed in `scripts/todos/worker_git_guard.py`: a staging git (add/mv/rm) run by xargs is denied,
  59:- #7 fixed where the hook event names the agent's cwd (the harness always sends it): the worktree must sit
  64:- #5 and #6 fixed in `.claude/hooks/test-guard-todo-worker-git.sh`: the 21 GIT_* deny cases end in
  67:- #9 fixed in `scripts/todos/state.py`: `execute-args` refuses a `--worktree-root` that is not a
  ```

### 2026-10-12 - Completed by the todo sweep (run 2026-10-12-2056)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-12 - Repaired by the todo sweep (run 2026-10-12-2056)

- Round-1 review: the #1/#4 xargs deny looked only at the wrapper right around git, so `xargs -I % env git -C
  WT/% add -A`, `xargs nice git ...` and `echo -f | xargs env git -C WT add backend/.env` were allowed. In
  `scripts/todos/worker_git_guard.py` the xargs state is now sticky: everything judged below an xargs (any
  wrapper, any depth) denies a staging git, and a shell `-c` under xargs is denied outright, since `-I %`
  can put the input into the script itself (`xargs -I % sh -c '%'`).
- Round-1 review: the #3 exemption let any `word=(` through, but zsh reads `x=(e:'git push':)` in argument
  position as a glob qualifier that runs a command. A glued `(` after `NAME=` (or `NAME+=`) is now exempt only
  in assignment position (first in its command, or after other assignments); anywhere else it is a parse
  failure, so it is denied.
- Tests: 14 new cases in `.claude/hooks/test-guard-todo-worker-git.sh` (xargs with env, nice, timeout,
  command and sh/bash -c; `ls WT/x=(e:'git push':)`, `echo foo=(...)`, `export x=(...)`; controls that
  `arr=(a b)`, `arr+=(c)`, a read under `xargs env` and a git after the xargs segment stay allowed).
