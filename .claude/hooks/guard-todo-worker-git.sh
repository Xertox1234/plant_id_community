#!/usr/bin/env bash
# PreToolUse hook (Bash) — keep todo-worker / todo-verifier / todo-reviewer agents from
# committing, pushing, moving branches or calling gh. The decision lives in
# scripts/todos/worker_git_guard.py (see its docstring); every other caller
# passes through. Fails open when python3 or the script is missing or the event
# is unparseable (exit 2 here would block every Bash call in the session).
#
# Tests: .claude/hooks/test-guard-todo-worker-git.sh
set -uo pipefail
command -v python3 >/dev/null 2>&1 || exit 0
SCRIPT="$(cd "$(dirname "$0")/../.." && pwd)/scripts/todos/worker_git_guard.py"
[ -f "$SCRIPT" ] || exit 0
exec python3 "$SCRIPT"
