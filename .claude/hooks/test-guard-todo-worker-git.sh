#!/usr/bin/env bash
# Tests for guard-todo-worker-git.sh — run from anywhere.
# The guard limits todo-worker / todo-verifier Bash calls to staging-only git
# (spec §4.1). The cases that matter are the disguises: wrappers, absolute
# paths, compound commands, bash -c, $(...), a second line — and the harmless
# mention of "git commit" inside a grep, which must still be allowed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/guard-todo-worker-git.sh"
PASS=0; FAIL=0

event() {
  python3 -c 'import json, sys; print(json.dumps({"agent_type": sys.argv[1], "tool_input": {"command": sys.argv[2]}}))' "$1" "$2"
}

assert_deny() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if grep -q '"permissionDecision": "deny"' <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected deny)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

assert_allow() {
  local name="$1" out
  out=$(event "$2" "$3" | bash "$HOOK" 2>/dev/null)
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected allow)"; echo "  got: $out"; FAIL=$((FAIL+1))
  fi
}

W=todo-worker
assert_deny  "worker: git commit"                    $W 'git commit -m x'
assert_deny  "worker: git push"                      $W 'git push origin HEAD'
assert_deny  "worker: absolute git with -C"          $W '/usr/bin/git -C /tmp/wt commit -m x'
assert_deny  "worker: rtk wrapper"                   $W 'rtk git commit -m x'
assert_deny  "worker: env prefix"                    $W 'FOO=1 git push'
assert_deny  "worker: compound after cd"             $W 'cd /tmp/wt && git switch main'
assert_deny  "worker: git stash"                     $W 'git stash push -m x'
assert_deny  "worker: git checkout"                  $W 'git checkout -- a.py'
assert_deny  "worker: git -c option then reset"      $W 'git -c core.x=y reset --hard'
assert_deny  "worker: bash -c"                       $W 'bash -c "git push"'
assert_deny  "worker: command substitution"          $W 'echo $(git reset --hard)'
assert_deny  "worker: second line"                   $W $'git add a.py\ngit commit -m x'
assert_deny  "worker: gh"                            $W 'gh pr create --fill'
assert_deny  "worker: unparseable quoting"           $W 'git add "a.py'
assert_deny  "verifier: git commit"                  todo-verifier 'git commit -m x'
assert_allow "worker: git add -A"                    $W 'git -C /tmp/wt add -A'
assert_allow "worker: status porcelain"              $W '/usr/bin/git -C /tmp/wt status --porcelain'
assert_allow "worker: write-tree"                    $W 'git write-tree'
assert_allow "worker: diff cached vs origin/main"    $W 'git diff --cached --name-status origin/main'
assert_allow "worker: mention inside grep"           $W 'grep -rn "git commit" docs/'
assert_allow "worker: pytest via slot_env"           $W 'python3 scripts/todos/slot_env.py 1 -- python -m pytest apps/x'
assert_allow "main session (no agent_type)"          "" 'git commit -m x'
assert_allow "another agent type"                    code-review-orchestrator 'git push'

OUT=$(echo 'not json' | bash "$HOOK" 2>/dev/null)
if [ -z "$OUT" ]; then echo "PASS: malformed JSON fails open"; PASS=$((PASS+1)); else echo "FAIL: malformed JSON"; FAIL=$((FAIL+1)); fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
