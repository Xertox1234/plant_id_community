---
status: completed
priority: p3
issue_id: "496"
tags: [harness, todo-sweep, security]
dependencies: []
triage: ready
triaged: 2026-10-11
owner_decision: "Owner: finding 6 — refuse any 2+ letter unambiguous prefix of a listed dangerous option, keeping exact-match exceptions such as --text; do not derive option lists from git (2026-10-11)"
---

# Todo sweep: close the git-guard routes into the main checkout and into files

## Problem

`scripts/todos/worker_git_guard.py` (run by `.claude/hooks/guard-todo-worker-git.sh`) keeps a sweep
worker, verifier or reviewer from staging into the owner's main checkout, and keeps read-only reviewers
read-only. PR #880 (todo 477) taught it to follow `cd` and widened the reviewers' git set. Its review
rounds 2 and 3 found commands it still allows. Each one either runs git in MAIN (or against MAIN's
index) while the guard judges it against the worktree, or lets a "read-only" git call write or run
something. None was exploited: reviewers found them by probing the guard. This is the isolation boundary
for every worker, so it is p3, not a p4 follow-up (owner decision 2026-09-29).

## Findings

Line numbers are as of PR #880's merge (fd7305de). Each was probed ALLOWED by a reviewer from a worker
worktree (WT).

1. **`env -C` / `env --chdir` are not followed** (`worker_git_guard.py:457`–`477`, `check_wrapper`).
   They are skipped as a value option, so `env -C MAIN git add -A` and `env --chdir=MAIN git add x` are
   allowed. `/usr/bin/env -C` works on macOS. `sudo -D` has the same shape. Fix: apply the value to
   `CONTEXT["cwd"]` via `cd_target` before the recursive check.
2. **A `cd` in the last stage of a pipeline sticks under zsh** (`:362`). The guard restores the cwd
   after every piped stage, which is bash's behavior. zsh runs the last stage in the current shell:
   `zsh -c 'cd /usr; true | cd /; pwd'` prints `/`. So `true | cd MAIN; git add -A` is allowed and runs
   in MAIN. Round 3 confirmed the agents' Bash is zsh 5.9 (`$0=/bin/zsh`). Fix: undo the cd only for a
   non-last stage or a background job (`seg.end` in `|`, `|&`, `&`), or set the cwd UNKNOWN.
3. **`$(...)` bodies are judged in the starting cwd** (`:726`). They are checked before
   `check_segments` applies an earlier cd, so `cd MAIN && echo $(git add -A)` and
   `cd MAIN; x=$(git add -A)` are allowed but stage into MAIN.
4. **`~` targets are never checked** (`:443` `cd_target`, `:615` `_join`). Both map any `~` path to
   UNKNOWN, so the natural accidental forms `git -C ~/projects/plant_id_community add x` and
   `cd ~/projects/plant_id_community && git add x` are allowed. Expand `~` and `~/…` with
   `os.path.expanduser`; keep UNKNOWN only for `~user`.
5. **Only `NAME=value` GIT_* assignments are flagged** (`:383`, `:406`, `git_env`).
   `read GIT_DIR <<< MAIN/.git; export GIT_DIR; git add x` is allowed, as are `printf -v GIT_DIR` and
   `for GIT_DIR in …`. Deny a bare `GIT_*` operand to a declarer, and `read`/`printf -v`/`mapfile`/`for`
   targets named `GIT_*`.
6. **Option prefixes shorter than 3 letters pass `denied_option`** (`:645`). git takes any unambiguous
   prefix. Verified: `git grep --op=<cmd> x` reaches `--open-files-in-pager` (past the new `-O` ban),
   `git fetch --st` is `--stdin` (refspecs from stdin, unseen by the `:` refspec scan), and
   `cat-file --te` / `--fi` are the same. Derive the check per subcommand from git's real options, or
   deny any prefix of a listed dangerous option.
7. **`rev-list` is read-only-allowed with no denied options** (`:43`–`44`, `:70`). revision.c hands
   unknown options to `diff_opt_parse`, which opens `--output` for writing, so a reviewer's
   `git rev-list --output=<file> HEAD` truncates any file. Add `"rev-list": OUTPUT_OPTIONS`. The hook
   test has only an allow case for rev-list (`test-guard-todo-worker-git.sh:393`).
