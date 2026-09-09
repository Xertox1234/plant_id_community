---
status: pending
priority: p2
issue_id: "379"
tags: [harness, hooks, testing, tooling]
dependencies: []
source_review: "todos/378-pending-p2-local-venv-drift-invalidates-test-results.md"
---

# Hooks that catch a test run whose result cannot be trusted

## Problem

In one session on 2026-09-08 I twice reported test results to the user that
were wrong, and in both cases the cause was the *environment*, not the code:

1. **A drifted venv.** `backend/venv` was on Wagtail 7.4.3 while
   `requirements.txt` pinned 8.0 (plus 4 more mismatches — see todo 378). Two
   rendition tests failed locally and passed in CI. I attributed them to "local
   Pillow", which was wrong: Pillow matched its pin.
2. **A dirty working tree used as a control.** Asked whether 14 failures were
   mine, I re-ran the suite with my own files restored to HEAD and got 24
   failures both ways, so I called them "pre-existing and unrelated". Both arms
   still had a peer agent's uncommitted `bootstrap.py` in the tree, so control
   and treatment shared the actual cause. Twelve of those 14 were a real
   `post_migrate` bug, which only CI caught.

Neither failure mode announces itself. Both produce a plausible failure list
that a reader learns to discount — which is strictly worse than a crash, and is
exactly what happened.

The common shape: **a local test result is evidence about a tree that CI does
not run, and nothing at the moment of the run says so.**

## Recommended Action

Add a `PreToolUse` / `Bash` hook, `.claude/hooks/check-test-env.sh`, that fires
only for pytest invocations and emits `hookSpecificOutput.additionalContext`
naming what makes the imminent result untrustworthy. Context, not a block —
the run should still happen, with its caveat attached.

### Check 1 — venv drift (primary; proven, measured)

Parse `backend/requirements.txt` for `^name==version$` and compare against
`backend/venv/bin/pip freeze`. Report **mismatched** and **not-installed**
separately: on 2026-09-08 the tree had 3 of the former and 2 of the latter, and
a naive "compare what's installed" check would have missed `django-ninja` and
`swapper` entirely. The comparison ran in well under a second over 210 packages.

Message must name the packages. "Your venv is stale" gets ignored; "wagtail:
pinned 8.0, installed 7.4.3" does not.

### Check 2 — dirty tree on a whole-suite run (secondary; higher false-positive risk)

Only when the command is a **bare** `python -m pytest` (no path arguments) and
`git status --porcelain` is non-empty, add a line stating the count of
uncommitted files and that a revert check against this tree is not a control.

Scope it that narrowly on purpose. This is a shared checkout where a peer agent
frequently has work in progress, so a hook that fires on every dirty tree will
be tuned out within a day — which is the failure mode being fixed, reintroduced
one level up. If it still proves noisy, drop this check and keep Check 1.

## Technical Details

The closest precedent is `.claude/hooks/kimi-review.sh`, already a
`PreToolUse`/`Bash` hook that matches one command shape. Copy its structure:

- **Command extraction:** `INPUT=$(cat)` then
  `COMMAND=$(printf '%s' "$INPUT" | jq -re '.tool_input.command') || exit 0`.
- **Matching:** anchor at `^` so `echo python -m pytest` is rejected, and
  tolerate leading `VAR=val` env prefixes — see its `GIT_COMMIT_RE`. Must match
  `python -m pytest`, `pytest`, and a venv-qualified `venv/bin/python -m pytest`.
- **Skip semantics, all silent `exit 0`:** an env opt-out
  (`$SKIP_ENV_CHECK=1`), `jq` missing, `backend/venv` missing (a worktree has
  none — see below), `requirements.txt` unreadable. Fail open: this hook must
  never block a test run.
- **Registration:** append a second entry to the existing `PreToolUse` `Bash`
  matcher array in `.claude/settings.json` — do not replace it, `kimi-review.sh`
  lives there. Give it a short `timeout` (10s is ample) unlike kimi's 180.
- **`if` field:** the settings schema supports
  `"if": "Bash(python -m pytest*)"`, which avoids spawning the hook for every
  shell command. `kimi-review.sh` predates it and matches in-script instead.
  Either is fine; `if` plus an in-script anchored re-check is belt-and-braces,
  and the in-script check is what the self-test can actually exercise.

Gotchas this repo has already paid for:

- **`.claude/` is committed, so a new hook reaches only NEW worktrees.** Six
  worktrees exist; they keep their old setup until rebased.
- **A worktree has no `backend/venv`** (gitignored), so the hook must skip
  cleanly there rather than reporting everything as "not installed".
- **`inject-patterns.sh` truncates injected rules at 8800 bytes.** This hook's
  output is separate `additionalContext`, but keep the message short anyway —
  a 210-package dump helps nobody. Cap the list (e.g. first 10, then "+N more").
- **zsh does not word-split an unquoted `$VAR`** — a loop over package names
  needs `${=VAR}` or `xargs`, or it silently processes one giant argument.

## Acceptance Criteria

- [ ] `.claude/hooks/check-test-env.sh` exists, with
      `.claude/hooks/test-check-test-env.sh` beside it, matching the convention
      every other hook here follows
- [ ] Registered in `.claude/settings.json` **alongside** the existing
      `kimi-review.sh` Bash entry, not replacing it — verified by reading the
      file back
- [ ] Fires on `python -m pytest`, `pytest`, and `venv/bin/python -m pytest`;
      silent on `echo python -m pytest`, on non-pytest commands, and when
      `backend/venv` is absent
- [ ] Names the specific drifted packages, distinguishing mismatched from
      not-installed
- [ ] **The self-test fails when the drift comparison is removed from the
      script.** Not a test that only asserts the hook ran — this repo shipped
      two decorative tests in a single day, both of which passed with the fix
      taken out (`docs/rules/testing.md`)
- [ ] Proven by running `.claude/hooks/check-test-env.sh` with a synthesized
      hook payload on stdin, AND by a real pytest invocation in a session that
      has the hook loaded — a hook that validates but never fires is the exact
      false-green this todo exists to prevent

## Notes

p2 for the same reason as todo 378: this corrupts the evidence every other task
depends on. 378 fixes the current drift; this stops the class recurring.

Do 378's step 1 first (`pip install -r backend/requirements.txt`), or the new
hook's first real run will fire on a genuinely drifted venv and there will be
nothing to distinguish "the hook works" from "the hook always fires".
