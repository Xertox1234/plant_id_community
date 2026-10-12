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
# Todo 577 #5: "recorded" is now checked: a sweep run file in the main checkout names both as a todo's worktree.
mkdir -p "$REPO/todos"
printf '{"todos":{"1":{"worktree":"%s"},"2":{"worktree":"%s"},"3":{}}}' "$AGENT" "$WF" > "$REPO/todos/.sweep-run-r.json"
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

# ---- todo 577 #5: from the main checkout, a harness worktree is allowed only when a run records it ----
STRAY="$REPO/.claude/worktrees/wf_other-workflow-9"
OTHER_AGENT="$REPO/.claude/worktrees/agent-def456"
git -C "$REPO" worktree add -q -b wt-stray "$STRAY"
git -C "$REPO" worktree add -q -b wt-other-agent "$OTHER_AGENT"
assert_deny  "577 #5: worker in the main checkout: another workflow's unrecorded wf_* worktree is denied" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
assert_deny  "577 #5: worker in the main checkout: another agent's unrecorded agent-* worktree is denied" \
  "$(event todo-worker "$REPO" "$OTHER_AGENT/scripts/x.py")"
assert_deny  "577 #5: ... and so from the session worktree the engine ran from" \
  "$(event todo-worker "$SESSION" "$STRAY/scripts/x.py")"
mkdir -p "$SESSION/todos"
printf '{"todos":{"9":{"worktree":"%s"}}}' "$STRAY" > "$SESSION/todos/.sweep-run-s.json"
assert_allow "577 #5: a run file in the session worktree the engine ran from records a worktree too" \
  "$(event todo-worker "$SESSION" "$STRAY/scripts/x.py")"
printf 'not json' > "$REPO/todos/.sweep-run-bad.json"
assert_allow "577 #5: an unreadable run file records nothing and breaks nothing else" \
  "$(event todo-worker "$REPO" "$WF/scripts/x.py")"
assert_allow "577 #5: a sweep-* worktree needs no record" \
  "$(event todo-worker "$REPO" "$OTHER/scripts/x.py")"
# PR #1038 review: a brief with no worktree gets a harness-isolated one, and its retry edits it from the main
# checkout before ingest-execute records it. While a run has such a todo executing, that edit is allowed.
rm -f "$SESSION/todos/.sweep-run-s.json"
printf '{"todos":{"7":{"stage":"executing"}}}' > "$REPO/todos/.sweep-run-inflight.json"
assert_allow "PR #1038: a retry edits the unrecorded wf_* of a brief that named no worktree" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
printf '{"todos":{"7":{"stage":"verified"}}}' > "$REPO/todos/.sweep-run-inflight.json"
assert_deny  "PR #1038: ... and once nothing executes without one, it is denied again" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
rm -f "$REPO/todos/.sweep-run-inflight.json"
# Todo 596 #1: a reopened todo's earlier attempt (`previous`) still records its worktree, as state.py lists it.
printf '{"todos":{"5":{"stage":"verified","previous":[{"worktree":"%s"}]}}}' "$STRAY" \
  > "$REPO/todos/.sweep-run-prev.json"
assert_allow "596 #1: a worktree recorded only in an entry's previous attempts is allowed" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
# PR #1061 review: a stray_worktree is a path a worker wrongly reported, listed for cleanup only, never ownership.
printf '{"todos":{"5":{"stage":"verified","previous":[{"stray_worktree":"%s"}]}}}' "$STRAY" \
  > "$REPO/todos/.sweep-run-prev.json"
assert_deny  "PR #1061: a worktree recorded only as an earlier attempt's stray_worktree is denied" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
printf '{"todos":{"5":{"stage":"verified","stray_worktree":"%s"}}}' "$STRAY" \
  > "$REPO/todos/.sweep-run-prev.json"
assert_deny  "PR #1061: ... and so is one recorded only as an entry's top-level stray_worktree" \
  "$(event todo-worker "$REPO" "$STRAY/scripts/x.py")"
assert_deny  "596 #1: ... while an unrecorded harness worktree is still denied" \
  "$(event todo-worker "$REPO" "$OTHER_AGENT/scripts/x.py")"
rm -f "$REPO/todos/.sweep-run-prev.json"

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
