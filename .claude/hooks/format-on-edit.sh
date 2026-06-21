#!/usr/bin/env bash
# PostToolUse hook — auto-fix lint right after an Edit/Write/MultiEdit, friction-safe:
# autofix ONLY, never a whole-file reformat (black/isort/prettier/dart-format own
# formatting; whole-file reformats caused commit friction, todos 087/117). Single
# file only, never repo-wide. Fail-open: any missing tool → exit 0.
#
#   Python (backend/*.py)              → ruff F401 unused-import fix
#                                        residual F401 → exit 2 (feedback)
#   TS/TSX (web/src/*.ts[x])           → eslint --fix (lint autofix, NOT prettier)
#                                        residual eslint error → exit 2 (feedback)
#   Dart   (plant_community_mobile/*.dart, non-generated) → dart fix --apply
#                                        (analyzer autofix, NOT dart format)
#
# Why Dart has no exit-2: `dart fix` applies every fix it knows; it has no
# "couldn't-fix-its-own-domain" residual to report. Broader `dart analyze`
# findings are the flutter-analyze CI gate's job, and surfacing them per-edit
# would be noise. The exit-2 feedback mechanism is exercised by Python + TS.
#
# exit 2 in PostToolUse is ADVISORY — the edit already landed; it only feeds the
# remaining lint back so Claude self-corrects before the commit gate.
#
# Test seams: FORMAT_ON_EDIT_ROOT (repo root), FORMAT_ON_EDIT_{RUFF,ESLINT,DART}.
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

# Repo-relative path (for scope + skip-lists) and absolute path (for the fixers).
REL="${FILE_PATH#"$PROJECT_ROOT"/}"
case "$FILE_PATH" in
  /*) ABS="$FILE_PATH" ;;
  *)  ABS="$PROJECT_ROOT/$FILE_PATH" ;;
esac
[ -f "$ABS" ] || exit 0

# --- Python: ruff F401 unused-import fix (flake8 gate scopes to ^backend/.*\.py$) ---
python_branch() {
  # Skip files with intentional unused imports — mirrors setup.cfg per-file-ignores
  # (F401). Removing these would break re-exports / the import-smoke-test.
  # SKIPLIST-START — test-format-on-edit.sh asserts setup.cfg F401 ⊆ these (todo 232);
  # keep entries one-per-line as `backend/...py| \` so the sync check can parse them.
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
  # SKIPLIST-END

  # Resolve ruff: prefer the backend venv, fall back to PATH. Absent → fail-open.
  # FORMAT_ON_EDIT_RUFF is a test seam — when set it is authoritative.
  local RUFF
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
  local RESIDUAL
  RESIDUAL=$("$RUFF" check --isolated --select F401 --quiet --output-format concise "$ABS" 2>/dev/null)
  if [ -n "$RESIDUAL" ]; then
    printf 'Unused imports remain in %s (flake8 F401 will block the commit):\n%s\n' "$REL" "$RESIDUAL" >&2
    exit 2
  fi
  exit 0
}

# --- TS/TSX: eslint --fix (lint autofix; NOT prettier — no whole-file reformat) ---
ts_branch() {
  # FORMAT_ON_EDIT_ESLINT is a test seam; default to the web workspace binary.
  local ESLINT
  ESLINT="${FORMAT_ON_EDIT_ESLINT:-$PROJECT_ROOT/web/node_modules/.bin/eslint}"
  [ -x "$ESLINT" ] || exit 0

  # Run from web/ so eslint resolves its flat config. --fix applies only
  # autofixable rule violations (unused vars, etc.); it is NOT prettier --write.
  ( cd "$PROJECT_ROOT/web" && "$ESLINT" --fix "$ABS" ) >/dev/null 2>&1 || true

  # --quiet → errors only (not warnings); --format unix → empty output when clean.
  local RESIDUAL
  RESIDUAL=$( cd "$PROJECT_ROOT/web" && "$ESLINT" --quiet --format unix "$ABS" 2>/dev/null )
  if [ -n "$RESIDUAL" ]; then
    printf 'ESLint errors remain in %s (web CI lint will block):\n%s\n' "$REL" "$RESIDUAL" >&2
    exit 2
  fi
  exit 0
}

# --- Dart: dart fix --apply (analyzer autofix; NOT dart format) ---
dart_branch() {
  # Generated sources are rewritten by build_runner — never hand-fix them.
  case "$REL" in *.g.dart|*.freezed.dart) exit 0 ;; esac

  # FORMAT_ON_EDIT_DART is a test seam; default to dart on PATH.
  local DART
  DART="${FORMAT_ON_EDIT_DART:-$(command -v dart 2>/dev/null || true)}"
  [ -x "$DART" ] || exit 0

  # Run from the package root so pub context resolves; scope to the single file.
  ( cd "$PROJECT_ROOT/plant_community_mobile" && "$DART" fix --apply "$ABS" ) >/dev/null 2>&1 || true
  exit 0
}

case "$REL" in
  backend/*.py)                  python_branch ;;
  web/src/*.ts|web/src/*.tsx)    ts_branch ;;
  plant_community_mobile/*.dart) dart_branch ;;
  *) exit 0 ;;
esac
exit 0
