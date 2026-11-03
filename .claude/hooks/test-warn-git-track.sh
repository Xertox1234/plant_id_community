#!/usr/bin/env bash
# Tests for warn-git-track.sh — run from anywhere. Needs jq and python3 (real).
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/warn-git-track.sh"
PASS=0; FAIL=0

event() { jq -n --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
run_hook() { printf '%s' "$1" | bash "$HOOK" 2>/dev/null; }

assert_warn() {
  local name="$1" out
  out=$(run_hook "$(event "$2")")
  if jq -e '.hookSpecificOutput.additionalContext | contains("--no-track")' <<< "$out" >/dev/null 2>&1 \
    && jq -e '.systemMessage | length > 0' <<< "$out" >/dev/null 2>&1 \
    && ! grep -q permissionDecision <<< "$out"; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected a warning, no decision)"; echo "  got: $(head -3 <<< "$out")"; FAIL=$((FAIL + 1))
  fi
}

assert_quiet() {
  local name="$1" out
  out=$(run_hook "$2")
  if [ -z "$out" ]; then
    echo "PASS: $name"; PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected no output)"; echo "  got: $(head -3 <<< "$out")"; FAIL=$((FAIL + 1))
  fi
}

# ---- warns ----
assert_warn "switch -c from origin/main" "git switch -c chore/x origin/main"
assert_warn "checkout -b from origin/main" "git checkout -b chore/x origin/main"
assert_warn "switch -C (force-create) from origin/" "git switch -C chore/x origin/main"
assert_warn "checkout -B from origin/" "git checkout -B chore/x origin/main"
assert_warn "switch --create from origin/" "git switch --create chore/x origin/main"
assert_warn "switch with attached -c<name>" "git switch -cchore/x origin/main"
assert_warn "absolute git path with -C <dir>" "/usr/bin/git -C /some/wt switch -c chore/x origin/main"
assert_warn "start point given as refs/remotes/" "git switch -c chore/x refs/remotes/origin/main"
assert_warn "explicit --track from a local name" "git switch -c chore/x --track upstream-main"
assert_warn "inside a compound command" "git fetch origin && git switch -c chore/x origin/main && git status"
assert_warn "start point before the flag" "git checkout origin/main -b chore/x"

# ---- stays quiet ----
assert_quiet "--no-track (the safe form)" "$(event "git switch -c chore/x --no-track origin/main")"
assert_quiet "checkout -b --no-track" "$(event "git checkout -b chore/x --no-track origin/main")"
assert_quiet "switch -c from a local branch" "$(event "git switch -c chore/x main")"
assert_quiet "plain switch to an existing branch" "$(event "git switch main")"
assert_quiet "checkout of a file path" "$(event "git checkout -- origin/notes.md")"
assert_quiet "git branch is out of scope" "$(event "git branch probe origin/main")"
assert_quiet "--no-track in its own segment does not cover another" \
  "$(event "git switch -c a --no-track origin/main; echo done")"
assert_quiet "non-git command mentioning origin/" "$(event "echo switch -c x origin/main")"
assert_quiet "non-Bash tool" '{"tool_name":"Edit","tool_input":{"file_path":"x"}}'
assert_quiet "unparseable JSON" 'not json'
assert_quiet "unbalanced quote fails open" "$(event "git switch -c x origin/main 'oops")"

# A --no-track in a DIFFERENT simple command must not silence the one that tracks.
assert_warn "--no-track elsewhere does not excuse a tracking switch" \
  "git switch -c a --no-track origin/main && git switch -c b origin/main"

# Warn-only: the hook never exits non-zero (exit 2 would block the command).
printf '%s' "$(event "git switch -c x origin/main")" | bash "$HOOK" >/dev/null 2>&1
RC=$?
if [ "$RC" -eq 0 ]; then
  echo "PASS: exits 0 on a warning"; PASS=$((PASS + 1))
else
  echo "FAIL: exited $RC on a warning"; FAIL=$((FAIL + 1))
fi

# The warning names every safe path the rule promises (todo 689 AC).
OUT=$(run_hook "$(event "git switch -c x origin/main")")
CTX=$(jq -r '.hookSpecificOutput.additionalContext' <<< "$OUT" 2>/dev/null)
MISSING=""
for needle in "--no-track" "git push origin HEAD" "sync_with_base_branch" "git symbolic-ref HEAD refs/heads/<new>"; do
  grep -qF -- "$needle" <<< "$CTX" || MISSING="$MISSING [$needle]"
done
if [ -z "$MISSING" ]; then
  echo "PASS: warning names branch, push, sync and symbolic-ref repair"; PASS=$((PASS + 1))
else
  echo "FAIL: warning is missing:$MISSING"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
