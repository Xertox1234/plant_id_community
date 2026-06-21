#!/usr/bin/env bash
# Tests for format-on-edit.sh — run from anywhere.
# Builds a throwaway fake repo root (FORMAT_ON_EDIT_ROOT) so no real file is
# ever touched. Requires ruff (backend/venv/bin/ruff) and jq on the system.
set -uo pipefail

HOOK="$(cd "$(dirname "$0")" && pwd)/format-on-edit.sh"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# Resolve ruff the way the hook does: backend venv first, then PATH (CI installs it
# on PATH; local dev has it in the venv).
REAL_RUFF="$REPO_ROOT/backend/venv/bin/ruff"
[ -x "$REAL_RUFF" ] || REAL_RUFF="$(command -v ruff 2>/dev/null || true)"
PASS=0; FAIL=0

# The hook fail-opens without ruff, so there is nothing to assert if it is absent.
[ -x "$REAL_RUFF" ] || { echo "SKIP: ruff not installed (pip install ruff, or backend/venv/bin/pip install -r backend/requirements.txt)"; exit 0; }

# Throwaway fake repo root (FORMAT_ON_EDIT_ROOT) so no real file is touched, and
# the ruff test seam (FORMAT_ON_EDIT_RUFF) so resolution is deterministic.
ROOT="$(mktemp -d)"
export FORMAT_ON_EDIT_RUFF="$REAL_RUFF"
trap 'chmod -R u+w "$ROOT" 2>/dev/null; rm -rf "$ROOT"' EXIT

