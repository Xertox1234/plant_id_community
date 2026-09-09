#!/usr/bin/env bash
# PreToolUse hook for Bash — when the about-to-run command is a test invocation,
# report any drift between backend/venv and backend/requirements.txt as
# additionalContext, so the caveat is in context before the results are read.
#
# This is the SECOND surface for that check. The primary one is
# backend/conftest.py, which stamps the environment onto every pytest run and
# therefore also covers CI, every worktree, humans at a terminal, and other
# agents. This hook exists because it additionally covers `manage.py test` and
# puts the caveat in the model's context deterministically. Both call the same
# module: backend/apps/core/env_integrity.py.
#
# Never blocks — no permissionDecision. A drifted venv makes a result
# untrustworthy, not forbidden.
#
# Skip semantics (all early exit 0, silently):
#   - $SKIP_ENV_CHECK=1        → user opt-out
#   - `jq` not on PATH         → cannot parse the event or build JSON safely
#   - backend/venv absent      → a worktree has none (it is gitignored)
#   - the check itself errors  → fail open; never break a test run
# Tests: .claude/hooks/test-check-test-env.sh

set -uo pipefail

# 1) Explicit opt-out
[ -n "${SKIP_ENV_CHECK:-}" ] && exit 0

# 2) Required tooling — auto-skip if missing
command -v jq >/dev/null 2>&1 || exit 0

# 3) Read the hook event JSON and extract the pending Bash command
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -re '.tool_input.command' 2>/dev/null) || exit 0

# 4) Match only real test invocations. Anchored at ^ so `echo python -m pytest`
#    is rejected, with a trailing ([[:space:]]|$) so `manage.py testfoo` and
#    `pytest.ini` are rejected too. Allows leading VAR=val env prefixes and the
#    `cd <dir> && ` chain this repo uses constantly, plus a path prefix so
#    `venv/bin/python -m pytest` matches. Same shape as kimi-review.sh's
#    GIT_COMMIT_RE; note the RHS of =~ must stay unquoted.
TEST_CMD_RE='^([[:space:]]*[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+)*([[:space:]]*cd[[:space:]]+[^&;|]+&&[[:space:]]*)*[[:space:]]*([^[:space:];|&]*/)?(python[0-9.]*[[:space:]]+-m[[:space:]]+pytest|pytest|python[0-9.]*[[:space:]]+manage\.py[[:space:]]+test)([[:space:]]|$)'
[[ "$COMMAND" =~ $TEST_CMD_RE ]] || exit 0

# 5) Resolve paths relative to project root (two levels up from .claude/hooks/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${CHECK_TEST_ENV_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
VENV_PYTHON="$PROJECT_ROOT/backend/venv/bin/python"
CHECKER="$PROJECT_ROOT/backend/apps/core/env_integrity.py"

# 6) A worktree has no backend/venv (gitignored). Reporting all 210 pins as
#    "not installed" there would be pure noise, so skip cleanly instead.
[ -x "$VENV_PYTHON" ] || exit 0
[ -f "$CHECKER" ] || exit 0

# 7) Run the same comparison conftest.py uses, against the venv rather than
#    whatever python happens to be on PATH. Fail open on any error.
DRIFT=$("$VENV_PYTHON" "$CHECKER" --hook 2>/dev/null) || exit 0

# 8) Silent when the environment is clean. A hook that says nothing on a
#    healthy tree spends no attention, which is what keeps it credible on the
#    day it does fire.
[ -n "$DRIFT" ] || exit 0

jq -n --arg ctx "$DRIFT" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":$ctx}}' \
  2>/dev/null || true
exit 0
