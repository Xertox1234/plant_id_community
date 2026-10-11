#!/usr/bin/env bash
# Tests for guard-todo-worker-edit.sh (todo 541, #982-9) — run from anywhere.
# Builds a throwaway repository with a sweep worktree under .claude/worktrees/, then feeds the hook
# PreToolUse events as a todo-worker (and as other agents) would send them.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-todo-worker-edit.sh"
PASS=0; FAIL=0
TMP=$(mktemp -d "${TMPDIR:-/tmp}/edit-guard.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

REPO="$TMP/repo"
git init -q -b main "$REPO"
git -C "$REPO" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
WT="$REPO/.claude/worktrees/sweep-r-g1"
OTHER="$REPO/.claude/worktrees/sweep-r-g2"
git -C "$REPO" worktree add -q -b wt-g1 "$WT"
git -C "$REPO" worktree add -q -b wt-g2 "$OTHER"

event() {  # agent cwd path [key]
  printf '{"agent_type":"%s","cwd":"%s","tool_name":"Edit","tool_input":{"%s":"%s"}}' "$1" "$2" "${4:-file_path}" "$3"
}

assert_deny() {
  local name="$1" out
  out=$(printf '%s' "$2" | bash "$HOOK" 2>/dev/null)
  if grep -q '"permissionDecision": "deny"' <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected a deny decision)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_allow() {
  local name="$1" out
  out=$(printf '%s' "$2" | bash "$HOOK" 2>/dev/null)
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected no output / allow)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

# ---- a todo-worker whose cwd is the main checkout (execute-args made its worktree, todo 528) ----
assert_deny  "worker in the main checkout: a relative path lands in the main checkout and is denied" \
  "$(event todo-worker "$REPO" scripts/todos/state.py)"
assert_deny  "worker in the main checkout: an absolute main-checkout path is denied" \
  "$(event todo-worker "$REPO" "$REPO/scripts/todos/state.py")"
assert_deny  "worker in the main checkout: a .. that climbs out of the worktree is denied" \
  "$(event todo-worker "$REPO" "$WT/../../../scripts/x.py")"
assert_allow "worker in the main checkout: an absolute path inside a sweep worktree is allowed" \
  "$(event todo-worker "$REPO" "$WT/scripts/todos/state.py")"
assert_allow "worker in the main checkout: a path outside the repository (TMPDIR) is allowed" \
  "$(event todo-worker "$REPO" "$TMP/scratch.txt")"
assert_deny  "worker in the main checkout: NotebookEdit's notebook_path is guarded too" \
  "$(event todo-worker "$REPO" "$REPO/a.ipynb" notebook_path)"

# ---- a todo-worker whose cwd is inside a worktree (a harness-isolated worker) ----
assert_allow "worker in its worktree: a relative path stays in that worktree" \
  "$(event todo-worker "$WT" scripts/x.py)"
assert_deny  "worker in its worktree: a path in another group's worktree is denied" \
  "$(event todo-worker "$WT" "$OTHER/scripts/x.py")"
assert_deny  "worker in its worktree: a path in the main checkout is denied" \
  "$(mkdir -p "$WT/backend"; event todo-worker "$WT/backend" "$REPO/backend/x.py")"

# ---- todo 546: a session worktree as the cwd, human worktrees, plain files, harness worktrees ----
SESSION="$REPO/.claude/worktrees/session-x"
HUMAN="$REPO/.claude/worktrees/todo-543-hand-round-guards"
AGENT="$REPO/.claude/worktrees/agent-abc123"
git -C "$REPO" worktree add -q -b wt-session "$SESSION"
git -C "$REPO" worktree add -q -b wt-human "$HUMAN"
git -C "$REPO" worktree add -q -b wt-agent "$AGENT"
assert_allow "546 #1: the engine ran from a session worktree: its worker may edit its sweep worktree" \
  "$(event todo-worker "$SESSION" "$WT/scripts/x.py")"
assert_deny  "546 #1: ... but not the session worktree it inherited as its cwd (a relative path)" \
  "$(event todo-worker "$SESSION" scripts/x.py)"
assert_deny  "546 #9: worker in the main checkout: a human's worktree is denied" \
  "$(event todo-worker "$REPO" "$HUMAN/scripts/x.py")"
assert_deny  "546 #9: worker in the main checkout: a plain file directly in .claude/worktrees/ is denied" \
  "$(event todo-worker "$REPO" "$REPO/.claude/worktrees/notes.txt")"
assert_allow "546: a harness-isolated worker (agent-*) edits its own worktree" \
  "$(event todo-worker "$AGENT" "$AGENT/scripts/x.py")"
assert_deny  "546: ... and not a sweep worktree" \
  "$(event todo-worker "$AGENT" "$WT/scripts/x.py")"

# ---- todo 551 (#1005 finding 2): a retry/repair worker edits the group's recorded harness worktree ----
WF="$REPO/.claude/worktrees/wf_6b13b590-b1b-1"
git -C "$REPO" worktree add -q -b wt-wf "$WF"
assert_allow "551 #2: worker in the main checkout: a recorded agent-* worktree is allowed" \
  "$(event todo-worker "$REPO" "$AGENT/scripts/x.py")"
assert_allow "551 #2: worker in the main checkout: a recorded wf_* worktree is allowed" \
  "$(event todo-worker "$REPO" "$WF/scripts/x.py")"
assert_deny  "551 #2: ... while a human's worktree is still denied" \
  "$(event todo-worker "$REPO" "$HUMAN/scripts/x.py")"
assert_deny  "551 #2: ... and so is the session worktree the worker inherited" \
  "$(event todo-worker "$SESSION" "$SESSION/scripts/x.py")"
assert_allow "551 #2: a harness-isolated worker in wf_* edits its own worktree" \
  "$(event todo-worker "$WF" scripts/x.py)"
assert_deny  "551 #2: ... and not a sweep worktree" \
  "$(event todo-worker "$WF" "$WT/scripts/x.py")"

# ---- everyone else passes through ----
assert_allow "the main session (no agent_type) is untouched" \
  "$(printf '{"cwd":"%s","tool_input":{"file_path":"%s"}}' "$REPO" "$REPO/x.py")"
assert_allow "a todo-verifier is not this hook's business" \
  "$(event todo-verifier "$REPO" "$REPO/x.py")"
assert_allow "a cwd in no git checkout fails open" \
  "$(event todo-worker "$TMP" "$TMP/x.py")"
assert_allow "malformed JSON fails open" 'not json at all'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
