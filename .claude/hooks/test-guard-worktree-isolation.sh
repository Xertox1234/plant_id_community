#!/usr/bin/env bash
# Tests for guard-worktree-isolation.sh — run from anywhere.
# The hook only needs `jq` (real); no stubs are required.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-worktree-isolation.sh"
PASS=0; FAIL=0

run_hook() { echo "$1" | bash "$HOOK" 2>/dev/null; }

assert_deny() {
  local name="$1" out
  out=$(run_hook "$2")
  if echo "$out" | grep -q '"permissionDecision": "deny"'; then
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

REPO='/Users/x/projects/plant_id_community'
AGENT_WT="$REPO/.claude/worktrees/agent-abc"
NAMED_WT="$REPO/.worktrees/fix-csrf-duplication"

# ---- .claude/worktrees/agent-* form ----
assert_deny "agent worktree: absolute main-checkout path is denied" \
  "{\"cwd\":\"$AGENT_WT\",\"tool_input\":{\"file_path\":\"$REPO/backend/manage.py\"}}"

assert_deny "agent worktree: deny fires when cwd is a worktree subdirectory" \
  "{\"cwd\":\"$AGENT_WT/backend\",\"tool_input\":{\"file_path\":\"$REPO/backend/manage.py\"}}"

assert_allow "agent worktree: absolute path inside the worktree is allowed" \
  "{\"cwd\":\"$AGENT_WT\",\"tool_input\":{\"file_path\":\"$AGENT_WT/backend/manage.py\"}}"

# ---- .worktrees/<name> form ----
assert_deny "named worktree: absolute main-checkout path is denied" \
  "{\"cwd\":\"$NAMED_WT\",\"tool_input\":{\"file_path\":\"$REPO/backend/manage.py\"}}"

assert_allow "named worktree: absolute path inside the worktree is allowed" \
  "{\"cwd\":\"$NAMED_WT\",\"tool_input\":{\"file_path\":\"$NAMED_WT/backend/manage.py\"}}"

assert_allow "named worktree: relative path is allowed" \
  "{\"cwd\":\"$NAMED_WT\",\"tool_input\":{\"file_path\":\"backend/manage.py\"}}"

# ---- common cases ----
assert_allow "non-worktree session is untouched" \
  "{\"cwd\":\"$REPO\",\"tool_input\":{\"file_path\":\"$REPO/backend/manage.py\"}}"

assert_allow "absolute path outside the repo is allowed" \
  "{\"cwd\":\"$AGENT_WT\",\"tool_input\":{\"file_path\":\"/tmp/scratch.txt\"}}"

assert_allow "empty MAIN_ROOT edge case fails open" \
  '{"cwd":"/.claude/worktrees/agent-abc","tool_input":{"file_path":"/etc/passwd"}}'

assert_allow "malformed JSON fails open" \
  'not json at all'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
