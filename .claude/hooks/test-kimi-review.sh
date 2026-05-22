#!/usr/bin/env bash
# Tests for kimi-review.sh (the hook) + the vendored engine — run from anywhere.
# Hermetic: a stub `kimi-review` and `git` are shimmed onto PATH, and the engine
# Python unit tests import the vendored copy directly. No API key is ever needed.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="$DIR/kimi-review.sh"
ROOT="$(cd "$DIR/../.." && pwd)"   # .claude/hooks -> repo root
PASS=0; FAIL=0

# ---------- stub: exit-code aware ----------
# The hook now gates on the engine's EXIT CODE (2 = a verified CRITICAL), not on
# prose. KIMI_STUB_MODE sets both the printed text and the exit code:
#   critical          → prints a [CRITICAL] line, EXIT 2  → hook must DENY
#   bracket-no-exit   → prints a [CRITICAL] line, EXIT 0  → hook must NOT deny
#                       (proves gating is by exit code, not the [CRITICAL] text)
#   warning           → prints a [WARNING] line, EXIT 0   → additionalContext only
#   clean             → clean message,           EXIT 0   → additionalContext only
#   toolerror         → error text,              EXIT 1   → fail-open, must NOT deny
make_stub_path() {
  local mode="$1" dir
  dir=$(mktemp -d)
  cat > "$dir/kimi-review" <<EOF
#!/usr/bin/env bash
cat >/dev/null  # consume stdin so the pipe doesn't SIGPIPE
case "$mode" in
  critical)        echo "[CRITICAL] backend/apps/foo/views.py:42 — stub finding"; exit 2;;
  bracket-no-exit) echo "[CRITICAL] backend/apps/foo/views.py:42 — text only, downgraded"; exit 0;;
  warning)         echo "[WARNING] backend/apps/foo/views.py:5 — stub finding"; exit 0;;
  clean)           echo "No findings in requested tiers: CRITICAL, WARNING"; exit 0;;
  toolerror)       echo "[ERROR: kimi-review request failed]"; exit 1;;
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
  local mode="$1" input="$2" stubdir rc
  stubdir=$(make_stub_path "$mode")
  echo "$input" | PATH="$stubdir:$PATH" bash "$HOOK" 2>/dev/null
  rc=$?
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