8. **`git grep --textconv` is allowed** (`:71`), though diff/log/show/cat-file deny `textconv` because
   it runs a configured driver program. Make grep's entry `("open-files-in-pager", "textconv")`. (low)

## Acceptance Criteria

- [x] Each of findings 1–8 is refused by the guard, with an `assert_deny` case in
      `.claude/hooks/test-guard-todo-worker-git.sh` that fails when that fix is removed.
- [x] The allow cases that already pass still pass (the guard must not start refusing a worker's
      ordinary `git -C WT add` / `diff` / `status`).

## Work Log

### 2026-09-29 - Filed from PR #880 review rounds 2 and 3

Round 2 never repairs, and round 3 (the owner's call) did not either. All were rated non-blocking.
Findings 6 and 7 were first reported in round 2's wrap-up but never written to the run file; round 3
re-found both.

### 2026-10-11 - Implemented by the todo sweep (run 2026-10-11-1434)

- `scripts/todos/worker_git_guard.py`: env `-C`/`--chdir` and sudo `-D`/`--chdir` (bundled, glued or `=`)
  move only the wrapped command's directory (1); a cd in a pipeline's last stage sticks, as in zsh (2);
  each `$(...)`, backtick and heredoc-body substitution is judged with the segment it belongs to, after
  any earlier cd (3); an unquoted `~` / `~/...` is the home directory, `~user` stays unknown (4).
- GIT_* names set by a bare declarer operand, `read`/`mapfile`/`readarray`/`vared`/`getopts`,
  `printf -v`/`print -v` or a `for`/`select` loop variable are refused (5); a 2+ letter prefix of a listed
  dangerous option is refused, `--text` stays exact (6, owner decision 2026-10-11); `rev-list` denies
  `--output`/`--ext-diff`/`--textconv` (7) and `grep` denies `--textconv` (8).
- `.claude/hooks/test-guard-todo-worker-git.sh`: 34 new cases (496.1–496.8). Reverting each fix in a copy
  of the guard fails that finding's cases; all 310 cases pass with the fixes.

### 2026-10-11 - Verified by the todo sweep (run 2026-10-11-1434)

- AC 1: `bash .claude/hooks/test-guard-todo-worker-git.sh && python3 .sweep-evidence/g2/mutate496.py .` — evidence `.sweep-evidence/g2/496-ac0.txt` (not committed), last lines:

  ```text
  finding 7 reverted: 1 failing, 1 of them 496.7 cases
      FAIL: 496.7: git rev-list --output (expected deny)
  finding 8 reverted: 1 failing, 1 of them 496.8 cases
      FAIL: 496.8: git grep --textconv (expected deny)
  EVERY FINDING CAUGHT
  ```

- AC 2: `bash .claude/hooks/test-guard-todo-worker-git.sh` — evidence `.sweep-evidence/g2/496-ac1.txt` (not committed), last lines:

  ```text
  PASS: 496.7: git rev-list --count
  PASS: 496.8: git grep --textconv
  PASS: K10: missing script fails open

  Results: 310 passed, 0 failed
  ```

### 2026-10-11 - Completed by the todo sweep (run 2026-10-11-1434)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-10-11 - Repaired by the todo sweep (run 2026-10-11-1434): round 1 repair

- Finding 2 regression (PR #1023 review): the "a cd in a pipeline's last stage sticks" rule now applies only
  to shells that keep the last stage, `LAST_STAGE_SHELLS` in `scripts/todos/worker_git_guard.py` (zsh, the
  agents' shell, and ksh: macOS `/bin/ksh` is ksh93, which keeps it, probed with `ksh -c 'true | cd /; pwd'`).
  A `bash -c`, `sh -c` or `dash -c` body undoes a piped stage's cd again; `$(...)` and eval keep the caller's shell.
- Finding 6: `denied_option` denies any non-empty prefix of a listed option, so the one-letter `git cat-file --t`
  (git resolves it to `--textconv`) is refused; `GIT_EXACT_OPTIONS` (`--text`) stays exact-match only.
- `.claude/hooks/test-guard-todo-worker-git.sh` gained cases 496.2r and 496.6r (additions only): 310 to 321
  passing. Reverting each fix in a temporary copy fails its new cases (5, 1 and 2 failures).
- Left for a follow-up todo, as the owner decided: env -P, zsh allexport, a multi-variable for, sudo --chd.
