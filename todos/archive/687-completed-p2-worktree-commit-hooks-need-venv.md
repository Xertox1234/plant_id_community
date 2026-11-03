---
status: completed
priority: p2
issue_id: "687"
tags: [harness, pre-commit, worktrees]
dependencies: []
triage: ready
triaged: 2026-11-03
---

# mypy-staged and pytest-staged fail in every worktree: no backend/venv

## Problem

A git worktree has no `backend/venv`, because it is gitignored and lives only in the main checkout. Both staged-file commit hooks fail closed. Every worktree commit therefore either skips them (`SKIP=mypy-staged,pytest-staged`), which defeats the gate, or first symlinks the main venv, which then has to be unlinked before the todo engine's `review-args`.

## Findings

- `scripts/test-staged.sh:30` checks `venv/bin/python`. If it is missing, it prints "backend/venv/bin/python is missing; create the venv or commit with SKIP=pytest-staged" and exits.
- `scripts/mypy_staged.py:33` hard-codes `PYTHON = BACKEND / "venv" / "bin" / "python"` and fails closed with the same message (line 56).
- **2026-11-03, PR #1252:** both hooks failed on commit from `.claude/worktrees/brave-babbage-ee00a5`. The commit went in with both skipped, and the checks were run by hand.
- **The symlink workaround has its own trap** (memory note, 2026-10-29): `review-args` runs `git hash-object` on untracked paths and dies on a symlink to a directory, so the symlink must be removed right after the commit.

## Proposed Solutions

### Option 1: fall back to the main checkout's venv (recommended)

- **Implementation:** when `backend/venv/bin/python` is missing, look in the main worktree. `git rev-parse --path-format=absolute --git-common-dir` gives `<main>/.git`, so use its parent plus `/backend/venv/bin/python`. Apply this in both scripts.
- **Pros:** no symlink and no cleanup step, and works in every worktree, including todo-engine worktrees.
- **Cons:** the main venv's editable `wagtail_forum` points at the main checkout. That is fine once todo 688 lands.
- **Effort:** 1 hour.
- **Risk:** low. Both scripts still fail closed when neither venv exists.

## Recommended Action

1. Add a small `resolve_backend_python()` helper, shared or duplicated in the two scripts, with this order:
   1. `backend/venv/bin/python`
   2. the main checkout's `backend/venv/bin/python`
   3. fail closed with the existing message
2. Set `PYTHONPATH=<this worktree>/backend/packages/wagtail_forum` for the pytest run, unless todo 688 already covers it.
3. Drop the "symlink the venv, then unlink it" step from the docs that teach it (todo-engine docs, `docs/LEARNINGS.md` pointer).

## Technical Details

- `scripts/test-staged.sh`, `scripts/mypy_staged.py`, `.pre-commit-config.yaml` (hooks `pytest-staged`, `mypy-staged`).
- Main venv path in this setup: `<main checkout>/backend/venv` (Python 3.13).

## Acceptance Criteria

- [x] A commit staging a backend test file from a fresh `.claude/worktrees/<name>` (no `backend/venv`) runs `pytest-staged` and `mypy-staged` with no SKIP and no symlink.
- [x] With no venv in either place, both hooks still fail closed with a clear message.

## Work Log

### 2026-11-03 - Filed

- Hit on PR #1252, where the commit needed `SKIP=kimi-review,mypy-staged,pytest-staged`. The owner asked for todos for repeated agent friction.

### 2026-11-03 - Implemented by the todo sweep (run 2026-11-03-2214)

- `scripts/mypy_staged.py` (`resolve_backend_python()`) and `scripts/test-staged.sh` (`backend_python()`) now use this checkout's `backend/venv/bin/python`, else the main checkout's, found as the parent of `git rev-parse --path-format=absolute --git-common-dir`; with neither, both still fail closed and name the `SKIP=` bypass.
- `pytest-staged` prepends the worktree's own `backend/packages/wagtail_forum` to `PYTHONPATH`, so the main venv's editable install does not shadow the worktree's package. Harmless once todo 688 lands. `mypy-staged` is left as it is: package drift there is todo 688's scope.
- New `scripts/test_staged_hooks_venv.py` (6 cases: worktree fallback, fallback under a hook's `GIT_DIR`, own venv wins, main checkout, no venv anywhere, no git repo), wired into `.github/workflows/harness-ci.yml`. With the old scripts restored, all 6 fail.
- `docs/PRE_COMMIT_SETUP.md` documents the lookup. No repo doc taught the venv symlink step; it lived only in agent memory notes.

### 2026-11-03 - Verified by the todo sweep (run 2026-11-03-2214)

- AC 1: `env -u SKIP bash -c 'cd . && test ! -e backend/venv && echo "backend/venv absent in this worktree" && python3 -c "import sys; sys.path.insert(0, \"scripts\"); import mypy_staged; print(\"resolved interpreter:\", mypy_staged.resolve_backend_python())" && python3 scripts/todos/slot_env.py --main-root . 3 -- pre-commit run pytest-staged --verbose --files backend/apps/core/tests/test_classify_send_error.py && pre-commit run mypy-staged --verbose --files backend/apps/core/services/email_service.py && test ! -e backend/venv && echo "still no backend/venv (no symlink)"'` — evidence `.sweep-evidence/g3/687-ac0.txt` (not committed), last lines:

  ```text
  ======================== 22 passed, 2 warnings in 0.79s ========================
  …
  - hook id: mypy-staged
  - duration: 4.22s
  still no backend/venv (no symlink)

  [exit 0]
  ```

- AC 2: `python3 scripts/test_staged_hooks_venv.py -v` — evidence `.sweep-evidence/g3/687-ac1.txt` (not committed), last lines:

  ```text
  Ran 6 tests in 2.487s

  OK

  [exit 0]
  ```

### 2026-11-03 - Completed by the todo sweep (run 2026-11-03-2214)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.

### 2026-11-03 - Review round 1: non-blocking findings (PR #1264)

- FIXED (low, two reports at `scripts/mypy_staged.py:104`): mypy-staged ran the main checkout's venv without this checkout's `backend/packages/wagtail_forum` first on `PYTHONPATH`, so worktree forum edits could be typed against main's editable install. It now passes that prefix to the mypy subprocess, as `test-staged.sh` does.
- FIXED (low, `scripts/test_staged_hooks_venv.py:143`): the tests now assert the forum package heads `PYTHONPATH` for both hooks, in the main-venv fallback case and the own-venv case. Mutation check: with `env=env` dropped from the mypy call, 2 tests fail; restored, 6 pass.
- DECLINED (low, `scripts/test-staged.sh:31`): `rev-parse --path-format=absolute` needs git 2.31 or newer. Every machine and CI runner here has a newer git, and on an older one the hook still fails closed with a `SKIP=` hint, so the worst case is a misleading message, not a bypass.
