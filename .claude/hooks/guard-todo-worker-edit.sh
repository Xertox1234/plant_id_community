#!/usr/bin/env bash
# PreToolUse hook (Edit/Write/MultiEdit/NotebookEdit) — keep a todo-worker's edits inside a worktree
# (todo 541, #982-9). Since todo 528 the worker's cwd is the main checkout, where
# guard-worktree-isolation.sh does not act, so a relative or mistyped absolute path would land in the
# main checkout. The decision lives in scripts/todos/worker_edit_guard.py (see its docstring); every
# other agent passes through. Fails open when python3 or the script is missing or the event is
# unparseable (exit 2 here would block every edit in the session).
#
# Tests: .claude/hooks/test-guard-todo-worker-edit.sh
set -uo pipefail
command -v python3 >/dev/null 2>&1 || exit 0
SCRIPT="$(cd "$(dirname "$0")/../.." && pwd)/scripts/todos/worker_edit_guard.py"
[ -f "$SCRIPT" ] || exit 0
exec python3 "$SCRIPT"
