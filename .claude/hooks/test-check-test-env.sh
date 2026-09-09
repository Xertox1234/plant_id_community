#!/usr/bin/env bash
# Tests for check-test-env.sh — run from anywhere.
#
# Hermetic: every case builds a fake project root under mktemp with a stub
# `backend/venv/bin/python`, injected via $CHECK_TEST_ENV_ROOT. Nothing here
# reads the real venv, so these tests keep passing after the real venv is
# healed (todo 378) and they run in CI, which has no backend venv at all.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$DIR/check-test-env.sh"
PASS=0; FAIL=0

# ---------- fake project root ----------
# STUB_MODE sets what the stubbed checker prints and its exit code:
#   drift → the drift message, exit 0  → hook must emit additionalContext
#   clean → nothing,           exit 0  → hook must stay silent
#   error → nothing,           exit 1  → fail open, hook must stay silent
#   novenv → no venv at all             → hook must stay silent
make_root() {
  local mode="$1" root
  root=$(mktemp -d)
  mkdir -p "$root/backend/apps/core"
  : > "$root/backend/apps/core/env_integrity.py"
  [ "$mode" = "novenv" ] && { printf '%s' "$root"; return; }
  mkdir -p "$root/backend/venv/bin"
  cat > "$root/backend/venv/bin/python" <<EOF
#!/usr/bin/env bash
case "$mode" in
  drift) printf '%s\n' "backend/venv does not match backend/requirements.txt:" \
                       "  mismatched: wagtail (pinned 8.0, installed 7.4.3)" \
                       "  not installed: django-ninja (pinned 1.7.0)"; exit 0;;
  clean) exit 0;;
  error) exit 1;;
esac
EOF
  chmod +x "$root/backend/venv/bin/python"
  printf '%s' "$root"
}

run_hook() {
  local mode="$1" cmd="$2" root out
  root=$(make_root "$mode")
  out=$(printf '{"tool_input":{"command":"%s"}}' "$cmd" \
        | CHECK_TEST_ENV_ROOT="$root" bash "$HOOK" 2>/dev/null)
  rm -rf "$root"
  printf '%s' "$out"
}

assert_contains() {
  local name="$1" haystack="$2" needle="$3"
  if grep -q -- "$needle" <<< "$haystack"; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name (expected to find: $needle)"
    echo "  got: $(echo "$haystack" | head -3)"
    FAIL=$((FAIL+1))
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

# ---------- Command matcher: must fire ----------
for CMD in \
  'python -m pytest' \
  'pytest' \
  'pytest apps/core -k foo' \
  'venv/bin/python -m pytest' \
  'backend/venv/bin/python -m pytest apps/core' \
  'cd backend && python -m pytest' \
  'python manage.py test apps.blog --keepdb' \
  'PYTHONPATH=. python -m pytest' \
  'python3.13 -m pytest'
do
  OUT=$(run_hook drift "$CMD")
  assert_contains "matches: $CMD" "$OUT" "additionalContext"
done

# ---------- Command matcher: must NOT fire ----------
for CMD in \
  'echo python -m pytest' \
  'git commit -m x' \
  'python manage.py runserver' \
  'python manage.py testfoo' \
  'ls pytest' \
  'grep -r pytest .' \
  'cat pytest.ini'
do
  OUT=$(run_hook drift "$CMD")
  assert_empty "does NOT match: $CMD" "$OUT"
done

# ---------- The drift comparison must actually reach the model ----------
# These are the discriminating assertions: they fail if the hook stops
# invoking the checker or stops forwarding what it said. A test that only
# asserted "the hook ran" would pass with the comparison gutted.
OUT=$(run_hook drift 'python -m pytest')
assert_contains "drift output names the mismatched package" "$OUT" "wagtail"
assert_contains "drift output names the not-installed package" "$OUT" "django-ninja"
assert_contains "drift output keeps mismatched and missing separate" "$OUT" "not installed"
assert_contains "emits PreToolUse hookEventName" "$OUT" "PreToolUse"

# ---------- Never blocks ----------
OUT=$(run_hook drift 'python -m pytest')
if grep -q "permissionDecision" <<< "$OUT"; then
  echo "FAIL: hook must never block a test run"; FAIL=$((FAIL+1))
else
  echo "PASS: hook never blocks a test run"; PASS=$((PASS+1))
fi

# ---------- Silent when there is nothing to say ----------
OUT=$(run_hook clean 'python -m pytest')
assert_empty "clean environment is silent" "$OUT"

OUT=$(run_hook error 'python -m pytest')
assert_empty "checker error fails open (silent)" "$OUT"

OUT=$(run_hook novenv 'python -m pytest')
assert_empty "missing backend/venv is silent (worktrees)" "$OUT"

# ---------- Skip semantics ----------
# The env var must bind to the HOOK, not to printf — a common mistake this
# repo has already made once in test-kimi-review.sh.
ROOT=$(make_root drift)
OUT=$(printf '{"tool_input":{"command":"python -m pytest"}}' \
      | SKIP_ENV_CHECK=1 CHECK_TEST_ENV_ROOT="$ROOT" bash "$HOOK" 2>/dev/null)
assert_empty "SKIP_ENV_CHECK=1 skips" "$OUT"

OUT=$(printf 'not json' | CHECK_TEST_ENV_ROOT="$ROOT" bash "$HOOK" 2>/dev/null)
assert_empty "malformed event JSON fails open" "$OUT"

# jq lives in /usr/bin on macOS, so the usual `PATH="$EMPTY:/usr/bin:/bin"`
# idiom would still find it. Empty the PATH entirely and resolve bash before
# it takes effect — the hook checks for jq before it needs any other binary.
EMPTY_DIR=$(mktemp -d)
BASH_BIN="$(command -v bash)"
OUT=$(printf '{"tool_input":{"command":"python -m pytest"}}' \
      | CHECK_TEST_ENV_ROOT="$ROOT" PATH="$EMPTY_DIR" "$BASH_BIN" "$HOOK" 2>/dev/null)
rm -rf "$EMPTY_DIR"
assert_empty "missing jq skips" "$OUT"
rm -rf "$ROOT"

# ---------- The CI stamp must stay observable ----------
# backend-ci.yml carries a comment saying its pytest invocation must stay bare,
# because pytest_report_header is gated on `verbosity >= 0` and a routine
# "quieten the logs" edit would silently delete the environment stamp from the
# one job that proves it reads clean. A comment is documentation, not a guard —
# this assertion is the guard. Runs in harness-ci.yml, a required check.
CI_YML="$(cd "$DIR/../.." && pwd)/.github/workflows/backend-ci.yml"
if [ -f "$CI_YML" ]; then
  PYTEST_STEP=$(grep -E '^\s*run: python -m pytest' "$CI_YML" || true)
  if [ -z "$PYTEST_STEP" ]; then
    echo "FAIL: backend-ci.yml has no bare 'run: python -m pytest' step"
    echo "  (if the runner changed, update this assertion deliberately)"
    FAIL=$((FAIL+1))
  elif grep -qE '\-q|--no-header|--quiet' <<< "$PYTEST_STEP"; then
    echo "FAIL: backend-ci.yml pytest step suppresses the environment stamp"
    echo "  got: $PYTEST_STEP"
    FAIL=$((FAIL+1))
  else
    echo "PASS: backend-ci.yml pytest step keeps the environment stamp visible"
    PASS=$((PASS+1))
  fi
else
  echo "SKIP: backend-ci.yml not found — CI stamp assertion"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
