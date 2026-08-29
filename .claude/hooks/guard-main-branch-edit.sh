#!/usr/bin/env bash
# PreToolUse hook — block Edit/Write/MultiEdit while checked out on main.
# This repo's workflow is always feature branch + PR (branch protection
# blocks a direct push anyway); this catches the mistake before the edit
# even happens. Only blocks edits that land inside the repo at $CWD — files
# outside it (e.g. ~/.claude memory notes) are unaffected even while on main.
#
# Skip semantics (all early exit 0, silently):
#   - $SKIP_MAIN_BRANCH_GUARD=1  → user opt-out (matches SKIP_KIMI_REVIEW)
#   - `jq` not on PATH           → cannot parse hook event or build JSON safely
#   - any parse/git failure      → fails open
#
# Tests: .claude/hooks/test-guard-main-branch-edit.sh
set -uo pipefail

[ -z "${SKIP_MAIN_BRANCH_GUARD:-}" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -re '.cwd' 2>/dev/null) || exit 0
FILE_PATH=$(printf '%s' "$INPUT" | jq -re '.tool_input.file_path' 2>/dev/null) || exit 0

cd "$CWD" 2>/dev/null || exit 0

BRANCH=$(git branch --show-current 2>/dev/null)
[ "$BRANCH" = "main" ] || exit 0

CWD_TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$CWD_TOPLEVEL" ] || exit 0

# Resolve FILE_PATH to absolute (a relative path resolves against $CWD) so
# both cases go through the same toplevel check below — a relative path
# with ".." segments that actually escapes the repo must not be treated as
# automatically in-scope.
case "$FILE_PATH" in
  /*) ABS_FILE_PATH="$FILE_PATH" ;;
  *) ABS_FILE_PATH="$CWD/$FILE_PATH" ;;
esac

# Compare git-resolved toplevels on both sides (not string prefixes): git
# internally canonicalizes symlinks (e.g. macOS /tmp -> /private/tmp) when
# locating a repo, so two `--show-toplevel` calls stay consistent with each
# other even when the raw path strings wouldn't line up. `cd` itself walks
# ".." components via real filesystem lookups, so this also correctly
# resolves a path that escapes the repo through "..".
DIR=$(dirname -- "$ABS_FILE_PATH")
# Walk up to the nearest existing ancestor — a Write into a not-yet-created
# nested directory has no `dirname` to `cd` into yet.
while [ ! -d "$DIR" ] && [ "$DIR" != "/" ]; do
  DIR=$(dirname -- "$DIR")
done
[ -d "$DIR" ] || exit 0
FILE_TOPLEVEL=$(cd "$DIR" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
[ "$FILE_TOPLEVEL" = "$CWD_TOPLEVEL" ] || exit 0

REASON="You're on main. Create a feature branch first (git checkout -b <name>) — this repo requires feature branches + PRs, never direct edits on main. (Bypass: SKIP_MAIN_BRANCH_GUARD=1)"

jq -n --arg r "$REASON" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$r}}'
exit 0