mkfixture() { # path-under-root, content
  local p="$ROOT/$1"; mkdir -p "$(dirname "$p")"; printf '%b' "$2" > "$p"
}
run() { # file_path (repo-relative), tool_name → runs hook, sets RC/ERR
  local fp="$1" tool="${2:-Edit}"
  ERR=$(printf '{"tool_name":"%s","tool_input":{"file_path":"%s"}}' "$tool" "$fp" \
        | FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
}
ok()   { echo "PASS: $1"; PASS=$((PASS+1)); }
no()   { echo "FAIL: $1"; echo "  $2"; FAIL=$((FAIL+1)); }

# 1. Core: unused import is auto-removed, used one kept, and a CLEAN fix exits 0
#    (RC=0 guards against ruff's "All checks passed!" being read as a residual).
mkfixture backend/apps/scratch.py 'import os\nimport sys\n\nprint(sys.version)\n'
run backend/apps/scratch.py
if ! grep -q '^import os$' "$ROOT/backend/apps/scratch.py" \
   && grep -q 'import sys' "$ROOT/backend/apps/scratch.py" && [ "$RC" -eq 0 ]; then
  ok "removes unused import, keeps used one, exits 0"
else
  no "removes unused import, keeps used one, exits 0" "rc=$RC file: $(tr '\n' ' ' < "$ROOT/backend/apps/scratch.py")"
fi

# 2. Skip-list: a per-file-ignore path is left untouched (intentional re-exports).
mkfixture backend/apps/plant_identification/models.py 'import os\n'
run backend/apps/plant_identification/models.py
if grep -q '^import os$' "$ROOT/backend/apps/plant_identification/models.py" && [ "$RC" -eq 0 ]; then
  ok "skip-list file untouched"
else
  no "skip-list file untouched" "rc=$RC content=$(cat "$ROOT/backend/apps/plant_identification/models.py")"
fi

# 3. Non-.py file is ignored.
mkfixture backend/notes.txt 'import os\n'
run backend/notes.txt
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/backend/notes.txt" && ok "non-.py ignored" || no "non-.py ignored" "rc=$RC"

# 4. Non-backend .py is ignored (gate scopes to backend/).
mkfixture web/scripts/foo.py 'import os\n'
run web/scripts/foo.py
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/web/scripts/foo.py" && ok "non-backend .py ignored" || no "non-backend .py ignored" "rc=$RC"

# 5. Missing file_path (e.g. Read-style event) → no-op, exit 0.
ERR=$(printf '{"tool_name":"Edit","tool_input":{}}' | FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && ok "missing file_path → exit 0" || no "missing file_path → exit 0" "rc=$RC"

# 6. Fail-open: ruff absent (seam points at a nonexistent path) → exit 0, untouched.
mkfixture backend/apps/failopen.py 'import os\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/failopen.py"}}' \
      | FORMAT_ON_EDIT_RUFF="$ROOT/no-such-ruff" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && grep -q 'import os' "$ROOT/backend/apps/failopen.py" && ok "ruff missing → fail-open exit 0" || no "ruff missing → fail-open exit 0" "rc=$RC"

# 7. Residual F401 that ruff cannot auto-fix → exit 2 + stderr feedback.
#    The hook's contract is "if ruff still REPORTS F401 after the --fix pass, exit
#    2" — test that control flow with a stub ruff (real ruff's fix heuristics are
#    ruff's concern, not the hook's), which is deterministic.
STUB="$ROOT/fake-ruff"
{ echo '#!/usr/bin/env bash'; echo 'echo "residual.py:1:8: F401 os imported but unused"'; echo 'exit 1'; } > "$STUB"
chmod +x "$STUB"
mkfixture backend/apps/residual.py 'import os\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/residual.py"}}' \
      | FORMAT_ON_EDIT_RUFF="$STUB" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
if [ "$RC" -eq 2 ] && printf '%s' "$ERR" | grep -qi 'F401\|unused'; then
  ok "unfixable F401 → exit 2 with feedback"
else
  no "unfixable F401 → exit 2 with feedback" "rc=$RC err=$ERR"
fi

# --- TS/TSX branch (eslint --fix; seam: FORMAT_ON_EDIT_ESLINT) ---

# 8. TS clean: eslint reports nothing → exit 0.
ESLINT_OK="$ROOT/eslint-ok"
{ echo '#!/usr/bin/env bash'; echo 'exit 0'; } > "$ESLINT_OK"; chmod +x "$ESLINT_OK"
mkfixture web/src/clean.ts 'export const x = 1;\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"web/src/clean.ts"}}' \
      | FORMAT_ON_EDIT_ESLINT="$ESLINT_OK" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && ok "TS clean → exit 0" || no "TS clean → exit 0" "rc=$RC err=$ERR"

# 9. TS residual: eslint --fix no-ops, the residual pass reports an error → exit 2.
ESLINT_ERR="$ROOT/eslint-err"
{ echo '#!/usr/bin/env bash'
  echo 'for a in "$@"; do [ "$a" = "--fix" ] && exit 0; done'
  echo 'echo "src/bad.ts:1:1: error oops no-undef"'
  echo 'exit 1'; } > "$ESLINT_ERR"; chmod +x "$ESLINT_ERR"
mkfixture web/src/bad.ts 'const y = z;\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"web/src/bad.ts"}}' \
      | FORMAT_ON_EDIT_ESLINT="$ESLINT_ERR" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
if [ "$RC" -eq 2 ] && printf '%s' "$ERR" | grep -qi 'eslint'; then
  ok "TS residual error → exit 2 with feedback"
else
  no "TS residual error → exit 2 with feedback" "rc=$RC err=$ERR"
fi

# 10. TS fail-open: eslint binary absent → exit 0.
mkfixture web/src/failopen.ts 'export const a = 1;\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"web/src/failopen.ts"}}' \
      | FORMAT_ON_EDIT_ESLINT="$ROOT/no-such-eslint" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && ok "TS eslint missing → fail-open exit 0" || no "TS eslint missing → fail-open exit 0" "rc=$RC"

# --- Dart branch (dart fix --apply; seam: FORMAT_ON_EDIT_DART) ---

DARTSTUB="$ROOT/dart-stub"
{ echo '#!/usr/bin/env bash'; echo "echo called >> '$ROOT/dart-called'"; echo 'exit 0'; } > "$DARTSTUB"; chmod +x "$DARTSTUB"

# 11. Dart: dart fix is invoked on a normal .dart file → exit 0, fixer called.
mkfixture plant_community_mobile/lib/foo.dart 'void main() {}\n'
rm -f "$ROOT/dart-called"
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"plant_community_mobile/lib/foo.dart"}}' \
      | FORMAT_ON_EDIT_DART="$DARTSTUB" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
