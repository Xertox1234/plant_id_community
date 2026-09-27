#!/usr/bin/env bash
# PreToolUse hook (Bash) — keep todo-worker / todo-verifier agents from
# committing, pushing, moving branches or calling gh. The decision lives in
# scripts/todos/worker_git_guard.py (see its docstring); every other caller
# passes through. Fails open when python3 is missing or the event is unparseable.
#
# Tests: .claude/hooks/test-guard-todo-worker-git.sh
set -uo pipefail
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$(cd "$(dirname "$0")/../.." && pwd)/scripts/todos/worker_git_guard.py"
