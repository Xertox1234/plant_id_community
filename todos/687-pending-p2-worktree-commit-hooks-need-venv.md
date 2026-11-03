---
status: pending
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

- [ ] A commit staging a backend test file from a fresh `.claude/worktrees/<name>` (no `backend/venv`) runs `pytest-staged` and `mypy-staged` with no SKIP and no symlink.
- [ ] With no venv in either place, both hooks still fail closed with a clear message.

## Work Log

### 2026-11-03 - Filed

- Hit on PR #1252, where the commit needed `SKIP=kimi-review,mypy-staged,pytest-staged`. The owner asked for todos for repeated agent friction.