if [ "$RC" -eq 0 ] && [ -f "$ROOT/dart-called" ]; then ok "Dart fix invoked → exit 0"; else
  no "Dart fix invoked → exit 0" "rc=$RC called=$([ -f "$ROOT/dart-called" ] && echo yes || echo no)"; fi

# 12. Dart generated file (.g.dart) is skipped — fixer NOT called.
mkfixture plant_community_mobile/lib/foo.g.dart '// GENERATED\n'
rm -f "$ROOT/dart-called"
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"plant_community_mobile/lib/foo.g.dart"}}' \
      | FORMAT_ON_EDIT_DART="$DARTSTUB" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
if [ "$RC" -eq 0 ] && [ ! -f "$ROOT/dart-called" ]; then ok "Dart generated .g.dart skipped"; else
  no "Dart generated .g.dart skipped" "rc=$RC called=$([ -f "$ROOT/dart-called" ] && echo yes || echo no)"; fi

# 13. Dart fail-open: dart binary absent → exit 0.
mkfixture plant_community_mobile/lib/failopen.dart 'void main() {}\n'
ERR=$(printf '{"tool_name":"Edit","tool_input":{"file_path":"plant_community_mobile/lib/failopen.dart"}}' \
      | FORMAT_ON_EDIT_DART="$ROOT/no-such-dart" FORMAT_ON_EDIT_ROOT="$ROOT" bash "$HOOK" 2>&1 >/dev/null); RC=$?
[ "$RC" -eq 0 ] && ok "Dart missing → fail-open exit 0" || no "Dart missing → fail-open exit 0" "rc=$RC"

# 14. Skip-list ↔ setup.cfg F401 sync (todo 232): every setup.cfg [flake8]
#     per-file-ignore carrying F401 must be in the hook's skip-list (between the
#     SKIPLIST sentinels), or the hook would strip an intentional re-export. Assert
#     the F401 set ⊆ the skip-list (the hook may legitimately carry extras like
#     settings.py). Runs against the REAL repo files (not the fake ROOT).
SETUP_CFG="$REPO_ROOT/backend/setup.cfg"
if [ -f "$SETUP_CFG" ] && command -v python3 >/dev/null 2>&1; then
  SKIP=$(awk '/SKIPLIST-START/{f=1;next} /SKIPLIST-END/{f=0} f' "$HOOK" \
    | grep -oE 'backend/[A-Za-z0-9_./-]+\.py' | sed 's#^backend/##' | sort -u)
  CFG=$(python3 - "$SETUP_CFG" <<'PY'
import configparser, sys
cp = configparser.ConfigParser(interpolation=None)
cp.read(sys.argv[1])
for line in cp.get('flake8', 'per-file-ignores', fallback='').splitlines():
    line = line.strip()
    if ':' in line:
        path, codes = line.split(':', 1)
        if 'F401' in codes:
            print(path.strip())
PY
)
  check_subset() { # $1=needles(newline-sep)  $2=haystack(newline-sep) → echoes missing
    local m=""
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      printf '%s\n' "$2" | grep -qxF "$p" || m="$m $p"
    done <<< "$1"
    printf '%s' "$m"
  }
  # (a) Current state must be in sync (and CFG must be non-empty, so a broken parse
  #     fails loudly instead of passing vacuously).
  REAL_MISSING=$(check_subset "$CFG" "$SKIP")
  if [ -z "$REAL_MISSING" ] && [ -n "$CFG" ]; then
    ok "skip-list ⊇ setup.cfg F401 ignores (in sync)"
  else
    no "skip-list ⊇ setup.cfg F401 ignores (in sync)" "missing:$REAL_MISSING cfg_empty?=$([ -z "$CFG" ] && echo yes || echo no)"
  fi
  # (b) Teeth: a setup.cfg F401 entry NOT in the skip-list is detected as missing.
  if printf '%s' "$(check_subset 'apps/fake_reexport.py' "$SKIP")" | grep -q 'fake_reexport'; then
    ok "sync check detects an unmirrored F401 ignore"
  else
    no "sync check detects an unmirrored F401 ignore" "fake entry not flagged"
  fi
else
  ok "skip-list sync check (setup.cfg or python3 absent — skipped)"
fi

echo "----"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
