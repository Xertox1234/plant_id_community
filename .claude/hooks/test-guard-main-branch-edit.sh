#!/usr/bin/env bash
# Tests for guard-main-branch-edit.sh — run from anywhere.
# Unlike guard-worktree-isolation.sh (pure path-string matching), this hook
# reads real git state, so tests build scratch repos under a temp dir.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-main-branch-edit.sh"
PASS=0; FAIL=0

run_hook() { echo "$1" | bash "$HOOK" 2>/dev/null; }

assert_deny() {
  local name="$1" out
  out=$(run_hook "$2")
  if grep -q '"permissionDecision": "deny"' <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected a deny decision)"
    echo "  got: $(echo "$out" | head -3)"
    FAIL=$((FAIL+1))
  fi
}

assert_allow() {
  local name="$1" out
  out=$(run_hook "$2")
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected no output / allow)"
    echo "  got: $(echo "$out" | head -3)"
    FAIL=$((FAIL+1))
  fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

MAIN_REPO="$TMP/main-repo"
mkdir -p "$MAIN_REPO"
git -C "$MAIN_REPO" init -q -b main
git -C "$MAIN_REPO" -c user.email=t@t.com -c user.name=t commit -q --allow-empty -m init

FEATURE_REPO="$TMP/feature-repo"
mkdir -p "$FEATURE_REPO"
git -C "$FEATURE_REPO" init -q -b main
git -C "$FEATURE_REPO" -c user.email=t@t.com -c user.name=t commit -q --allow-empty -m init
git -C "$FEATURE_REPO" checkout -q -b feature-branch

# ---- on main ----
assert_deny "on main: absolute path inside repo is denied" \
  "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"$MAIN_REPO/backend/manage.py\"}}"

assert_deny "on main: relative path is denied" \
  "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"backend/manage.py\"}}"

mkdir -p "$MAIN_REPO/backend"
assert_deny "on main: cwd is a subdirectory, file_path is absolute" \
  "{\"cwd\":\"$MAIN_REPO/backend\",\"tool_input\":{\"file_path\":\"$MAIN_REPO/backend/manage.py\"}}"

assert_allow "on main: absolute path outside the repo is allowed" \
  "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"/tmp/scratch.txt\"}}"

assert_allow "on main: absolute path resolving into a different repo is allowed" \
  "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"$FEATURE_REPO/backend/manage.py\"}}"

assert_allow "on main: relative path with .. that escapes the repo is allowed" \
  "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"../outside.txt\"}}"

assert_deny "on main: relative path with .. that stays inside the repo is denied" \
  "{\"cwd\":\"$MAIN_REPO/backend\",\"tool_input\":{\"file_path\":\"../README.md\"}}"

BYPASS_OUT=$(SKIP_MAIN_BRANCH_GUARD=1 bash "$HOOK" <<< "{\"cwd\":\"$MAIN_REPO\",\"tool_input\":{\"file_path\":\"$MAIN_REPO/backend/manage.py\"}}" 2>/dev/null)
if [ -z "$BYPASS_OUT" ]; then
  echo "PASS: SKIP_MAIN_BRANCH_GUARD=1 bypasses the guard"; PASS=$((PASS+1))
else
  echo "FAIL: SKIP_MAIN_BRANCH_GUARD=1 bypasses the guard (expected no output / allow)"
  echo "  got: $(echo "$BYPASS_OUT" | head -3)"
  FAIL=$((FAIL+1))
fi

# ---- on a feature branch ----
assert_allow "feature branch: edit inside repo is allowed" \
  "{\"cwd\":\"$FEATURE_REPO\",\"tool_input\":{\"file_path\":\"$FEATURE_REPO/backend/manage.py\"}}"

# ---- common edge cases ----
assert_allow "non-repo cwd fails open" \
  "{\"cwd\":\"$TMP\",\"tool_input\":{\"file_path\":\"$TMP/scratch.txt\"}}"

assert_allow "malformed JSON fails open" \
  'not json at all'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