# ---------- Exit-code gating (the migration) ----------
OUT=$(run_hook critical '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "engine exit 2 → permissionDecision deny" "$OUT" '"permissionDecision": "deny"'
assert_contains "deny carries permissionDecisionReason" "$OUT" "permissionDecisionReason"

OUT=$(run_hook bracket-no-exit '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "[CRITICAL] text but exit 0 does NOT block (gates on exit code)" "$OUT" '"permissionDecision": "deny"'
assert_contains "exit 0 still emits additionalContext" "$OUT" "additionalContext"

OUT=$(run_hook warning '{"tool_input":{"command":"git commit -m x"}}')
assert_contains "WARNING (exit 0) emits additionalContext" "$OUT" "additionalContext"
assert_not_contains "WARNING does not deny" "$OUT" '"permissionDecision": "deny"'

OUT=$(run_hook clean '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "clean does not deny" "$OUT" '"permissionDecision": "deny"'
assert_contains "clean emits additionalContext" "$OUT" "additionalContext"

OUT=$(run_hook toolerror '{"tool_input":{"command":"git commit -m x"}}')
assert_not_contains "tool error (exit 1) fails open — no deny" "$OUT" '"permissionDecision": "deny"'

# ---------- Vendored engine invariants + canonical parity ----------
# importlib needs a .py suffix; the engine files are extensionless, so shim each
# via a temp symlink. The engine uses __file__.resolve(), so the symlink still
# resolves kimi-profiles.json next to the real engine.
shim_engine() {
  local src="$1" tmp
  tmp=$(mktemp -d)
  ln -s "$src" "$tmp/kimi_engine.py"
  printf '%s' "$tmp/kimi_engine.py"
}

run_engine_tests() {
  local engine="$1"
  command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; return 1; }
  python3 - "$engine" <<'PY'
import importlib.util, pathlib, sys, tempfile, subprocess, types
spec = importlib.util.spec_from_file_location("kimi_engine", pathlib.Path(sys.argv[1]))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# parse_findings: tier filter + malformed handling (defense-in-depth)
good = '{"findings":[{"tier":"CRITICAL","claim_type":"semantic","file":"a.py","line":1,"symbol":null,"detail":"d"}]}'
assert len(m.parse_findings(good, {"CRITICAL"})) == 1
assert m.parse_findings("not json", {"CRITICAL"}) == []
miss = '{"findings":[{"tier":"CRITICAL","claim_type":"semantic","line":1,"symbol":null,"detail":"d"}]}'
assert m.parse_findings(miss, {"CRITICAL"}) == [], "finding missing file must be dropped"

# apply_downgrades: monotonic — CRITICAL→WARNING only, never promote
f = [{"tier":"CRITICAL","claim_type":"semantic","file":"a.py","line":1,"symbol":None,"detail":"d"}]
assert m.apply_downgrades(f, {0:"downgrade"})[0]["tier"] == "WARNING"
assert m.apply_downgrades(f, {0:"keep"})[0]["tier"] == "CRITICAL"
w = [{"tier":"WARNING","claim_type":"semantic","file":"a.py","line":1,"symbol":None,"detail":"d"}]
assert m.apply_downgrades(w, {0:"keep"})[0]["tier"] == "WARNING", "verify must never promote"

# verify_deterministic: staged-tree routing (absent_symbol / semantic F2)
d = tempfile.mkdtemp()
def git(*a): return subprocess.run(["git","-C",d,*a], capture_output=True, text=True)
git("init","-q"); git("config","user.email","t@t"); git("config","user.name","t")
(pathlib.Path(d)/"a.py").write_text("def require_owner():\n    pass\n")
git("add","a.py")
present = {"tier":"CRITICAL","claim_type":"absent_symbol","file":"a.py","line":None,"symbol":"require_owner","detail":"d"}
missing = {"tier":"CRITICAL","claim_type":"absent_symbol","file":"a.py","line":None,"symbol":"nope","detail":"d"}
sem     = {"tier":"CRITICAL","claim_type":"semantic","file":"a.py","line":1,"symbol":None,"detail":"d"}
vs = m.verify_deterministic([present, missing, sem], cwd=d)
assert vs == ["downgrade","keep","downgrade"], vs

# context_blocks: a missing pattern/rule is non-fatal (no sys.exit fail-open)
args = types.SimpleNamespace(paths=None, patterns="nope-not-real-xyz", pattern_max_chars=12000, rules=None)
assert m.context_blocks(args, d) == "", "missing pattern must be skipped, not fatal"

# profile loader resolves kimi-profiles.json next to the engine and has plant_id
assert "plant_id" in m.PROFILES, sorted(m.PROFILES.keys())

print("ENGINE OK")
PY
}

VEND_SHIM=$(shim_engine "$ROOT/scripts/kimi-review")
if run_engine_tests "$VEND_SHIM" >/dev/null; then
  echo "PASS: vendored engine invariants (parse/monotonic/verify/pattern-skip/profile)"; PASS=$((PASS+1))
else
  echo "FAIL: vendored engine invariants"; FAIL=$((FAIL+1))
fi
rm -rf "$(dirname "$VEND_SHIM")"

CANON="${KIMI_ENGINE_CANONICAL:-$HOME/.local/share/claude-coworker/tools/kimi-review}"
if [ -f "$CANON" ]; then
  CANON_SHIM=$(shim_engine "$CANON")
  if run_engine_tests "$CANON_SHIM" >/dev/null; then
    echo "PASS: canonical engine matches vendored behavior"; PASS=$((PASS+1))
  else
    echo "FAIL: canonical engine diverges from vendored behavior"; FAIL=$((FAIL+1))
  fi
  rm -rf "$(dirname "$CANON_SHIM")"
else
  echo "SKIP: canonical engine absent — behavioral parity check"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ]
