#!/usr/bin/env bash
# PostToolUse hook — auto-remove unused Python imports (flake8 F401) right after
# an Edit/Write/MultiEdit, so they never reach the commit gate and abort it.
#
# Implements the Python branch of todo 227. Uses `ruff check --select F401 --fix`
# as an F401 FIXER ONLY — NOT a formatter (black + isort own formatting, todo 087).
# Single-file only, never repo-wide. Fail-open: any missing tool → exit 0.
#
# Residual F401 that ruff cannot auto-fix are printed to stderr with exit 2 so
# Claude sees the feedback and self-corrects (the edit itself already landed —
# exit 2 in PostToolUse is advisory, it does not undo the edit).
#
# Skips the files whose F401 is intentional (re-exports / import-smoke-test),
# mirroring setup.cfg [flake8] per-file-ignores — keep the two lists in sync.
# Tests: .claude/hooks/test-format-on-edit.sh
set -uo pipefail

# (1) Kill switch: instant disable with no commit (mirrors INJECT_PATTERNS_DISABLE).
[[ -n "${FORMAT_ON_EDIT_DISABLE:-}" ]] && exit 0

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -re '.tool_name' 2>/dev/null) || exit 0
FILE_PATH=$(printf '%s' "$INPUT" | jq -re '.tool_input.file_path' 2>/dev/null) || exit 0

[[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]] || exit 0

# Resolve paths relative to project root (two levels up from .claude/hooks/).
# FORMAT_ON_EDIT_ROOT overrides it for tests (mirrors match_triggers' INJECT_PROJECT_ROOT).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${FORMAT_ON_EDIT_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# Repo-relative path (for backend/ scope + skip-list) and absolute path (for ruff).
REL="${FILE_PATH#"$PROJECT_ROOT"/}"
case "$FILE_PATH" in
  /*) ABS="$FILE_PATH" ;;
  *)  ABS="$PROJECT_ROOT/$FILE_PATH" ;;
esac

# Only backend Python files (the flake8 gate scopes to ^backend/.*\.py$).
[[ "$REL" == backend/*.py ]] || exit 0
[ -f "$ABS" ] || exit 0

# Skip files with intentional unused imports — mirrors setup.cfg per-file-ignores
# (F401). Removing these would break re-exports / the import-smoke-test.
case "$REL" in
  backend/plant_community_backend/settings.py| \
  backend/apps/blog/api/viewsets.py| \
  backend/apps/blog/tests/test_analytics.py| \
  backend/apps/plant_identification/models.py| \
  backend/apps/plant_identification/views.py| \
  backend/apps/users/views.py| \
  backend/test_django_imports.py)
    exit 0 ;;
esac

# Resolve ruff: prefer the backend venv, fall back to PATH. Absent → fail-open.
# FORMAT_ON_EDIT_RUFF is a test seam — when set it is authoritative (the test
# points it at a nonexistent path to exercise the fail-open branch).
if [ -n "${FORMAT_ON_EDIT_RUFF:-}" ]; then
  RUFF="$FORMAT_ON_EDIT_RUFF"
else
  RUFF="$PROJECT_ROOT/backend/venv/bin/ruff"
  [ -x "$RUFF" ] || RUFF="$(command -v ruff 2>/dev/null || true)"
fi
[ -x "$RUFF" ] || exit 0

# Auto-fix unused imports in this one file (F401 only; no formatting, no reorder).
# --isolated ignores ambient ruff config so behavior is exactly "remove unused
# imports, nothing else" regardless of any future ruff.toml.
"$RUFF" check --isolated --select F401 --fix --quiet "$ABS" >/dev/null 2>&1 || true

# Report any F401 ruff could not auto-fix so Claude can resolve them before commit.
RESIDUAL=$("$RUFF" check --isolated --select F401 --output-format concise "$ABS" 2>/dev/null) || RESIDUAL=""
if [ -n "$RESIDUAL" ]; then
  printf 'Unused imports remain in %s (flake8 F401 will block the commit):\n%s\n' "$REL" "$RESIDUAL" >&2
  exit 2
fi
exit 0
