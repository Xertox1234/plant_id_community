#!/usr/bin/env bash
# Tests for kimi-review.sh — run from anywhere.
# Tests are hermetic: a stub `kimi-review` and `git` are shimmed onto PATH via a
# temp dir, so no real review is ever invoked and no API key is needed.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/kimi-review.sh"
PASS=0; FAIL=0

# Stub modes mirror kimi-review's real output. KIMI_STUB_MODE controls it:
#   critical          → a plain [CRITICAL] finding line
#   critical-bracket  → a bullet+indent decorated [CRITICAL] finding line
#   critical-bold     → a markdown-bold-wrapped [CRITICAL] finding line
#   critical-nobody   → a bare [CRITICAL] tag with no finding body
#   warning           → a [WARNING] finding line
#   noisy-prose       → lowercase "critical" in prose, no real finding
#   negative-prose    → the model's "No CRITICAL or WARNING findings" phrasing
#   clean             → kimi-review's real clean-output message
make_stub_path() {
  local mode="$1"
  local dir
  dir=$(mktemp -d)
  cat > "$dir/kimi-review" <<EOF
#!/usr/bin/env bash
cat >/dev/null  # consume stdin so the pipe doesn't SIGPIPE
case "$mode" in
  critical)         echo "[CRITICAL] backend/apps/foo/views.py:42 — stub finding for tests";;
  critical-bracket) echo "  - [CRITICAL] backend/apps/foo/views.py:10 — bullet+indent decorated finding";;
  critical-bold)    echo "**[CRITICAL]** backend/apps/foo/views.py:10 — markdown-bold form";;
  critical-nobody)  echo "[CRITICAL]";;
  warning)          echo "[WARNING] backend/apps/foo/views.py:5 — stub finding for tests";;
  noisy-prose)      echo "no critical issues found in stub run";;
  negative-prose)   echo "No CRITICAL or WARNING findings";;
  clean)            echo "No findings in requested tiers: CRITICAL, WARNING";;
esac
EOF
  chmod +x "$dir/kimi-review"
  cat > "$dir/git" <<'EOF'
#!/usr/bin/env bash
case "$* " in
  "diff --cached --name-only "*) echo "backend/apps/foo/views.py";;
  "diff --cached "*)              echo "diff --git a/x b/x";;
  *) exec /usr/bin/env -i PATH="/usr/bin:/bin" git "$@";;
esac
EOF
  chmod +x "$dir/git"
  printf '%s' "$dir"
}

run_hook() {
  local mode="$1" input="$2"
  local stubdir
  stubdir=$(make_stub_path "$mode")
  echo "$input" | PATH="$stubdir:$PATH" bash "$HOOK" 2>/dev/null
  local rc=$?
  rm -rf "$stubdir"
  return $rc
}

assert_contains() {
  local name="$1" haystack="$2" needle="$3"
  if echo "$haystack" | grep -q "$needle"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected to find: $needle)"
    echo "  got: $(echo "$haystack" | head -3)"
    FAIL=$((FAIL+1))
  fi
}

assert_not_contains() {
  local name="$1" haystack="$2" needle="$3"
  if echo "$haystack" | grep -q "$needle"; then
    echo "FAIL: $name (expected NOT to find: $needle)"
    echo "  got: $(echo "$haystack" | head -3)"
    FAIL=$((FAIL+1))
  else
    echo "PASS: $name"; PASS=$((PASS+1))
  fi
}

assert_empty() {
  local name="$1" haystack="$2"
  if [ -z "$haystack" ]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected empty output)"
    echo "  got: $(echo "$haystack" | head -3)"
    FAIL=$((FAIL+1))
  fi
}

# ---------- Command matcher tests ----------
OUT=$(run_hook clean '{"tool_input":{"command":"git commit -m \"x\""}}')
assert_contains "git commit matches and emits review JSON" "$OUT" "additionalContext"

OUT=$(run_hook clean '{"tool_input":{"command":"git -c user.name=x commit -m y"}}')
assert_contains "git -c ... commit matches" "$OUT" "additionalContext"

OUT=$(run_hook clean '{"tool_input":{"command":"GIT_AUTHOR_NAME=foo git commit -m y"}}')
assert_contains "FOO=bar git commit matches" "$OUT" "additionalContext"

OUT=$(run_hook clean '{"tool_input":{"command":"git commit-graph write"}}')
assert_empty "git commit-graph does NOT match" "$OUT"

OUT=$(run_hook clean '{"tool_input":{"command":"echo git commit -m x"}}')
assert_empty "echo git commit does NOT match" "$OUT"

OUT=$(run_hook clean '{"tool_input":{"command":"foo git commit bar"}}')
assert_empty "substring git commit does NOT match" "$OUT"

OUT=$(run_hook clean '{"tool_input":{"command":"git push origin main"}}')
assert_empty "git push does NOT match" "$OUT"

# ---------- Skip semantics ----------
OUT=$(SKIP_KIMI_REVIEW=1 echo '{"tool_input":{"command":"git commit -m x"}}' | bash "$HOOK" 2>/dev/null)
assert_empty "SKIP_KIMI_REVIEW=1 skips" "$OUT"

EMPTY_DIR=$(mktemp -d)
OUT=$(echo '{"tool_input":{"command":"git commit -m x"}}' | \
  PATH="$EMPTY_DIR:/usr/bin:/bin" bash "$HOOK" 2>/dev/null)
rm -rf "$EMPTY_DIR"
assert_empty "missing kimi-review skips" "$OUT"

# ---------- Tier handling ----------
OUT=$(run_hook warning '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "WARNING emits additionalContext (non-blocking)" "$OUT" "additionalContext"
assert_not_contains "WARNING does not emit permissionDecision deny" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook critical '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "CRITICAL emits permissionDecision deny" "$OUT" '"permissionDecision": "deny"'
assert_contains "CRITICAL emits permissionDecisionReason" "$OUT" "permissionDecisionReason"

OUT=$(run_hook critical-bracket '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "bullet+indent decorated [CRITICAL] blocks" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook critical-bold '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "**[CRITICAL]** markdown-bold form blocks" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook critical-nobody '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "bare [CRITICAL] with no body does NOT block" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook noisy-prose '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "lowercase 'critical' in prose does NOT block" "$OUT" '"permissionDecision": "deny"'
assert_contains "noisy-prose still emits additionalContext" "$OUT" "additionalContext"

OUT=$(run_hook clean '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "clean-output message does NOT block" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook negative-prose '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "negative phrasing does NOT block" "$OUT" '"permissionDecision": "deny"'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
