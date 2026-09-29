---
status: pending
priority: p3
issue_id: "496"
tags: [harness, todo-sweep, security]
dependencies: []
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

- [ ] Each of findings 1–8 is refused by the guard, with an `assert_deny` case in
      `.claude/hooks/test-guard-todo-worker-git.sh` that fails when that fix is removed.
- [ ] The allow cases that already pass still pass (the guard must not start refusing a worker's
      ordinary `git -C WT add` / `diff` / `status`).

## Work Log

### 2026-09-29 - Filed from PR #880 review rounds 2 and 3

Round 2 never repairs, and round 3 (the owner's call) did not either. All were rated non-blocking.
Findings 6 and 7 were first reported in round 2's wrap-up but never written to the run file; round 3
re-found both.
